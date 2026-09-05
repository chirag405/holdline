"""Tiny in-process pub/sub for live dashboard updates (Server-Sent Events).

`publish(kind, **data)` is sync and safe to call from anywhere (agent tools,
CallSession, the bridge). Each SSE client gets its own queue via `subscribe()`,
and a short replay buffer lets a dashboard that connects mid-call catch up.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from typing import Any

_subscribers: set[asyncio.Queue] = set()
_recent: deque[dict] = deque(maxlen=300)
_seq = 0


def publish(kind: str, **data: Any) -> dict:
    global _seq
    _seq += 1
    evt = {"seq": _seq, "kind": kind, "ts": time.time(), **data}
    _recent.append(evt)
    for q in list(_subscribers):
        try:
            q.put_nowait(evt)
        except asyncio.QueueFull:  # a stuck client shouldn't block the call
            pass
    return evt


@contextlib.asynccontextmanager
async def subscribe():
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    _subscribers.add(q)
    try:
        yield q
    finally:
        _subscribers.discard(q)


def recent(after_seq: int = 0) -> list[dict]:
    return [e for e in _recent if e["seq"] > after_seq]


def reset() -> None:
    _recent.clear()
    _subscribers.clear()


__all__ = ["publish", "recent", "reset", "subscribe"]
