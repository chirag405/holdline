"""The per-call flow as a Strands Graph: plan -> call -> debrief.

    Planner  ->  Call (Caller + Supervisor live on the phone)  ->  Debrief (Scribe + memory)

Each node is a `MultiAgentBase`. They coordinate through a module-level run
registry keyed by a run id (passed in `invocation_state`), because a live
5-minute phone call does not fit passing a value between graph nodes.

The bridge calls `run_call_graph(...)`. `USE_GRAPH=false` falls back to calling
`run_call_session` + `summarize_and_persist` directly (same steps, no Graph).
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

import structlog
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status

from holdline import events
from holdline.session import CallSession, run_call_session

log = structlog.get_logger("graph")

# run_id -> mutable bag shared by the three nodes
_RUNS: dict[str, dict[str, Any]] = {}


def _done() -> MultiAgentResult:
    return MultiAgentResult(status=Status.COMPLETED)


class _Node(MultiAgentBase):
    def __init__(self, node_id: str) -> None:
        super().__init__()
        self.id = node_id


class PlannerNode(_Node):
    """Ensure the run has a Brief. Usually a passthrough -- the dashboard plans
    via POST /tasks before the call -- but if a raw request came in, plan it now."""

    def __init__(self) -> None:
        super().__init__("planner")

    async def invoke_async(self, task, invocation_state=None, **kw) -> MultiAgentResult:
        run = _RUNS[(invocation_state or {})["run_id"]]
        t = run["task"]
        if not t.get("brief") and run.get("request_text"):
            from holdline.orchestrator import create_and_plan, instructions_for_task

            t = await asyncio.to_thread(
                create_and_plan, run["request_text"], run.get("fields") or {}
            )
            run["task"] = t
            run["instructions"] = instructions_for_task(t)
        return _done()


class CallNode(_Node):
    """Run the live call: Caller + Supervisor on the phone until it hangs up."""

    def __init__(self) -> None:
        super().__init__("call")

    async def invoke_async(self, task, invocation_state=None, **kw) -> MultiAgentResult:
        run = _RUNS[(invocation_state or {})["run_id"]]
        session: CallSession = run["session"]
        try:
            await run_call_session(session, run["stream"], instructions=run.get("instructions"))
        except Exception as exc:  # noqa: BLE001 - debrief must still run
            run["call_error"] = str(exc)
            log.warning("graph.call_node_error", error=str(exc))
        return _done()


class DebriefNode(_Node):
    """Scribe the transcript, persist the call, teach provider memory, emit the
    call_ended event."""

    def __init__(self) -> None:
        super().__init__("debrief")

    async def invoke_async(self, task, invocation_state=None, **kw) -> MultiAgentResult:
        run = _RUNS[(invocation_state or {})["run_id"]]
        session: CallSession = run["session"]
        t = run["task"]
        call_id = run.get("call_id")
        call_error = run.get("call_error")
        recorded = getattr(session.stream, "outcome", None)
        summary: dict | None = None

        if call_id and call_error and not recorded and len(session.transcript) < 2:
            # The call blew up before anything useful happened -- don't pay for a
            # Scribe pass on an empty transcript, just record the failure.
            from holdline.state import store

            with contextlib.suppress(Exception):
                store.finish_call(call_id, outcome="error")
            with contextlib.suppress(Exception):
                store.set_task_status(t["task_id"], "failed")
            log.info("graph.debrief_error_shortcut", call_id=call_id, error=call_error)
        elif call_id:
            try:
                from holdline.orchestrator import summarize_and_persist

                summary = await asyncio.to_thread(
                    summarize_and_persist, call_id, t, session.transcript
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("graph.debrief_error", error=str(exc))
                from holdline.state import store

                with contextlib.suppress(Exception):
                    store.finish_call(
                        call_id,
                        outcome=recorded or "unknown",
                        confirmation_number=getattr(session.stream, "confirmation_number", None),
                    )
        run["summary"] = summary
        events.publish(
            "call_ended",
            call_id=call_id,
            task_id=t.get("task_id"),
            outcome=(summary or {}).get("outcome_status")
            or getattr(session.stream, "outcome", None)
            or "unknown",
            confirmation_number=(summary or {}).get("confirmation_number")
            or getattr(session.stream, "confirmation_number", None),
            summary=summary,
            turns=len(session.transcript),
        )
        return _done()


def build_call_graph():
    """Assemble the Strands Graph: planner -> call -> debrief."""
    from strands.multiagent import GraphBuilder

    b = GraphBuilder()
    b.add_node(PlannerNode(), "planner")
    b.add_node(CallNode(), "call")
    b.add_node(DebriefNode(), "debrief")
    b.add_edge("planner", "call")
    b.add_edge("call", "debrief")
    b.set_entry_point("planner")
    with contextlib.suppress(Exception):
        b.set_node_timeout(60 * 30)  # a call can be long; don't let the graph kill it
    with contextlib.suppress(Exception):
        b.set_execution_timeout(60 * 40)
    return b.build()


async def run_call_graph(
    session: CallSession,
    stream,
    task: dict,
    call_id: str | None,
    *,
    instructions: str | None = None,
) -> dict | None:
    """Drive one call through the Graph. Returns the Scribe summary dict (or None)."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    _RUNS[run_id] = {
        "session": session,
        "stream": stream,
        "task": task,
        "call_id": call_id,
        "instructions": instructions,
        "request_text": task.get("request_text"),
        "fields": task.get("fields"),
    }
    try:
        graph = build_call_graph()
        result = await graph.invoke_async(
            "run one Holdline call", invocation_state={"run_id": run_id}
        )
        log.info("graph.done", run_id=run_id, status=getattr(result, "status", None))
        return _RUNS[run_id].get("summary")
    finally:
        _RUNS.pop(run_id, None)


__all__ = ["CallNode", "DebriefNode", "PlannerNode", "build_call_graph", "run_call_graph"]
