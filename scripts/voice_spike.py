"""Day 1 spike: talk to the Holdline Caller agent through your laptop microphone.

No phone call, no Twilio -- this proves the voice core works end to end:
Strands BidiAgent -> Amazon Nova 2 Sonic (speech-to-speech) -> tool calls,
with barge-in / interruption handled by the SDK.

Prereqs:
  - pip install -e ".[dev,mic]"   (mic extra pulls PyAudio; PortAudio ships in the
    Windows wheel, so no separate install needed there)
  - AWS credentials in the environment with Bedrock Nova 2 Sonic access in AWS_REGION
  - A working microphone + speakers (a headset avoids the model hearing itself)

Run:
  python scripts/voice_spike.py

Say something like: "Hi, I'm calling to cancel my gym membership."
Ask it to read back the plan. Say "okay, we're done here" to make it wrap up.
Press Ctrl+C any time to stop.

API verified against strands-agents 1.54.0.
"""

from __future__ import annotations

import asyncio
import sys

import structlog

from holdline.config import get_settings

log = structlog.get_logger("voice_spike")

SYSTEM_PROMPT = """\
You are Holdline, an automated assistant placing a phone call on behalf of your \
user, Chirag. Your goal on this call: cancel Chirag's gym membership at \
Iron Peak Fitness, effective at the end of the current billing month, and obtain \
a cancellation confirmation number.

Hard rules:
- You may NOT accept a membership pause, a downgrade, or a discounted "stay" offer. \
If the other party pushes one, politely decline and restate that you want to cancel.
- If asked, state clearly that you are an automated assistant calling on Chirag's behalf.
- Keep turns short and natural, like a calm person on the phone.
- When the cancellation is confirmed and you have a confirmation number, call \
record_outcome, say a brief goodbye, then call stop_conversation.
- If you truly cannot proceed without a decision only Chirag can make, say so out loud \
(the real escalation path is added in a later milestone; for this spike just narrate it).
"""


def build_model():
    """Construct the Nova 2 Sonic bidirectional model (strands 1.54.0 API)."""
    from strands.experimental.bidi.models.nova_sonic import BidiNovaSonicModel

    s = get_settings()
    model = BidiNovaSonicModel(
        model_id=s.nova_sonic_model_id,
        client_config={"region": s.aws_region},
        provider_config={"audio": {"voice": s.nova_sonic_voice}},
    )
    log.info("nova_sonic.model_built", model_id=s.nova_sonic_model_id, region=s.aws_region)
    return model


def build_agent():
    from strands import tool
    from strands.experimental.bidi import BidiAgent
    from strands.experimental.bidi.tools import stop_conversation

    @tool
    def record_outcome(status: str, confirmation_number: str = "", notes: str = "") -> str:
        """Record the final result of the call.

        Args:
            status: one of "cancelled", "refused", "needs_human", "failed".
            confirmation_number: the cancellation/reference number if one was given.
            notes: anything the user should know.
        """
        log.info(
            "tool.record_outcome",
            status=status,
            confirmation_number=confirmation_number,
            notes=notes,
        )
        return "Outcome recorded."

    return BidiAgent(
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[record_outcome, stop_conversation],
    )


async def main() -> int:
    from strands.experimental.bidi.io import BidiAudioIO, BidiTextIO

    agent = build_agent()
    audio_io = BidiAudioIO()
    text_io = BidiTextIO()

    log.info("voice_spike.start", hint="speak into your mic; Ctrl+C to quit")
    try:
        await agent.run(
            inputs=[audio_io.input()],
            outputs=[audio_io.output(), text_io.output()],
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        try:
            await agent.stop()
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            log.warning("voice_spike.stop_error", error=str(exc))
    log.info("voice_spike.done")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
