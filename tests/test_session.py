"""CallSession escalation: resolves with an external answer, or times out to the
Brief's default. Plus the Supervisor loop routing an 'escalate' verdict."""

import asyncio

import pytest

from holdline import session as session_mod
from holdline.config import get_settings
from holdline.session import CallSession


class FakeAgent:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, event) -> None:
        self.sent.append(getattr(event, "text", str(event)))

    async def stop(self) -> None:
        pass


def _session(brief=None) -> CallSession:
    task = {"task_id": None, "brief": brief}
    s = CallSession(stream=object(), task=task, call_id=None)
    s.agent = FakeAgent()
    return s


@pytest.mark.asyncio
async def test_escalate_resolves_with_external_answer():
    s = _session()
    esc = asyncio.create_task(s.escalate("Accept 50% off?", ["hold firm", "accept"]))
    await asyncio.sleep(0.05)
    assert s.pending_list(), "decision should be pending"
    did = s.pending_list()[0]["decision_id"]

    assert s.resolve(did, "hold firm") is True
    answer = await asyncio.wait_for(esc, timeout=1)
    assert answer == "hold firm"
    assert s.escalations == [{"question": "Accept 50% off?", "answer": "hold firm"}]
    assert s.pending_list() == []


@pytest.mark.asyncio
async def test_escalate_times_out_to_brief_default(monkeypatch):
    monkeypatch.setenv("ESCALATION_TIMEOUT_S", "0.3")
    get_settings.cache_clear()
    s = _session(brief={"default_on_timeout": "cancel no matter what"})
    answer = await asyncio.wait_for(
        s.escalate("Accept the pause?", ["hold firm", "accept"]), timeout=2
    )
    assert "no response" in answer and "cancel no matter what" in answer
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_resolve_unknown_decision_is_false():
    s = _session()
    assert s.resolve("dec_nope", "x") is False


@pytest.mark.asyncio
async def test_hold_and_escalate_steers_then_resumes():
    s = _session()
    task = asyncio.create_task(s.hold_and_escalate("Accept?", ["hold firm", "accept"]))
    await asyncio.sleep(0.05)
    did = s.pending_list()[0]["decision_id"]
    s.resolve(did, "hold firm")
    await asyncio.wait_for(task, timeout=1)
    # one steer before (hold, don't commit) and one after (act on the answer)
    assert len(s.agent.sent) == 2
    assert "hold" in s.agent.sent[0].lower()
    assert "hold firm" in s.agent.sent[1]


@pytest.mark.asyncio
async def test_supervisor_escalate_verdict_triggers_escalation(monkeypatch):
    from holdline.models import SupervisorVerdict

    monkeypatch.setenv("SUPERVISOR_INTERVAL_S", "0.05")
    monkeypatch.setenv("ESCALATION_TIMEOUT_S", "2")
    get_settings.cache_clear()

    calls = {"n": 0}

    def fake_review(brief, transcript, prior):
        calls["n"] += 1
        if calls["n"] == 1:
            return SupervisorVerdict(
                verdict="escalate", question="Accept offer?", options=["hold firm", "accept"]
            )
        return SupervisorVerdict(verdict="continue")

    monkeypatch.setattr("holdline.agents.supervisor.review_call", fake_review)

    s = _session()
    s.transcript.append({"role": "other", "text": "I can offer you 50% off if you stay."})
    sup = asyncio.create_task(session_mod._supervise(s))

    for _ in range(40):
        await asyncio.sleep(0.05)
        if s.pending_list():
            break
    assert s.pending_list(), "supervisor should have opened an escalation"
    s.resolve(s.pending_list()[0]["decision_id"], "hold firm")

    await asyncio.sleep(0.1)
    s.ended = True
    sup.cancel()
    assert s.escalations and s.escalations[0]["answer"] == "hold firm"
    get_settings.cache_clear()
