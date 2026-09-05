"""Shared data shapes: the Call Brief the Planner produces and the Supervisor verdict.

These are plain pydantic models so they can be used as Strands structured-output
schemas and serialized straight into DynamoDB.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Boundaries(BaseModel):
    """What the Caller may settle on its own vs. what must come back to the user."""

    may_agree_to: list[str] = Field(
        default_factory=list,
        description="Concessions the agent is allowed to accept without asking, "
        "e.g. 'cancellation effective at end of billing period'.",
    )
    must_escalate: list[str] = Field(
        default_factory=list,
        description="Situations that require the user's decision, e.g. 'any "
        "retention or discount counter-offer', 'early-termination fee over $0', "
        "'change to a different plan'.",
    )


class CallBrief(BaseModel):
    """Everything the Caller agent needs to run one call. Produced by the Planner."""

    objective: str = Field(description="One sentence: what a successful call achieves.")
    provider_name: str = Field(description="Company being called, as the user named it.")
    identity_info: dict[str, str] = Field(
        default_factory=dict,
        description="Facts the rep may ask to verify identity: name, account number, "
        "phone, email, DOB, last 4 of card. Only what the user supplied.",
    )
    boundaries: Boundaries = Field(default_factory=Boundaries)
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Concrete checks, e.g. 'rep states the membership is cancelled', "
        "'a confirmation or reference number is provided'.",
    )
    ivr_hint: str | None = Field(
        default=None,
        description="Known menu path for this provider, from memory of past calls. "
        "Free text, e.g. \"press 2 for membership, then 4 to cancel\".",
    )
    default_on_timeout: str = Field(
        default="hold firm on the original objective and do not accept any counter-offer",
        description="What the Caller should do if an escalation to the user times out.",
    )
    opening_line: str = Field(
        default="",
        description="Optional first thing to say once a human is reached.",
    )


Verdict = Literal["continue", "escalate", "abort"]


class SupervisorVerdict(BaseModel):
    """The Supervisor's read of the live call, produced every few seconds."""

    verdict: Verdict = "continue"
    reason: str = ""
    # Populated only when verdict == "escalate"
    question: str = ""
    options: list[str] = Field(default_factory=list)


class CallSummary(BaseModel):
    """The Scribe's post-call output."""

    outcome_status: Literal["cancelled", "refused", "needs_human", "failed", "partial"]
    summary: str
    confirmation_number: str = ""
    follow_up_draft: str = ""
    follow_up_date: str = ""  # ISO date or "" if none
    learned_ivr_path: str = ""  # written back to provider memory


__all__ = [
    "Boundaries",
    "CallBrief",
    "CallSummary",
    "SupervisorVerdict",
    "Verdict",
]
