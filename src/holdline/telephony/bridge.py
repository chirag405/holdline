"""FastAPI bridge: place an outbound call, then stream its audio between Twilio
and the Nova Sonic Caller agent.

Routes
------
GET  /health          liveness
POST /calls           {"to": "+1...", "goal": "<optional override>"}  -> places the call
GET  /twiml           Twilio fetches this when the call connects; returns <Connect><Stream>
WS   /ts              Twilio Media Streams socket -> Caller agent

Run locally:
    python scripts/run_bridge.py
    # expose it:  cloudflared tunnel --url http://localhost:8000   (or ngrok http 8000)
    # put the https/wss base in PUBLIC_WS_URL, then:  python scripts/place_call.py +1YOURCELL
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, Response

from holdline.config import get_settings
from holdline.telephony.caller_agent import build_caller_agent
from holdline.telephony.twilio_io import TwilioMediaStream

log = structlog.get_logger("telephony.bridge")

app = FastAPI(title="Holdline bridge")

# In-memory: goal override to hand the next inbound WS. Fine for a single-call demo;
# Day 4 keys this by call_sid via DynamoDB.
_pending_goal: dict[str, str] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/calls")
async def place_call(request: Request) -> JSONResponse:
    body = await request.json()
    to = body.get("to")
    if not to:
        return JSONResponse({"error": "missing 'to'"}, status_code=400)
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
        return JSONResponse({"error": "Twilio env not configured"}, status_code=500)
    if not s.public_ws_url:
        return JSONResponse({"error": "PUBLIC_WS_URL not set"}, status_code=500)

    from twilio.rest import Client

    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    call = client.calls.create(
        to=to,
        from_=s.twilio_from_number,
        url=f"{_https_base(s.public_ws_url)}/twiml",
        method="GET",
    )
    if body.get("goal"):
        _pending_goal[call.sid] = body["goal"]
    log.info("call.placed", call_sid=call.sid, to=to)
    return JSONResponse({"call_sid": call.sid, "status": call.status})


@app.get("/twiml")
async def twiml() -> Response:
    s = get_settings()
    ws_url = f"{_wss_base(s.public_ws_url)}/ts"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Connect><Stream url=\"{ws_url}\"/></Connect>"
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml")


@app.websocket("/ts")
async def media_stream(ws: WebSocket) -> None:
    await ws.accept()
    log.info("ws.accepted")
    transcript: list[tuple[str, str]] = []

    def on_transcript(role: str, text: str, is_final: bool) -> None:
        if is_final and text.strip():
            transcript.append((role, text))
            log.info("transcript", role=role, text=text)

    stream = TwilioMediaStream(ws, on_transcript=on_transcript)
    stream.start_reader()

    goal = None
    # Twilio sends `start` within the first frames; give the reader a beat to set call_sid.
    import asyncio

    for _ in range(50):
        if stream.call_sid:
            goal = _pending_goal.pop(stream.call_sid, None)
            break
        await asyncio.sleep(0.1)

    agent = build_caller_agent(stream, instructions=goal)
    try:
        await agent.run(inputs=[stream.input()], outputs=[stream.output()])
    except* Exception as eg:  # noqa: BLE001 - stream closed / agent stop
        log.info("ws.agent_run_end", errors=[repr(e) for e in eg.exceptions])
    finally:
        await stream.aclose()
        try:
            await agent.stop()
        except Exception:  # noqa: BLE001
            pass
        log.info("ws.done", turns=len(transcript))


def _https_base(u: str) -> str:
    return u.replace("wss://", "https://").replace("ws://", "http://").rstrip("/")


def _wss_base(u: str) -> str:
    return u.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
