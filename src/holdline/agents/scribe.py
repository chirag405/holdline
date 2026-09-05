"""Scribe agent: call transcript -> structured CallSummary.

Runs once, after the call. Produces the plain-English summary, pulls out the
confirmation number, and drafts a follow-up if the rep promised something.
"""

from __future__ import annotations

import structlog

from holdline.agents._model import text_agent
from holdline.models import CallBrief, CallSummary

log = structlog.get_logger("agents.scribe")

_SYSTEM = """\
You write a short, factual after-action summary of a phone call an automated
assistant just made on someone's behalf.

- outcome_status: cancelled | refused | needs_human | failed | partial. Base it
  strictly on what the transcript shows the representative actually said.
- summary: 2-4 sentences, plain language, no fluff. What was asked, what happened,
  where it landed.
- confirmation_number: the exact reference/confirmation number the rep gave, with
  no spaces or filler words. "" if none was given.
- follow_up_draft: if the rep promised a future action (a refund will post, a
  letter will be mailed, a callback), a 2-3 sentence email the account holder
  could send to confirm it later. Otherwise "".
- follow_up_date: ISO date (YYYY-MM-DD) by which the follow-up should happen, if
  one is implied. Otherwise "".
- learned_ivr_path: if the transcript reveals the phone-menu path taken (e.g.
  "pressed 2 then 4"), state it briefly so a future call can reuse it. Otherwise "".
"""


def summarize_call(brief: CallBrief, transcript: list[dict] | list[tuple[str, str]]) -> CallSummary:
    lines = []
    for seg in transcript:
        if isinstance(seg, dict):
            lines.append(f"{seg.get('role', '?')}: {seg.get('text', '')}")
        else:
            lines.append(f"{seg[0]}: {seg[1]}")
    body = "\n".join(lines) or "(no transcript captured)"
    prompt = (
        f"CALL OBJECTIVE: {brief.objective}\n"
        f"PROVIDER: {brief.provider_name}\n\n"
        f"TRANSCRIPT (role: text):\n{body}\n\n"
        "Write the summary."
    )
    summary: CallSummary = text_agent(_SYSTEM).structured_output(CallSummary, prompt)
    summary.confirmation_number = summary.confirmation_number.replace(" ", "")
    log.info(
        "scribe.summary",
        outcome=summary.outcome_status,
        confirmation_number=summary.confirmation_number,
    )
    return summary


__all__ = ["summarize_call"]
