"""Trigger an outbound test call through a running bridge.

    python scripts/place_call.py +1YOURCELL ["optional goal override"]

Requires the bridge running (scripts/run_bridge.py) and reachable at
DASHBOARD_HOST:DASHBOARD_PORT, plus Twilio + PUBLIC_WS_URL configured in .env.
"""

from __future__ import annotations

import sys

import httpx

from holdline.config import get_settings


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    to = sys.argv[1]
    goal = sys.argv[2] if len(sys.argv) > 2 else None
    s = get_settings()
    url = f"http://{s.dashboard_host}:{s.dashboard_port}/calls"
    payload = {"to": to}
    if goal:
        payload["goal"] = goal
    r = httpx.post(url, json=payload, timeout=30)
    print(r.status_code, r.text)
    return 0 if r.status_code < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
