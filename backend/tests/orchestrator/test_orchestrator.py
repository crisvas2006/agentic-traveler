import pytest
from unittest.mock import MagicMock, patch

from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.orchestrator.sagas.base import ChoiceOption, SagaResult, SlotRequest
from agentic_traveler.tools.user_repo import UserRepository


@pytest.fixture
def mock_user_repo():
    return MagicMock(spec=UserRepository)


@pytest.fixture
def patched_deps():
    """Patch the orchestrator's collaborators. After Task 36 the Chat/Trip/
    Planner agents live inside the SagaDispatcher, so we patch the dispatcher
    and the TripRepository here instead of the individual agents."""
    with patch("agentic_traveler.orchestrator.agent.RouterAgent") as mock_router, \
         patch("agentic_traveler.orchestrator.agent.SagaDispatcher") as mock_dispatcher, \
         patch("agentic_traveler.orchestrator.agent.TripRepository") as mock_trip_repo, \
         patch("agentic_traveler.orchestrator.agent.ConversationManager") as mock_conv, \
         patch("agentic_traveler.orchestrator.agent.credit_manager") as mock_credits, \
         patch("agentic_traveler.orchestrator.agent.off_topic_guard") as mock_guard, \
         patch("agentic_traveler.orchestrator.agent.get_client") as mock_get_client:

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_credits.has_credits.return_value = True
        mock_guard.is_restricted.return_value = None
        mock_conv.return_value.build_context_block.return_value = "Mock history"
        # No trips by default → resolver returns None.
        mock_trip_repo.return_value.list_trip_summaries.return_value = []
        mock_trip_repo.return_value.upsert_trip.return_value.model_dump.return_value = {
            "id": "trip-1"
        }

        yield {
            "router": mock_router,
            "dispatcher": mock_dispatcher,
            "trip_repo": mock_trip_repo,
            "conv": mock_conv,
            "credits": mock_credits,
            "guard": mock_guard,
            "client": mock_client,
        }


def _route(deps, **fields):
    base = {
        "intent": "CHAT", "preference_raw": None, "response": None,
        "entities": {}, "raw_response": MagicMock(), "latency_ms": 100,
    }
    base.update(fields)
    deps["router"].return_value.classify.return_value = base


def _owner(deps, name, text):
    owner = MagicMock()
    owner.name = name
    owner.run.return_value = SagaResult(text=text)
    deps["dispatcher"].return_value.select.return_value = (owner, [])
    return owner


def test_new_user_onboarding(mock_user_repo, patched_deps):
    """Unknown Telegram ID → onboarding link."""
    mock_user_repo.get_user_with_ref.return_value = (None, None)
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("unknown_id", "Hello")
    assert response["action"] == "ONBOARDING_REQUIRED"
    assert "tally.so" in response["text"]


def test_credit_exhausted(mock_user_repo, patched_deps):
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["credits"].has_credits.return_value = False
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "NO_CREDITS"
    assert response["text"] == patched_deps["credits"].CREDITS_EXHAUSTED_MSG


def test_user_restricted(mock_user_repo, patched_deps):
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    patched_deps["guard"].is_restricted.return_value = "You are restricted"
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Hello")
    assert response["action"] == "RESTRICTED"
    assert "restricted" in response["text"].lower()


def test_off_topic_intent(mock_user_repo, patched_deps):
    """OFF_TOPIC is handled inline (before saga dispatch) and records the counter."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    _route(patched_deps, intent="OFF_TOPIC", response="Please ask travel questions")
    patched_deps["guard"].record_off_topic.return_value = {"restricted": False}
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Help with math")
    assert response["action"] == "RESPONSE"
    assert "travel" in response["text"]
    patched_deps["guard"].record_off_topic.assert_called_once()


def test_trip_intent_dispatches_via_saga(mock_user_repo, patched_deps):
    """TRIP intent → saga dispatcher's owner produces the reply."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    _route(patched_deps, intent="TRIP")
    owner = _owner(patched_deps, "DiscoverySaga", "Check out Paris!")
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Where should I go?")
    assert response["action"] == "RESPONSE"
    assert "Paris" in response["text"]
    owner.run.assert_called_once()


def test_plan_intent_dispatches_via_saga(mock_user_repo, patched_deps):
    """PLAN intent → saga dispatcher's owner produces the reply."""
    mock_user_repo.get_user_with_ref.return_value = ({"user_name": "Alice"}, "user-id-123")
    _route(patched_deps, intent="PLAN")
    owner = _owner(patched_deps, "PlanningSaga", "Day 1: Rome")
    agent = OrchestratorAgent(user_repo=mock_user_repo)
    response = agent.process_request("123", "Plan me 3 days in Rome")
    assert response["action"] == "RESPONSE"
    assert "Rome" in response["text"]
    owner.run.assert_called_once()


# ---------------------------------------------------------------------------
# task 43 — selection entrypoint (deterministic tap, no router/extraction)
# ---------------------------------------------------------------------------

def _planning_in_dispatcher(deps, next_result):
    """Register a mock PlanningSaga in the (mocked) dispatcher whose
    run_after_selection returns next_result."""
    saga = MagicMock()
    saga.name = "PlanningSaga"
    saga.run_after_selection.return_value = next_result
    deps["dispatcher"].return_value.sagas = [saga]
    return saga


def test_web_selection_applies_pref_and_returns_next_prompt(mock_user_repo, patched_deps):
    mock_user_repo.get_user_by_id.return_value = {"user_name": "Alice"}
    nxt = SagaResult(
        text="How structured do you want it?",
        slot_request=SlotRequest(
            slot="structure", prompt="How structured?",
            choices=[ChoiceOption("loose", "Loose", "loose")],
        ),
    )
    saga = _planning_in_dispatcher(patched_deps, nxt)
    agent = OrchestratorAgent(user_repo=mock_user_repo)

    resp = agent.process_request_for_user(
        "user-1", "Slow — room to breathe",
        selection={"slot": "pace", "values": ["slow"]},
    )

    # The pace write landed deterministically (no router/extractor involved).
    patched_deps["router"].return_value.classify.assert_not_called()
    calls = patched_deps["trip_repo"].return_value.apply_side_effect.call_args_list
    se = calls[0].args[1]
    assert se.kind == "trip_patch"
    assert se.payload["preferences"]["pace"] == "slow"
    # The saga continuation ran without extraction and surfaced the next slot.
    saga.run_after_selection.assert_called_once()
    assert resp["action"] == "RESPONSE"
    assert resp["slot_request"]["slot"] == "structure"


def test_web_selection_illegal_value_is_rejected_no_write(mock_user_repo, patched_deps):
    mock_user_repo.get_user_by_id.return_value = {"user_name": "Alice"}
    nxt = SagaResult(
        text="What pace feels right?",
        slot_request=SlotRequest(
            slot="pace", prompt="What pace?",
            choices=[ChoiceOption("slow", "Slow", "slow")],
        ),
    )
    _planning_in_dispatcher(patched_deps, nxt)
    agent = OrchestratorAgent(user_repo=mock_user_repo)

    resp = agent.process_request_for_user(
        "user-1", "zoomy", selection={"slot": "pace", "values": ["zoomy"]},
    )

    # Illegal value → no trip write; the same slot is re-asked.
    patched_deps["trip_repo"].return_value.apply_side_effect.assert_not_called()
    assert resp["slot_request"]["slot"] == "pace"
