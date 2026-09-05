"""Offline Day 5 check: mid-call escalation (pause / ask / resume) and the
Supervisor loop -- no Nova, no Bedrock, no telephony.

    python scripts/verify_day5.py
"""

from __future__ import annotations

import asyncio
import os
import sys

os.environ.setdefault("STATE_BACKEND", "memory")
os.environ.setdefault("ESCALATION_TIMEOUT_S", "1")
os.environ.setdefault("SUPERVISOR_INTERVAL_S", "0.05")


def main() -> int:
    from holdline.config import get_settings

    get_settings.cache_clear()
    ok = True

    def check(label, coro):
        nonlocal ok
        try:
            asyncio.run(coro())
            print(f"  ok    {label}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  FAIL  {label}: {exc!r}")

    from holdline.session import CallSession

    class FakeAgent:
        def __init__(self):
            self.sent = []

        async def send(self, e):
            self.sent.append(getattr(e, "text", str(e)))

        async def stop(self):
            pass

    def sess(brief=None):
        s = CallSession(stream=object(), task={"task_id": None, "brief": brief}, call_id=None)
        s.agent = FakeAgent()
        return s

    print("escalation:")

    async def _resolve_path():
        s = sess()
        esc = asyncio.create_task(s.escalate("Accept 3 months half price?", ["hold firm", "accept"]))
        await asyncio.sleep(0.05)
        did = s.pending_list()[0]["decision_id"]
        assert s.resolve(did, "hold firm")
        assert await asyncio.wait_for(esc, 1) == "hold firm"
        assert s.escalations[0]["answer"] == "hold firm"

    check("caller escalates -> account holder answers -> answer returned", _resolve_path)

    async def _timeout_path():
        s = sess(brief={"default_on_timeout": "cancel regardless"})
        ans = await asyncio.wait_for(s.escalate("Accept?", ["hold firm"]), 2)
        assert "no response" in ans and "cancel regardless" in ans

    check("no answer in time -> falls back to the Brief default", _timeout_path)

    print("supervisor:")

    async def _supervisor_forces_it():
        from holdline import session as sm
        from holdline.models import SupervisorVerdict

        n = {"i": 0}

        def review(brief, transcript, prior):
            n["i"] += 1
            if n["i"] == 1:
                return SupervisorVerdict(verdict="escalate", question="Offer?", options=["hold firm"])
            return SupervisorVerdict(verdict="continue")

        import holdline.agents.supervisor as sup_mod

        sup_mod.review_call = review  # _supervise imports review_call from here

        s = sess()
        s.transcript.append({"role": "other", "text": "50% off if you stay?"})
        task = asyncio.create_task(sm._supervise(s))
        for _ in range(60):
            await asyncio.sleep(0.05)
            if s.pending_list():
                break
        assert s.pending_list(), "supervisor did not open an escalation"
        s.resolve(s.pending_list()[0]["decision_id"], "hold firm")
        await asyncio.sleep(0.1)
        s.ended = True
        task.cancel()
        assert s.escalations and s.escalations[0]["answer"] == "hold firm"
        assert any("hold" in m.lower() for m in s.agent.sent)

    check("supervisor 'escalate' verdict pauses the call and asks", _supervisor_forces_it)

    print("bridge routes:")

    def _routes():
        from fastapi.testclient import TestClient

        from holdline.telephony.bridge import app

        c = TestClient(app)
        assert c.get("/decisions").json() == {"pending": []}
        assert c.post("/decisions/nope", json={"answer": "x"}).status_code == 404

    try:
        _routes()
        print("  ok    /decisions and /decisions/{id} respond")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  FAIL  /decisions routes: {exc!r}")

    print()
    print("DAY 5 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
