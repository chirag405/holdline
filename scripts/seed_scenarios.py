"""Drive the three demo scenarios against the practice IVR, end to end.

Needs the full live stack: bridge running + tunnel + Twilio + AWS Bedrock, and
PRACTICE_IVR_NUMBER set (its Voice webhook pointed at <tunnel>/practice/entry).

    python scripts/seed_scenarios.py            # all three
    python scripts/seed_scenarios.py b          # just scenario b

  a  clean auto-cancel        -- agent declines the retention offer itself
  b  retention -> hold firm   -- you answer the escalation "hold firm"
  c  escalation -> accept     -- you answer "accept", agent keeps the membership
"""

from __future__ import annotations

import sys
import time

import httpx

from holdline.config import get_settings

S = get_settings()
BASE = f"http://{S.dashboard_host}:{S.dashboard_port}"

SCENARIOS = {
    "a": {
        "request": (
            "Cancel my Iron Peak Fitness membership, effective end of the billing "
            "period. Get a confirmation number. Do not accept a pause, downgrade, "
            "or any discount to stay."
        ),
        "answer": None,
    },
    "b": {
        "request": (
            "Cancel my Iron Peak Fitness membership and get a confirmation number. "
            "If they offer anything to keep me, ask me first."
        ),
        "answer": "Hold firm on the original request",
    },
    "c": {
        "request": (
            "Cancel my Iron Peak Fitness membership, but if they offer three months "
            "at half price or better, ask me before deciding."
        ),
        "answer": "Accept the offer",
    },
}


def run(key: str) -> None:
    sc = SCENARIOS[key]
    print(f"\n=== scenario {key} ===\n{sc['request']}")
    task = httpx.post(
        f"{BASE}/tasks",
        json={"request": sc["request"], "fields": {"account_number": "IPF-99123"}},
        timeout=60,
    ).json()
    print("brief:", task["brief"]["objective"], "| ivr_hint:", task["brief"]["ivr_hint"])

    placed = httpx.post(
        f"{BASE}/calls", json={"to": S.practice_ivr_number, "task_id": task["task_id"]}, timeout=60
    ).json()
    print("call:", placed)

    deadline = time.time() + 240
    answered = False
    while time.time() < deadline:
        time.sleep(3)
        pend = httpx.get(f"{BASE}/decisions", timeout=15).json().get("pending", [])
        if pend and sc["answer"] and not answered:
            d = pend[0]
            print(f"  decision: {d['question']}  -> answering: {sc['answer']!r}")
            httpx.post(f"{BASE}/decisions/{d['decision_id']}", json={"answer": sc["answer"]}, timeout=15)
            answered = True
        calls = httpx.get(f"{BASE}/calls", timeout=15).json()["calls"]
        mine = [c for c in calls if c["task_id"] == task["task_id"]]
        if mine and mine[0]["status"] in ("ended", "failed"):
            c = mine[0]
            print(f"  -> outcome={c['outcome']}  confirmation={c['confirmation_number']}")
            if c.get("summary"):
                print(f"     {c['summary'].get('summary')}")
            return
    print("  !! scenario did not finish in time")


def main() -> int:
    keys = sys.argv[1:] or ["a", "b", "c"]
    for k in keys:
        if k not in SCENARIOS:
            print(f"unknown scenario {k!r}")
            return 2
        run(k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
