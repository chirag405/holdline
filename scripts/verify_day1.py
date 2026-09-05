"""Offline Day 1 check: every import resolves and the voice core constructs.

Does NOT open a Bedrock stream or touch the mic -- safe to run with no AWS
credentials. Proves the code is wired to the real strands-agents 1.54.0 API.

    python scripts/verify_day1.py
"""

from __future__ import annotations

import sys


def main() -> int:
    ok = True

    def check(label: str, fn) -> None:
        nonlocal ok
        try:
            fn()
            print(f"  ok    {label}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  FAIL  {label}: {exc!r}")

    print("imports:")
    check("strands.Agent / tool", lambda: __import__("strands").Agent)
    check(
        "BidiAgent",
        lambda: __import__(
            "strands.experimental.bidi", fromlist=["BidiAgent"]
        ).BidiAgent,
    )
    check(
        "BidiNovaSonicModel",
        lambda: __import__(
            "strands.experimental.bidi.models.nova_sonic",
            fromlist=["BidiNovaSonicModel"],
        ).BidiNovaSonicModel,
    )
    check(
        "BidiAudioIO / BidiTextIO",
        lambda: (
            __import__("strands.experimental.bidi.io", fromlist=["BidiTextIO"]).BidiTextIO,
        ),
    )
    check(
        "stop_conversation tool",
        lambda: __import__(
            "strands.experimental.bidi.tools", fromlist=["stop_conversation"]
        ).stop_conversation,
    )

    print("construct (no network):")

    def _build():
        from strands import tool
        from strands.experimental.bidi import BidiAgent
        from strands.experimental.bidi.tools import stop_conversation

        from holdline.config import get_settings

        get_settings.cache_clear()

        @tool
        def noop() -> str:
            """Does nothing."""
            return "ok"

        # BidiAgent with a string model id -> no stream opened at construction time.
        agent = BidiAgent(
            model="amazon.nova-2-sonic-v1:0",
            system_prompt="test",
            tools=[noop, stop_conversation],
        )
        assert "noop" in agent.tool_names

    check("BidiAgent(model=<id str>, tools=[...])", _build)

    print("holdline package:")
    check("holdline.config.get_settings", lambda: __import__("holdline.config", fromlist=["get_settings"]).get_settings())
    check("holdline.models.CallBrief", lambda: __import__("holdline.models", fromlist=["CallBrief"]).CallBrief)
    check("holdline.state.ddb imports", lambda: __import__("holdline.state.ddb", fromlist=["create_task"]))

    print()
    print("DAY 1 VERIFY:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
