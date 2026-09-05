"""DTMF synthesis produces the right amount of audio in Twilio-sized frames."""

import base64

from holdline.telephony import dtmf


def test_single_digit_length():
    mulaw = dtmf.digits_to_mulaw("1", tone_ms=200, gap_ms=80)
    # 280 ms of mu-law 8k = ~2240 bytes (1 byte/sample)
    assert abs(len(mulaw) - int(dtmf.RATE * 0.280)) <= 4


def test_multi_digit_and_pause():
    plain = dtmf.digits_to_mulaw("42", tone_ms=100, gap_ms=50)
    withpause = dtmf.digits_to_mulaw("4,2", tone_ms=100, gap_ms=50)
    assert len(withpause) > len(plain)  # the ',' adds 500 ms


def test_frames_are_20ms_and_base64():
    frames = dtmf.digits_to_mulaw_frames("123", frame_ms=20)
    assert len(frames) >= 1
    for f in frames[:-1]:
        assert len(base64.b64decode(f)) == 160  # 20 ms * 8k * 1 byte


def test_ignores_non_dtmf_chars():
    assert dtmf.digits_to_mulaw("ab-9") == dtmf.digits_to_mulaw("9")
