"""Offline Day 3 check: the practice IVR runs end to end and the Caller agent
builds against it. No telephony, no AWS.

    python scripts/verify_day3.py
"""

from __future__ import annotations

import re
import sys


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

    print("practice IVR (simulated Twilio calls):")

    def _flow():
        from fastapi.testclient import TestClient

        from holdline.telephony.bridge import app

        c = TestClient(app)
        sid = "CAverify3"

        def post(path, **f):
            f.setdefault("CallSid", sid)
            r = c.post(path, data=f)
            assert r.status_code == 200, (path, r.text)
            return r.text

        assert "Iron Peak Fitness" in post("/practice/entry")
        assert "/practice/membership" in post("/practice/menu", Digits="2")
        held = post("/practice/membership", Digits="4")
        assert "<Play>" in held and "/practice/rep_intro" in held
        assert "member services" in post("/practice/rep_intro").lower()
        assert "fifty percent" in post("/practice/rep", SpeechResult="I would like to cancel").lower()
        done = post("/practice/rep", SpeechResult="no, just cancel please")
        m = re.search(r"confirmation number is ([\dA-Z ]+?)\.", done)
        assert m, done
        conf = m.group(1).replace(" ", "")
        assert conf.startswith("IPF") and len(conf) == 9
        print(f"        -> autonomous path reached confirmation number {conf}")

    check("dial -> menu(2) -> membership(4) -> hold -> rep -> confirmation #", _flow)

    print("caller agent:")

    def _agent():
        from holdline.telephony.caller_agent import build_caller_agent

        class FakeStream:
            call_sid = "CAx"

            async def send_dtmf(self, digits):
                self.pressed = digits

        agent = build_caller_agent(FakeStream())
        for t in ("press_keys", "record_outcome", "stop_conversation"):
            assert t in agent.tool_names, agent.tool_names

    check("build_caller_agent has press_keys / record_outcome / stop_conversation", _agent)

    print()
    print("DAY 3 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
