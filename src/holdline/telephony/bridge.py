"""FastAPI bridge: place an outbound call, then stream its audio between Twilio
and the Nova Sonic Caller agent.

Routes
------
GET  /health            liveness
GET  /config            non-secret settings the dashboard needs (practice number, flags)
POST /tasks             {"request","fields"} -> plan a task (Planner), returns the Brief
GET  /tasks/{id}        task + Brief
POST /calls             {"to","task_id"|"request"|"goal"} -> places the call
GET  /calls             call history (newest first)
GET  /calls/{id}        one call: transcript, outcome, confirmation #, summary
GET  /twiml             Twilio fetches this when the call connects; returns <Connect><Stream>
WS   /ts                Twilio Media Streams socket -> Caller + Supervisor -> (post-call) Scribe
GET  /decisions         pending mid-call escalations awaiting the account holder
POST /decisions/{id}    {"answer": "..."} -> resolve one, the call resumes
GET  /stream            Server-Sent Events: turn / status / decision_open / call_ended / ...
GET  /practice/*        the self-hosted practice IVR (Day 3 target)

Run locally:
    python scripts/run_bridge.py
    # expose it:  cloudflared tunnel --url http://localhost:8000   (or ngrok http 8000)
    # put the https/wss base in PUBLIC_WS_URL, then:  python scripts/place_call.py +1YOURCELL
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from holdline import events
from holdline.config import get_settings
from holdline.practice.ivr import router as practice_router
from holdline.session import CallSession, all_pending, resolve_pending, run_call_session
from holdline.telephony.twilio_io import TwilioMediaStream

log = structlog.get_logger("telephony.bridge")

app = FastAPI(title="Holdline bridge")
# The dashboard is a separate Next.js app; allow it to call the API in dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# The self-hosted practice IVR (Day 3 demo target) rides on the same server.
app.include_router(practice_router)

# call_sid -> {"task": <task dict>, "instructions": <str>}. Populated by POST /calls,
# consumed by the WS handler once Twilio reports the call_sid in its `start` frame.
_pending: dict[str, dict] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
async def config() -> JSONResponse:
    s = get_settings()
    return JSONResponse(
        {
            "practice_ivr_number": s.practice_ivr_number,
            "has_twilio": bool(s.twilio_account_sid and s.twilio_from_number),
            "public_ws_url_set": bool(s.public_ws_url),
            "supervisor_enabled": s.supervisor_enabled,
            "escalation_timeout_s": s.escalation_timeout_s,
            "state_backend": s.state_backend,
        }
    )


@app.post("/tasks")
async def create_task_route(request: Request) -> JSONResponse:
    body = await request.json()
    if not body.get("request"):
        return JSONResponse({"error": "missing 'request'"}, status_code=400)
    from holdline.orchestrator import create_and_plan

    task = create_and_plan(body["request"], body.get("fields") or {})
    return JSONResponse({"task_id": task["task_id"], "brief": task["brief"], "task": task})


@app.get("/tasks/{task_id}")
async def get_task_route(task_id: str) -> JSONResponse:
    from holdline.state import store

    task = store.get_task(task_id)
    return JSONResponse(task or {"error": "not found"}, status_code=200 if task else 404)


@app.get("/calls")
async def list_calls_route() -> JSONResponse:
    from holdline.state import store

    return JSONResponse({"calls": store.list_calls()})


@app.get("/calls/{call_id}")
async def get_call_route(call_id: str) -> JSONResponse:
    from holdline.state import store

    call = store.get_call(call_id)
    return JSONResponse(call or {"error": "not found"}, status_code=200 if call else 404)


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


@app.get("/decisions")
async def list_decisions() -> JSONResponse:
    return JSONResponse({"pending": all_pending()})


@app.post("/decisions/{decision_id}")
async def resolve_decision_route(decision_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    answer = (body.get("answer") or "").strip()
    if not answer:
        return JSONResponse({"error": "missing 'answer'"}, status_code=400)
    ok = resolve_pending(decision_id, answer)
    return JSONResponse({"resolved": ok}, status_code=200 if ok else 404)


@app.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    """Server-Sent Events feed of everything happening on calls, for the dashboard."""
    try:
        after = int(request.query_params.get("after", "0"))
    except ValueError:
        after = 0

    once = request.query_params.get("once") in ("1", "true", "yes")

    async def gen():
        for evt in events.recent(after):
            yield f"data: {json.dumps(evt)}\n\n"
        if once:
            return
        async with events.subscribe() as q:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(evt)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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

    stream = TwilioMediaStream(ws)  # transcript wired to the session below
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

    call_id: str | None = None
    if task.get("task_id"):
        try:
            call_id = store.create_call(task["task_id"])["call_id"]
            store.set_task_status(task["task_id"], "calling")
        except Exception as exc:  # noqa: BLE001
            log.warning("call.create_failed", error=str(exc))

    session = CallSession(stream=stream, task=task, call_id=call_id)
    stream.set_transcript_cb(session.add_turn)  # route final turns into the session

    try:
        await run_call_session(session, stream, instructions=instructions)
    finally:
        await stream.aclose()
        await _finalize(task, call_id, session.transcript, stream)


async def _finalize(task: dict, call_id: str | None, transcript: list[dict], stream) -> None:
    outcome = getattr(stream, "outcome", None)
    confirmation = getattr(stream, "confirmation_number", None)
    log.info("ws.done", turns=len(transcript), outcome=outcome, confirmation_number=confirmation)
    summary: dict | None = None
    if call_id:
        try:
            from holdline.orchestrator import summarize_and_persist

            # Scribe is sync + does a Bedrock call; keep it off the event loop.
            summary = await asyncio.to_thread(summarize_and_persist, call_id, task, transcript)
            log.info("scribe.persisted", call_id=call_id, summary=summary)
        except Exception as exc:  # noqa: BLE001 - a summary failure must not lose the call row
            log.warning("scribe.failed", call_id=call_id, error=str(exc))
            from holdline.state import store

            store.finish_call(
                call_id, outcome=outcome or "unknown", confirmation_number=confirmation
            )
    events.publish(
        "call_ended",
        call_id=call_id,
        task_id=task.get("task_id"),
        outcome=(summary or {}).get("outcome_status") or outcome or "unknown",
        confirmation_number=(summary or {}).get("confirmation_number") or confirmation,
        summary=summary,
        turns=len(transcript),
    )


def _https_base(u: str) -> str:
    return u.replace("wss://", "https://").replace("ws://", "http://").rstrip("/")


def _wss_base(u: str) -> str:
    return u.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
