"""
Single-call structured extraction. Uses gemini-3.1-flash-lite with the
SDK's structured-output mode so the model returns valid JSON per a Pydantic
schema we define here. NEVER calls grounded search — bookings are
self-contained text.
"""

import logging
from typing import Literal, Optional, Tuple, Any

from pydantic import BaseModel

from agentic_traveler.orchestrator.client_factory import get_client
from google.genai import types

logger = logging.getLogger(__name__)

class FlightExtraction(BaseModel):
    kind: Literal["outbound", "return", "internal"] = "outbound"
    airline: Optional[str] = None
    number: Optional[str] = None
    from_: Optional[str] = None
    to: Optional[str] = None
    depart_local: Optional[str] = None
    arrive_local: Optional[str] = None
    confirmation_code: Optional[str] = None
    notes: Optional[str] = None

class AccommodationExtraction(BaseModel):
    kind: Literal["accommodation"] = "accommodation"
    name: Optional[str] = None
    address: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    confirmation_code: Optional[str] = None
    notes: Optional[str] = None

class GroundExtraction(BaseModel):
    kind: Literal["ground"] = "ground"
    from_: Optional[str] = None
    to: Optional[str] = None
    datetime_local: Optional[str] = None
    confirmation_code: Optional[str] = None
    notes: Optional[str] = None

class RestaurantExtraction(BaseModel):
    name: Optional[str] = None
    datetime_local: Optional[str] = None
    reservation_status: Optional[str] = None
    notes: Optional[str] = None

class ActivityExtraction(BaseModel):
    name: Optional[str] = None
    datetime_local: Optional[str] = None
    reservation_status: Optional[str] = None
    notes: Optional[str] = None

class BookingExtraction(BaseModel):
    booking_kind: Literal["flight", "accommodation", "ground", "restaurant", "activity"]
    flight: Optional[FlightExtraction] = None
    accommodation: Optional[AccommodationExtraction] = None
    ground: Optional[GroundExtraction] = None
    restaurant: Optional[RestaurantExtraction] = None
    activity: Optional[ActivityExtraction] = None
    confidence: float
    fallback_notes: Optional[str] = None

PROMPT = """\
Parse the booking text into the schema. If unsure of a field, leave null.
Anything that doesn't fit a field, put in fallback_notes verbatim.
Booking text:
<booking_text>
{text}
</booking_text>
"""

def parse_booking(text: str) -> Tuple[BookingExtraction, Any]:
    """
    Parse the booking text using gemini-3.1-flash-lite.
    Returns a tuple of (structured BookingExtraction, raw_response).
    If the model fails or returns garbage, returns a low confidence fallback.
    """
    client = get_client()
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=BookingExtraction,
        temperature=0.0,
        max_output_tokens=256,
        system_instruction="You are a strict data extractor. Extract booking details into the requested JSON schema. Never invent information.",
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=PROMPT.format(text=text),
            config=config,
        )
        if not response.text:
            raise ValueError("Empty response from model")
        
        return BookingExtraction.model_validate_json(response.text), response
    except Exception as e:
        logger.warning(f"Booking parsing failed: {e}")
        # Return a fallback extraction on failure
        fallback = BookingExtraction(
            booking_kind="activity",  # use activity as generic fallback
            confidence=0.0,
            fallback_notes=text[:1000] # clamp to 1000 chars per DB notes limit
        )
        return fallback, None
