# Task 39 — Booking input saga (paste → AI parse → confirm → structured row)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §4.6 (B3 hybrid), §5.4.
> Depends on tasks 34–37.

## 1. Problem Statement

Aletheia has no booking engine and never will (alpha decision). But the
user wants to *bring their bookings in* — a flight confirmation from Wizz
Air, a hotel reservation from Booking.com, a tea-ceremony slot, a train
ticket — so the dashboard can show the flight card, attach it to the right
itinerary day, count down to departure, etc. Two pure approaches both fail:
a fully-structured form is high-friction and abandoned mid-fill; a totally
free-text note can't power any UI. This task lands the **B3 hybrid** with a
**deliberately tight field whitelist** (per the user's decision §4.6):
structured fields the user can fill directly when they want to, free-text
fallback the AI parses (cheap `gemini-3.1-flash-lite`), and a confirmation
turn so the user owns the final structure. Anything outside the whitelist
goes into a single `notes` field — never parsed, never overconstrained.

## 2. Goals & Non-Goals

### Goals

- The user can paste a flight confirmation into chat, see the bot extract
  airline / number / origin / destination / times / confirmation code,
  confirm it, and have a `trip_bookings` row created.
- The user can manually fill a structured form (in the dashboard's
  Logistics rail) for a flight / accommodation / ground / restaurant /
  activity. Fewer than 8 fields per kind.
- Inflight bookings appear as cards in the dashboard, attached visually to
  the relevant itinerary day when the date matches.
- The user can edit any structured field after confirmation — both via chat
  ("change the seat to 14A") and via the UI form.

### Non-Goals

- Parsing PDFs or email attachments — out of scope for alpha (no file
  storage, per user's cost discipline).
- Booking via affiliate links — no.
- Frequent-flyer integration / loyalty point accrual — no.
- Calendar export — defer to a future micro-task.
- Real-time price tracking — no.

## 3. Acceptance Criteria

AC-1. `BookingInputSaga` activates when the router's entity extraction
  sets `booking_shaped=true` OR when the user message matches a regex
  catalog of common booking shapes (flight number `[A-Z]{2,3}\d{2,4}`,
  IATA-pair `[A-Z]{3}-[A-Z]{3}`, "booking confirmation", "reservation",
  "PNR", etc.).

AC-2. The saga calls `gemini-3.1-flash-lite` with a structured-output
  prompt (JSON schema mode) to extract the booking kind + fields. One LLM
  call, ≤ 512 input tokens, ≤ 256 output tokens.

AC-3. The saga's reply is a confirmation turn:
  *"Found a {kind}: {one-line summary}. Add it to your {trip name}
  trip?"* with a yes/no inline button on Telegram and a confirm/edit
  button row on web. Maximum 280 chars.
  (Alignment note, 2026-06-10: reuse the task-43 chip machinery — web
  buttons ride `messages.metadata.ui` via `SlotRequest`/`ui_block_from_wire`,
  Telegram uses the existing inline-keyboard builder in
  `interfaces/routers/telegram.py`. Do NOT invent a parallel button
  mechanism.)

AC-4. On user confirm, a `trip_bookings` row is inserted. On user
  reject or edit, the saga either drops the row (reject) or re-presents
  the structured form for inline edit (edit).

AC-5. The whitelist of fields per kind (matching proposal §4.6 exactly):
  - flight: kind, airline, number, from, to, depart_local, arrive_local,
    confirmation_code, notes (8 fields)
  - accommodation: kind, name, address, check_in, check_out,
    confirmation_code, notes (7 fields)
  - ground: kind, from, to, datetime_local, confirmation_code, notes (6)
  - restaurant: name, datetime_local, reservation_status, notes (4)
  - activity: name, datetime_local, reservation_status, notes (4)

AC-6. Anything the LLM extracted that doesn't fit the whitelist goes into
  `notes` verbatim. No silent loss of pasted data.

AC-7. The dashboard's Logistics rail renders each booking as a small card
  with the kind icon, key fields, and an Edit button.

AC-8. Cards are visually attached to the itinerary day whose date matches
  the booking's `datetime_local` (a thin connecting line in the desktop
  layout; an inline group on mobile).

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/sagas/booking_input.py     [create]
backend/src/agentic_traveler/orchestrator/sagas/dispatcher.py        [modify]
backend/src/agentic_traveler/tools/booking_parser.py                 [create]
backend/src/agentic_traveler/tools/trip_repo.py                      [modify — booking writer/editor]
backend/src/agentic_traveler/orchestrator/router_agent.py            [modify — booking-shape detection]
backend/tests/test_booking_input_saga.py                             [create]
backend/tests/test_booking_parser.py                                 [create]
frontend/src/components/dashboard/LogisticsRail.tsx                  [create]
frontend/src/components/dashboard/BookingCard.tsx                    [create]
frontend/src/components/dashboard/BookingFormSheet.tsx               [create]
frontend/src/components/dashboard/TripDetailPanel.tsx                [modify]
README.md                                                            [modify]
```

## 5. Constraints

- The parser is the cheapest model tier — never `flash`. Output budget
  ≤ 256 tokens. If the model returns more, truncate + log WARN.
- The whitelist is the source of truth. Adding a field requires a spec
  amendment, not a code-only change.
- The saga MUST present a confirmation turn — never auto-insert.
- No file storage; no PDF / image attachments in alpha.
- The Edit button in the UI uses the same JSONB shape — no separate edit
  endpoint.
- `notes` field is text-only and limited to 1 000 chars at the DB layer.

## 6. Edge Cases

- **Ambiguous paste** (could be flight or train) → ask one clarifying
  question, not two: *"Looks like a {best_guess} — is that right?"*
- **Two bookings in one paste** (round-trip with two flight legs) →
  surface as two confirmation cards in one bot reply, user can confirm
  both with a single tap.
- **Already-confirmed duplicate** (same `confirmation_code` already in
  `trip_bookings`) → silently no-op + bot says "already on file."
- **Date in past** → still inserted; the UI shows a faded card "past"
  with no day-attachment.
- **Booking belongs to a different trip than active** → the saga uses
  the booking's `datetime_local` to pick the matching trip (closest
  `[start_date, end_date]`); if none matches, asks the user *"For your
  Iceland trip?"*.
- **No trip exists yet** → the saga creates one in `DREAMING` with the
  destination inferred from the booking.
- **Parser returns garbage / fails schema validation** → the saga falls
  back to "I couldn't parse that — paste the basics and I'll save it as
  a note?" and inserts the raw text into `notes` of a minimal flight/
  accommodation row of `kind="other"` (the schema does NOT have "other"
  for flight/ground — restrict to restaurant/activity as the fallback
  kind so the schema stays clean).

## 7. Implementation Plan

### Step 1 — `booking_parser.py`

```python
"""Single-call structured extraction. Uses gemini-3.1-flash-lite with the
SDK's structured-output mode so the model returns valid JSON per a Pydantic
schema we define here. NEVER calls grounded search — bookings are
self-contained text."""

from pydantic import BaseModel
from typing import Literal, Optional

class FlightExtraction(BaseModel):
    kind: Literal["outbound", "return", "internal"] = "outbound"
    airline: Optional[str]
    number: Optional[str]
    from_: Optional[str]
    to: Optional[str]
    depart_local: Optional[str]
    arrive_local: Optional[str]
    confirmation_code: Optional[str]
    notes: Optional[str]

# Similar Pydantic models for AccommodationExtraction, GroundExtraction,
# RestaurantExtraction, ActivityExtraction.

class BookingExtraction(BaseModel):
    booking_kind: Literal["flight","accommodation","ground","restaurant","activity"]
    flight: Optional[FlightExtraction] = None
    accommodation: Optional[AccommodationExtraction] = None
    ground: Optional[GroundExtraction] = None
    restaurant: Optional[RestaurantExtraction] = None
    activity: Optional[ActivityExtraction] = None
    confidence: float
    fallback_notes: Optional[str]   # anything that didn't fit a field

PROMPT = """\
Parse the booking text into the schema. If unsure of a field, leave null.
Anything that doesn't fit a field, put in fallback_notes verbatim.
Booking text:
{text}
"""

def parse_booking(text: str) -> BookingExtraction:
    # gemini-3.1-flash-lite with response_mime_type="application/json"
    # and the BookingExtraction schema. ~250ms typical.
    ...
```

### Step 2 — `BookingInputSaga`

```python
class BookingInputSaga(BaseSaga):
    name = "BookingInputSaga"

    def should_activate(self, intent, entities, trip, state):
        if entities.get("booking_shaped"): return True, True
        # Also activate as listener if a recent message contained shape
        # tokens but router missed them.
        return False, False

    @traceable(name="saga.booking_input.run")
    def run(self, message, user_doc, trip, state, conv, events):
        events.emit("metric", {"name": "saga_entered", "saga": self.name})
        extraction = parse_booking(message)
        if extraction.confidence < 0.5:
            text = "I couldn't parse that — paste the basics or describe it?"
            events.emit("metric", {"name": "booking_parse_low_confidence"})
            return SagaResult(text=text)
        summary = _summarize(extraction)
        # Stash in state, await user yes/no in next turn
        return SagaResult(
            text=f"Found {extraction.booking_kind}: {summary}. Add it?",
            state_delta={"pending_booking_extraction": extraction.model_dump()},
        )
```

A second saga turn handles the user's confirmation; on "yes" it writes via
`trip_repo.upsert_booking`. The saga's state is the in-flight extraction.

### Step 3 — Trip repo

```python
def upsert_booking(trip_id: str, kind: str, payload: dict,
                   datetime_local: str | None, confirmation_code: str | None) -> dict:
    # If confirmation_code matches existing row -> update; else insert.
```

### Step 4 — UI: `LogisticsRail` + `BookingCard` + `BookingFormSheet`

`LogisticsRail`:
- Grouped collapsible sections: Flights, Stays, Transit, Restaurants,
  Activities.
- Each empty section shows a tiny `+ Add flight` ghost CTA (per
  progressive disclosure rules).
- Each section, when populated, shows BookingCards.

`BookingCard`:
- Kind icon + line-1 (e.g., "LH716 · MUC → KIX") + line-2 (date / hotel
  address / restaurant name).
- Tap → opens `BookingFormSheet` (read-mode by default with an Edit
  button).

`BookingFormSheet`:
- Structured form matching the whitelist for the booking's kind.
- `notes` is a single textarea at the bottom.
- Save → calls a Next.js Route Handler that PATCHes the row via the
  backend.

### Step 5 — Visual attachment to itinerary day

The dashboard's day accordion includes a small "Linked bookings" strip at
the top of each day when `trip_bookings.datetime_local::date` matches the
day's `date`. On desktop, draw a 1px gradient line from the day card to
the booking card. On mobile, group inline.

### Step 6 — Tests

`test_booking_parser.py`: ten realistic paste samples (flight, hotel,
train, restaurant, activity), assert correct kind + filled fields + that
nothing valuable went silently missing.

`test_booking_input_saga.py`: state-machine across two turns (paste →
confirm); duplicate-confirmation-code → no-op; low-confidence path.

## 8. Testing Plan

- **Unit:** parser per-kind correctness; saga state across two turns;
  whitelist enforcement (extra extracted fields routed to notes).
- **Integration:** end-to-end "paste this Wizz Air confirmation" flow
  against real Supabase + mocked Gemini.
- **Manual:** paste samples from Wizz Air, Lufthansa, Booking.com,
  Airbnb, Trenitalia, OpenTable — verify each parses sensibly.
- **Manual mobile + desktop:** Logistics rail layout, BookingFormSheet
  usability, day-attachment visual.

Sample expected output:

```
User: "PNR: ABC123, LH716, MUC→KIX, Dec 15 11:25am → Dec 16 6:55am"
Bot:  "Found flight: LH716 MUC → KIX, Dec 15. Add it?"  (33 chars excl. q-mark)
```

## 9. Conditional Sections

### 9.2 LLM Considerations

- Model: `gemini-3.1-flash-lite`, JSON-mode response.
- Token budget: input ≤ 512, output ≤ 256.
- Prompt injection: message text is the parser input — fully fenced
  in the prompt with `<booking_text>...</booking_text>`. Model is
  instructed to output JSON only.
- Output handling: parsed via Pydantic; any validation failure → low
  confidence + fallback.
- Tool versioning: `BookingExtraction` schema versioned in the row
  payload (`payload._schema_version: 1`).

### 9.3 Observability

- Metrics: `booking_parsed`, `booking_confirmed`, `booking_rejected`,
  `booking_edited`, `booking_parse_low_confidence`.
- LangSmith trace per parse.

### 9.4 Rollback Plan

- Remove the saga from the dispatcher; existing bookings remain in
  `trip_bookings`. UI's Logistics rail can be feature-flagged off.

## 10. Findings & Follow-ups

(Populated during implementation.)

## 11. Definition of Done

- [ ] ACs 1–8 pass.
- [ ] Unit + integration tests pass.
- [ ] Mobile + desktop verified.
- [ ] README documents the booking input feature.

## Manual operations (user, post-implementation)

1. Provide 10 sanitized paste samples (real bookings with PII redacted)
   as a fixtures file. The parser test suite asserts each parses correctly.
