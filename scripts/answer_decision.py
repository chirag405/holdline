"""List and answer mid-call escalations from the terminal (stand-in for the
Day 6 dashboard).

    python scripts/answer_decision.py                       # list pending
    python scripts/answer_decision.py <decision_id> "hold firm"
"""

from __future__ import annotations

import sys

import httpx

from holdline.config import get_settings


def _base() -> str:
    s = get_settings()
    return f"http://{s.dashboard_host}:{s.dashboard_port}"


def main() -> int:
    if len(sys.argv) == 1:
        r = httpx.get(f"{_base()}/decisions", timeout=10)
        pend = r.json().get("pending", [])
        if not pend:
            print("(no pending decisions)")
            return 0
        for p in pend:
            print(f"\n{p['decision_id']}")
            print(f"  Q: {p['question']}")
            print(f"  options: {p['options']}")
        return 0

    decision_id, answer = sys.argv[1], " ".join(sys.argv[2:]) or "hold firm"
    r = httpx.post(f"{_base()}/decisions/{decision_id}", json={"answer": answer}, timeout=10)
    print(r.status_code, r.text)
    return 0 if r.status_code < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
