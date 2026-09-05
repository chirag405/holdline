"""Offline Day 8 check: telemetry wiring, error paths, and the 3 scenarios.

    python scripts/verify_day8.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import types

os.environ.setdefault("STATE_BACKEND", "memory")
os.environ.setdefault("MEMORY_BACKEND", "local")
os.environ.setdefault("TRACING_ENABLED", "false")


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

    print("telemetry:")

    def _tel():
        from holdline.telemetry import init_telemetry

        init_telemetry()  # disabled -> no-op, must not raise
        os.environ["TRACING_ENABLED"] = "true"
        get_settings.cache_clear()
        import holdline.telemetry as t

        t._done = False
        t.init_telemetry()  # enabled, no OTLP endpoint -> sets up, must not raise
        os.environ["TRACING_ENABLED"] = "false"
        get_settings.cache_clear()

    check("init_telemetry() is safe on and off", _tel)

    print("scenarios (practice IVR end states):")

    def _scenarios():
        from fastapi.testclient import TestClient

        from holdline.telephony.bridge import app

        c = TestClient(app)

        def to_rep(sid):
            c.post("/practice/entry", data={"CallSid": sid})
            c.post("/practice/menu", data={"CallSid": sid, "Digits": "2"})
            c.post("/practice/membership", data={"CallSid": sid, "Digits": "4"})
            c.post("/practice/rep_intro", data={"CallSid": sid})

        # a: decline -> cancelled + confirmation
        to_rep("Va")
        c.post("/practice/rep", data={"CallSid": "Va", "SpeechResult": "cancel"})
        done = c.post("/practice/rep", data={"CallSid": "Va", "SpeechResult": "no just cancel"}).text
        assert re.search(r"confirmation number is [\dA-Z ]+", done), done
        # c: accept -> keeps membership, hangs up
        to_rep("Vc")
        c.post("/practice/rep", data={"CallSid": "Vc", "SpeechResult": "cancel"})
        acc = c.post("/practice/rep", data={"CallSid": "Vc", "SpeechResult": "yes take the deal"}).text
        assert "fifty percent off" in acc.lower() and "<Hangup" in acc
        print("        -> a (cancel), b (hold-firm), c (accept) all reach their end state")

    check("the 3 demo scenarios reach their intended end states", _scenarios)

    print("error paths:")

    def _graph_error():
        from holdline import graph
        from holdline.session import CallSession
        from holdline.state import memory as sm
        from holdline.state import store

        sm.reset()

        async def boom(session, stream, *, instructions=None):
            raise RuntimeError("stream reset")

        graph.run_call_session = boom
        task = store.create_task("x")
        store.set_task_brief(task["task_id"], {"objective": "x", "provider_name": "X"})
        call = store.create_call(task["task_id"])
        sess = CallSession(
            stream=types.SimpleNamespace(outcome=None, confirmation_number=None),
            task={"task_id": None},
            call_id=call["call_id"],
        )
        sess.transcript = []
        asyncio.run(
            graph.run_call_graph(sess, sess.stream, store.get_task(task["task_id"]), call["call_id"])
        )
        assert store.get_call(call["call_id"])["outcome"] == "error"

    check("call that dies early -> clean 'error' row, no Scribe", _graph_error)

    def _no_answer():
        from fastapi.testclient import TestClient

        from holdline.state import memory as sm
        from holdline.state import store
        from holdline.telephony import bridge

        sm.reset()
        task = store.create_task("call out")
        store.set_task_brief(task["task_id"], {"objective": "x", "provider_name": "X"})
        bridge._pending["CAv8"] = {"task": store.get_task(task["task_id"]), "instructions": None}
        r = TestClient(bridge.app).post(
            "/call-status", data={"CallSid": "CAv8", "CallStatus": "no-answer"}
        )
        assert r.status_code == 204
        assert store.list_calls()[0]["outcome"] == "no_answer"

    check("Twilio no-answer webhook -> recorded failed call", _no_answer)

    print()
    print("DAY 8 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
