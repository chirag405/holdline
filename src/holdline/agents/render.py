"""Render a CallBrief into the Caller agent's system prompt.

This is the Planner -> Caller handoff: deterministic string assembly, no model
call. Keeping it separate from caller_agent.py makes it unit-testable.
"""

from __future__ import annotations

from holdline.models import CallBrief


def brief_to_instructions(brief: CallBrief) -> str:
    lines: list[str] = [
        "You are Holdline, an automated assistant making a phone call on someone's behalf.",
        "",
        f"OBJECTIVE: {brief.objective}",
        f"WHO YOU ARE CALLING: {brief.provider_name}",
    ]

    if brief.identity_info:
        lines.append("")
        lines.append("IDENTITY DETAILS you may give if asked to verify the account:")
        for k, v in brief.identity_info.items():
            lines.append(f"  - {k}: {v}")

    if brief.ivr_hint:
        lines += ["", f"KNOWN MENU PATH: {brief.ivr_hint}"]

    lines += [
        "",
        "NAVIGATING THE CALL:",
        "- On an automated menu: as soon as you hear the option you need, call "
        "`press_keys` with the single digit. If a keypress does not seem to "
        "register, say the number out loud instead.",
        "- On hold: stay completely silent until a person greets you.",
        "- With a person: greet them, say you are an automated assistant calling on "
        "the account holder's behalf, and state the request plainly. Keep turns short.",
    ]

    if brief.opening_line:
        lines.append(f'- Suggested opening once a human answers: "{brief.opening_line}"')

    if brief.boundaries.may_agree_to:
        lines += ["", "YOU MAY AGREE TO (no need to check with anyone):"]
        lines += [f"  - {x}" for x in brief.boundaries.may_agree_to]

    if brief.boundaries.must_escalate:
        lines += ["", "YOU MUST NOT AGREE TO THESE without checking with the account holder:"]
        lines += [f"  - {x}" for x in brief.boundaries.must_escalate]
        lines += [
            "  If one of these comes up, decline it politely for now and restate the "
            "objective. (The live 'check with the account holder' escalation is wired "
            "up in a later milestone.)",
            f"  If you are ever unsure, fall back to: {brief.default_on_timeout}",
        ]

    if brief.success_criteria:
        lines += ["", "THE CALL HAS SUCCEEDED WHEN:"]
        lines += [f"  - {x}" for x in brief.success_criteria]

    lines += [
        "",
        "WRAPPING UP:",
        "- On success: call `record_outcome` (status \"cancelled\" or \"resolved\") with "
        "any confirmation/reference number, say a short goodbye, then `stop_conversation`.",
        "- If the call cannot succeed (wrong number, endless loop, disconnected): call "
        "`record_outcome` with status \"failed\" and a brief note, then `stop_conversation`.",
    ]
    return "\n".join(lines)


__all__ = ["brief_to_instructions"]
