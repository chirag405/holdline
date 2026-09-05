"""Build the Caller: a BidiAgent (Nova 2 Sonic) that runs one live phone call.

Day 2 uses a hardcoded goal so the bridge can be exercised end to end. Day 4
swaps the hardcoded prompt for one rendered from a `CallBrief`, and Day 5 adds
the real `escalate_to_user` tool + Supervisor.
"""

from __future__ import annotations

from typing import Any

import structlog

from holdline.config import get_settings

log = structlog.get_logger("telephony.caller_agent")

_DAY2_GOAL = """\
You are Holdline, an automated assistant on a phone call on behalf of Chirag.

Goal: cancel Chirag's membership at Iron Peak Fitness, effective at the end of the
current billing period, and get a cancellation confirmation number.

How to behave on the call:
- You are talking to an automated menu (IVR) first. Listen to the options. When
  you know which key to press, call the `press_keys` tool with the digits -- do
  NOT say the digits out loud.
- When you reach a hold queue, wait quietly. Say nothing until a person speaks.
- With a person: state who you are (an automated assistant for Chirag) if asked,
  then make the cancellation request. Keep turns short and natural.
- You may accept: cancellation effective at the end of the billing period.
- You may NOT accept: a pause, a downgrade, a discount to stay, or a new plan. If
  pushed, decline once and restate that you want to cancel. (The real
  "check with Chirag" escalation path is added in a later milestone.)
- When cancellation is confirmed and you have a reference/confirmation number,
  call `record_outcome`, say a brief goodbye, then call `stop_conversation`.
"""


def build_caller_agent(stream: Any, *, instructions: str | None = None) -> Any:
    """Create the per-call BidiAgent. `stream` is the live TwilioMediaStream so
    the DTMF tool can inject tones into it."""
    from strands import tool
    from strands.experimental.bidi import BidiAgent
    from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel
    from strands.experimental.bidi.tools import stop_conversation

    s = get_settings()

    @tool
    async def press_keys(digits: str) -> str:
        """Press keys on the phone keypad (DTMF). Use for IVR menus and entering
        account or phone numbers. `digits` may contain 0-9 * # and ',' for a pause."""
        await stream.send_dtmf(digits)
        return f"Pressed {digits}."

    @tool
    def record_outcome(status: str, confirmation_number: str = "", notes: str = "") -> str:
        """Record the final result of the call.

        Args:
            status: "cancelled" | "refused" | "needs_human" | "failed"
            confirmation_number: reference number the rep gave, if any.
            notes: anything the user should know.
        """
        log.info(
            "tool.record_outcome",
            call_sid=getattr(stream, "call_sid", None),
            status=status,
            confirmation_number=confirmation_number,
            notes=notes,
        )
        return "Recorded."

    model = BidiNovaSonicModel(
        model_id=s.nova_sonic_model_id,
        client_config={"region": s.aws_region},
        provider_config={
            "audio": {"input_rate": 8000, "output_rate": 8000, "voice": s.nova_sonic_voice}
        },
    )
    return BidiAgent(
        model=model,
        system_prompt=instructions or _DAY2_GOAL,
        tools=[press_keys, record_outcome, stop_conversation],
    )


__all__ = ["build_caller_agent"]
