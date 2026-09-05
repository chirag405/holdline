"""Backend-agnostic state facade.

Import from here (or from `holdline.state`) rather than from `ddb` / `memory`
directly. `STATE_BACKEND` (env) selects the implementation:

    dynamodb  -> holdline.state.ddb      (default; needs AWS + tables)
    memory    -> holdline.state.memory   (in-process; dev, tests, verify scripts)
"""

from __future__ import annotations

from holdline.config import get_settings

_NAMES = (
    "create_task", "set_task_brief", "set_task_status", "get_task",
    "create_call", "append_transcript", "set_call_status", "finish_call",
    "get_call", "list_calls",
    "create_decision", "resolve_decision", "get_decision", "pending_decisions",
    "new_id", "now_ts",
)


def _backend():
    if get_settings().state_backend == "memory":
        from holdline.state import memory as m

        return m
    from holdline.state import ddb as d

    return d


def __getattr__(name: str):  # PEP 562 module-level getattr
    if name in _NAMES:
        return getattr(_backend(), name)
    if name == "reset":
        return getattr(_backend(), "reset", lambda: None)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [*_NAMES, "reset"]
