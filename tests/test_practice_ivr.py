"""The self-hosted practice IVR walks from greeting to a confirmation number.

Drives the TwiML endpoints the way Twilio would (form-encoded POSTs carrying
Digits / SpeechResult / CallSid), no telephony involved.
"""

import re

import pytest
from fastapi.testclient import TestClient

from holdline.telephony.bridge import app

client = TestClient(app)
SID = "CAtest123"


def post(path: str, **form) -> str:
    form.setdefault("CallSid", SID)
    r = client.post(path, data=form)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/xml")
    return r.text


def test_happy_path_reaches_confirmation_number():
    entry = post("/practice/entry")
    assert "Iron Peak Fitness" in entry
    assert 'action="/practice/menu"' in entry

    # press 2 -> membership submenu
    menu = post("/practice/menu", Digits="2")
    assert 'action="/practice/membership"' in menu

    # press 4 -> hold queue then rep
    member = post("/practice/membership", Digits="4")
    assert "<Play>" in member and "hold" in member.lower()
    assert "/practice/rep_intro" in member

    intro = post("/practice/rep_intro")
    assert "member services" in intro.lower()

    # ask to cancel -> retention offer
    offer = post("/practice/rep", SpeechResult="Hi, I'd like to cancel the membership please")
    assert "fifty percent" in offer.lower()

    # decline -> cancellation + confirmation number
    done = post("/practice/rep", SpeechResult="No thank you, please just cancel it")
    assert "cancelled your membership" in done.lower()
    m = re.search(r"confirmation number is ([\dA-Z ]+?)\.", done)
    assert m, done
    digits = m.group(1).replace(" ", "")
    assert digits.startswith("IPF") and len(digits) == 9


def test_speech_only_navigation_works():
    sid = "CAspeech"
    client.post("/practice/entry", data={"CallSid": sid})
    menu = client.post("/practice/menu", data={"CallSid": sid, "SpeechResult": "membership"})
    assert "/practice/membership" in menu.text
    member = client.post(
        "/practice/membership", data={"CallSid": sid, "SpeechResult": "cancel my membership"}
    )
    assert "/practice/rep_intro" in member.text


def test_accept_retention_offer_branch():
    sid = "CAaccept"
    client.post("/practice/entry", data={"CallSid": sid})
    client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "I want to cancel"})
    accepted = client.post(
        "/practice/rep", data={"CallSid": sid, "SpeechResult": "yes I'll take that offer"}
    )
    assert "fifty percent off" in accepted.text.lower()
    assert "<Hangup" in accepted.text


@pytest.mark.parametrize("junk", ["", "I want to speak to a human", "gibberish"])
def test_menu_reprompts_on_unrecognized(junk):
    r = client.post("/practice/menu", data={"CallSid": "CAx", "SpeechResult": junk})
    assert "/practice/entry" in r.text
