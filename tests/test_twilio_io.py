"""TwilioMediaStream adapts Twilio JSON <-> Strands bidi events correctly.

No network, no Nova model -- a fake websocket feeds frames in and captures frames out.
"""

import asyncio
import base64
import json

import pytest
from strands.experimental.bidi.types import events as ev

from holdline.telephony.twilio_io import TwilioMediaStream


class FakeWS:
    def __init__(self, incoming: list[dict]):
        self._in = asyncio.Queue()
        for m in incoming:
            self._in.put_nowait(json.dumps(m))
        self.sent: list[dict] = []

    async def receive_text(self) -> str:
        if self._in.empty():
            # emulate the socket going quiet then closing
            await asyncio.sleep(0.05)
            raise RuntimeError("closed")
        return await self._in.get()

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))


MULAW_20MS = base64.b64encode(b"\xff" * 160).decode()


@pytest.mark.asyncio
async def test_inbound_media_becomes_audio_input_event():
    ws = FakeWS(
        [
            {"event": "connected", "protocol": "Call"},
            {"event": "start", "streamSid": "MZ123", "start": {"callSid": "CA1"}},
            {"event": "media", "media": {"track": "inbound", "payload": MULAW_20MS}},
        ]
    )
    s = TwilioMediaStream(ws)
    s.start_reader()
    event = await asyncio.wait_for(s._next_input_event(), timeout=1)
    assert isinstance(event, ev.BidiAudioInputEvent)
    assert event["format"] == "pcm"
    assert event["sample_rate"] == 8000
    assert s.stream_sid == "MZ123"
    assert s.call_sid == "CA1"
    await s.aclose()


@pytest.mark.asyncio
async def test_agent_audio_becomes_twilio_media():
    ws = FakeWS([{"event": "start", "streamSid": "MZ9", "start": {"callSid": "CA9"}}])
    s = TwilioMediaStream(ws)
    s.start_reader()
    await asyncio.sleep(0.05)  # let reader consume `start`

    pcm = base64.b64encode(b"\x00\x10" * 160).decode()
    out = ev.BidiAudioStreamEvent(audio=pcm, format="pcm", sample_rate=8000, channels=1)
    await s._handle_output_event(out)

    media = [m for m in ws.sent if m.get("event") == "media"]
    assert media and media[0]["streamSid"] == "MZ9"
    assert base64.b64decode(media[0]["media"]["payload"])  # valid b64
    await s.aclose()


@pytest.mark.asyncio
async def test_interruption_sends_clear():
    ws = FakeWS([{"event": "start", "streamSid": "MZ7", "start": {"callSid": "CA7"}}])
    s = TwilioMediaStream(ws)
    s.start_reader()
    await asyncio.sleep(0.05)

    await s._handle_output_event(ev.BidiInterruptionEvent(reason="user_speech"))
    assert any(m.get("event") == "clear" and m["streamSid"] == "MZ7" for m in ws.sent)
    await s.aclose()


@pytest.mark.asyncio
async def test_transcript_callback_fires_on_final():
    seen = []
    ws = FakeWS([{"event": "start", "streamSid": "MZ5", "start": {"callSid": "CA5"}}])
    s = TwilioMediaStream(ws, on_transcript=lambda r, t, f: seen.append((r, t, f)))
    s.start_reader()
    await asyncio.sleep(0.05)

    from strands.types.streaming import ContentBlockDelta

    delta: ContentBlockDelta = {"text": "hello"}
    await s._handle_output_event(
        ev.BidiTranscriptStreamEvent(delta=delta, text="hello", role="assistant", is_final=True)
    )
    assert seen == [("assistant", "hello", True)]
    await s.aclose()
