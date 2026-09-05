"""Failure paths become clean recorded outcomes, never a hang."""

import types

import pytest
from fastapi.testclient import TestClient

from holdline import graph, orchestrator
from holdline.session import CallSession
from holdline.state import store
from holdline.telephony.bridge import app

client = TestClient(app)


def test_planner_failure_degrades_to_a_plain_brief(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bedrock exploded")

    monkeypatch.setattr(orchestrator, "plan_call", boom)
    task = orchestrator.create_and_plan(
        "Cancel my Iron Peak Fitness membership", {"account_number": "IPF-1"}
    )
    assert task["status"] == "briefed"
    assert task["brief"]["objective"].startswith("Cancel my Iron Peak Fitness")
    # a known provider still gets its IVR hint from memory
    assert "press 2 for membership" in (task["brief"]["ivr_hint"] or "")


@pytest.mark.asyncio
async def test_graph_records_error_row_when_call_blows_up_early(monkeypatch):
    async def boom(session, stream, *, instructions=None):
        raise RuntimeError("nova stream reset")

    scribe_ran = {"v": False}

    def scribe(*a, **k):
        scribe_ran["v"] = True
        return {}

    monkeypatch.setattr(graph, "run_call_session", boom)
    monkeypatch.setattr("holdline.orchestrator.summarize_and_persist", scribe)

    task = store.create_task("x")
    store.set_task_brief(task["task_id"], {"objective": "x", "provider_name": "X"})
    call = store.create_call(task["task_id"])
    sess = CallSession(
        stream=types.SimpleNamespace(outcome=None, confirmation_number=None),
        task={"task_id": None},
        call_id=call["call_id"],
    )
    sess.transcript = []  # nothing happened

    await graph.run_call_graph(
        sess, sess.stream, store.get_task(task["task_id"]), call["call_id"]
    )

    assert scribe_ran["v"] is False, "no Scribe pass on an empty failed call"
    assert store.get_call(call["call_id"])["outcome"] == "error"
    assert store.get_task(task["task_id"])["status"] == "failed"


def test_call_status_no_answer_records_failed_call():
    task = store.create_task("call somewhere")
    store.set_task_brief(task["task_id"], {"objective": "x", "provider_name": "X"})
    # simulate POST /calls having stashed this pending call
    from holdline.telephony import bridge

    bridge._pending["CAno1"] = {"task": store.get_task(task["task_id"]), "instructions": None}

    r = client.post(
        "/call-status", data={"CallSid": "CAno1", "CallStatus": "no-answer"}
    )
    assert r.status_code == 204
    calls = store.list_calls()
    assert calls and calls[0]["outcome"] == "no_answer"
    assert store.get_task(task["task_id"])["status"] == "failed"


def test_call_status_completed_after_connect_is_ignored():
    from holdline.telephony import bridge

    bridge._ws_seen.add("CAok1")
    before = len(store.list_calls())
    r = client.post("/call-status", data={"CallSid": "CAok1", "CallStatus": "completed"})
    assert r.status_code == 204
    assert len(store.list_calls()) == before  # no phantom failure row
    bridge._ws_seen.discard("CAok1")
