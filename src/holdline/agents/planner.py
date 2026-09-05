"""Planner agent: plain-language request -> structured CallBrief.

Runs once, before the call. The Brief is what the Caller agent is briefed with and
what the Supervisor checks the live call against.
"""

from __future__ import annotations

import json

import structlog

from holdline.agents._model import text_agent
from holdline.models import CallBrief

log = structlog.get_logger("agents.planner")

_SYSTEM = """\
You turn a person's plain-language request to "handle this phone call for me" into
a precise Call Brief for an autonomous calling agent.

Principles:
- The objective is one concrete, checkable sentence.
- identity_info: only facts the person actually provided (name, account number,
  phone, email, last 4 of a card, date of birth). Never invent values.
- boundaries.may_agree_to: concessions a reasonable person would accept without
  being asked (e.g. "cancellation effective at the end of the current billing
  period", "email confirmation instead of a mailed letter").
- boundaries.must_escalate: anything that costs money, changes the deal, or is a
  judgment call the person should make -- ALWAYS include "any retention offer,
  discount, pause, downgrade, or plan change" for a cancellation.
- success_criteria: the observable things that mean the call worked (e.g. "the
  representative states the account is cancelled", "a confirmation or reference
  number is given").
- default_on_timeout: what the agent should do if it asks the person for a
  decision mid-call and gets no answer in time. Default to holding firm on the
  stated objective and refusing counter-offers.
- opening_line: a natural first sentence to a human, if useful. Otherwise "".
- ivr_hint: copy through any known menu path you are given; otherwise null.
"""


def plan_call(
    request_text: str,
    fields: dict[str, str] | None = None,
    *,
    ivr_hint: str | None = None,
) -> CallBrief:
    fields = fields or {}
    prompt = (
        f"REQUEST:\n{request_text}\n\n"
        f"FIELDS THE PERSON PROVIDED (may be empty):\n{json.dumps(fields, indent=2)}\n\n"
        f"KNOWN IVR PATH FOR THIS PROVIDER (may be empty):\n{ivr_hint or '(none)'}\n\n"
        "Produce the Call Brief."
    )
    brief: CallBrief = text_agent(_SYSTEM).structured_output(CallBrief, prompt)
    if ivr_hint and not brief.ivr_hint:
        brief.ivr_hint = ivr_hint
    log.info("planner.brief", provider=brief.provider_name, objective=brief.objective)
    return brief


__all__ = ["plan_call"]
