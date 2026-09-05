"""DynamoDB access for the three Holdline tables: tasks, calls, decisions.

One thin module. Every write is explicit; reads return plain dicts. Failures are
raised, never swallowed — the caller (agent orchestrator or dashboard) decides
whether that becomes an escalation or a surfaced error.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError

from holdline.config import get_settings

log = structlog.get_logger("state.ddb")

# Logical table name -> (hash key, optional range key)
_SCHEMA: dict[str, tuple[str, str | None]] = {
    "tasks": ("task_id", None),
    "calls": ("call_id", None),
    "decisions": ("decision_id", None),
}


def _resource():
    return boto3.resource("dynamodb", region_name=get_settings().aws_region)


def _table(logical: str):
    return _resource().Table(get_settings().table(logical))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_ts() -> int:
    return int(time.time())


# --------------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------------- #
def create_task(request_text: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "task_id": new_id("task"),
        "request_text": request_text,
        "fields": fields or {},
        "brief": None,
        "status": "new",  # new -> briefed -> calling -> done -> failed
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }
    _table("tasks").put_item(Item=item)
    log.info("task.created", task_id=item["task_id"])
    return item


def set_task_brief(task_id: str, brief: dict[str, Any]) -> None:
    _update("tasks", {"task_id": task_id}, {"brief": brief, "status": "briefed"})


def set_task_status(task_id: str, status: str) -> None:
    _update("tasks", {"task_id": task_id}, {"status": status})


def get_task(task_id: str) -> dict[str, Any] | None:
    return _get("tasks", {"task_id": task_id})


# --------------------------------------------------------------------------- #
# calls
# --------------------------------------------------------------------------- #
def create_call(task_id: str) -> dict[str, Any]:
    item = {
        "call_id": new_id("call"),
        "task_id": task_id,
        "status": "dialing",  # dialing -> in_ivr -> on_hold -> with_rep -> ended -> failed
        "transcript": [],  # list of {role, text, ts}
        "recording_url": None,
        "outcome": None,
        "confirmation_number": None,
        "started_at": now_ts(),
        "ended_at": None,
    }
    _table("calls").put_item(Item=item)
    log.info("call.created", call_id=item["call_id"], task_id=task_id)
    return item


def append_transcript(call_id: str, role: str, text: str) -> None:
    """Append one utterance. role is 'agent' | 'other' | 'system'."""
    _table("calls").update_item(
        Key={"call_id": call_id},
        UpdateExpression="SET transcript = list_append(transcript, :seg)",
        ExpressionAttributeValues={":seg": [{"role": role, "text": text, "ts": now_ts()}]},
    )


def set_call_status(call_id: str, status: str) -> None:
    _update("calls", {"call_id": call_id}, {"status": status})


def finish_call(
    call_id: str,
    *,
    outcome: str,
    confirmation_number: str | None = None,
    recording_url: str | None = None,
) -> None:
    _update(
        "calls",
        {"call_id": call_id},
        {
            "status": "ended" if outcome not in {"failed", "error"} else "failed",
            "outcome": outcome,
            "confirmation_number": confirmation_number,
            "recording_url": recording_url,
            "ended_at": now_ts(),
        },
    )
    log.info("call.finished", call_id=call_id, outcome=outcome)


def get_call(call_id: str) -> dict[str, Any] | None:
    return _get("calls", {"call_id": call_id})


def list_calls(limit: int = 50) -> list[dict[str, Any]]:
    resp = _table("calls").scan(Limit=limit)
    items = resp.get("Items", [])
    return sorted(items, key=lambda c: c.get("started_at", 0), reverse=True)


# --------------------------------------------------------------------------- #
# decisions (the escalation queue)
# --------------------------------------------------------------------------- #
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
    _table("decisions").put_item(Item=item)
    log.info("decision.created", decision_id=item["decision_id"], call_id=call_id)
    return item


def resolve_decision(decision_id: str, answer: str) -> None:
    _update(
        "decisions",
        {"decision_id": decision_id},
        {"answer": answer, "resolved_at": now_ts()},
    )
    log.info("decision.resolved", decision_id=decision_id, answer=answer)


def get_decision(decision_id: str) -> dict[str, Any] | None:
    return _get("decisions", {"decision_id": decision_id})


def pending_decisions() -> list[dict[str, Any]]:
    resp = _table("decisions").scan(
        FilterExpression="attribute_not_exists(resolved_at) OR resolved_at = :n",
        ExpressionAttributeValues={":n": None},
    )
    return resp.get("Items", [])


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _update(logical: str, key: dict[str, Any], changes: dict[str, Any]) -> None:
    changes = {**changes, "updated_at": now_ts()}
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in changes)
    try:
        _table(logical).update_item(
            Key=key,
            UpdateExpression=expr,
            ExpressionAttributeNames={f"#{k}": k for k in changes},
            ExpressionAttributeValues={f":{k}": v for k, v in changes.items()},
        )
    except ClientError:
        log.exception("ddb.update_failed", table=logical, key=key)
        raise


def _get(logical: str, key: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return _table(logical).get_item(Key=key).get("Item")
    except ClientError:
        log.exception("ddb.get_failed", table=logical, key=key)
        raise


__all__ = [
    "create_task", "set_task_brief", "set_task_status", "get_task",
    "create_call", "append_transcript", "set_call_status", "finish_call",
    "get_call", "list_calls",
    "create_decision", "resolve_decision", "get_decision", "pending_decisions",
    "new_id", "now_ts",
]
