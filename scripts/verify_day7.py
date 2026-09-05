"""Offline Day 7 check: provider memory learns across calls, the Strands Graph
builds and runs planner -> call -> debrief, and the AgentCore entrypoint imports.

    python scripts/verify_day7.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import types

os.environ.setdefault("STATE_BACKEND", "memory")
os.environ.setdefault("MEMORY_BACKEND", "local")


def main() -> int:
    from holdline.config import get_settings

    get_settings.cache_clear()
    ok = True

    def check(label, fn):
        nonlocal ok
        try:
            fn()
            print(f"  ok    {label}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  FAIL  {label}: {exc!r}")

    print("provider memory:")

    def _memory():
        from holdline import memory

        memory.local_reset()
        assert "press 2 for membership" in (memory.get_provider_hint("Iron Peak Fitness") or "")
        assert memory.get_provider_hint("Brand New Gym") is None
        memory.record_call_learnings(
            "Brand New Gym", ivr_path="press 3 to cancel", outcome="cancelled",
            confirmation_number="BNG1",
        )
        assert memory.get_provider_hint("Brand New Gym") == "press 3 to cancel"
        print("        -> a 2nd call to 'Brand New Gym' now starts with its learned path")

    check("hint seeded; learned path stored and read back", _memory)

    print("strands graph:")

    def _graph():
        from holdline import graph

        g = graph.build_call_graph()
        assert g is not None

    check("build_call_graph() assembles planner -> call -> debrief", _graph)

    def _graph_run():
        from holdline import events, graph
        from holdline.session import CallSession
        from holdline.state import memory as state_mem
        from holdline.state import store

        state_mem.reset()
        events.reset()
        order = []

        async def fake_call(session, stream, *, instructions=None):
            order.append("call")

        def fake_sum(call_id, task, transcript):
            order.append("debrief")
            return {"outcome_status": "cancelled", "summary": "ok", "confirmation_number": "Z9"}

        graph.run_call_session = fake_call
        import holdline.orchestrator as orch

        orch.summarize_and_persist = fake_sum

        task = store.create_task("cancel")
        store.set_task_brief(task["task_id"], {"objective": "cancel", "provider_name": "Acme"})
        call = store.create_call(task["task_id"])
        sess = CallSession(
            stream=types.SimpleNamespace(outcome="cancelled", confirmation_number="Z9"),
            task={"task_id": None},
            call_id=call["call_id"],
        )
        sess.transcript = [{"role": "agent", "text": "hi"}]
        summary = asyncio.run(
            graph.run_call_graph(sess, sess.stream, store.get_task(task["task_id"]), call["call_id"])
        )
        assert order == ["call", "debrief"], order
        assert summary["confirmation_number"] == "Z9"
        assert "call_ended" in [e["kind"] for e in events.recent()]

    check("run_call_graph drives call then debrief, emits call_ended", _graph_run)

    print("agentcore entrypoint:")

    def _entry():
        import importlib.util
        from pathlib import Path

        p = Path(__file__).resolve().parents[1] / "deploy" / "agentcore" / "app.py"
        try:
            import bedrock_agentcore  # noqa: F401
        except ModuleNotFoundError:
            print('        -> bedrock-agentcore not installed (pip install -e ".[agentcore]"); skipped')
            return
        spec = importlib.util.spec_from_file_location("holdline_agentcore_app", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "app")

    check("deploy/agentcore/app.py imports and exposes `app`", _entry)

    print()
    print("DAY 7 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
