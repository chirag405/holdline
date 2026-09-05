"""Day 1 spike: talk to the Holdline Caller agent through your laptop microphone.

No phone call, no Twilio — this proves the voice core works end to end:
Strands BidiAgent -> Amazon Nova 2 Sonic (speech-to-speech) -> tool calls,
with barge-in / interruption handled by the SDK.

Prereqs:
  - pip install -e ".[dev,mic]"
  - AWS credentials in the environment with Bedrock Nova 2 Sonic access in AWS_REGION
  - A working microphone + speakers

Run:
  python scripts/voice_spike.py

Then say something like:
  "Hi, I'm calling to cancel my gym membership."
Ask it to read back the plan, then say "okay, we're done here" to trigger end_call.
Press Ctrl+C any time to stop.
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
- When the cancellation is confirmed and you have a confirmation number, call the \
record_outcome tool, then call end_call.
- If you truly cannot proceed without a decision only Chirag can make, say so out loud \
(the escalation path is added in a later milestone; for this spike just narrate it).
"""


def _build_model():
    """Construct the Nova 2 Sonic bidirectional model, tolerating API drift."""
    from strands.experimental.bidi.models import BedrockNovaSonicModel

    s = get_settings()
    for kwargs in (
        {"model_id": s.nova_sonic_model_id, "region": s.aws_region, "voice_id": s.nova_sonic_voice},
        {"model_id": s.nova_sonic_model_id, "region_name": s.aws_region},
        {"model_id": s.nova_sonic_model_id},
        {},
    ):
        try:
            model = BedrockNovaSonicModel(**kwargs)
            log.info("nova_sonic.model_built", kwargs=list(kwargs))
            return model
        except TypeError as exc:  # unexpected kwarg -> try the next shape
            log.debug("nova_sonic.kwargs_rejected", kwargs=list(kwargs), error=str(exc))
    raise RuntimeError("Could not construct BedrockNovaSonicModel with any known signature.")


def _build_agent():
    from strands import tool
    from strands.experimental.bidi import BidiAgent

    stop = asyncio.Event()

    @tool
    def record_outcome(status: str, confirmation_number: str = "", notes: str = "") -> str:
        """Record the final result of the call.

        Args:
            status: one of "cancelled", "refused", "needs_human", "failed".
            confirmation_number: the cancellation/reference number if one was given.
            notes: anything the user should know.
        """
        log.info("tool.record_outcome", status=status, confirmation_number=confirmation_number, notes=notes)
        return "Outcome recorded."

    @tool
    def end_call(reason: str = "objective complete") -> str:
        """Hang up. Call this once the objective is done or the call cannot continue."""
        log.info("tool.end_call", reason=reason)
        stop.set()
        return "Call ended."

    agent = BidiAgent(
        model=_build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[record_outcome, end_call],
    )
    return agent, stop


async def main() -> int:
    from strands.experimental.bidi import BidiAudioIO

    agent, stop = _build_agent()
    audio_io = BidiAudioIO()

    log.info("voice_spike.start", hint="speak into your mic; Ctrl+C to quit")
    runner = asyncio.create_task(
        agent.run(inputs=[audio_io.input()], outputs=[audio_io.output()])
    )
    try:
        done, _ = await asyncio.wait(
            {runner, asyncio.create_task(stop.wait())},
            return_when=asyncio.FIRST_COMPLETED,
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        runner.cancel()
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
