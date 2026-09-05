"""Offline Day 2 check: the telephony bridge wires up without network/AWS/Twilio.

    python scripts/verify_day2.py
"""

from __future__ import annotations

import base64
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

    print("audio:")
    check(
        "mu-law->pcm->mu-law near identity",
        lambda: _assert_roundtrip(),
    )
    print("dtmf:")
    check(
        "digits -> 20ms base64 frames",
        lambda: _assert_frames(),
    )
    print("bridge app:")

    def _app():
        from holdline.telephony.bridge import app

        routes = {getattr(r, "path", None) for r in app.routes}
        for p in ("/health", "/calls", "/twiml", "/ts"):
            assert p in routes, f"missing route {p}"

    check("FastAPI app exposes /health /calls /twiml /ts", _app)

    def _twiml():
        from fastapi.testclient import TestClient

        from holdline.telephony.bridge import app

        c = TestClient(app)
        assert c.get("/health").json() == {"status": "ok"}
        body = c.get("/twiml").text
        assert "<Stream" in body and "Connect" in body

    check("GET /twiml renders <Connect><Stream>", _twiml)

    def _caller_importable():
        import holdline.telephony.caller_agent as m

        assert hasattr(m, "build_caller_agent")

    check("caller_agent.build_caller_agent importable", _caller_importable)

    print()
    print("DAY 2 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def _assert_roundtrip():
    from holdline.telephony import audio

    mulaw = bytes(range(256)) * 4
    pcm = audio.mulaw_b64_to_pcm(base64.b64encode(mulaw).decode())
    assert len(pcm) == len(mulaw) * 2
    re = base64.b64decode(audio.pcm_to_mulaw_b64(pcm))
    assert len(re) == len(mulaw)


def _assert_frames():
    from holdline.telephony import dtmf

    frames = dtmf.digits_to_mulaw_frames("1234", frame_ms=20)
    assert frames and len(base64.b64decode(frames[0])) == 160


if __name__ == "__main__":
    sys.exit(main())
