"""In-process implementation of the state API (tasks / calls / decisions).

Same function surface as `state.ddb`, backed by plain dicts. Used for local dev,
tests, and the offline verify scripts (STATE_BACKEND=memory). Data lives only for
the process lifetime.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

_tasks: dict[str, dict] = {}
_calls: dict[str, dict] = {}
_decisions: dict[str, dict] = {}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_ts() -> int:
    return int(time.time())


def reset() -> None:
    _tasks.clear()
    _calls.clear()
    _decisions.clear()


# -- tasks ------------------------------------------------------------------ #
def create_task(request_text: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "task_id": new_id("task"),
        "request_text": request_text,
        "fields": fields or {},
        "brief": None,
        "status": "new",
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    _tasks[item["task_id"]] = item
    return dict(item)


def set_task_brief(task_id: str, brief: dict[str, Any]) -> None:
    _tasks[task_id].update(brief=brief, status="briefed", updated_at=now_ts())


def set_task_status(task_id: str, status: str) -> None:
    _tasks[task_id].update(status=status, updated_at=now_ts())


def get_task(task_id: str) -> dict[str, Any] | None:
    t = _tasks.get(task_id)
    return dict(t) if t else None


# -- calls ---------------------------------------------------------------- #
def create_call(task_id: str) -> dict[str, Any]:
    item = {
        "call_id": new_id("call"),
        "task_id": task_id,
        "status": "dialing",
        "transcript": [],
        "recording_url": None,
        "outcome": None,
        "confirmation_number": None,
        "summary": None,
        "started_at": now_ts(),
        "ended_at": None,
    }
    _calls[item["call_id"]] = item
    return dict(item)


def append_transcript(call_id: str, role: str, text: str) -> None:
    _calls[call_id]["transcript"].append({"role": role, "text": text, "ts": now_ts()})
    _calls[call_id]["updated_at"] = now_ts()


def set_call_status(call_id: str, status: str) -> None:
    _calls[call_id].update(status=status, updated_at=now_ts())


def finish_call(
    call_id: str,
    *,
    outcome: str,
    confirmation_number: str | None = None,
    recording_url: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    _calls[call_id].update(
        status="ended" if outcome not in {"failed", "error"} else "failed",
        outcome=outcome,
        confirmation_number=confirmation_number,
        recording_url=recording_url,
        summary=summary,
        ended_at=now_ts(),
    )


def get_call(call_id: str) -> dict[str, Any] | None:
    c = _calls.get(call_id)
    return dict(c) if c else None


def list_calls(limit: int = 50) -> list[dict[str, Any]]:
    return sorted(
        (dict(c) for c in _calls.values()), key=lambda c: c.get("started_at", 0), reverse=True
    )[:limit]


# -- decisions ---------------------------------------------------------- #
def create_decision(
    call_id: str, question: str, options: list[str], context: str = ""
) -> dict[str, Any]:
    item = {
        "decision_id": new_id("dec"),
        "call_id": call_id,
        "question": question,
        "options": options,
        "context": context,
        "answer": None,
        "created_at": now_ts(),
        "resolved_at": None,
    }
    _decisions[item["decision_id"]] = item
    return dict(item)


def resolve_decision(decision_id: str, answer: str) -> None:
    _decisions[decision_id].update(answer=answer, resolved_at=now_ts())


def get_decision(decision_id: str) -> dict[str, Any] | None:
    d = _decisions.get(decision_id)
    return dict(d) if d else None


def pending_decisions() -> list[dict[str, Any]]:
    return [dict(d) for d in _decisions.values() if d.get("resolved_at") is None]
