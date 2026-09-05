"""Glue between the pieces: create a task, plan it, and (post-call) summarize it.

Day 4 version -- sequential and synchronous. Day 7 wraps planning + the call +
the summary in a Strands Graph and pulls the IVR hint from AgentCore Memory.
"""

from __future__ import annotations

import structlog

from holdline.agents.planner import plan_call
from holdline.agents.render import brief_to_instructions
from holdline.agents.scribe import summarize_call
from holdline.models import CallBrief
from holdline.state import store

log = structlog.get_logger("orchestrator")

# Known menu paths by provider name (lowercased). Day 7 moves this into
# AgentCore Memory and lets the Scribe write new entries back.
_KNOWN_IVR: dict[str, str] = {
    "iron peak fitness": "main menu: press 2 for membership; membership menu: press 4 to cancel",
}


def known_ivr_hint(provider_name: str) -> str | None:
    return _KNOWN_IVR.get(provider_name.strip().lower())


def create_and_plan(request_text: str, fields: dict[str, str] | None = None) -> dict:
    """Create a task row, run the Planner, persist the Brief. Returns the task dict
    (with `brief` populated)."""
    task = store.create_task(request_text, fields)
    # A cheap provider-name guess for the IVR-hint lookup before we have the Brief.
    hint = None
    for name in _KNOWN_IVR:
        if name in request_text.lower():
            hint = _KNOWN_IVR[name]
            break
    brief = plan_call(request_text, fields, ivr_hint=hint)
    if not brief.ivr_hint:
        brief.ivr_hint = known_ivr_hint(brief.provider_name)
    store.set_task_brief(task["task_id"], brief.model_dump())
    log.info("task.planned", task_id=task["task_id"], provider=brief.provider_name)
    return store.get_task(task["task_id"])


def instructions_for_task(task: dict) -> str:
    brief = CallBrief.model_validate(task["brief"])
    return brief_to_instructions(brief)


def summarize_and_persist(call_id: str, task: dict, transcript: list[dict]) -> dict:
    brief = CallBrief.model_validate(task["brief"]) if task.get("brief") else _blank_brief(task)
    summary = summarize_call(brief, transcript)
    store.finish_call(
        call_id,
        outcome=summary.outcome_status,
        confirmation_number=summary.confirmation_number or None,
        summary=summary.model_dump(),
    )
    if task.get("task_id"):
        store.set_task_status(task["task_id"], "done")
    return summary.model_dump()


def _blank_brief(task: dict) -> CallBrief:
    return CallBrief(
        objective=task.get("request_text", "complete the call"),
        provider_name=task.get("fields", {}).get("provider", "unknown"),
    )


__all__ = [
    "create_and_plan",
    "instructions_for_task",
    "known_ivr_hint",
    "summarize_and_persist",
]
