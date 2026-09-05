"""Supervisor agent: watch the live call transcript against the Call Brief.

Runs every few seconds during the call (in a worker thread so it never blocks the
audio loop). Returns one of:
  - continue : nothing to do
  - escalate : a must-not-decide situation is on the table; ask the account holder
  - abort    : the call cannot succeed (disconnected, stuck in a loop, wrong dept)

It is a safety net. The Caller is also told to call `escalate_to_user` itself; the
Supervisor exists for when the model under pressure forgets to.
"""

from __future__ import annotations

import json

import structlog

from holdline.agents._model import text_agent
from holdline.models import SupervisorVerdict

log = structlog.get_logger("agents.supervisor")

_SYSTEM = """\
You supervise an autonomous agent ("the Caller") that is on a phone call handling
a task for someone. You see the Call Brief and the transcript so far. Decide what
should happen next.

Return verdict:
- "escalate" ONLY when the other party has put something on the table that the
  Brief says must NOT be decided by the Caller (a retention offer, discount, fee,
  pause, plan change, refund amount, contract extension, etc.) AND the Caller has
  not already escalated that same point. Provide `question` (a crisp yes/no or
  choose-one for the account holder) and `options` (2-4 short choices, first =
  the safe default of holding firm).
- "abort" when the call clearly cannot succeed: the line dropped, you have been
  transferred in circles, the number is wrong, or the same exchange has repeated
  many times with no progress. Put the reason in `reason`.
- "continue" otherwise. When in doubt, continue -- do not escalate routine back
  and forth, identity checks, or the Caller simply being asked to hold.

Never escalate the same issue twice. If `prior_escalations` already covers what
you are seeing, return "continue".
"""


def review_call(
    brief: dict | None,
    transcript: list[dict],
    prior_escalations: list[dict] | None = None,
) -> SupervisorVerdict:
    recent = transcript[-14:]
    lines = "\n".join(f"{t.get('role', '?')}: {t.get('text', '')}" for t in recent) or "(silence)"
    must_escalate = (brief or {}).get("boundaries", {}).get("must_escalate", [])
    prompt = (
        f"CALL BRIEF:\n{json.dumps(_slim_brief(brief), indent=2)}\n\n"
        f"MUST NOT BE DECIDED BY THE CALLER:\n{json.dumps(must_escalate, indent=2)}\n\n"
        f"ESCALATIONS ALREADY MADE THIS CALL:\n{json.dumps(prior_escalations or [], indent=2)}\n\n"
        f"TRANSCRIPT (most recent last):\n{lines}\n\n"
        "Your verdict:"
    )
    try:
        verdict: SupervisorVerdict = text_agent(_SYSTEM).structured_output(SupervisorVerdict, prompt)
    except Exception as exc:  # noqa: BLE001 - a supervisor hiccup must not end the call
        log.warning("supervisor.error", error=str(exc))
        return SupervisorVerdict(verdict="continue", reason=f"supervisor error: {exc}")
    log.info("supervisor.verdict", verdict=verdict.verdict, reason=verdict.reason)
    return verdict


def _slim_brief(brief: dict | None) -> dict:
    if not brief:
        return {}
    return {
        "objective": brief.get("objective"),
        "provider_name": brief.get("provider_name"),
        "success_criteria": brief.get("success_criteria", []),
        "default_on_timeout": brief.get("default_on_timeout"),
    }


__all__ = ["review_call"]
