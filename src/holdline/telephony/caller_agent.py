"""Build the Caller: a BidiAgent (Nova 2 Sonic) that runs one live phone call.

Day 3 targets the self-hosted practice IVR with a fixed goal so the full
dial -> menu -> hold -> rep -> confirmation-number path can run autonomously.
Day 4 renders the prompt from a `CallBrief`. Day 5 adds `escalate_to_user`, which
pauses the call and asks the account holder while the line stays open.
"""

from __future__ import annotations

from typing import Any

import structlog

from holdline.config import get_settings

log = structlog.get_logger("telephony.caller_agent")

_PRACTICE_GOAL = """\
You are Holdline, an automated assistant making a phone call on behalf of Chirag.

GOAL: cancel Chirag's membership at Iron Peak Fitness, effective at the end of the
current billing period, and obtain a cancellation confirmation number.

You will first hear an automated menu (IVR). Known path for this line:
  main menu  -> option 2 (membership)
  membership -> option 4 (cancel membership)
Then you go on hold; then a human representative picks up.

HOW TO BEHAVE:
- On a menu: as soon as you hear the option you need, call `press_keys` with the
  single digit (e.g. "2"). This line also accepts spoken digits, so if a keypress
  does not seem to register, simply say the number instead.
- On hold: stay completely silent. Do not talk until a person greets you.
- With the representative: greet them, say you are an automated assistant calling
  for Chirag, and ask to cancel the membership.
- You MAY accept: cancellation effective at the end of the current billing period.
- If the representative offers a retention deal (a discount, a pause, a downgrade,
  free months, a plan change): you are NOT authorized to accept or reject it. Tell
  them "let me check with the account holder, can you hold for a moment?", then
  call `escalate_to_user` with a short question and the offer details. Act on the
  answer it returns.
- When the representative confirms the cancellation AND gives a confirmation or
  reference number, call `record_outcome` with status "cancelled" and that number.
  Then say a short goodbye and call `stop_conversation`.
- If the call clearly cannot succeed (wrong number, endless loop, disconnected),
  call `record_outcome` with status "failed" and a short note, then
  `stop_conversation`.
"""


def build_caller_agent(
    stream: Any,
    *,
    instructions: str | None = None,
    brief: dict | None = None,
    session: Any = None,
) -> Any:
    """Create the per-call BidiAgent. `stream` is the live TwilioMediaStream: the
    DTMF tool injects tones into it, and `record_outcome` stashes the result on it
    so the bridge can log/persist it after the call. `brief` (a CallBrief dict) is
    exposed via `lookup_task_context`. `session` (a CallSession) backs
    `escalate_to_user` -- the pause-and-ask-the-account-holder path."""
    from strands import tool
    from strands.experimental.bidi import BidiAgent
    from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
    from strands.experimental.bidi.tools import stop_conversation

    s = get_settings()

    @tool
    async def escalate_to_user(question: str, options: list[str] | None = None, context: str = "") -> str:
        """Pause and ask the ACCOUNT HOLDER a question you are not authorized to
        decide yourself -- a retention offer, a fee, a plan change, anything outside
        your limits. Say a brief holding phrase to the representative first ("let me
        check with the account holder, can you hold a moment?"). Keep the line open.
        This returns the account holder's decision as text; then continue the call.

        Args:
            question: a short, specific question (ideally yes/no or choose-one).
            options: 2-4 short choices; put the safe "hold firm" option first.
            context: one line of context (what the rep offered, in their words).
        """
        if session is None:
            return "No account holder is reachable right now; hold firm on the original request."
        return await session.escalate(question, options or [], context)

    @tool
    def lookup_task_context(question: str = "") -> str:
        """Recall details about this call: the objective, identity/account details
        to verify with, and what you may or may not agree to. Use it if you need an
        account number or forget a boundary mid-conversation."""
        if not brief:
            return "No structured brief for this call; follow your instructions."
        import json as _json

        return _json.dumps(
            {
                "objective": brief.get("objective"),
                "provider_name": brief.get("provider_name"),
                "identity_info": brief.get("identity_info", {}),
                "boundaries": brief.get("boundaries", {}),
                "success_criteria": brief.get("success_criteria", []),
            },
            indent=2,
        )

    @tool
    async def press_keys(digits: str) -> str:
        """Press keys on the phone keypad (DTMF touch-tones). Use for IVR menus and
        for entering account or phone numbers. `digits` may contain 0-9 * # and
        ',' for a short pause."""
        ok = await stream.send_dtmf(digits)
        if ok:
            return f"Pressed {digits}."
        return (
            f"Could not send tones for {digits} (the line isn't ready or the "
            "keypress didn't register). Say the digits out loud instead."
        )

    @tool
    def record_outcome(status: str, confirmation_number: str = "", notes: str = "") -> str:
        """Record the final result of the call.

        Args:
            status: "cancelled" | "refused" | "needs_human" | "failed"
            confirmation_number: reference number the representative gave, if any.
            notes: anything the user should know.
        """
        stream.outcome = status
        stream.confirmation_number = confirmation_number or None
        stream.outcome_notes = notes
        log.info(
            "tool.record_outcome",
            call_sid=getattr(stream, "call_sid", None),
            status=status,
            confirmation_number=confirmation_number,
            notes=notes,
        )
        return "Recorded."

    model = BidiNovaSonicModel(
        model_id=s.nova_sonic_model_id,
        client_config={"region": s.aws_region},
        provider_config={
            "audio": {"input_rate": 8000, "output_rate": 8000, "voice": s.nova_sonic_voice}
        },
    )
    return BidiAgent(
        model=model,
        system_prompt=instructions or _PRACTICE_GOAL,
        tools=[
            press_keys,
            record_outcome,
            lookup_task_context,
            escalate_to_user,
            stop_conversation,
        ],
    )


__all__ = ["build_caller_agent"]
