"""
CountryIntelSaga — Background fetcher for country safety, visa, health, etc.
"""

import asyncio
import logging
from typing import Any, Optional, Tuple

from agentic_traveler.analytics import metrics_tracker
from agentic_traveler.economy import credit_manager
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.sagas.base import BaseSaga, SagaState, SagaResult
from agentic_traveler.tools.country_intel_fetcher import fetch_country_intel
from agentic_traveler.tools.trip_repo import TripRepository
from agentic_traveler.tools.user_repo import UserRepository

logger = logging.getLogger(__name__)

class CountryIntelSaga(BaseSaga):
    name = "CountryIntelSaga"

    def __init__(self, client: Any = None):
        self._client = client

    def should_activate(
        self,
        intent: str,
        entities: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
    ) -> Tuple[bool, bool]:
        """Return (can_act, wants_to_own)."""
        # Listen for newly confirmed destinations in this turn.
        side_effects = entities.get("side_effects_seen", [])
        if any(s.get("kind") == "destination_upsert" and s.get("payload", {}).get("status") == "confirmed" for s in side_effects):
            return True, False
            
        # Also check if destination_just_confirmed boolean is passed
        if any(s.get("destination_just_confirmed") for s in side_effects):
            return True, False

        # Owner: when the user explicitly asks an intel question
        if entities.get("intel_question"):
            return True, True

        return False, False

    @traceable(name="saga.country_intel.run")
    def run(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conv: dict[str, Any],
        events: Any,
    ) -> SagaResult:
        activation_mode = state.get("activation_mode")
        
        if activation_mode == "owner":
            return self._answer_question(message, user_doc, trip, state, conv, events)
            
        # It's running as a listener
        self._fetch_for_confirmed_destination(message, user_doc, trip, state, conv, events)
        return SagaResult()

    def _answer_question(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conv: dict[str, Any],
        events: Any,
    ) -> SagaResult:
        # Handle explicit question: could do a live fetch or use existing intel
        # For simplicity, if we have a trip, we trigger an async refresh on the first confirmed destination
        if trip:
            destinations = trip.get("destinations", [])
            confirmed = [d for d in destinations if d.get("status") == "confirmed" and d.get("iso_country")]
            if confirmed:
                logger.info("CountryIntelSaga (owner) triggering refresh for %s", confirmed[0]["name"])
                # We do this asynchronously so we can return a response to the user immediately
                asyncio.create_task(
                    self._run_fetch_async(
                        trip["id"],
                        user_doc["id"],
                        confirmed[0]["iso_country"],
                        confirmed[0]["name"],
                        month_name=self._get_trip_month(trip),
                    )
                )
                
                return SagaResult(text=f"I'll check the latest facts for {confirmed[0]['name']}. The intel strip will update shortly.")
        
        return SagaResult(text="I can look up travel facts for you. Which country are you planning to visit?")

    def _fetch_for_confirmed_destination(
        self,
        message: str,
        user_doc: dict[str, Any],
        trip: Optional[dict[str, Any]],
        state: SagaState,
        conv: dict[str, Any],
        events: list[Any],
    ) -> None:
        if not trip:
            return

        side_effects = state.get("side_effects", [])
        confirmed = []
        for s in side_effects:
            if s.get("kind") == "destination_upsert":
                payload = s.get("payload", {})
                if payload.get("status") == "confirmed" and payload.get("iso_country"):
                    confirmed.append(payload)

        month_name = self._get_trip_month(trip)

        # Run async fetch
        for dest in confirmed:
            logger.info("CountryIntelSaga (listener) queueing fetch for %s", dest["name"])
            asyncio.create_task(
                self._run_fetch_async(
                    trip["id"],
                    user_doc["id"],
                    dest["iso_country"],
                    dest["name"],
                    month_name,
                )
            )

    async def _run_fetch_async(self, trip_id: str, user_id: str, iso_country: str, country_name: str, month_name: str):
        """Runs the fetch synchronously inside the executor."""
        loop = asyncio.get_running_loop()
        
        # Double check credits right before the heavy LLM operation
        user_repo = UserRepository()
        user_doc = await loop.run_in_executor(None, user_repo.get_user_by_id, user_id)
        if not user_doc or not credit_manager.has_credits(user_doc):
            logger.info("CountryIntelSaga skipping fetch for %s due to 0 credits", user_id)
            return

        try:
            snapshot = await loop.run_in_executor(
                None,
                fetch_country_intel,
                iso_country,
                country_name,
                month_name,
            )
            
            # Pop token records and bill the user
            token_records = snapshot.pop("_token_records", [])
            if token_records:
                try:
                    await loop.run_in_executor(
                        None,
                        credit_manager.record_usage_and_bill,
                        user_id,
                        token_records,
                        "country_intel",
                        False # Since we are already in executor, we don't want a background thread
                    )
                except Exception:
                    logger.exception("Failed to bill for country intel fetch")
            
            repo = TripRepository()
            await loop.run_in_executor(
                None,
                repo.upsert_country_intel,
                trip_id,
                user_id,
                snapshot,
            )
            
            metrics_tracker.record_event(
                "country_intel_fetched",
                user_id=user_id,
                trip_id=trip_id,
                payload={"iso_country": iso_country},
            )
        except Exception:
            logger.exception("Async fetch failed for %s", country_name)
            metrics_tracker.record_event(
                "error_raised",
                user_id=user_id,
                trip_id=trip_id,
                payload={"scope": "country_intel_saga", "error_class": "fetch_failed"},
            )

    def _get_trip_month(self, trip: dict[str, Any]) -> str:
        """Extract the month from the trip timeframe or default to 'any'."""
        timeframe = trip.get("discovery", {}).get("timeframe", {})
        start_date = timeframe.get("start_date")
        if start_date:
            try:
                import datetime
                dt = datetime.datetime.fromisoformat(start_date)
                return dt.strftime("%B")
            except Exception:
                pass
        return "any month"
