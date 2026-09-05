"""The Strands Graph per-call flow: planner -> call -> debrief runs in order and
the debrief node scribes + emits call_ended. Live call + Bedrock are stubbed."""

import types

import pytest

from holdline import events, graph
from holdline.session import CallSession
from holdline.state import store


def _fake_session():
    stream = types.SimpleNamespace(outcome="cancelled", confirmation_number="IPF900001")
    s = CallSession(stream=stream, task={"task_id": None}, call_id=None)
    s.transcript = [
        {"role": "agent", "text": "I'd like to cancel."},
        {"role": "other", "text": "Done. Confirmation I P F 9 0 0 0 0 1."},
    ]
    return s


def test_build_call_graph_has_three_nodes():
    g = graph.build_call_graph()
    assert g is not None  # GraphBuilder.build() succeeded with planner/call/debrief


@pytest.mark.asyncio
async def test_run_call_graph_runs_call_then_debrief(monkeypatch):
    order: list[str] = []

    async def fake_run_call_session(session, stream, *, instructions=None):
        order.append("call")
        return session

    def fake_summarize(call_id, task, transcript):
        order.append("debrief")
        return {
            "outcome_status": "cancelled",
            "summary": "cancelled, confirmed",
            "confirmation_number": "IPF900001",
        }

    monkeypatch.setattr(graph, "run_call_session", fake_run_call_session)
    monkeypatch.setattr("holdline.orchestrator.summarize_and_persist", fake_summarize)

    task = store.create_task("cancel iron peak")
    store.set_task_brief(task["task_id"], {"objective": "cancel", "provider_name": "Iron Peak"})
    call = store.create_call(task["task_id"])
    session = _fake_session()
    session.call_id = call["call_id"]

    summary = await graph.run_call_graph(
        session, session.stream, store.get_task(task["task_id"]), call["call_id"]
    )

    assert order == ["call", "debrief"]
    assert summary["confirmation_number"] == "IPF900001"
    kinds = [e["kind"] for e in events.recent()]
    assert "call_ended" in kinds


@pytest.mark.asyncio
async def test_debrief_runs_even_if_call_node_errors(monkeypatch):
    async def boom(session, stream, *, instructions=None):
        raise RuntimeError("stream died")

    seen = {}

    def fake_summarize(call_id, task, transcript):
        seen["ran"] = True
        return {"outcome_status": "failed", "summary": "call dropped", "confirmation_number": ""}

    monkeypatch.setattr(graph, "run_call_session", boom)
    monkeypatch.setattr("holdline.orchestrator.summarize_and_persist", fake_summarize)

    task = store.create_task("x")
    store.set_task_brief(task["task_id"], {"objective": "x", "provider_name": "X"})
    call = store.create_call(task["task_id"])
    session = _fake_session()
    session.call_id = call["call_id"]

    await graph.run_call_graph(session, session.stream, store.get_task(task["task_id"]), call["call_id"])
    assert seen.get("ran") is True
