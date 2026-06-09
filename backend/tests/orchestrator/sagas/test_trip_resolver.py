"""Trip resolution priority + explicit-name override (Task 36). No DB."""

from agentic_traveler.orchestrator.sagas.trip_resolver import resolve_active_trip


def _summary(id_, **kw):
    base = {
        "id": id_, "title": None, "status": "planning",
        "reference_date": None, "vision_summary": None, "updated_at": "2027-01-01",
    }
    base.update(kw)
    return base


def test_empty_returns_none():
    assert resolve_active_trip([], "plan my trip") is None


def test_active_beats_more_recent_planning():
    trips = [
        _summary("a", status="planning", updated_at="2027-05-01"),
        _summary("b", status="active", updated_at="2027-01-01"),
    ]
    assert resolve_active_trip(trips, "what's the weather like")["id"] == "b"


def test_ready_beats_planning_when_no_active():
    trips = [
        _summary("a", status="planning", updated_at="2027-05-01"),
        _summary("b", status="ready", updated_at="2027-01-01"),
    ]
    assert resolve_active_trip(trips, "any updates?")["id"] == "b"


def test_falls_back_to_most_recently_updated():
    trips = [
        _summary("a", status="planning", updated_at="2027-01-01"),
        _summary("b", status="planning", updated_at="2027-05-01"),
    ]
    assert resolve_active_trip(trips, "hello")["id"] == "b"


def test_explicit_name_overrides_priority():
    trips = [
        _summary("a", title="Iceland, winter escape", status="planning", updated_at="2027-01-01"),
        _summary("b", title="Kyoto trip", status="active", updated_at="2027-05-01"),
    ]
    # Even though 'b' is active + newer, naming Iceland resolves to 'a'.
    assert resolve_active_trip(trips, "let's tweak my Iceland plans")["id"] == "a"


def test_short_and_stopword_titles_do_not_false_match():
    trips = [
        _summary("a", title="My trip", status="planning", updated_at="2027-01-01"),
        _summary("b", title="Lisbon", status="active", updated_at="2027-05-01"),
    ]
    # "trip"/"my" are stopwords; should fall through to the active trip.
    assert resolve_active_trip(trips, "plan my trip")["id"] == "b"
