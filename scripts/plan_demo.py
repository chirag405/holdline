"""Run the real Planner (Bedrock) on a plain-language request and print the Brief.

    python scripts/plan_demo.py "Cancel my Iron Peak Fitness gym membership, effective
        end of the month. Get a confirmation number. Don't accept a pause or discount."

Needs AWS creds + Bedrock access to TEXT_MODEL_ID. Writes a task row if
STATE_BACKEND=memory is not set it will try DynamoDB.
"""

from __future__ import annotations

import json
import sys

from holdline.orchestrator import create_and_plan, instructions_for_task


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    request = sys.argv[1]
    fields = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    task = create_and_plan(request, fields)
    print("=== TASK", task["task_id"], "===")
    print(json.dumps(task["brief"], indent=2))
    print("\n=== CALLER INSTRUCTIONS ===\n")
    print(instructions_for_task(task))
    return 0


if __name__ == "__main__":
    sys.exit(main())
