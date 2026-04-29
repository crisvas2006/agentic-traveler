# Task 27 — Flight Search Tool Integration

**Status:** 🔲 Planned

---

## Goal

Give users real flight price data directly inside the Agentic Traveler conversation — no more "go check Skyscanner yourself." Users asking about ticket costs or trying to estimate a trip budget should get an immediate, accurate ballpark without leaving the chat.

This covers the two most common flight-related questions:
1. *"How much does a return flight from Bucharest to Bali cost in May?"* — price estimate from cached data
2. *"Find me specific flights on May 15th"* — real-time availability (Phase 2 / Amadeus)

---

## Architecture Overview — Two-Tier Design

The flight tool follows the same pattern as `check_weather`: a **direct orchestrator tool** (not a sub-agent). The LLM calls it, gets structured text back, and synthesises a natural reply.

```
User: "How much is OTP → DPS in May?"
  → Orchestrator LLM → calls get_flight_price_estimate(origin="OTP", destination="DPS", month="2026-05")
  → TravelpayoutsService → GET /v2/prices/latest or /v2/prices/month-matrix
  → formats top 3 options (price, airline, stops, duration)
  → LLM presents result conversationally
```

### Why not Google Flights?
Google's QPX Express API was discontinued in 2018. All "Google Flights APIs" on the market (SerpAPI, Scrapeless, etc.) are paid third-party scrapers — they violate Google's ToS and carry maintenance risk when Google changes its layout. Not suitable as a foundation.

### Provider selection rationale

| Provider | Cost | Data type | Why chosen / not |
|---|---|---|---|
| **Travelpayouts (Aviasales)** | Free (affiliate token) | Cached prices from last 48h of real searches | ✅ Phase 1 — zero cost, instant signup, clean REST API |
| **Amadeus** | Free quota (~2,000 calls/mo) | Live GDS inventory | ✅ Phase 2 — real specific-date flights, more complex setup |
| SerpAPI | $25/mo | Google Flights scrape | ❌ Paid, ToS risk |
| Duffel | Free search; booking fees | Real inventory + booking | ❌ Overkill until booking is in scope (Phase 5) |

---

## Phase 1 Scope (This Task) — Travelpayouts

### What Travelpayouts provides
- Cheapest prices found for a route in the last 48 hours (based on real Aviasales user searches)
- Monthly price calendar (cheapest price per departure day for a whole month)
- Data covers a wide range of routes; strong on European, CIS, and Asia routes
- **Not** real-time live inventory — it is a pricing intelligence layer

### Travelpayouts API setup
- Register at travelpayouts.com → connect to Aviasales programme → get API token immediately (no approval delay)
- Authentication: `X-Access-Token: <token>` header
- Base URL: `https://api.travelpayouts.com`
- No rate limit published; reasonable use is fine

### Endpoints used

```
GET /v2/prices/latest?origin=OTP&destination=DPS&currency=eur&one_way=false&limit=5
→ Cheapest cached prices for route (used for "how much does it cost?")

GET /v2/prices/month-matrix?origin=OTP&destination=DPS&month=2026-05&currency=eur&one_way=false
→ Cheapest price per day for a whole month (used for "when is cheapest in May?")
```

---

## Phase 2 Scope (Future Task) — Amadeus

### What Amadeus provides
- Real, live flight availability and pricing for a specific date
- GDS-sourced: actual bookable fares from airlines
- Can evolve into booking with `FlightCreateOrders` API (aligns with Phase 5 roadmap)

### Amadeus API setup
- Register at developers.amadeus.com → create app → receive API key + secret
- OAuth2 token (`POST /v1/security/oauth2/token`) — 30 min TTL, must refresh
- Base URL: `https://api.amadeus.com/v1/shopping/flight-offers`

### When to route to Amadeus (future)
- User asks for flights on a **specific date**
- User explicitly requests "available flights" vs. price estimates
- User wants to compare specific flights (airline, departure time, stops)

---

## New Files

### `src/agentic_traveler/tools/flight_search.py`

```python
class TravelpayoutsService:
    BASE_URL = "https://api.travelpayouts.com"

    @classmethod
    def get_price_estimate(cls, origin: str, destination: str, currency: str = "eur", one_way: bool = False) -> Optional[dict]:
        """Fetch cheapest cached prices for a route."""

    @classmethod
    def get_month_calendar(cls, origin: str, destination: str, month: str, currency: str = "eur", one_way: bool = False) -> Optional[dict]:
        """Fetch cheapest price per day for a whole month."""

    @classmethod
    def format_estimate_result(cls, origin: str, destination: str, data: dict) -> str:
        """Format top results into a concise LLM-friendly string."""

    @classmethod
    def format_calendar_result(cls, origin: str, destination: str, month: str, data: dict) -> str:
        """Summarise month calendar: cheapest week, typical range, best day."""


# Stub for Phase 2
class AmadeusService:
    """Placeholder. Implement in Phase 2."""
    pass
```

In-memory result cache:
```python
_cache: dict[str, tuple[dict, float]] = {}  # key → (result, expiry_timestamp)
CACHE_TTL_SECONDS = 3600  # 1 hour
```

---

## Modified Files

### `src/agentic_traveler/orchestrator/agent.py`

Add two new orchestrator tool methods to `OrchestratorAgent`:

**`get_flight_price_estimate(origin, destination, trip_type, month)`**
```
Args:
  origin:      IATA airport code (e.g. "OTP"). The LLM must infer this from the user's city.
  destination: IATA airport code (e.g. "DPS").
  trip_type:   "round_trip" or "one_way"
  month:       Optional. "YYYY-MM" format. If omitted, returns general cheapest found.
Returns:
  Formatted text with top price options.
```

**`search_available_flights(origin, destination, outbound_date, return_date, adults)`** *(stub — Phase 2)*
```
Returns:
  "Flight availability search is coming soon. Use get_flight_price_estimate for a price estimate."
```

Register both in `_call_llm`'s tools list.

Update `_SYSTEM_PROMPT`:

```
CAPABILITIES (add):
• Checking flight price estimates — call get_flight_price_estimate(origin="<IATA>", destination="<IATA>", trip_type="round_trip"|"one_way", month="YYYY-MM")

ROUTING RULES (add):
14. IATA INFERENCE: When calling any flight tool, you MUST convert city/country names to IATA airport codes.
    Common examples: Bucharest → OTP, Bali/Denpasar → DPS, London → LHR or LGW (prefer LHR for international),
    Bangkok → BKK, Singapore → SIN, Tokyo → NRT. If the city has multiple airports, pick the main international one.
    Never pass city names directly — always pass the IATA code.
15. FLIGHT ESTIMATES: When the user asks about flight costs, prices, or "how much is a flight", call
    get_flight_price_estimate(). Note in your reply that prices are based on recent searches and
    may vary — always include a link to search live: "Check live prices at kiwi.com or google.com/flights"
16. SPECIFIC FLIGHTS: If the user asks for flights on a specific date, use get_flight_price_estimate()
    with the closest month and note that specific-date search is coming soon.
```

### `src/agentic_traveler/credit_manager.py`

Add flat credit costs:
```python
FLIGHT_ESTIMATE_COST_CREDITS = 2   # Travelpayouts is free but it's a premium feature
FLIGHT_SEARCH_COST_CREDITS = 5     # Phase 2: Amadeus real-time (reserved)
```

Add `deduct_flat_credits(user_doc_ref, credits)` helper — or reuse existing `deduct_credits_async`.
The orchestrator calls this inside `get_flight_price_estimate` via `_deduct_flat_credits_bg()`.

### `.env`
```
TRAVELPAYOUTS_TOKEN=your-token-here
# Phase 2:
# AMADEUS_API_KEY=your-key
# AMADEUS_API_SECRET=your-secret
```

---

## Credit Billing

Flight search credits are deducted **flat per tool call**, not based on tokens (no tokens are consumed — it's a direct HTTP call).

| Operation | Credits | Notes |
|---|---|---|
| `get_flight_price_estimate` | 2 | Deducted even if no results found (API call was made) |
| `search_available_flights` | 5 | Phase 2 / Amadeus only |

Deduction follows the same async pattern as grounding: fire-and-forget background thread so it doesn't delay the Telegram response.

---

## Caching

```python
cache_key = f"{origin}:{destination}:{month or 'any'}:{trip_type}:{currency}"
TTL = 3600 seconds (1 hour)
```

- Cached result is served instantly, **no credit deducted** on cache hit (no API call was made)
- Cache is in-memory; resets on restart. Acceptable — flight prices don't need cross-restart persistence.

---

## Error Handling

| Condition | LLM-visible return |
|---|---|
| `TRAVELPAYOUTS_TOKEN` not set | `"Flight price search isn't available right now — missing configuration."` |
| No results for route | `"I couldn't find recent price data for that route. It may be too obscure or no searches were made recently. Try checking Skyscanner directly."` |
| API timeout / 5xx | `"I'm having trouble reaching flight price data right now. Please try again in a moment."` |
| Invalid IATA inferred by LLM | Travelpayouts will return empty; handled by "no results" path above |

---

## Implementation Steps

1. **Sign up** for Travelpayouts affiliate account → get API token → add to `.env`
2. **Create** `src/agentic_traveler/tools/flight_search.py` with `TravelpayoutsService` (+ `AmadeusService` stub)
3. **Write** unit tests: `tests/test_flight_search.py` — mock HTTP, test formatting, cache hit/miss
4. **Add** `get_flight_price_estimate` and stub `search_available_flights` to `OrchestratorAgent`
5. **Update** `_SYSTEM_PROMPT` with IATA inference rule + new routing rules
6. **Add** credit constants and flat deduction call in `credit_manager.py`
7. **Verify**: test conversationally with "How much is Bucharest to Bali in May?" — confirm IATA inference, API call, formatted result, 2 credits deducted

---

## Risks & Open Questions

- **Data gaps:** Travelpayouts data is sparse for obscure routes (e.g. OTP → DPS is a multi-stop route that may have limited searches in their cache). The agent must handle empty results gracefully and fall back to a "check these sites" message.
- **IATA inference accuracy:** The LLM is good at inferring IATA codes but may occasionally be wrong (e.g., "London" could map to LHR, LGW, STN, or LTN). A future improvement could be an IATA lookup helper.
- **Price staleness:** Travelpayouts data is up to 48h old — this must be clearly surfaced to users so they don't treat it as a current booking price.

---

## Out of Scope (This Task)

- Real-time specific-date flight availability (Phase 2 — Amadeus)
- Flight booking (Phase 5 — Duffel)
- Multi-city routing
- Price alerts
- Filtering by airline, stops, departure time
