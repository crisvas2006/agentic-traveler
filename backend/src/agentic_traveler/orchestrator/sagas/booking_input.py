"""
Booking Input Saga
Handles the B3 hybrid booking input flow (paste -> parse -> confirm -> insert).
"""

import logging
from typing import Any

from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.sagas.base import BaseSaga, SagaResult, SlotRequest, ChoiceOption
from agentic_traveler.tools.booking_parser import parse_booking

logger = logging.getLogger(__name__)

class BookingInputSaga(BaseSaga):
    name = "BookingInputSaga"

    def should_activate(self, intent: str, entities: dict[str, Any], trip: dict[str, Any] | None, state: dict[str, Any]) -> tuple[bool, bool]:
        # Activate if router extracted booking_shaped
        if entities.get("booking_shaped"):
            return True, True
        
        # Or if state has pending extraction awaiting confirmation
        if state.get("pending_booking_extraction"):
            return True, True
            
        return False, False

    @traceable(name="saga.booking_input.run")
    def run(self, message: str, user_doc: dict[str, Any], trip: dict[str, Any] | None, state: dict[str, Any], conv: list[dict], events: Any) -> SagaResult:
        events.emit("metric", {"name": "saga_entered", "saga": self.name})

        # Turn 2: Waiting for confirmation
        pending = state.get("pending_booking_extraction")
        if pending:
            # Reclassify yes/no (simple lowercase check for now since router intent might just be CHAT)
            msg_lower = message.lower()
            if msg_lower in ("yes", "y", "confirm", "add it", "sure", "ok"):
                from agentic_traveler.tools.trip_repo import TripRepository
                
                repo = TripRepository()
                kind = pending.get("booking_kind", "activity")
                
                # Default to current date if missing so it has something
                from datetime import datetime
                dt = pending.get(kind, {}).get("datetime_local") or pending.get(kind, {}).get("depart_local") or pending.get(kind, {}).get("check_in") or datetime.now().isoformat()
                
                # Find trip to attach to (or create DREAMING trip if none)
                # For now, attach to the in-focus trip if it exists, otherwise create
                user_id = user_doc["id"]
                if trip:
                    trip_id = trip["id"]
                else:
                    new_trip = repo.upsert_trip(user_id, {"status": "DREAMING", "title": f"Trip for {kind}"})
                    trip_id = new_trip.id

                conf_code = pending.get(kind, {}).get("confirmation_code")
                
                payload = {
                    "kind": kind,
                    **pending.get(kind, {}),
                    "notes": pending.get("fallback_notes")
                }
                
                try:
                    repo.upsert_booking(trip_id=trip_id, kind=kind, payload=payload, datetime_local=dt, confirmation_code=conf_code)
                    events.emit("metric", {"name": "booking_confirmed"})
                    text = "Added to your trip! You can edit the details in the logistics rail."
                except Exception:
                    logger.exception("Failed to upsert booking")
                    text = "I encountered an error saving that booking."
                
                # Clear state
                return SagaResult(text=text, state_delta={"pending_booking_extraction": None})
                
            elif msg_lower in ("no", "n", "cancel", "nevermind", "stop"):
                events.emit("metric", {"name": "booking_rejected"})
                return SagaResult(text="Okay, I won't save that booking.", state_delta={"pending_booking_extraction": None})
            else:
                # Ambiguous, re-ask
                return SagaResult(
                    text="Did you want to add that booking to your trip? Yes or No.",
                    slot_request=SlotRequest(
                        slot="booking_confirm",
                        prompt="Add this booking?",
                        choices=[
                            ChoiceOption("yes", "Yes, add it", "Yes"),
                            ChoiceOption("no", "No, cancel", "No"),
                        ]
                    )
                )

        # Turn 1: Parse the message
        extraction, raw_response = parse_booking(message)
        
        if extraction.confidence < 0.5:
            events.emit("metric", {"name": "booking_parse_low_confidence"})
            text = "I couldn't quite parse that booking — paste the basics or describe it and I'll save it as a note."
            return SagaResult(text=text, _raw_response=raw_response)
            
        # Summarize
        k = extraction.booking_kind
        detail = extraction.model_dump().get(k, {})
        if k == "flight":
            summary = f"{detail.get('airline', '')} {detail.get('number', '')} {detail.get('from_', '')} → {detail.get('to', '')}".strip()
        elif k == "accommodation":
            summary = f"{detail.get('name', 'Hotel')} check-in {detail.get('check_in', '')}".strip()
        elif k == "ground":
            summary = f"Transit {detail.get('from_', '')} → {detail.get('to', '')}".strip()
        else:
            summary = detail.get("name", "Reservation")
            
        text = f"Found {k}: {summary}. Add it?"
        
        return SagaResult(
            text=text,
            state_delta={"pending_booking_extraction": extraction.model_dump()},
            slot_request=SlotRequest(
                slot="booking_confirm",
                prompt=text,
                choices=[
                    ChoiceOption("yes", "Yes, add it", "Yes"),
                    ChoiceOption("no", "No, cancel", "No"),
                ]
            ),
            _raw_response=raw_response
        )
