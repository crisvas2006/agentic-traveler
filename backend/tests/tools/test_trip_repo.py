"""
Unit tests for TripRepository (Task 34).

All tests mock `get_db` so they run without real Supabase credentials.
Integration tests are marked with `@pytest.mark.integration` and require
a real Supabase project + `_INTEGRATION_TESTS=1`.

Sample inputs / expected outputs are documented inline with each test.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from agentic_traveler.tools.trip_repo import (
    Trip,
    TripDestination,
    TripRepository,
    TripSummary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(*, trip_row: dict | None = None, lists: dict | None = None):
    """
    Build a mock supabase client for TripRepository.

    ``trip_row``  — the row returned by trips.maybe_single()
    ``lists``     — dict mapping table name → list of rows for .execute()
    """
    lists = lists or {}
    db = MagicMock()

    def _table_side_effect(table_name):
        tbl = MagicMock()

        def _select(*_a, **_kw):
            sel = MagicMock()

            def _eq(*_a2, **_kw2):
                eq = MagicMock()

                def _maybe_single():
                    ms = MagicMock()
                    ms.execute.return_value = MagicMock(data=trip_row)
                    return ms

                def _order(*_a3, **_kw3):
                    ord_mock = MagicMock()
                    rows = lists.get(table_name, [])
                    ord_mock.execute.return_value = MagicMock(data=rows)
                    ord_mock.order.return_value = ord_mock  # chain
                    return ord_mock

                eq.maybe_single = _maybe_single
                eq.order = _order
                eq.execute.return_value = MagicMock(data=lists.get(table_name, []))
                return eq

            sel.eq = _eq
            sel.order.return_value = sel
            return sel

        tbl.select = _select

        # update / insert / delete / upsert all return a chainable mock
        chainable = MagicMock()
        chainable.eq.return_value = chainable
        chainable.execute.return_value = MagicMock(data=[trip_row or {}])
        tbl.update.return_value = chainable
        tbl.insert.return_value = chainable
        tbl.delete.return_value = chainable
        tbl.upsert.return_value = chainable

        return tbl

    db.table.side_effect = _table_side_effect
    return db


_TRIP_ROW = {
    "id": "trip-1",
    "user_id": "user-1",
    "status": "dreaming",
    "saga_state": None,
    "title": "Kyoto Spring",
    "reference_date": "2027-04-01",
    "vision_summary": "Cherry blossoms and temples",
    "discovery": {"timeframe": {"start_date": "2027-04-01", "end_date": "2027-04-10"}},
    "travelers": {},
    "preferences": {},
    "country_intel": [],
    "budget": {},
    "live_state": {},
    "scratchpad": {},
    "journal": {},
    "cover": {},
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


# ---------------------------------------------------------------------------
# get_trip
# ---------------------------------------------------------------------------

class TestGetTrip:
    def test_returns_none_when_not_found(self):
        db = _make_db(trip_row=None)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.get_trip("nonexistent")
        assert result is None

    def test_returns_full_trip_with_empty_children(self):
        db = _make_db(trip_row=_TRIP_ROW)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.get_trip("trip-1")

        assert isinstance(result, Trip)
        assert result.id == "trip-1"
        assert result.user_id == "user-1"
        assert result.title == "Kyoto Spring"
        assert result.destinations == []
        assert result.bookings == []
        assert result.days == []
        assert result.day_blocks == []
        assert result.checklist == []

    def test_returns_trip_with_populated_children(self):
        dest_row = {
            "id": "dest-1", "trip_id": "trip-1", "name": "Kyoto",
            "iso_country": "JP", "status": "confirmed", "ord": 0,
            "created_at": None, "updated_at": None,
        }
        day_row = {
            "id": "day-1", "trip_id": "trip-1", "n": 1,
            "date": "2027-04-01", "title": "Arrival", "energy_target": 2,
            "weather_snapshot": None, "ai_note": None,
            "created_at": None, "updated_at": None,
        }
        db = _make_db(
            trip_row=_TRIP_ROW,
            lists={
                "trip_destinations": [dest_row],
                "trip_days": [day_row],
            },
        )
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.get_trip("trip-1")

        assert len(result.destinations) == 1
        assert result.destinations[0].name == "Kyoto"
        assert len(result.days) == 1
        assert result.days[0].n == 1


# ---------------------------------------------------------------------------
# list_trip_summaries
# ---------------------------------------------------------------------------

class TestListTripSummaries:
    def test_returns_empty_for_user_with_no_trips(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value \
            .order.return_value.order.return_value.execute.return_value \
            = MagicMock(data=[])
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.list_trip_summaries("user-1")
        assert result == []

    def test_returns_summaries_for_user_trips(self):
        summary_rows = [
            {
                "id": "trip-1",
                "title": "Kyoto Spring",
                "status": "dreaming",
                "reference_date": "2027-04-01",
                "vision_summary": "Cherry blossoms",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value \
            .order.return_value.order.return_value.execute.return_value \
            = MagicMock(data=summary_rows)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.list_trip_summaries("user-1")
        assert len(result) == 1
        assert isinstance(result[0], TripSummary)
        assert result[0].title == "Kyoto Spring"


# ---------------------------------------------------------------------------
# upsert_trip
# ---------------------------------------------------------------------------

class TestUpsertTrip:
    def test_insert_new_trip(self):
        """upsert_trip with no 'id' in patch should INSERT and return Trip."""
        inserted_row = {**_TRIP_ROW, "id": "trip-new", "title": "New Trip"}
        db = _make_db(trip_row=inserted_row)
        # Override insert to return the new id
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"id": "trip-new"}])
        db.table.return_value.insert.return_value = insert_chain

        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.upsert_trip("user-1", {"title": "New Trip", "status": "dreaming"})

        assert isinstance(result, Trip)

    def test_update_existing_trip_raises_permission_error_for_wrong_user(self):
        """upsert_trip with 'id' belonging to another user should raise PermissionError."""
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError, match="belongs to a different user"):
                repo.upsert_trip("user-1", {"id": "trip-1", "title": "Updated"})

    def test_unknown_patch_keys_accepted_and_logged(self, caplog):
        """upsert_trip should accept unknown keys (JSONB flexibility) and log at DEBUG."""
        inserted_row = {**_TRIP_ROW, "id": "trip-new"}
        db = _make_db(trip_row=inserted_row)
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"id": "trip-new"}])
        db.table.return_value.insert.return_value = insert_chain

        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            import logging
            with caplog.at_level(logging.DEBUG, logger="agentic_traveler.tools.trip_repo"):
                repo = TripRepository()
                repo.upsert_trip("user-1", {"status": "dreaming", "unknown_field": "xyz"})

        assert "unknown_field" in caplog.text


# ---------------------------------------------------------------------------
# delete_trip
# ---------------------------------------------------------------------------

class TestDeleteTrip:
    def test_raises_permission_error_for_wrong_user(self):
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError, match="belongs to a different user"):
                repo.delete_trip("trip-1", "user-1")

    def test_raises_permission_error_when_trip_not_found(self):
        db = _make_db(trip_row=None)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError, match="not found"):
                repo.delete_trip("nonexistent", "user-1")

    def test_deletes_owned_trip(self):
        db = _make_db(trip_row=_TRIP_ROW)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            repo.delete_trip("trip-1", "user-1")  # should not raise
        # Verify delete() was invoked by checking table was called with 'trips'
        called_table_names = [c.args[0] for c in db.table.call_args_list]
        assert "trips" in called_table_names


# ---------------------------------------------------------------------------
# Child upserts — ownership enforcement
# ---------------------------------------------------------------------------

class TestChildUpserts:
    def test_upsert_destination_raises_for_wrong_user(self):
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError):
                repo.upsert_destination("trip-1", "user-1", {"name": "Tokyo"})

    def test_upsert_booking_raises_for_wrong_user(self):
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError):
                repo.upsert_booking("trip-1", "user-1", {"kind": "flight"})

    def test_upsert_day_block_raises_for_wrong_user(self):
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError):
                repo.upsert_day_block(
                    "trip-1", "user-1",
                    {"day_id": "day-1", "title": "Walk", "ord": 0},
                )

    def test_upsert_checklist_item_raises_for_wrong_user(self):
        wrong_owner_row = {**_TRIP_ROW, "user_id": "user-OTHER"}
        db = _make_db(trip_row=wrong_owner_row)
        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError):
                repo.upsert_checklist_item(
                    "trip-1", "user-1",
                    {"scope": "packing", "label": "Sunscreen"},
                )

    def test_upsert_destination_calls_trip_destinations_table(self):
        """Verify the correct table is targeted on a successful upsert."""
        dest_result = {
            "id": "dest-1", "trip_id": "trip-1", "name": "Kyoto",
            "iso_country": "JP", "status": "considering", "ord": 0,
            "created_at": None, "updated_at": None,
        }

        # Build a db where the ownership check returns the owned trip
        # and the upsert on trip_destinations returns dest_result.
        db = MagicMock()

        def _table_dispatch(table_name):
            tbl = MagicMock()
            if table_name == "trips":
                # ownership check: .select().eq().maybe_single().execute()
                sel = MagicMock()
                eq = MagicMock()
                ms = MagicMock()
                ms.execute.return_value = MagicMock(data=_TRIP_ROW)
                eq.maybe_single.return_value = ms
                sel.eq.return_value = eq
                tbl.select.return_value = sel
                # _touch_parent: .update().eq().execute()
                upd = MagicMock()
                upd.eq.return_value = upd
                upd.execute.return_value = MagicMock(data=[])
                tbl.update.return_value = upd
            elif table_name == "trip_destinations":
                # _assert_child_owner check: .select().eq().maybe_single().execute()
                # returns None (new destination, so it doesn't belong to another trip)
                sel = MagicMock()
                eq = MagicMock()
                ms = MagicMock()
                ms.execute.return_value = MagicMock(data=None)
                eq.maybe_single.return_value = ms
                sel.eq.return_value = eq
                tbl.select.return_value = sel
                # upsert:
                upsert_chain = MagicMock()
                upsert_chain.execute.return_value = MagicMock(data=[dest_result])
                tbl.upsert.return_value = upsert_chain
            return tbl

        db.table.side_effect = _table_dispatch

        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            result = repo.upsert_destination(
                "trip-1", "user-1", {"name": "Kyoto", "iso_country": "JP"}
            )

        assert isinstance(result, TripDestination)
        assert result.name == "Kyoto"
        assert result.trip_id == "trip-1"

    def test_upsert_destination_raises_when_id_belongs_to_other_trip(self):
        """Verify upsert_destination raises PermissionError if the target id belongs to another trip."""
        db = MagicMock()

        def _table_dispatch(table_name):
            tbl = MagicMock()
            if table_name == "trips":
                # ownership check for parent trip (trip-1): owned by user-1
                sel = MagicMock()
                eq = MagicMock()
                ms = MagicMock()
                ms.execute.return_value = MagicMock(data=_TRIP_ROW)
                eq.maybe_single.return_value = ms
                sel.eq.return_value = eq
                tbl.select.return_value = sel
            elif table_name == "trip_destinations":
                # child ownership check: select("trip_id").eq("id", "dest-1").maybe_single().execute()
                # Should return a row with a different trip_id (trip-OTHER)
                sel = MagicMock()
                eq = MagicMock()
                ms = MagicMock()
                ms.execute.return_value = MagicMock(data={"trip_id": "trip-OTHER"})
                eq.maybe_single.return_value = ms
                sel.eq.return_value = eq
                tbl.select.return_value = sel
            return tbl

        db.table.side_effect = _table_dispatch

        with patch("agentic_traveler.tools.trip_repo.get_db", return_value=db):
            repo = TripRepository()
            with pytest.raises(PermissionError, match="belongs to a different trip"):
                repo.upsert_destination("trip-1", "user-1", {"id": "dest-1", "name": "Kyoto"})


# ---------------------------------------------------------------------------
# Integration test (skipped without _INTEGRATION_TESTS=1)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTripRepositoryIntegration:
    """
    End-to-end smoke test against the real Supabase project.
    Marks all rows with a _test=true convention in scratchpad for cleanup.
    Run with:
        $env:_INTEGRATION_TESTS="1"
        python -m pytest backend/tests -m integration -v
    """

    def test_full_round_trip(self):
        """
        Create a trip, upsert destination + booking + day + two day blocks,
        read back via get_trip, assert round-trip, call derive_saga_state.
        """
        import os
        if not os.getenv("_INTEGRATION_TESTS"):
            pytest.skip("Integration tests require _INTEGRATION_TESTS=1")

        # Import real client (env must have SUPABASE_URL + SUPABASE_SERVICE_KEY)
        from agentic_traveler.tools.db_client import get_db
        from agentic_traveler.tools.trip_repo import TripRepository

        repo = TripRepository()
        db = get_db()

        # 1. Create a test user (use a real existing user_id from your project)
        user_id = os.environ["_TEST_USER_ID"]

        # 2. Create trip
        trip = repo.upsert_trip(user_id, {
            "title": "Integration Test Trip — DELETE ME",
            "status": "dreaming",
            "scratchpad": {"_test": True},
        })
        trip_id = trip.id

        try:
            # 3. Upsert destination
            dest = repo.upsert_destination(trip_id, user_id, {
                "name": "Tokyo", "iso_country": "JP", "status": "considering",
            })
            assert dest.name == "Tokyo"

            # 4. Upsert a flight booking
            booking = repo.upsert_booking(trip_id, user_id, {
                "kind": "flight",
                "payload": {"airline": "JAL", "flight": "JL402"},
                "confirmation_code": "XYZ123",
            })
            assert booking.kind == "flight"

            # 5. Upsert day
            day = repo.upsert_day(trip_id, user_id, {
                "n": 1, "date": "2027-04-01", "title": "Arrival Day",
            })
            assert day.n == 1

            # 6. Upsert two day blocks
            repo.upsert_day_block(trip_id, user_id, {
                "day_id": day.id, "ord": 0,
                "time_slot": "morning", "title": "Ramen breakfast",
                "type": "food",
            })
            repo.upsert_day_block(trip_id, user_id, {
                "day_id": day.id, "ord": 1,
                "time_slot": "afternoon", "title": "Senso-ji Temple",
                "type": "culture",
            })

            # 7. Read back full trip
            full = repo.get_trip(trip_id)
            assert full is not None
            assert full.id == trip_id
            assert len(full.destinations) == 1
            assert len(full.bookings) == 1
            assert len(full.days) == 1
            assert len(full.day_blocks) == 2
            assert full.destinations[0].name == "Tokyo"
            assert full.bookings[0].confirmation_code == "XYZ123"

            # 8. Call derive_saga_state RPC
            rpc_resp = db.rpc("derive_saga_state", {"p_trip_id": trip_id}).execute()
            state = rpc_resp.data
            # Bookings exist → DETAILING
            assert state == "DETAILING"

        finally:
            # 9. Cleanup — delete the test trip (cascades to all children)
            repo.delete_trip(trip_id, user_id)
            orphan = repo.get_trip(trip_id)
            assert orphan is None
