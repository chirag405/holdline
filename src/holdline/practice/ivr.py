"""A self-hosted practice IVR that behaves like a real gym-cancellation line.

This is a **test fixture**, not a fake business. Holdline dials it exactly like a
real number; every mechanism it exercises (PSTN call, IVR menus, DTMF, a hold
queue, a retention-offer conversation) is real. It lives in the repo so anyone
can reproduce the demo without a Twilio Studio flow to import.

Call flow:
    /practice/entry       greeting + main menu   (say/press 2 = membership)
    /practice/menu        -> membership submenu  (say/press 4 = cancel)
    /practice/membership  -> hold queue (~18s)   -> rep
    /practice/rep_intro   "this is Jordan in member services..."
    /practice/rep         retention offer, then cancels + reads a confirmation #
    /practice/rep_close   goodbye / hangup

Point your practice Twilio number's Voice webhook at:  https://<tunnel>/practice/entry
"""

from __future__ import annotations

import random

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import Response

log = structlog.get_logger("practice.ivr")

router = APIRouter(prefix="/practice", tags=["practice-ivr"])

# Per-call state, keyed by Twilio CallSid. Fine for a single-call demo.
_state: dict[str, dict] = {}

REP_VOICE = "Polly.Joanna"
HOLD_MUSIC = "http://demo.twilio.com/docs/classic.mp3"  # public Twilio demo asset


def _xml(body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
        media_type="text/xml",
    )


async def _params(request: Request) -> dict[str, str]:
    if request.method == "POST":
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
    return {k: str(v) for k, v in request.query_params.items()}


def _said(p: dict[str, str], *needles: str) -> bool:
    heard = (p.get("SpeechResult", "") + " " + p.get("Digits", "")).lower()
    return any(n in heard for n in needles)


@router.api_route("/entry", methods=["GET", "POST"])
async def entry(request: Request) -> Response:
    p = await _params(request)
    _state.pop(p.get("CallSid", ""), None)  # fresh call
    return _xml(
        '<Pause length="1"/>'
        '<Say>Thank you for calling Iron Peak Fitness.</Say>'
        '<Gather input="dtmf speech" numDigits="1" timeout="6" speechTimeout="auto" '
        'action="/practice/menu" method="POST" '
        'hints="membership, billing, hours, cancel">'
        "<Say>For membership, press or say 2. For billing, press 3. "
        "For club hours, press 4.</Say>"
        "</Gather>"
        '<Redirect method="POST">/practice/entry</Redirect>'
    )


@router.api_route("/menu", methods=["GET", "POST"])
async def menu(request: Request) -> Response:
    p = await _params(request)
    if _said(p, "2", "member"):
        return _xml(
            '<Say>Membership services.</Say>'
            '<Gather input="dtmf speech" numDigits="1" timeout="6" speechTimeout="auto" '
            'action="/practice/membership" method="POST" '
            'hints="change plan, cancel, cancel membership">'
            "<Say>To change your plan, press or say 1. "
            "To cancel your membership, press or say 4.</Say>"
            "</Gather>"
            '<Redirect method="POST">/practice/entry</Redirect>'
        )
    return _xml('<Say>Sorry, I did not get that.</Say><Redirect method="POST">/practice/entry</Redirect>')


@router.api_route("/membership", methods=["GET", "POST"])
async def membership(request: Request) -> Response:
    p = await _params(request)
    if _said(p, "4", "cancel"):
        return _xml(
            '<Say>I can help you cancel. Let me connect you to a membership specialist.</Say>'
            '<Say>All of our specialists are currently helping other members. '
            'Please hold and the next available specialist will be with you.</Say>'
            f'<Play>{HOLD_MUSIC}</Play>'
            '<Pause length="6"/>'
            '<Say>Thank you for continuing to hold.</Say>'
            f'<Play>{HOLD_MUSIC}</Play>'
            '<Redirect method="POST">/practice/rep_intro</Redirect>'
        )
    if _said(p, "1", "change", "plan"):
        return _xml(
            '<Say>Plan changes must be done in the app. Returning to the main menu.</Say>'
            '<Redirect method="POST">/practice/entry</Redirect>'
        )
    return _xml('<Say>Sorry, I did not get that.</Say><Redirect method="POST">/practice/entry</Redirect>')


@router.api_route("/rep_intro", methods=["GET", "POST"])
async def rep_intro(request: Request) -> Response:
    return _xml(
        f'<Say voice="{REP_VOICE}">Thanks for holding. This is Jordan in member '
        f"services. How can I help you today?</Say>"
        '<Gather input="speech" speechTimeout="auto" action="/practice/rep" method="POST"/>'
        '<Redirect method="POST">/practice/rep_intro</Redirect>'
    )


@router.api_route("/rep", methods=["GET", "POST"])
async def rep(request: Request) -> Response:
    p = await _params(request)
    sid = p.get("CallSid", "demo")
    st = _state.setdefault(sid, {})

    # First mention of cancelling -> make the retention offer.
    if not st.get("offered") and _said(p, "cancel", "close my account", "end my membership"):
        st["offered"] = True
        return _xml(
            f'<Say voice="{REP_VOICE}">I can take care of that. Before I do — I am '
            f"able to offer you three months at fifty percent off if you stay with "
            f"us. Would you like to take that offer?</Say>"
            '<Gather input="speech" speechTimeout="auto" action="/practice/rep" method="POST"/>'
            '<Redirect method="POST">/practice/rep_intro</Redirect>'
        )

    # After the offer, a "yes" takes the discount (scenario C, wired up later).
    if st.get("offered") and _said(p, "yes", "sure", "okay", "i'll take it", "sounds good"):
        st["accepted_offer"] = True
        return _xml(
            f'<Say voice="{REP_VOICE}">Wonderful. I have applied three months at fifty '
            f"percent off to your account. You are all set.</Say>"
            '<Gather input="speech" speechTimeout="auto" action="/practice/rep_close" method="POST"/>'
            '<Hangup/>'
        )

    # A "no" (or a repeated cancel request) -> actually cancel + read a confirmation number.
    if _said(p, "no", "cancel", "just cancel", "not interested", "go ahead", "proceed"):
        conf = st.get("confirmation") or f"IPF{random.randint(100000, 999999)}"
        st["confirmation"] = conf
        st["cancelled"] = True
        spaced = " ".join(conf)
        return _xml(
            f'<Say voice="{REP_VOICE}">No problem. I have cancelled your membership, '
            f"effective at the end of your current billing period. Your cancellation "
            f"confirmation number is {spaced}. Again, that is {spaced}. "
            f"Is there anything else I can help you with?</Say>"
            '<Gather input="speech" speechTimeout="auto" action="/practice/rep_close" method="POST"/>'
            '<Hangup/>'
        )

    return _xml(
        f'<Say voice="{REP_VOICE}">Sorry, could you say that again?</Say>'
        '<Gather input="speech" speechTimeout="auto" action="/practice/rep" method="POST"/>'
        '<Redirect method="POST">/practice/rep_intro</Redirect>'
    )


@router.api_route("/rep_close", methods=["GET", "POST"])
async def rep_close(request: Request) -> Response:
    p = await _params(request)
    if _said(p, "no", "that's all", "thats all", "nothing", "we're done", "were done", "bye"):
        return _xml(f'<Say voice="{REP_VOICE}">Thanks for being a member. Goodbye.</Say><Hangup/>')
    return _xml(
        f'<Say voice="{REP_VOICE}">Okay.</Say>'
        '<Gather input="speech" speechTimeout="auto" action="/practice/rep_close" method="POST"/>'
        '<Hangup/>'
    )


__all__ = ["router"]
