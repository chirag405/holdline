"""Offline Day 4 check: state backend, Planner->Caller render, Scribe persistence.

No AWS. The Planner/Scribe model calls are stubbed; set AWS creds and run
`python scripts/plan_demo.py "<request>"` for a real end-to-end plan.

    python scripts/verify_day4.py
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("STATE_BACKEND", "memory")


def main() -> int:
    ok = True

    def check(label, fn):
        nonlocal ok
        try:
            fn()
            print(f"  ok    {label}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  FAIL  {label}: {exc!r}")

    from holdline.config import get_settings

    get_settings.cache_clear()

    print("state (memory backend):")

    def _state():
        from holdline.state import memory, store

        memory.reset()
        task = store.create_task("cancel my gym", {"account": "IPF-1"})
        store.set_task_brief(task["task_id"], {"objective": "cancel"})
        call = store.create_call(task["task_id"])
        store.append_transcript(call["call_id"], "agent", "I'd like to cancel.")
        store.finish_call(call["call_id"], outcome="cancelled", confirmation_number="IPF111222")
        c = store.get_call(call["call_id"])
        assert c["status"] == "ended" and c["confirmation_number"] == "IPF111222"
        assert store.get_task(task["task_id"])["status"] == "briefed"

    check("tasks/calls/decisions round-trip via store facade", _state)

    print("planner -> caller render:")

    def _render():
        from holdline.agents.render import brief_to_instructions
        from holdline.models import Boundaries, CallBrief

        b = CallBrief(
            objective="Cancel the Iron Peak Fitness membership.",
            provider_name="Iron Peak Fitness",
            identity_info={"account_number": "IPF-99"},
            boundaries=Boundaries(must_escalate=["any retention offer or discount"]),
            success_criteria=["a confirmation number is given"],
            ivr_hint="press 2 then 4",
        )
        instr = brief_to_instructions(b)
        for needle in ("OBJECTIVE:", "IPF-99", "press 2 then 4", "any retention offer", "press_keys"):
            assert needle in instr, needle

    check("CallBrief renders to a complete Caller prompt", _render)

    print("scribe persistence (stubbed model):")

    def _scribe():
        from holdline import orchestrator
        from holdline.models import CallSummary
        from holdline.state import memory, store

        memory.reset()
        orchestrator.plan_call = lambda *a, **k: _dummy_brief()
        orchestrator.summarize_call = lambda brief, tr: CallSummary(
            outcome_status="cancelled", summary="done", confirmation_number="IPF999000"
        )
        task = orchestrator.create_and_plan("Cancel my Iron Peak Fitness membership")
        call = store.create_call(task["task_id"])
        out = orchestrator.summarize_and_persist(call["call_id"], task, [{"role": "agent", "text": "hi"}])
        assert out["confirmation_number"] == "IPF999000"
        assert store.get_call(call["call_id"])["status"] == "ended"
        assert store.get_task(task["task_id"])["status"] == "done"

    check("summarize_and_persist writes the call row and closes the task", _scribe)

    print("bridge routes:")

    def _routes():
        from fastapi.testclient import TestClient

        from holdline.telephony.bridge import app

        paths = {getattr(r, "path", None) for r in app.routes}
        for p in ("/tasks", "/calls", "/twiml", "/ts"):
            assert p in paths, p
        # included routers aren't flattened into app.routes on this FastAPI
        # version -- check the practice IVR by actually calling it
        c = TestClient(app)
        assert c.post("/practice/entry", data={"CallSid": "verify"}).status_code == 200

    check("app exposes /tasks /calls /twiml /ts and /practice/* responds", _routes)

    print()
    print("DAY 4 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _dummy_brief():
    from holdline.models import CallBrief

    return CallBrief(objective="Cancel it.", provider_name="Iron Peak Fitness")


if __name__ == "__main__":
    sys.exit(main())
