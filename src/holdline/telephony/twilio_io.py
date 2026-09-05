"""Adapt a Twilio Media Streams WebSocket to Strands BidiInput / BidiOutput.

One `TwilioMediaStream` wraps the live call socket. `.input()` yields the caller's
audio to the agent as PCM16/8k events; `.output()` takes the agent's audio/tool/
transcript events and turns agent speech into Twilio `media` frames, interruptions
into `clear`, and transcript deltas into a callback.

Twilio -> server messages: connected | start | media | dtmf | mark | stop
server -> Twilio messages:  media | mark | clear
    https://www.twilio.com/docs/voice/media-streams/websocket-messages
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from holdline.telephony.audio import (
    mulaw_b64_to_pcm,
    pcm_to_mulaw_b64,
    reset_resample_state,
)
from holdline.telephony.dtmf import digits_to_mulaw_frames

log = structlog.get_logger("telephony.twilio_io")

# Lazy imports of the Strands event classes so importing this module is cheap.
_ev: Any = None


def _events():
    global _ev
    if _ev is None:
        from strands.experimental.bidi.types import events as _ev  # type: ignore
    return _ev


TranscriptCb = Callable[[str, str, bool], None]  # (role, text, is_final)


class TwilioMediaStream:
    def __init__(self, websocket: Any, *, on_transcript: TranscriptCb | None = None) -> None:
        self._ws = websocket
        self._on_transcript = on_transcript or (lambda r, t, f: None)
        self._inbound: asyncio.Queue[Any] = asyncio.Queue(maxsize=200)
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.caller_dtmf: list[str] = []
        self._closed = asyncio.Event()
        self._reader: asyncio.Task | None = None
        reset_resample_state()

    # -- lifecycle -------------------------------------------------------- #
    def start_reader(self) -> None:
        self._reader = asyncio.create_task(self._read_loop(), name="twilio-reader")

    def set_transcript_cb(self, cb: TranscriptCb) -> None:
        """Swap the transcript sink after construction (the session isn't built
        until the call_sid arrives)."""
        self._on_transcript = cb

    @property
    def closed(self) -> asyncio.Event:
        return self._closed

    async def aclose(self) -> None:
        self._closed.set()
        if self._reader:
            self._reader.cancel()

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self._ws.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")
                if event == "start":
                    start = msg.get("start", {})
                    self.stream_sid = msg.get("streamSid") or start.get("streamSid")
                    self.call_sid = start.get("callSid")
                    log.info("twilio.start", stream_sid=self.stream_sid, call_sid=self.call_sid)
                elif event == "media":
                    m = msg["media"]
                    if m.get("track", "inbound") != "inbound":
                        continue
                    pcm = mulaw_b64_to_pcm(m["payload"], target_rate=8000)
                    ai = _events().BidiAudioInputEvent(
                        audio=base64.b64encode(pcm).decode("ascii"),
                        format="pcm",
                        sample_rate=8000,
                        channels=1,
                    )
                    if self._inbound.full():
                        _ = self._inbound.get_nowait()  # drop oldest, stay real-time
                    self._inbound.put_nowait(ai)
                elif event == "dtmf":
                    digit = msg.get("dtmf", {}).get("digit", "")
                    self.caller_dtmf.append(digit)
                    log.info("twilio.caller_dtmf", digit=digit)
                elif event == "mark":
                    pass
                elif event in ("stop", "closed"):
                    log.info("twilio.stop")
                    break
                elif event == "connected":
                    log.info("twilio.connected", protocol=msg.get("protocol"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - socket closed / malformed frame
            log.info("twilio.read_loop_end", error=str(exc))
        finally:
            self._closed.set()

    # -- BidiInput ------------------------------------------------------- #
    def input(self) -> _Input:
        return _Input(self)

    async def _next_input_event(self) -> Any:
        getter = asyncio.create_task(self._inbound.get())
        done, _ = await asyncio.wait(
            {getter, asyncio.create_task(self._closed.wait())},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if getter in done:
            return getter.result()
        getter.cancel()
        raise _StreamClosed

    # -- BidiOutput ---------------------------------------------------- #
    def output(self) -> _Output:
        return _Output(self)

    async def _handle_output_event(self, event: Any) -> None:
        e = _events()
        if isinstance(event, e.BidiAudioStreamEvent):
            await self._send_agent_audio(event)
        elif isinstance(event, e.BidiInterruptionEvent):
            await self._send_clear()
        elif isinstance(event, e.BidiTranscriptStreamEvent):
            self._on_transcript(event.role, event.text, event.is_final)

    async def _send_agent_audio(self, event: Any) -> None:
        if not self.stream_sid:
            return
        pcm = base64.b64decode(event.audio)
        payload_b64 = pcm_to_mulaw_b64(pcm, source_rate=int(event.sample_rate))
        await self._ws.send_text(
            json.dumps(
                {"event": "media", "streamSid": self.stream_sid, "media": {"payload": payload_b64}}
            )
        )

    async def _send_clear(self) -> None:
        if not self.stream_sid:
            return
        await self._ws.send_text(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
        log.info("twilio.clear_sent")

    async def send_dtmf(self, digits: str) -> bool:
        """Inject touch-tones into the call as audio (keeps the stream alive).
        Returns False if the stream isn't ready yet."""
        if not self.stream_sid:
            log.warning("twilio.send_dtmf_no_stream", digits=digits)
            return False
        try:
            for frame_b64 in digits_to_mulaw_frames(digits):
                await self._ws.send_text(
                    json.dumps(
                        {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": frame_b64},
                        }
                    )
                )
                await asyncio.sleep(0.02)
        except Exception as exc:  # noqa: BLE001 - socket may have closed mid-send
            log.warning("twilio.dtmf_send_failed", digits=digits, error=str(exc))
            return False
        log.info("twilio.dtmf_sent", digits=digits)
        return True


class _StreamClosed(Exception):
    pass


class _Input:
    """Strands BidiInput: an awaitable that returns the next caller-audio event."""

    def __init__(self, parent: TwilioMediaStream) -> None:
        self._p = parent

    async def start(self, agent: Any) -> None:
        return

    async def stop(self) -> None:
        return

    def __call__(self) -> Awaitable[Any]:
        return self._p._next_input_event()


class _Output:
    """Strands BidiOutput: receives agent events, drives the Twilio socket."""

    def __init__(self, parent: TwilioMediaStream) -> None:
        self._p = parent

    async def start(self, agent: Any) -> None:
        return

    async def stop(self) -> None:
        return

    def __call__(self, event: Any) -> Awaitable[None]:
        return self._p._handle_output_event(event)


__all__ = ["TwilioMediaStream"]
