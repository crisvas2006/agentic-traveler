"""TripRepository.apply_side_effect routing (Task 36).

Patches the typed upsert methods so we test only the kind → method dispatch,
no DB. Side effects are duck-typed (.kind / .payload)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from agentic_traveler.tools.trip_repo import TripRepository


def _se(kind, payload):
    return SimpleNamespace(kind=kind, payload=payload)


def test_trip_patch_routes_to_upsert_trip():
    repo = TripRepository()
    repo.upsert_trip = MagicMock()
    repo.apply_side_effect("u1", _se("trip_patch", {"id": "t1", "preferences": {"pace": "slow"}}))
    repo.upsert_trip.assert_called_once_with("u1", {"id": "t1", "preferences": {"pace": "slow"}})


def test_destination_upsert_routes_and_strips_trip_id():
    repo = TripRepository()
    repo.upsert_destination = MagicMock()
    repo.apply_side_effect(
        "u1", _se("destination_upsert", {"trip_id": "t1", "name": "Iceland", "status": "considering"})
    )
    repo.upsert_destination.assert_called_once_with(
        "t1", "u1", {"name": "Iceland", "status": "considering"}
    )


def test_booking_upsert_routes_to_upsert_booking():
    repo = TripRepository()
    repo.upsert_booking = MagicMock()
    repo.apply_side_effect("u1", _se("booking_upsert", {"trip_id": "t1", "kind": "flight"}))
    repo.upsert_booking.assert_called_once_with("t1", "u1", {"kind": "flight"})


def test_unknown_kind_is_ignored():
    repo = TripRepository()
    repo.upsert_trip = MagicMock()
    repo.upsert_destination = MagicMock()
    repo.apply_side_effect("u1", _se("mystery", {"trip_id": "t1"}))
    repo.upsert_trip.assert_not_called()
    repo.upsert_destination.assert_not_called()


def test_child_kind_missing_trip_id_is_skipped():
    repo = TripRepository()
    repo.upsert_destination = MagicMock()
    repo.apply_side_effect("u1", _se("destination_upsert", {"name": "Iceland"}))
    repo.upsert_destination.assert_not_called()
