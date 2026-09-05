"""Test fixtures: force the in-process state backend and start each test clean."""

from __future__ import annotations

import pytest

from holdline.config import get_settings


@pytest.fixture(autouse=True)
def _memory_state(monkeypatch):
    monkeypatch.setenv("STATE_BACKEND", "memory")
    monkeypatch.setenv("MEMORY_BACKEND", "local")
    get_settings.cache_clear()
    from holdline import events
    from holdline import memory as provider_memory
    from holdline.state import memory

    memory.reset()
    events.reset()
    provider_memory.local_reset()
    yield
    memory.reset()
    events.reset()
    provider_memory.local_reset()
    get_settings.cache_clear()
