"""Glue between the pieces: create a task, plan it, and (post-call) summarize it.

Planning pulls a provider's known IVR path from provider memory (local or
AgentCore); the Scribe writes the path + outcome back. `holdline.graph` composes
these same steps as a Strands Graph for the per-call orchestration path.
"""

from __future__ import annotations

import structlog

from holdline import memory
from holdline.agents.planner import plan_call
from holdline.agents.render import brief_to_instructions
from holdline.agents.scribe import summarize_call
from holdline.models import CallBrief
from holdline.state import store

log = structlog.get_logger("orchestrator")


def _guess_provider(request_text: str) -> str | None:
    """Cheap provider-name guess for a memory lookup before the Brief exists."""
    low = request_text.lower()
    for snap in memory.local_snapshot().values():
        name = snap.get("provider_name", "")
        if name and name.lower() in low:
            return name
    return None


def create_and_plan(request_text: str, fields: dict[str, str] | None = None) -> dict:
    """Create a task row, run the Planner, persist the Brief. Returns the task dict
    (with `brief` populated)."""
    task = store.create_task(request_text, fields)
    guess = _guess_provider(request_text)
    hint = memory.get_provider_hint(guess) if guess else None

    brief = plan_call(request_text, fields, ivr_hint=hint)
    if not brief.ivr_hint:
        brief.ivr_hint = memory.get_provider_hint(brief.provider_name)

    store.set_task_brief(task["task_id"], brief.model_dump())
    log.info(
        "task.planned",
        task_id=task["task_id"],
        provider=brief.provider_name,
        had_memory_hint=bool(brief.ivr_hint),
    )
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

    # Teach provider memory what this call revealed.
    memory.record_call_learnings(
        brief.provider_name,
        ivr_path=summary.learned_ivr_path,
        outcome=summary.outcome_status,
        confirmation_number=summary.confirmation_number,
    )
    return summary.model_dump()


def _blank_brief(task: dict) -> CallBrief:
    return CallBrief(
        objective=task.get("request_text", "complete the call"),
        provider_name=task.get("fields", {}).get("provider", "unknown"),
    )


__all__ = [
    "create_and_plan",
    "instructions_for_task",
    "summarize_and_persist",
]
