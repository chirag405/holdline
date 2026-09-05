"""FastAPI bridge: place an outbound call, then stream its audio between Twilio
and the Nova Sonic Caller agent.

Routes
------
GET  /health          liveness
POST /tasks           {"request": "...", "fields": {...}} -> plan a task (Planner), returns the Brief
POST /calls           {"to": "+1...", "task_id"|"request"|"goal": ...} -> places the call
GET  /twiml           Twilio fetches this when the call connects; returns <Connect><Stream>
WS   /ts              Twilio Media Streams socket -> Caller agent -> (post-call) Scribe
GET  /practice/*      the self-hosted practice IVR (Day 3 target)

Run locally:
    python scripts/run_bridge.py
    # expose it:  cloudflared tunnel --url http://localhost:8000   (or ngrok http 8000)
    # put the https/wss base in PUBLIC_WS_URL, then:  python scripts/place_call.py +1YOURCELL
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse, Response

from holdline.config import get_settings
from holdline.practice.ivr import router as practice_router
from holdline.telephony.caller_agent import build_caller_agent
from holdline.telephony.twilio_io import TwilioMediaStream

log = structlog.get_logger("telephony.bridge")

app = FastAPI(title="Holdline bridge")
# The self-hosted practice IVR (Day 3 demo target) rides on the same server.
app.include_router(practice_router)

# call_sid -> {"task": <task dict>, "instructions": <str>}. Populated by POST /calls,
# consumed by the WS handler once Twilio reports the call_sid in its `start` frame.
_pending: dict[str, dict] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks")
async def create_task_route(request: Request) -> JSONResponse:
    body = await request.json()
    if not body.get("request"):
        return JSONResponse({"error": "missing 'request'"}, status_code=400)
    from holdline.orchestrator import create_and_plan

    task = create_and_plan(body["request"], body.get("fields") or {})
    return JSONResponse({"task_id": task["task_id"], "brief": task["brief"]})


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

    # Resolve what the Caller should be told to do.
    task, instructions = _resolve_goal(body)

    from twilio.rest import Client

    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    call = client.calls.create(
        to=to,
        from_=s.twilio_from_number,
        url=f"{_https_base(s.public_ws_url)}/twiml",
        method="GET",
    )
    _pending[call.sid] = {"task": task, "instructions": instructions}
    log.info("call.placed", call_sid=call.sid, to=to, task_id=task.get("task_id"))
    return JSONResponse({"call_sid": call.sid, "status": call.status})


def _resolve_goal(body: dict) -> tuple[dict, str | None]:
    """Return (task_dict, caller_instructions_or_None) from a /calls body."""
    from holdline.orchestrator import create_and_plan, instructions_for_task
    from holdline.state import store

    if body.get("task_id"):
        task = store.get_task(body["task_id"]) or {"task_id": body["task_id"]}
        return task, instructions_for_task(task) if task.get("brief") else None
    if body.get("request"):
        task = create_and_plan(body["request"], body.get("fields") or {})
        return task, instructions_for_task(task)
    # Raw passthrough (Day 2/3 style). No task row.
    return {"task_id": None, "request_text": body.get("goal", "")}, body.get("goal")


@app.get("/twiml")
async def twiml() -> Response:
    s = get_settings()
    ws_url = f"{_wss_base(s.public_ws_url)}/ts"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Connect><Stream url="{ws_url}"/></Connect>'
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml")


@app.websocket("/ts")
async def media_stream(ws: WebSocket) -> None:
    await ws.accept()
    log.info("ws.accepted")

    from holdline.state import store

    transcript: list[dict] = []
    call_id: str | None = None

    def on_transcript(role: str, text: str, is_final: bool) -> None:
        if is_final and text.strip():
            transcript.append({"role": role, "text": text})
            log.info("transcript", role=role, text=text)
            if call_id:
                try:
                    store.append_transcript(call_id, role, text)
                except Exception as exc:  # noqa: BLE001 - never let persistence kill a call
                    log.warning("transcript.persist_failed", error=str(exc))

    stream = TwilioMediaStream(ws, on_transcript=on_transcript)
    stream.start_reader()

    # Twilio sends `start` within the first frames; wait for the call_sid.
    pending: dict = {}
    for _ in range(50):
        if stream.call_sid:
            pending = _pending.pop(stream.call_sid, {})
            break
        await asyncio.sleep(0.1)

    task = pending.get("task") or {"task_id": None}
    instructions = pending.get("instructions")

    if task.get("task_id"):
        try:
            call_id = store.create_call(task["task_id"])["call_id"]
            store.set_task_status(task["task_id"], "calling")
        except Exception as exc:  # noqa: BLE001
            log.warning("call.create_failed", error=str(exc))

    agent = build_caller_agent(stream, instructions=instructions, brief=task.get("brief"))
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
        await _finalize(task, call_id, transcript, stream)


async def _finalize(task: dict, call_id: str | None, transcript: list[dict], stream) -> None:
    outcome = getattr(stream, "outcome", None)
    confirmation = getattr(stream, "confirmation_number", None)
    log.info("ws.done", turns=len(transcript), outcome=outcome, confirmation_number=confirmation)
    if not call_id:
        return
    try:
        from holdline.orchestrator import summarize_and_persist

        # Scribe is sync + does a Bedrock call; keep it off the event loop.
        summary = await asyncio.to_thread(summarize_and_persist, call_id, task, transcript)
        log.info("scribe.persisted", call_id=call_id, summary=summary)
    except Exception as exc:  # noqa: BLE001 - a summary failure must not lose the call row
        log.warning("scribe.failed", call_id=call_id, error=str(exc))
        from holdline.state import store

        store.finish_call(call_id, outcome=outcome or "unknown", confirmation_number=confirmation)


def _https_base(u: str) -> str:
    return u.replace("wss://", "https://").replace("ws://", "http://").rstrip("/")


def _wss_base(u: str) -> str:
    return u.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
