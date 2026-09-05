"""CallSession: runs one live call with the Caller and the Supervisor side by side.

The two share this object as working memory: the Caller appends turns to
`transcript`, the Supervisor reads it every few seconds, and either of them can
open an escalation -- a `decisions` row plus a blocking wait for the account
holder's answer, while the phone line stays open.

The bridge builds a CallSession (it has the task + call_id by then) and calls
`run_call_session(session, stream)`.
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog

from holdline.config import get_settings
from holdline.state import store

log = structlog.get_logger("session")

# Live sessions, so the /decisions routes can resolve a pending escalation.
SESSIONS: list[CallSession] = []


class CallSession:
    def __init__(self, *, stream, task: dict, call_id: str | None) -> None:
        self.stream = stream
        self.task = task
        self.call_id = call_id
        self.brief: dict | None = task.get("brief")
        self.transcript: list[dict] = []
        self.agent = None  # the BidiAgent; set by the runner
        self.ended = False
        self.escalations: list[dict] = []
        # decision_id -> {"question","options","answer","event"}
        self._pending: dict[str, dict] = {}

    # -- transcript (TranscriptCb: (role, text, is_final)) ----------------- #
    def add_turn(self, role: str, text: str, is_final: bool = True) -> None:
        if not (is_final and text.strip()):
            return
        self.transcript.append({"role": role, "text": text})
        log.info("turn", role=role, text=text)
        if self.call_id:
            with contextlib.suppress(Exception):
                store.append_transcript(self.call_id, role, text)

    # -- escalation ------------------------------------------------------ #
    @property
    def pending(self) -> dict[str, dict]:
        return self._pending

    def pending_list(self) -> list[dict]:
        return [
            {
                "decision_id": did,
                "call_id": self.call_id,
                "question": p["question"],
                "options": p["options"],
            }
            for did, p in self._pending.items()
        ]

    def resolve(self, decision_id: str, answer: str) -> bool:
        p = self._pending.get(decision_id)
        if not p:
            return False
        p["answer"] = answer
        p["event"].set()
        return True

    async def escalate(self, question: str, options: list[str], context: str = "") -> str:
        """Open a decision, block until the account holder answers or it times out,
        then return the answer text. Safe to call from the Caller tool or the
        Supervisor loop."""
        s = get_settings()
        options = options or ["Hold firm on the original request", "Accept the offer"]
        row = None
        if self.call_id:
            with contextlib.suppress(Exception):
                row = store.create_decision(self.call_id, question, options, context)
        did = row["decision_id"] if row else store.new_id("dec")

        ev = asyncio.Event()
        self._pending[did] = {"question": question, "options": options, "answer": None, "event": ev}
        log.info("escalation.open", decision_id=did, question=question, options=options)

        default = (self.brief or {}).get(
            "default_on_timeout", "hold firm and refuse any counter-offer"
        )
        try:
            await asyncio.wait_for(ev.wait(), timeout=s.escalation_timeout_s)
            answer = self._pending[did]["answer"] or default
        except TimeoutError:
            answer = f"(no response in {int(s.escalation_timeout_s)}s) {default}"
            log.info("escalation.timeout", decision_id=did)

        self._pending.pop(did, None)
        self.escalations.append({"question": question, "answer": answer})
        if self.call_id and row:
            with contextlib.suppress(Exception):
                store.resolve_decision(did, answer)
        log.info("escalation.resolved", decision_id=did, answer=answer)
        return answer

    async def steer(self, guidance: str) -> None:
        """Feed a private instruction to the Caller mid-call (text, not spoken)."""
        if self.agent is None:
            return
        try:
            from strands.experimental.bidi.types.events import BidiTextInputEvent

            await self.agent.send(
                BidiTextInputEvent(
                    text=f"[GUIDANCE - do not read this aloud] {guidance}", role="user"
                )
            )
            log.info("session.steer", guidance=guidance)
        except Exception as exc:  # noqa: BLE001
            log.warning("session.steer_failed", error=str(exc))

    async def hold_and_escalate(self, question: str, options: list[str]) -> str:
        await self.steer(
            "The representative has offered something you are not allowed to accept. "
            "Tell them you need to check with the account holder and ask them to hold. "
            "Do not agree to anything yet."
        )
        answer = await self.escalate(question, options)
        await self.steer(
            f'The account holder responded: "{answer}". Act on that now. If it means '
            "hold firm, politely decline the offer and insist on the original request."
        )
        return answer

    async def abort(self, reason: str) -> None:
        log.info("session.abort", reason=reason)
        await self.steer(
            f"This call cannot succeed ({reason}). Wrap up politely, call "
            "record_outcome with status \"failed\" and this reason, then stop_conversation."
        )


async def _supervise(session: CallSession) -> None:
    s = get_settings()
    if not s.supervisor_enabled:
        return
    from holdline.agents.supervisor import review_call

    seen = 0
    checks = 0
    while not session.ended:
        await asyncio.sleep(s.supervisor_interval_s)
        if session.ended or session._pending:
            continue
        if len(session.transcript) == seen:
            continue
        seen = len(session.transcript)
        checks += 1
        if checks > s.supervisor_max_checks:
            log.info("supervisor.max_checks_reached")
            return
        verdict = await asyncio.to_thread(
            review_call, session.brief, session.transcript, session.escalations
        )
        if session.ended:
            return
        if verdict.verdict == "escalate":
            await session.hold_and_escalate(
                verdict.question or "The representative made an offer. How should I respond?",
                verdict.options or ["Hold firm", "Accept"],
            )
        elif verdict.verdict == "abort":
            await session.abort(verdict.reason or "no progress")


async def run_call_session(
    session: CallSession, stream, *, instructions: str | None = None
) -> CallSession:
    """Build the Caller, start the Supervisor, run the call to completion.

    `instructions` overrides the prompt; otherwise it is rendered from the Brief.
    """
    from holdline.telephony.caller_agent import build_caller_agent

    if instructions is None and session.task.get("brief"):
        from holdline.agents.render import brief_to_instructions
        from holdline.models import CallBrief

        instructions = brief_to_instructions(CallBrief.model_validate(session.task["brief"]))

    agent = build_caller_agent(
        stream, instructions=instructions, brief=session.brief, session=session
    )
    session.agent = agent

    SESSIONS.append(session)
    supervisor = asyncio.create_task(_supervise(session), name="supervisor")
    try:
        await agent.run(inputs=[stream.input()], outputs=[stream.output()])
    except* Exception as eg:  # noqa: BLE001 - stream closed / agent stop
        log.info("session.run_end", errors=[repr(e) for e in eg.exceptions])
    finally:
        session.ended = True
        supervisor.cancel()
        with contextlib.suppress(ValueError):
            SESSIONS.remove(session)
        with contextlib.suppress(Exception):
            await agent.stop()
    return session


def resolve_pending(decision_id: str, answer: str) -> bool:
    """Used by the /decisions route: find whichever live session owns this id."""
    for sess in SESSIONS:
        if sess.resolve(decision_id, answer):
            return True
    with contextlib.suppress(Exception):
        store.resolve_decision(decision_id, answer)
        return True
    return False


def all_pending() -> list[dict]:
    out: list[dict] = []
    for sess in SESSIONS:
        out.extend(sess.pending_list())
    return out


__all__ = ["SESSIONS", "CallSession", "all_pending", "resolve_pending", "run_call_session"]
