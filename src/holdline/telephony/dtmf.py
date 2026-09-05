"""Synthesize DTMF (touch-tone) digits as mu-law 8k audio.

Twilio's Media Streams WebSocket only accepts `media` / `mark` / `clear` back --
there is no "send DTMF" message. To press an IVR menu key without tearing down
the stream (a REST call-update with `<Play digits>` would), we generate the
actual dual-tone signal and inject it as `media`.

Standard DTMF: each key is the sum of one low and one high sine tone.
"""

from __future__ import annotations

import audioop
import base64
import math

_ROW = {"1": 697, "2": 697, "3": 697, "A": 697,
        "4": 770, "5": 770, "6": 770, "B": 770,
        "7": 852, "8": 852, "9": 852, "C": 852,
        "*": 941, "0": 941, "#": 941, "D": 941}
_COL = {"1": 1209, "2": 1336, "3": 1477, "A": 1633,
        "4": 1209, "5": 1336, "6": 1477, "B": 1633,
        "7": 1209, "8": 1336, "9": 1477, "C": 1633,
        "*": 1209, "0": 1336, "#": 1477, "D": 1633}

RATE = 8000
_AMP = 8000  # per-tone amplitude; sum stays well under int16 clip

# Keys we will actually press. A-D are valid DTMF but omitted: they never appear
# in real IVR menus and would collide with letters in a dial string.
_PRESSABLE = frozenset("0123456789*#")


def _tone_pcm(digit: str, ms: int) -> bytes:
    lo, hi = _ROW[digit], _COL[digit]
    n = int(RATE * ms / 1000)
    out = bytearray()
    for i in range(n):
        t = i / RATE
        s = _AMP * math.sin(2 * math.pi * lo * t) + _AMP * math.sin(2 * math.pi * hi * t)
        v = max(-32768, min(32767, int(s)))
        out += int(v).to_bytes(2, "little", signed=True)
    return bytes(out)


def _silence_pcm(ms: int) -> bytes:
    return b"\x00\x00" * int(RATE * ms / 1000)


def digits_to_mulaw(digits: str, *, tone_ms: int = 200, gap_ms: int = 80) -> bytes:
    """Render a digit string (0-9 A-D * #) to raw mu-law 8k bytes.

    Non-DTMF chars are ignored; ',' or 'w' insert an extra 500 ms pause (common
    dial-string convention for "wait").
    """
    pcm = bytearray()
    for ch in digits:
        if ch in _PRESSABLE:
            pcm += _tone_pcm(ch, tone_ms)
            pcm += _silence_pcm(gap_ms)
        elif ch in (",", "w", "W"):
            pcm += _silence_pcm(500)
        # anything else (letters in a dial string, spaces, dashes) is ignored
    return audioop.lin2ulaw(bytes(pcm), 2)


def digits_to_mulaw_frames(
    digits: str, *, frame_ms: int = 20, **kw
) -> list[str]:
    """Same as `digits_to_mulaw` but chunked into base64 frames sized for Twilio
    `media` messages (20 ms of mu-law 8k = 160 bytes)."""
    mulaw = digits_to_mulaw(digits, **kw)
    step = int(RATE * frame_ms / 1000)  # bytes (1 byte/sample in mu-law)
    return [
        base64.b64encode(mulaw[i : i + step]).decode("ascii")
        for i in range(0, len(mulaw), step)
    ]


__all__ = ["RATE", "digits_to_mulaw", "digits_to_mulaw_frames"]
