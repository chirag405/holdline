"""Audio format conversion between Twilio and Nova Sonic.

Twilio Media Streams speak G.711 mu-law ("audio/x-mulaw"), 8 kHz, mono, base64.
Strands / Nova Sonic speak linear PCM 16-bit at 8k / 16k / 24k / 48k (no mu-law).

So the bridge does, per direction:
    Twilio  -> decode base64 -> mu-law 8k -> PCM16 8k -> (optional resample) -> Nova
    Nova    -> PCM16 @ rate -> (optional resample) -> PCM16 8k -> mu-law 8k -> base64 -> Twilio

We run Nova with input_rate = output_rate = 8000 so the common path needs no
resampling at all; `resample_pcm` is here for the fallback where a provider only
emits 16k/24k.

`audioop` is a CPython stdlib module (present through 3.12, removed in 3.13 — the
`audioop-lts` backport covers 3.13; see pyproject).
"""

from __future__ import annotations

import audioop
import base64

TWILIO_RATE = 8000
SAMPLE_WIDTH = 2  # 16-bit PCM
CHANNELS = 1


def mulaw_b64_to_pcm(payload_b64: str, *, target_rate: int = TWILIO_RATE) -> bytes:
    """Twilio inbound `media.payload` -> linear PCM16 bytes at `target_rate`."""
    mulaw = base64.b64decode(payload_b64)
    pcm8k = audioop.ulaw2lin(mulaw, SAMPLE_WIDTH)
    if target_rate == TWILIO_RATE:
        return pcm8k
    return resample_pcm(pcm8k, TWILIO_RATE, target_rate)


def pcm_to_mulaw_b64(pcm: bytes, *, source_rate: int = TWILIO_RATE) -> str:
    """Linear PCM16 bytes at `source_rate` -> base64 mu-law 8k for a Twilio `media` message."""
    if source_rate != TWILIO_RATE:
        pcm = resample_pcm(pcm, source_rate, TWILIO_RATE)
    mulaw = audioop.lin2ulaw(pcm, SAMPLE_WIDTH)
    return base64.b64encode(mulaw).decode("ascii")


_ratecv_state: dict[tuple[int, int], object] = {}


def resample_pcm(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample mono PCM16. Keeps per-(from,to) converter state so streamed
    chunks don't click at boundaries."""
    if from_rate == to_rate:
        return pcm
    key = (from_rate, to_rate)
    converted, _ratecv_state[key] = audioop.ratecv(
        pcm, SAMPLE_WIDTH, CHANNELS, from_rate, to_rate, _ratecv_state.get(key)
    )
    return converted


def reset_resample_state() -> None:
    """Call between calls so a new conversation starts clean."""
    _ratecv_state.clear()


__all__ = [
    "TWILIO_RATE",
    "mulaw_b64_to_pcm",
    "pcm_to_mulaw_b64",
    "resample_pcm",
    "reset_resample_state",
]
