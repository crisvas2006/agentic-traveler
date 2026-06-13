"""Task 54 — deterministic profile write path (chips, reactions, backfill)."""

from agentic_traveler.orchestrator.profile_write import (
    apply_profile_patch,
    backfill_user,
    profile_selection_to_side_effect,
    reaction_to_profile_patch,
)


def test_selection_legal_single():
    se = profile_selection_to_side_effect("travel_company", ["duo"])
    assert se is not None and se.kind == "profile_patch"
    assert se.payload == {"qid": "travel_company", "value": "duo", "source": "chat_tap"}


def test_selection_illegal_value_rejected():
    assert profile_selection_to_side_effect("travel_company", ["spaceship"]) is None


def test_selection_unknown_qid_rejected():
    assert profile_selection_to_side_effect("not_a_question", ["duo"]) is None


def test_selection_skip_sentinel():
    se = profile_selection_to_side_effect("pace", ["__skip__"])
    assert se is not None and se.payload["value"] == "__skip__"


def test_selection_multi_select_keeps_list():
    se = profile_selection_to_side_effect("deal_breakers", ["no_wifi", "crowds"])
    assert se is not None and se.payload["value"] == ["no_wifi", "crowds"]


def test_selection_single_select_truncates_extra():
    se = profile_selection_to_side_effect("pace", ["slow", "fast"])
    assert se is not None and se.payload["value"] == "slow"


class _FakeRepo:
    def __init__(self):
        self.calls = []

    def merge_answered_question(self, user_id, qid, value, source="chat_tap"):
        self.calls.append((user_id, qid, value, source))


def test_apply_profile_patch_calls_repo_no_llm():
    repo = _FakeRepo()
    apply_profile_patch(
        "u1", {"qid": "pace", "value": "slow", "source": "chat_tap"}, repo=repo
    )
    assert repo.calls == [("u1", "pace", "slow", "chat_tap")]


def test_apply_profile_patch_ignores_missing_qid():
    repo = _FakeRepo()
    apply_profile_patch("u1", {"value": "slow"}, repo=repo)
    assert repo.calls == []


class _FakeAgent:
    def __init__(self):
        self.saved = []

    def save_preference(self, text, user_doc, user_id, token_records=None):
        self.saved.append((text, user_id))


def test_reaction_delegates_to_agent():
    agent = _FakeAgent()
    reaction_to_profile_patch(
        "u1", {"user_profile": {}}, "I don't like museums", agent=agent
    )
    assert agent.saved == [("I don't like museums", "u1")]


def test_backfill_marks_tally_keys_only():
    repo = _FakeRepo()
    # travel_company.tally_key == "travel_bubble".
    n = backfill_user("u1", {"travel_bubble": "The Duo", "unrelated": "x"}, repo)
    assert n == 1
    assert repo.calls[0][1] == "travel_company"
    assert repo.calls[0][3] == "tally_backfill"
