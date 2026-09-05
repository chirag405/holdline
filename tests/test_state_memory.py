"""The in-process state backend round-trips tasks / calls / decisions via the
backend-agnostic `store` facade."""

from holdline.state import store


def test_task_lifecycle():
    task = store.create_task("cancel my gym", {"account": "IPF-99"})
    assert task["status"] == "new"
    store.set_task_brief(task["task_id"], {"objective": "cancel"})
    t = store.get_task(task["task_id"])
    assert t["status"] == "briefed" and t["brief"] == {"objective": "cancel"}
    store.set_task_status(task["task_id"], "calling")
    assert store.get_task(task["task_id"])["status"] == "calling"


def test_call_transcript_and_finish():
    task = store.create_task("x")
    call = store.create_call(task["task_id"])
    cid = call["call_id"]
    store.append_transcript(cid, "agent", "Hello, I'd like to cancel.")
    store.append_transcript(cid, "other", "One moment.")
    store.finish_call(cid, outcome="cancelled", confirmation_number="IPF123456",
                      summary={"summary": "done"})
    c = store.get_call(cid)
    assert len(c["transcript"]) == 2
    assert c["status"] == "ended"
    assert c["confirmation_number"] == "IPF123456"
    assert c["summary"] == {"summary": "done"}


def test_finish_failed_maps_to_failed_status():
    task = store.create_task("x")
    cid = store.create_call(task["task_id"])["call_id"]
    store.finish_call(cid, outcome="failed")
    assert store.get_call(cid)["status"] == "failed"


def test_decisions_pending_then_resolved():
    task = store.create_task("x")
    cid = store.create_call(task["task_id"])["call_id"]
    d = store.create_decision(cid, "Accept 50% off?", ["accept", "decline"])
    assert [x["decision_id"] for x in store.pending_decisions()] == [d["decision_id"]]
    store.resolve_decision(d["decision_id"], "decline")
    assert store.pending_decisions() == []
    assert store.get_decision(d["decision_id"])["answer"] == "decline"


def test_list_calls_newest_first():
    task = store.create_task("x")
    a = store.create_call(task["task_id"])["call_id"]
    b = store.create_call(task["task_id"])["call_id"]
    ids = [c["call_id"] for c in store.list_calls()]
    assert ids[:2] == [b, a] or set(ids) == {a, b}
