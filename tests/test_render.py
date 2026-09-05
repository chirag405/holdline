"""brief_to_instructions turns a CallBrief into a complete Caller system prompt."""

from holdline.agents.render import brief_to_instructions
from holdline.models import Boundaries, CallBrief


def _brief(**kw) -> CallBrief:
    base = dict(
        objective="Cancel the Iron Peak Fitness membership effective end of billing period.",
        provider_name="Iron Peak Fitness",
        identity_info={"name": "Chirag Dhouni", "account_number": "IPF-99123"},
        boundaries=Boundaries(
            may_agree_to=["cancellation effective at end of billing period"],
            must_escalate=["any retention offer, discount, pause, downgrade, or plan change"],
        ),
        success_criteria=["the representative states the membership is cancelled",
                          "a confirmation or reference number is given"],
        ivr_hint="main menu: press 2; membership menu: press 4",
        default_on_timeout="hold firm and refuse any counter-offer",
        opening_line="Hi, I'm an automated assistant calling on behalf of Chirag Dhouni.",
    )
    base.update(kw)
    return CallBrief(**base)


def test_includes_all_sections():
    text = brief_to_instructions(_brief())
    assert "OBJECTIVE:" in text
    assert "Iron Peak Fitness" in text
    assert "IPF-99123" in text
    assert "KNOWN MENU PATH: main menu: press 2" in text
    assert "YOU MUST NOT DECIDE THESE YOURSELF" in text
    assert "escalate_to_user" in text
    assert "retention offer" in text
    assert "hold firm and refuse any counter-offer" in text
    assert "THE CALL HAS SUCCEEDED WHEN:" in text
    assert "press_keys" in text and "stop_conversation" in text


def test_minimal_brief_still_renders():
    text = brief_to_instructions(
        CallBrief(objective="Ask a billing question.", provider_name="Acme")
    )
    assert "OBJECTIVE: Ask a billing question." in text
    assert "Acme" in text
    # no identity / ivr / boundaries sections when empty
    assert "IDENTITY DETAILS" not in text
    assert "KNOWN MENU PATH" not in text
