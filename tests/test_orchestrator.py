"""Orchestrator wiring: planning writes a Brief; post-call summarizing writes the
call row and closes the task. Planner + Scribe are stubbed (no Bedrock in CI)."""

from holdline import orchestrator
from holdline.models import Boundaries, CallBrief, CallSummary
from holdline.state import store


def _fake_brief(request_text, fields=None, *, ivr_hint=None):
    return CallBrief(
        objective="Cancel the Iron Peak Fitness membership.",
        provider_name="Iron Peak Fitness",
        identity_info=fields or {},
        boundaries=Boundaries(must_escalate=["any retention offer"]),
        success_criteria=["confirmation number given"],
        ivr_hint=ivr_hint,
    )


def _fake_summary(brief, transcript):
    return CallSummary(
        outcome_status="cancelled",
        summary="Asked to cancel; declined the retention offer; cancellation confirmed.",
        confirmation_number="IPF654321",
        learned_ivr_path="pressed 2 then 4",
    )


def test_create_and_plan_persists_brief(monkeypatch):
    monkeypatch.setattr(orchestrator, "plan_call", _fake_brief)
    task = orchestrator.create_and_plan(
        "Cancel my Iron Peak Fitness membership", {"account_number": "IPF-99"}
    )
    assert task["status"] == "briefed"
    assert task["brief"]["provider_name"] == "Iron Peak Fitness"
    # IVR hint for a known provider gets filled in from orchestrator's table
    assert "press 2 for membership" in (task["brief"]["ivr_hint"] or "")


def test_instructions_for_task_roundtrip(monkeypatch):
    monkeypatch.setattr(orchestrator, "plan_call", _fake_brief)
    task = orchestrator.create_and_plan("Cancel my Iron Peak Fitness membership")
    instr = orchestrator.instructions_for_task(task)
    assert "OBJECTIVE: Cancel the Iron Peak Fitness membership." in instr
    assert "any retention offer" in instr


def test_summarize_and_persist_closes_out(monkeypatch):
    monkeypatch.setattr(orchestrator, "plan_call", _fake_brief)
    monkeypatch.setattr(orchestrator, "summarize_call", _fake_summary)
    task = orchestrator.create_and_plan("Cancel my Iron Peak Fitness membership")
    call = store.create_call(task["task_id"])
    transcript = [{"role": "agent", "text": "I'd like to cancel."},
                  {"role": "other", "text": "Your confirmation number is I P F 6 5 4 3 2 1."}]
    summary = orchestrator.summarize_and_persist(call["call_id"], task, transcript)

    assert summary["confirmation_number"] == "IPF654321"
    c = store.get_call(call["call_id"])
    assert c["status"] == "ended"
    assert c["confirmation_number"] == "IPF654321"
    assert c["summary"]["outcome_status"] == "cancelled"
    assert store.get_task(task["task_id"])["status"] == "done"
