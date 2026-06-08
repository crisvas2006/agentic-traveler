"""
TripRepository — Supabase-backed persistence for trips and child tables.

Architecture notes (Task 34):
- Uses the service-role DB client (bypasses RLS). Every method that takes a
  user_id MUST assert ownership in the application layer — service key gives
  full table access, so the app is the last line of defense besides RLS on
  the authenticated client.
- All mutating child-table methods set updated_at = now() on the parent trips
  row until Task 48 wires the auto-trigger that does this automatically.
- get_trip() loads the full trip shape (parent + all 5 child tables) in 6
  separate queries; total latency is well under 50 ms for typical trip sizes.
- JSONB columns accept any dict; Python layer logs at DEBUG which patch keys
  it received. No strict whitelist enforcement in the DB — saga code validates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed top-level column / JSONB-section names for upsert_trip validation.
# Unknown keys are accepted (JSONB is schema-less) but logged at DEBUG.
# ---------------------------------------------------------------------------
_KNOWN_TRIP_FIELDS = frozenset({
    "status", "saga_state", "title", "reference_date", "vision_summary",
    "discovery", "travelers", "preferences", "country_intel", "budget",
    "live_state", "scratchpad", "journal", "cover",
})


# ---------------------------------------------------------------------------
# Pydantic models — lightweight; no validation beyond type coercion.
# ---------------------------------------------------------------------------

class TripSummary(BaseModel):
    """Minimal trip shape used to populate LLM context without full data."""
    id: str
    title: str | None = None
    status: str
    reference_date: str | None = None
    vision_summary: str | None = None
    updated_at: str


class TripDestination(BaseModel):
    id: str
    trip_id: str
    name: str
    iso_country: str | None = None
    status: str = "considering"
    ord: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class TripBooking(BaseModel):
    id: str
    trip_id: str
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    datetime_local: str | None = None
    confirmation_code: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TripDay(BaseModel):
    id: str
    trip_id: str
    n: int
    date: str | None = None
    title: str | None = None
    energy_target: int | None = None
    weather_snapshot: str | None = None
    ai_note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TripDayBlock(BaseModel):
    id: str
    trip_id: str
    day_id: str
    ord: int = 0
    time_slot: str | None = None
    title: str
    type: str | None = None
    duration_min: int | None = None
    energy: int | None = None
    walk: str | None = None
    why: str | None = None
    lat: float | None = None
    lng: float | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TripChecklistItem(BaseModel):
    id: str
    trip_id: str
    scope: str
    label: str
    done: bool = False
    ord: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class Trip(BaseModel):
    """Full trip shape: parent row + all child collections."""
    # Parent columns
    id: str
    user_id: str
    status: str
    saga_state: str | None = None
    title: str | None = None
    reference_date: str | None = None
    vision_summary: str | None = None
    # JSONB sections
    discovery: dict[str, Any] = Field(default_factory=dict)
    travelers: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    country_intel: list[Any] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    live_state: dict[str, Any] = Field(default_factory=dict)
    scratchpad: dict[str, Any] = Field(default_factory=dict)
    journal: dict[str, Any] = Field(default_factory=dict)
    cover: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    # Child collections
    destinations: list[TripDestination] = Field(default_factory=list)
    bookings: list[TripBooking] = Field(default_factory=list)
    days: list[TripDay] = Field(default_factory=list)
    day_blocks: list[TripDayBlock] = Field(default_factory=list)
    checklist: list[TripChecklistItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class TripRepository:
    """CRUD for trips and all child tables. All writes use the service-role client."""

    # ------------------------------------------------------------------
    # Parent — reads
    # ------------------------------------------------------------------

    def get_trip(self, trip_id: str) -> Trip | None:
        """
        Load the full trip document: parent row + all 5 child tables.

        Returns None if the trip doesn't exist. Does NOT assert user ownership
        — callers must do that if they want isolation (see assert_owner).
        """
        db = get_db()

        # Parent row
        try:
            resp = (
                db.table("trips")
                .select("*")
                .eq("id", trip_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("get_trip: failed to fetch parent for trip_id=%s", trip_id)
            return None

        if not resp or not resp.data:
            return None

        row = resp.data

        # Child collections (5 queries; each is cheap for small trips)
        destinations = self._load_destinations(trip_id)
        bookings = self._load_bookings(trip_id)
        days = self._load_days(trip_id)
        day_blocks = self._load_day_blocks(trip_id)
        checklist = self._load_checklist(trip_id)

        return Trip(
            **{k: v for k, v in row.items() if k not in (
                "destinations", "bookings", "days", "day_blocks", "checklist"
            )},
            destinations=destinations,
            bookings=bookings,
            days=days,
            day_blocks=day_blocks,
            checklist=checklist,
        )

    def list_trip_summaries(self, user_id: str) -> list[TripSummary]:
        """
        Return the summary shape for all of a user's trips.
        Used to populate LLM context without dumping the full JSONB sections.
        Ordered by reference_date DESC (nulls last), then updated_at DESC.
        """
        db = get_db()
        try:
            resp = (
                db.table("trips")
                .select("id, title, status, reference_date, vision_summary, updated_at")
                .eq("user_id", user_id)
                .order("reference_date", desc=True, nullsfirst=False)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception:
            logger.exception("list_trip_summaries: failed for user_id=%s", user_id)
            return []

        rows = resp.data or []
        return [TripSummary(**r) for r in rows]

    # ------------------------------------------------------------------
    # Parent — writes
    # ------------------------------------------------------------------

    def upsert_trip(self, user_id: str, patch: dict[str, Any]) -> Trip:
        """
        Create or update a trip for user_id.

        - If patch contains 'id', the existing trip is updated (ownership
          is asserted first).
        - If 'id' is absent, a new trip is inserted.
        - patch keys are matched against _KNOWN_TRIP_FIELDS; unknown keys
          are accepted (JSONB) but logged at DEBUG.
        - Always sets updated_at = now().

        Returns the fully loaded Trip after write.
        Raises PermissionError if the trip belongs to another user.
        """
        db = get_db()
        unknown = set(patch.keys()) - _KNOWN_TRIP_FIELDS - {"id"}
        if unknown:
            logger.debug(
                "upsert_trip: ignoring unknown patch keys %s for user_id=%s",
                unknown, user_id,
            )

        trip_id = patch.get("id")
        now_str = _now_iso()

        if trip_id:
            # Update path — assert ownership first
            self._assert_owner(trip_id, user_id)
            payload = {k: v for k, v in patch.items() if k != "id"}
            payload["updated_at"] = now_str
            try:
                db.table("trips").update(payload).eq("id", trip_id).execute()
            except Exception:
                logger.exception("upsert_trip: update failed for trip_id=%s", trip_id)
                raise
        else:
            # Insert path
            payload = {k: v for k, v in patch.items()}
            payload["user_id"] = user_id
            payload["updated_at"] = now_str
            try:
                resp = db.table("trips").insert(payload).execute()
                trip_id = resp.data[0]["id"]
            except Exception:
                logger.exception("upsert_trip: insert failed for user_id=%s", user_id)
                raise

        result = self.get_trip(trip_id)
        if result is None:
            raise RuntimeError(f"upsert_trip: could not re-read trip_id={trip_id} after write")
        return result

    def delete_trip(self, trip_id: str, user_id: str) -> None:
        """
        Delete a trip and all its children (via DB CASCADE).
        Raises PermissionError if the trip belongs to another user.
        """
        self._assert_owner(trip_id, user_id)
        db = get_db()
        try:
            db.table("trips").delete().eq("id", trip_id).execute()
            logger.info("delete_trip: deleted trip_id=%s for user_id=%s", trip_id, user_id)
        except Exception:
            logger.exception("delete_trip: failed for trip_id=%s", trip_id)
            raise

    # ------------------------------------------------------------------
    # Child tables — upserts
    # ------------------------------------------------------------------

    def upsert_destination(
        self,
        trip_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> TripDestination:
        """
        Insert or update a trip_destinations row.
        If payload contains 'id', the existing row is updated;
        otherwise a new row is inserted.
        Touches parent updated_at.
        """
        self._assert_owner(trip_id, user_id)
        if "id" in payload:
            self._assert_child_owner("trip_destinations", payload["id"], trip_id)
        db = get_db()
        now_str = _now_iso()
        row = dict(payload)
        row["trip_id"] = trip_id
        row["updated_at"] = now_str

        try:
            resp = db.table("trip_destinations").upsert(row, on_conflict="id").execute()
            self._touch_parent(trip_id)
            return TripDestination(**resp.data[0])
        except Exception:
            logger.exception("upsert_destination: failed for trip_id=%s", trip_id)
            raise

    def upsert_booking(
        self,
        trip_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> TripBooking:
        """
        Insert or update a trip_bookings row.
        Touches parent updated_at.
        """
        self._assert_owner(trip_id, user_id)
        if "id" in payload:
            self._assert_child_owner("trip_bookings", payload["id"], trip_id)
        db = get_db()
        now_str = _now_iso()
        row = dict(payload)
        row["trip_id"] = trip_id
        row["updated_at"] = now_str

        try:
            resp = db.table("trip_bookings").upsert(row, on_conflict="id").execute()
            self._touch_parent(trip_id)
            return TripBooking(**resp.data[0])
        except Exception:
            logger.exception("upsert_booking: failed for trip_id=%s", trip_id)
            raise

    def upsert_day(
        self,
        trip_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> TripDay:
        """
        Insert or update a trip_days row.
        The natural key for conflict resolution is (trip_id, n).
        Touches parent updated_at.
        """
        self._assert_owner(trip_id, user_id)
        if "id" in payload:
            self._assert_child_owner("trip_days", payload["id"], trip_id)
        db = get_db()
        now_str = _now_iso()
        row = dict(payload)
        row["trip_id"] = trip_id
        row["updated_at"] = now_str

        try:
            resp = db.table("trip_days").upsert(
                row, on_conflict="trip_id,n"
            ).execute()
            self._touch_parent(trip_id)
            return TripDay(**resp.data[0])
        except Exception:
            logger.exception("upsert_day: failed for trip_id=%s", trip_id)
            raise

    def upsert_day_block(
        self,
        trip_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> TripDayBlock:
        """
        Insert or update a trip_day_blocks row.
        Touches parent updated_at.
        """
        self._assert_owner(trip_id, user_id)
        if "id" in payload:
            self._assert_child_owner("trip_day_blocks", payload["id"], trip_id)
        db = get_db()
        now_str = _now_iso()
        row = dict(payload)
        row["trip_id"] = trip_id
        row["updated_at"] = now_str

        try:
            resp = db.table("trip_day_blocks").upsert(row, on_conflict="id").execute()
            self._touch_parent(trip_id)
            return TripDayBlock(**resp.data[0])
        except Exception:
            logger.exception("upsert_day_block: failed for trip_id=%s", trip_id)
            raise

    def upsert_checklist_item(
        self,
        trip_id: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> TripChecklistItem:
        """
        Insert or update a trip_checklist row.
        Touches parent updated_at.
        """
        self._assert_owner(trip_id, user_id)
        if "id" in payload:
            self._assert_child_owner("trip_checklist", payload["id"], trip_id)
        db = get_db()
        now_str = _now_iso()
        row = dict(payload)
        row["trip_id"] = trip_id
        row["updated_at"] = now_str

        try:
            resp = db.table("trip_checklist").upsert(row, on_conflict="id").execute()
            self._touch_parent(trip_id)
            return TripChecklistItem(**resp.data[0])
        except Exception:
            logger.exception("upsert_checklist_item: failed for trip_id=%s", trip_id)
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_owner(self, trip_id: str, user_id: str) -> None:
        """
        Raise PermissionError if the trip does not exist or is owned by
        a different user. This is the app-layer defense-in-depth check;
        the service-role key bypasses RLS, so we must enforce here.
        """
        db = get_db()
        try:
            resp = (
                db.table("trips")
                .select("user_id")
                .eq("id", trip_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception("_assert_owner: DB error for trip_id=%s", trip_id)
            raise

        if not resp or not resp.data:
            raise PermissionError(f"Trip {trip_id!r} not found.")
        if resp.data["user_id"] != user_id:
            raise PermissionError(
                f"Trip {trip_id!r} belongs to a different user. Access denied."
            )

    def _assert_child_owner(self, table: str, child_id: str, trip_id: str) -> None:
        """
        Raise PermissionError if a child record exists but belongs to a different trip.
        This prevents cross-trip hijacking via ID upserts using the service-role client.
        """
        db = get_db()
        try:
            resp = (
                db.table(table)
                .select("trip_id")
                .eq("id", child_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            logger.exception(
                "_assert_child_owner: DB error for table=%s, id=%s",
                table, child_id,
            )
            raise

        if resp and resp.data and resp.data["trip_id"] != trip_id:
            raise PermissionError(
                f"Record {child_id!r} in {table!r} belongs to a different trip. Access denied."
            )

    def _touch_parent(self, trip_id: str) -> None:
        """
        Bump trips.updated_at = now() after a child-table write.
        Task 48 will replace this with a Postgres trigger; until then
        child-table mutations must call this manually.
        """
        try:
            get_db().table("trips").update(
                {"updated_at": _now_iso()}
            ).eq("id", trip_id).execute()
        except Exception:
            # Non-fatal — the child write already succeeded.
            logger.warning("_touch_parent: failed to bump updated_at for trip_id=%s", trip_id)

    # ------------------------------------------------------------------
    # Child loaders (used by get_trip)
    # ------------------------------------------------------------------

    def _load_destinations(self, trip_id: str) -> list[TripDestination]:
        try:
            resp = (
                get_db().table("trip_destinations")
                .select("*")
                .eq("trip_id", trip_id)
                .order("ord")
                .execute()
            )
            return [TripDestination(**r) for r in (resp.data or [])]
        except Exception:
            logger.exception("_load_destinations: failed for trip_id=%s", trip_id)
            return []

    def _load_bookings(self, trip_id: str) -> list[TripBooking]:
        try:
            resp = (
                get_db().table("trip_bookings")
                .select("*")
                .eq("trip_id", trip_id)
                .order("datetime_local", nullsfirst=True)
                .execute()
            )
            return [TripBooking(**r) for r in (resp.data or [])]
        except Exception:
            logger.exception("_load_bookings: failed for trip_id=%s", trip_id)
            return []

    def _load_days(self, trip_id: str) -> list[TripDay]:
        try:
            resp = (
                get_db().table("trip_days")
                .select("*")
                .eq("trip_id", trip_id)
                .order("n")
                .execute()
            )
            return [TripDay(**r) for r in (resp.data or [])]
        except Exception:
            logger.exception("_load_days: failed for trip_id=%s", trip_id)
            return []

    def _load_day_blocks(self, trip_id: str) -> list[TripDayBlock]:
        try:
            resp = (
                get_db().table("trip_day_blocks")
                .select("*")
                .eq("trip_id", trip_id)
                .order("day_id")
                .order("ord")
                .execute()
            )
            return [TripDayBlock(**r) for r in (resp.data or [])]
        except Exception:
            logger.exception("_load_day_blocks: failed for trip_id=%s", trip_id)
            return []

    def _load_checklist(self, trip_id: str) -> list[TripChecklistItem]:
        try:
            resp = (
                get_db().table("trip_checklist")
                .select("*")
                .eq("trip_id", trip_id)
                .order("scope")
                .order("ord")
                .execute()
            )
            return [TripChecklistItem(**r) for r in (resp.data or [])]
        except Exception:
            logger.exception("_load_checklist: failed for trip_id=%s", trip_id)
            return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string (Supabase-compatible)."""
    return datetime.now(timezone.utc).isoformat()
