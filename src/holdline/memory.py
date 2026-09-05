"""Provider memory: what Holdline has learned about a company from past calls.

The Planner reads a provider's known IVR path before a call; the Scribe writes the
path (and outcome) back after. Two backends, chosen by MEMORY_BACKEND:

  local      in-process dict, seeded with a couple of known lines. Durable only
             for the life of the bridge process. Default -- no setup.
  agentcore  Amazon Bedrock AgentCore Memory. Durable, shared across runs.
             One event per call under session id "provider:<slug>".

Either way the surface is the same: get_provider_hint() / record_call_learnings().
"""

from __future__ import annotations

import re

import structlog

from holdline.config import get_settings

log = structlog.get_logger("memory")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "unknown").strip().lower()).strip("-")


# --------------------------------------------------------------------------- #
# local backend
# --------------------------------------------------------------------------- #
_LOCAL: dict[str, dict] = {
    "iron-peak-fitness": {
        "provider_name": "Iron Peak Fitness",
        "ivr_path": "main menu: press 2 for membership; membership menu: press 4 to cancel",
        "calls": 0,
        "last_outcome": None,
    },
}


def _local_get(name: str) -> str | None:
    p = _LOCAL.get(_slug(name))
    return p["ivr_path"] if p else None


def _local_record(name: str, *, ivr_path: str, outcome: str, confirmation_number: str) -> None:
    slug = _slug(name)
    p = _LOCAL.setdefault(
        slug, {"provider_name": name, "ivr_path": None, "calls": 0, "last_outcome": None}
    )
    if ivr_path:
        p["ivr_path"] = ivr_path
    p["calls"] += 1
    p["last_outcome"] = outcome
    p["last_confirmation"] = confirmation_number or None


def local_snapshot() -> dict[str, dict]:
    return {k: dict(v) for k, v in _LOCAL.items()}


def local_reset() -> None:
    for k in list(_LOCAL):
        if k != "iron-peak-fitness":
            del _LOCAL[k]
    _LOCAL["iron-peak-fitness"].update(calls=0, last_outcome=None)


# --------------------------------------------------------------------------- #
# agentcore backend
# --------------------------------------------------------------------------- #
_ACTOR = "holdline-user"
_mc = None
_memory_id: str | None = None


def _agentcore():
    """Return (MemoryClient, memory_id) or raise."""
    global _mc, _memory_id
    if _mc is not None and _memory_id:
        return _mc, _memory_id
    from bedrock_agentcore.memory import MemoryClient

    s = get_settings()
    _mc = MemoryClient(region_name=s.aws_region)
    if s.agentcore_memory_id:
        _memory_id = s.agentcore_memory_id
    else:
        created = _mc.create_or_get_memory(
            name="holdline_provider_memory",
            description="Holdline: learned IVR paths and outcomes per provider.",
        )
        _memory_id = created.get("memoryId") or created.get("id")
    log.info("agentcore.memory_ready", memory_id=_memory_id)
    return _mc, _memory_id


def _agentcore_get(name: str) -> str | None:
    mc, mid = _agentcore()
    slug = _slug(name)
    events = mc.list_events(
        memory_id=mid, actor_id=_ACTOR, session_id=f"provider:{slug}", max_results=20
    )
    for ev in reversed(events or []):  # newest last from list_events
        meta = ev.get("metadata") or {}
        path = meta.get("ivr_path")
        if path:
            return str(path)
    return None


def _agentcore_record(name: str, *, ivr_path: str, outcome: str, confirmation_number: str) -> None:
    mc, mid = _agentcore()
    slug = _slug(name)
    summary = f"Called {name}. Outcome: {outcome}."
    if ivr_path:
        summary += f" IVR path: {ivr_path}."
    if confirmation_number:
        summary += f" Confirmation: {confirmation_number}."
    mc.create_event(
        memory_id=mid,
        actor_id=_ACTOR,
        session_id=f"provider:{slug}",
        messages=[("assistant", summary)],
        metadata={
            "provider": slug,
            "ivr_path": ivr_path or "",
            "outcome": outcome,
        },
    )


# --------------------------------------------------------------------------- #
# public surface
# --------------------------------------------------------------------------- #
def _backend() -> str:
    return get_settings().memory_backend


def get_provider_hint(provider_name: str) -> str | None:
    if not provider_name:
        return None
    try:
        if _backend() == "agentcore":
            return _agentcore_get(provider_name)
        return _local_get(provider_name)
    except Exception as exc:  # noqa: BLE001 - memory is an optimization, never fatal
        log.warning("memory.get_failed", provider=provider_name, error=str(exc))
        return _local_get(provider_name)


def record_call_learnings(
    provider_name: str,
    *,
    ivr_path: str = "",
    outcome: str = "unknown",
    confirmation_number: str = "",
) -> None:
    if not provider_name:
        return
    try:
        if _backend() == "agentcore":
            _agentcore_record(
                provider_name,
                ivr_path=ivr_path,
                outcome=outcome,
                confirmation_number=confirmation_number,
            )
        _local_record(
            provider_name,
            ivr_path=ivr_path,
            outcome=outcome,
            confirmation_number=confirmation_number,
        )
        log.info("memory.recorded", provider=provider_name, ivr_path=bool(ivr_path), outcome=outcome)
    except Exception as exc:  # noqa: BLE001
        log.warning("memory.record_failed", provider=provider_name, error=str(exc))


__all__ = ["get_provider_hint", "local_reset", "local_snapshot", "record_call_learnings"]
