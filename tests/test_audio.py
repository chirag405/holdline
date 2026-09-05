"""mu-law <-> PCM conversion and resampling behave sanely."""

import base64

from holdline.telephony import audio


def test_mulaw_pcm_roundtrip_is_close():
    # 20 ms of mu-law 8k silence-ish + a ramp
    mulaw = bytes(range(256)) * 4  # 1024 samples
    b64 = base64.b64encode(mulaw).decode()
    pcm = audio.mulaw_b64_to_pcm(b64)
    assert len(pcm) == len(mulaw) * 2  # 16-bit
    back = audio.pcm_to_mulaw_b64(pcm)
    # mu-law is lossy but re-encoding the decoded signal is near-identity
    re = base64.b64decode(back)
    assert len(re) == len(mulaw)
    diff = sum(abs(a - b) for a, b in zip(mulaw, re))
    assert diff / len(mulaw) < 2.0


def test_resample_8k_to_16k_doubles_length():
    audio.reset_resample_state()
    pcm8k = b"\x00\x01" * 800  # 800 samples @ 8k = 100 ms
    pcm16k = audio.resample_pcm(pcm8k, 8000, 16000)
    # ~2x samples (ratecv may be off by a few at the edge)
    assert abs(len(pcm16k) - len(pcm8k) * 2) <= 8


def test_resample_noop_same_rate():
    data = b"\x10\x20" * 100
    assert audio.resample_pcm(data, 8000, 8000) == data


def test_pcm_to_mulaw_downsamples_when_needed():
    audio.reset_resample_state()
    pcm24k = b"\x00\x08" * 2400  # 100 ms @ 24k
    b64 = audio.pcm_to_mulaw_b64(pcm24k, source_rate=24000)
    out = base64.b64decode(b64)
    assert abs(len(out) - 800) <= 8  # 100 ms of mu-law 8k
