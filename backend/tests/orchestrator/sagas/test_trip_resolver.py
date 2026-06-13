"""Trip resolution priority + explicit-name override (Task 36) + directive-aware
focus (Task 44) + destination-match/focus/tie-break (Task 52). No DB."""

import datetime

from agentic_traveler.orchestrator.sagas.trip_resolver import (
    is_established,
    resolve_active_trip,
    resolve_trip_focus,
)


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


# ---------------------------------------------------------------------------
# task 44 — is_established + directive-aware resolve_trip_focus
# ---------------------------------------------------------------------------

def test_is_established_by_status():
    assert is_established(_summary("a", status="active"))
    assert is_established(_summary("a", status="ready"))
    assert not is_established(_summary("a", status="dreaming"))
    assert not is_established(_summary("a", status="draft"))


def test_is_established_by_vision_summary():
    # A blank-status trip with a vision summary still counts as established.
    assert is_established(_summary("a", status="dreaming", vision_summary="Sun + surf"))
    assert not is_established(_summary("a", status="dreaming", vision_summary=""))


def test_focus_new_directive_ignores_existing_and_reports_superseded():
    trips = [
        _summary("a", title="Japan, autumn", status="dreaming", vision_summary="Temples",
                 updated_at="2027-05-01"),
        _summary("b", title="Old draft", status="dreaming", updated_at="2027-01-01"),
    ]
    chosen, superseded, create_new = resolve_trip_focus(trips, "a new trip", {}, "new")
    assert chosen is None
    assert create_new is True
    assert superseded == "Japan, autumn"   # most-recent ESTABLISHED trip


def test_focus_new_directive_with_no_established_trip_has_no_superseded():
    trips = [_summary("b", title="Blank", status="dreaming", updated_at="2027-01-01")]
    chosen, superseded, create_new = resolve_trip_focus(trips, "new trip", {}, "new")
    assert chosen is None
    assert create_new is True
    assert superseded is None


def test_focus_continue_and_unspecified_delegate_to_resolve_active():
    trips = [
        _summary("a", status="planning", updated_at="2027-01-01"),
        _summary("b", status="active", updated_at="2027-05-01"),
    ]
    for directive in ("continue", "unspecified"):
        chosen, superseded, create_new = resolve_trip_focus(trips, "weather?", {}, directive)
        assert chosen["id"] == "b"
        assert superseded is None
        assert create_new is False


# ---------------------------------------------------------------------------
# task 52 — destination-match + focused_trip_id + tie-break
# ---------------------------------------------------------------------------

def _dest(name, iso=None, status="confirmed"):
    return {"name": name, "iso_country": iso, "status": status}


def _spain():
    return _summary(
        "spain", title="Spain trip", status="planning", updated_at="2027-01-01",
        destinations=[_dest("Barcelona", "ES"), _dest("Madrid", "ES", "considering")],
    )


def _japan():
    return _summary(
        "japan", title="Japan trip", status="planning", updated_at="2027-02-01",
        destinations=[_dest("Kyoto", "JP")],
    )


# AC-6 — best-effort destination match -------------------------------------

def test_destination_match_drifts_to_non_focused_trip():
    trips = [_spain(), _japan()]
    # Focused on Japan, but the message names Barcelona → drift to Spain.
    chosen, superseded, create_new = resolve_trip_focus(
        trips, "what can I see in Barcelona?", {"destinations": ["Barcelona"]},
        "unspecified", focused_trip_id="japan",
    )
    assert chosen["id"] == "spain"
    assert superseded is None
    assert create_new is False


def test_destination_match_to_focused_trip_stays_put():
    trips = [_spain(), _japan()]
    # The named city belongs to the already-focused trip → no drift.
    chosen, _s, _c = resolve_trip_focus(
        trips, "what can I see in Barcelona?", {"destinations": ["Barcelona"]},
        "unspecified", focused_trip_id="spain",
    )
    assert chosen["id"] == "spain"


def test_destination_match_is_case_insensitive():
    trips = [_spain(), _japan()]
    chosen, _s, _c = resolve_trip_focus(
        trips, "kyoto!", {"destinations": ["KYOTO"]}, "unspecified",
    )
    assert chosen["id"] == "japan"


def test_no_destination_uses_focused_trip():
    trips = [_spain(), _japan()]
    chosen, _s, _c = resolve_trip_focus(
        trips, "how's the weather?", {}, "unspecified", focused_trip_id="japan",
    )
    assert chosen["id"] == "japan"


def test_destination_matches_no_trip_falls_to_heuristic_none():
    # Paris matches no trip; no focus → heuristic; the explicit-destination
    # mismatch guard returns None so the turn is answered without forcing focus.
    trips = [_spain(), _japan()]
    chosen, _s, create_new = resolve_trip_focus(
        trips, "what is Paris like?", {"destinations": ["Paris"]}, "unspecified",
    )
    assert chosen is None
    assert create_new is False


# AC-8 — hallucination-safe focus ------------------------------------------

def test_stale_focused_trip_id_is_ignored():
    trips = [_summary("a", status="active", updated_at="2027-05-01")]
    # focused id is not among the user's trips → ignored, heuristic applies.
    chosen, _s, _c = resolve_trip_focus(
        trips, "hello", {}, "unspecified", focused_trip_id="ghost-trip",
    )
    assert chosen["id"] == "a"


# AC-7 — tie-break when destinations match multiple trips -------------------

def _today_offset(days):
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def test_tiebreak_active_trip_wins():
    trips = [
        _summary("past", title="Spain north", status="planning",
                 reference_date=_today_offset(-30), updated_at="2027-01-01",
                 destinations=[_dest("Bilbao")]),
        _summary("live", title="Spain south", status="active",
                 reference_date=_today_offset(-3), updated_at="2027-01-02",
                 destinations=[_dest("Seville")]),
    ]
    chosen, _s, _c = resolve_trip_focus(
        trips, "spain", {"destinations": ["Spain"]}, "unspecified",
    )
    assert chosen["id"] == "live"


def test_tiebreak_nearest_upcoming_when_no_active():
    trips = [
        _summary("far", title="Spain A", status="planning",
                 reference_date=_today_offset(365), updated_at="2027-01-01",
                 destinations=[_dest("A")]),
        _summary("near", title="Spain B", status="planning",
                 reference_date=_today_offset(20), updated_at="2027-01-02",
                 destinations=[_dest("B")]),
    ]
    chosen, _s, _c = resolve_trip_focus(
        trips, "spain", {"destinations": ["Spain"]}, "unspecified",
    )
    assert chosen["id"] == "near"


def test_tiebreak_most_recent_past_when_all_past():
    trips = [
        _summary("old", title="Spain A", status="planning",
                 reference_date=_today_offset(-365), updated_at="2027-01-01",
                 destinations=[_dest("A")]),
        _summary("recent", title="Spain B", status="planning",
                 reference_date=_today_offset(-20), updated_at="2027-01-02",
                 destinations=[_dest("B")]),
    ]
    chosen, _s, _c = resolve_trip_focus(
        trips, "spain", {"destinations": ["Spain"]}, "unspecified",
    )
    assert chosen["id"] == "recent"


def test_new_directive_still_overrides_destination_match():
    trips = [_spain(), _japan()]
    chosen, superseded, create_new = resolve_trip_focus(
        trips, "start a new Barcelona trip", {"destinations": ["Barcelona"]},
        "new", focused_trip_id="spain",
    )
    assert chosen is None
    assert create_new is True
