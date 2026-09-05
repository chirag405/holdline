"""Provider memory (local backend): seeded hints, and learning from a call."""

from holdline import memory


def test_seeded_provider_has_hint():
    assert "press 2 for membership" in (memory.get_provider_hint("Iron Peak Fitness") or "")


def test_unknown_provider_has_no_hint():
    assert memory.get_provider_hint("Nowhere Gym LLC") is None


def test_record_call_learnings_updates_snapshot():
    memory.record_call_learnings(
        "Nowhere Gym LLC",
        ivr_path="press 9 then 1 to cancel",
        outcome="cancelled",
        confirmation_number="NG-42",
    )
    hint = memory.get_provider_hint("Nowhere Gym LLC")
    assert hint == "press 9 then 1 to cancel"
    snap = memory.local_snapshot()["nowhere-gym-llc"]
    assert snap["calls"] == 1
    assert snap["last_outcome"] == "cancelled"


def test_record_without_path_keeps_prior_path():
    memory.record_call_learnings("Iron Peak Fitness", ivr_path="", outcome="refused")
    assert "press 2 for membership" in memory.get_provider_hint("Iron Peak Fitness")
    assert memory.local_snapshot()["iron-peak-fitness"]["last_outcome"] == "refused"
