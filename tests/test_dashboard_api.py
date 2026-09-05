"""The dashboard-facing API: config, call history/detail, and the SSE event feed."""

import json

from fastapi.testclient import TestClient

from holdline import events
from holdline.state import store
from holdline.telephony.bridge import app

client = TestClient(app)


def test_config_shape():
    body = client.get("/config").json()
    assert "practice_ivr_number" in body
    assert "supervisor_enabled" in body
    assert body["state_backend"] == "memory"


def test_calls_history_and_detail():
    task = store.create_task("cancel gym")
    call = store.create_call(task["task_id"])
    store.append_transcript(call["call_id"], "agent", "Hi there.")
    store.finish_call(call["call_id"], outcome="cancelled", confirmation_number="IPF42")

    lst = client.get("/calls").json()["calls"]
    assert any(c["call_id"] == call["call_id"] for c in lst)

    detail = client.get(f"/calls/{call['call_id']}").json()
    assert detail["confirmation_number"] == "IPF42"
    assert len(detail["transcript"]) == 1

    assert client.get("/calls/nope").status_code == 404


def test_stream_replays_recent_events():
    events.publish("turn", call_id="c1", role="agent", text="hello")
    events.publish("decision_open", call_id="c1", decision_id="d1",
                   question="Accept?", options=["hold firm", "accept"])

    r = client.get("/stream?after=0&once=1")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    lines = [json.loads(ln[6:]) for ln in r.text.splitlines() if ln.startswith("data: ")]
    kinds = [e["kind"] for e in lines]
    assert kinds == ["turn", "decision_open"]
    assert lines[1]["options"] == ["hold firm", "accept"]


def test_decisions_roundtrip_via_api():
    # no live session -> resolve falls through to the store
    task = store.create_task("x")
    call = store.create_call(task["task_id"])
    d = store.create_decision(call["call_id"], "Accept 50%?", ["hold firm", "accept"])
    r = client.post(f"/decisions/{d['decision_id']}", json={"answer": "hold firm"})
    assert r.status_code == 200 and r.json()["resolved"] is True
    assert store.get_decision(d["decision_id"])["answer"] == "hold firm"
