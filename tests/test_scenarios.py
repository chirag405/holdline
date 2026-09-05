"""The three demo scenarios, exercised against the practice IVR TwiML the way
Twilio drives it -- no telephony, no Nova. Asserts the rep-side end state each
scenario is built to reach."""

import re

from fastapi.testclient import TestClient

from holdline.telephony.bridge import app

client = TestClient(app)


def _walk_to_rep(sid: str) -> None:
    client.post("/practice/entry", data={"CallSid": sid})
    client.post("/practice/menu", data={"CallSid": sid, "Digits": "2"})
    r = client.post("/practice/membership", data={"CallSid": sid, "Digits": "4"})
    assert "/practice/rep_intro" in r.text
    client.post("/practice/rep_intro", data={"CallSid": sid})


def test_scenario_a_clean_auto_cancel():
    sid = "CAscnA"
    _walk_to_rep(sid)
    offer = client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "I want to cancel"})
    assert "fifty percent" in offer.text.lower()
    done = client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "no, just cancel"})
    m = re.search(r"confirmation number is ([\dA-Z ]+?)\.", done.text)
    assert m and m.group(1).replace(" ", "").startswith("IPF")


def test_scenario_b_retention_then_hold_firm():
    sid = "CAscnB"
    _walk_to_rep(sid)
    client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "cancel my membership"})
    # "hold firm" from the account holder -> the agent declines and insists
    done = client.post(
        "/practice/rep", data={"CallSid": sid, "SpeechResult": "no thanks, go ahead and cancel"}
    )
    assert "cancelled your membership" in done.text.lower()
    assert "confirmation number" in done.text.lower()


def test_scenario_c_escalation_then_accept():
    sid = "CAscnC"
    _walk_to_rep(sid)
    client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "I'd like to cancel"})
    accepted = client.post(
        "/practice/rep", data={"CallSid": sid, "SpeechResult": "yes, I'll take the discount"}
    )
    assert "fifty percent off" in accepted.text.lower()
    assert "<Hangup" in accepted.text  # kept the membership, call wraps up


def test_scenarios_are_independent():
    # running them back to back doesn't leak state between CallSids
    for sid in ("CAx1", "CAx2", "CAx3"):
        _walk_to_rep(sid)
        client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "cancel"})
        r = client.post("/practice/rep", data={"CallSid": sid, "SpeechResult": "no just cancel"})
        assert "cancelled your membership" in r.text.lower()
