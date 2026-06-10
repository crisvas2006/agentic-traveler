"""SagaDispatcher selection table (Task 36). No DB / LLM — agents are
constructed with a mock client and never invoked here."""

from unittest.mock import MagicMock

import pytest

from agentic_traveler.orchestrator.sagas.dispatcher import SagaDispatcher


@pytest.fixture
def dispatcher():
    return SagaDispatcher(client=MagicMock())


def test_registry_order(dispatcher):
    assert [s.name for s in dispatcher.sagas] == [
        "BookingInputSaga", "CountryIntelSaga", "PlanningSaga", "DiscoverySaga", "OffTopicSaga", "ChatSaga",
    ]


def test_plan_intent_owned_by_planning(dispatcher):
    owner, listeners = dispatcher.select("PLAN", {}, None, {})
    assert owner.name == "PlanningSaga"
    assert listeners == []


def test_trip_without_trip_owned_by_discovery(dispatcher):
    owner, _ = dispatcher.select("TRIP", {}, None, {})
    assert owner.name == "DiscoverySaga"


def test_trip_with_trip_owned_by_planning(dispatcher):
    owner, _ = dispatcher.select("TRIP", {}, {"id": "t1"}, {})
    assert owner.name == "PlanningSaga"


def test_chat_intent_owned_by_chat(dispatcher):
    owner, _ = dispatcher.select("CHAT", {}, None, {})
    assert owner.name == "ChatSaga"


def test_off_topic_owned_by_off_topic(dispatcher):
    owner, _ = dispatcher.select("OFF_TOPIC", {}, None, {})
    assert owner.name == "OffTopicSaga"


def test_unknown_intent_falls_back_to_chat(dispatcher):
    owner, _ = dispatcher.select("GIBBERISH", {}, None, {})
    assert owner.name == "ChatSaga"
