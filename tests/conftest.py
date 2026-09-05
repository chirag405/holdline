"""Test fixtures: force the in-process state backend and start each test clean."""

from __future__ import annotations

import pytest

from holdline.config import get_settings


@pytest.fixture(autouse=True)
def _memory_state(monkeypatch):
    monkeypatch.setenv("STATE_BACKEND", "memory")
    get_settings.cache_clear()
    from holdline.state import memory

    memory.reset()
    yield
    memory.reset()
    get_settings.cache_clear()
