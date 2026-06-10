# Task 38 — Country Intel saga + cached snapshot + safety warning UI

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §4.4, §4.5, §5.4, §6.
> Depends on tasks 34–37.

## 1. Problem Statement

A thoughtful traveler silently asks twelve questions on arrival: Am I
allowed in? Is it safe? Will I get sick? Can I pay? Can I stay connected?
How do I get around? How do I talk to people? When should I go? — and so on.
Today, Aletheia answers each question reactively through `TripAgent` + a
grounded web search, with no persistence: every refresh is a new search,
every answer evaporates after the turn. This task lands the
`CountryIntelSaga`: it fires once when a destination flips to `confirmed`,
fetches the structured snapshot via grounded search, writes it into
`trips.country_intel[]`, and **never silently refreshes** on view — refreshes
require an explicit user request (per proposal §4.4, modified L2). It also
implements the safety warning rule: when `safety.score_10 < 7` (or
advisory level ≥ 2), the UI surfaces a non-blocking informational banner
citing sources.

## 2. Goals & Non-Goals

### Goals

- The moment a destination is `confirmed`, the snapshot is fetched (async,
  doesn't block the user reply) and persisted with `fetched_at`.
- The dashboard renders a Country Intel strip from the snapshot — visa,
  safety, health, money, connectivity, plug, language, when-to-go cards.
- A safety warning banner renders only when the threshold is crossed.
- The user can request a refresh from the UI ("Refresh intel") or by
  asking in chat ("Is this still current?"). Refresh re-runs the grounded
  search, updates the snapshot in place, bumps `fetched_at`.
- Every card cites its sources and carries the disclaimer "Verify with
  official sources before booking."

### Non-Goals

- A global `country_intel_cache` table shared across users (proposal §4.4
  L3 — deferred until traffic justifies it).
- Authoritative legal/medical advice — explicitly never.
- Live FX rates beyond the snapshot — accept that FX in the snapshot is
  indicative and stale.
- A user-configurable per-trip safety threshold UI — uses the profile-level
  `risk_appetite` value, no per-trip override in v1.

## 3. Acceptance Criteria

AC-1. The `CountryIntelSaga` activates when (a) a destination status flips
  to `confirmed` or (b) the user message contains a country-intel-shaped
  question ("is X safe", "do I need a visa for Y", "what's the currency").

AC-2. The saga runs **async / fire-and-forget** when (a); blocking on it
  must never delay the user reply.

AC-3. The fetched snapshot follows the schema in proposal §4.2
  `country_intel[]` (entry, safety, health, money, connectivity, transport,
  language, climate_by_month, calendar, sources, fetched_at).

AC-4. Refresh-on-view does NOT trigger a fetch. The snapshot's `fetched_at`
  may be days old; the UI shows a small "Last checked: 14 days ago — refresh"
  affordance.

AC-5. A "Refresh intel" button in the UI triggers an explicit refresh —
  one grounded search round, updated snapshot, charged to the user's
  credit balance like any other grounded turn.

AC-6. `safety.score_10` is computed by the documented formula in §7.4; a
  warning banner renders when `score_10 < threshold(user)` where
  `threshold(user)` is 7 unless `risk_appetite` is high (→ 5) or low (→ 8).

AC-7. Every rendered intel card displays:
  (a) the fetched_at date,
  (b) at least one source URL,
  (c) the disclaimer "Verify with official sources before booking."

AC-8. The saga emits metrics: `country_intel_fetched`, `country_intel_refreshed`,
  `safety_warning_shown`, `country_intel_fetch_failed`.

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/sagas/country_intel.py     [create]
backend/src/agentic_traveler/orchestrator/sagas/dispatcher.py        [modify — register]
backend/src/agentic_traveler/tools/country_intel_fetcher.py          [create]
backend/src/agentic_traveler/tools/trip_repo.py                      [modify — country_intel writer]
backend/tests/test_country_intel_saga.py                             [create]
frontend/src/components/dashboard/CountryIntelStrip.tsx              [create]
frontend/src/components/dashboard/SafetyWarningBanner.tsx            [create]
frontend/src/components/dashboard/TripDetailPanel.tsx                [modify — render the strip]
frontend/src/lib/intel-render.ts                                     [create]
README.md                                                            [modify]
```

## 5. Constraints

- The fetcher uses `SearchAgent` (existing grounded-search proxy) — NOT a
  new direct web-search integration.
- The saga's prompt to the search agent must be tight; it asks for a
  single structured JSON response, not a verbose explanation.
- The fetcher uses `gemini-3.1-flash-lite` for the JSON-shaping step
  (cheaper) and `gemini-3.5-flash` for the grounded research step (higher
  reasoning quality).
- The snapshot writer must NEVER overwrite an existing snapshot with a
  partial one — if the fetcher returns missing sections, keep the prior
  values for those sections.
- The safety warning is **informational, never blocking** — the user can
  always continue planning.
- All visa, health, and legal information includes the disclaimer.

## 6. Edge Cases

- **Grounded search returns no usable info** → snapshot is created with
  empty sections, `sources=[]`, and a UI placeholder "We couldn't find
  reliable intel — try a manual search."
- **Refresh fails** → the prior snapshot remains; a transient WARN log;
  user sees a toast "Refresh failed — keep your prior intel."
- **User confirms two destinations in one turn** → saga fetches both
  sequentially (not parallel — to keep grounded-search cost predictable).
- **Country with no advisory data** (rare) → `advisory_level=null`,
  `score_10=null`; warning banner does not render.
- **Multi-country trip** → one snapshot per country; UI shows a strip per
  country tab.
- **Refresh requested via chat ("is this still current?")** → router
  detects the phrasing, dispatcher routes to CountryIntelSaga as the
  owner of this turn (not as a side-effect listener).

## 7. Implementation Plan

### Step 1 — `country_intel_fetcher.py`

```python
"""Two-step fetcher: (1) grounded research with gemini-3.5-flash, (2)
structured extraction with gemini-3.1-flash-lite.

NEVER imports network helpers directly — always goes through SearchAgent
so we get grounding + citations consistently.
"""

from agentic_traveler.orchestrator.search_agent import SearchAgent
from agentic_traveler.orchestrator.client_factory import get_client, gemini_generate

_RESEARCH_PROMPT = """\
You are researching travel-relevant facts for a single country: {country}.
Cover concisely: entry/visa rules, safety advisory, vaccine guidance,
currency and money habits, SIM/eSIM/wifi, plugs/voltage, transit, language,
climate for month {month}, and notable public holidays / festivals around
{month}. Be terse. Cite official sources. Do not invent.
"""

_STRUCTURE_PROMPT = """\
Extract the following research into this exact JSON schema. If a value is
unknown, use null. Do not invent.

{schema}

Research:
{research}
"""

def fetch_country_intel(iso_country: str, country_name: str, month: int) -> dict:
    research = ...  # gemini-3.5-flash via SearchAgent grounded call
    snapshot = ...  # gemini-3.1-flash-lite structuring step
    snapshot["iso_country"] = iso_country
    snapshot["fetched_at"]   = utcnow_iso()
    return snapshot
```

### Step 2 — `country_intel.py` saga

```python
class CountryIntelSaga(BaseSaga):
    name = "CountryIntelSaga"

    def should_activate(self, intent, entities, trip, state):
        # Listener: when a destination flipped to confirmed in THIS turn.
        if any(s.get("destination_just_confirmed") for s in entities.get("side_effects_seen", [])):
            return True, False
        # Owner: when the message asks about visa/safety/health/money/etc.
        if entities.get("intel_question"):
            return True, True
        return False, False

    @traceable(name="saga.country_intel.run")
    def run(self, message, user_doc, trip, state, conv, events):
        if state.get("activation_mode") == "owner":
            return self._answer_question(...)
        return self._fetch_for_confirmed_destination(...)
```

### Step 3 — Safety score formula

```python
def compute_safety_score_10(advisory_level: int | None, gpi_rank: int | None,
                            crime_signal: float | None) -> float | None:
    if advisory_level is None and gpi_rank is None:
        return None
    # Advisory: 1→10, 2→7, 3→4, 4→1 (linear-ish, capped)
    adv = {1:10.0, 2:7.0, 3:4.0, 4:1.0}.get(advisory_level, 7.0)
    # GPI: top50 → +1.5, top100 → 0, bottom 50 → -1.5
    gpi = 0.0
    if gpi_rank is not None:
        if gpi_rank <= 50:   gpi = +1.5
        elif gpi_rank > 110: gpi = -1.5
    # Crime: weight 0.5
    crime = -0.5 * (crime_signal or 0.0)
    return max(0.0, min(10.0, adv + gpi + crime))

def user_threshold(profile: dict) -> float:
    risk = (profile.get("personality_dimensions_scores") or {}).get("risk_appetite", 0.5)
    if risk >= 0.7: return 5.0
    if risk <= 0.3: return 8.0
    return 7.0
```

### Step 4 — TripRepository writer

`upsert_country_intel(trip_id, snapshot)`:

- Merge the new snapshot into `trips.country_intel[]` keyed by `iso_country`.
- Preserve prior snapshot sections that the new one left empty.
- Set `fetched_at` only on populated sections.

### Step 5 — Frontend `CountryIntelStrip.tsx`

Horizontal scroll of small cards. Each card:

- Icon + heading (Visa, Safety, Health, Money, Connectivity, Plug, Language, When).
- One-line summary (≤ 80 chars).
- Tap to open a sheet with full details.
- Bottom-right: small `fetched_at` chip + tiny refresh button.

If a section is absent in the snapshot, the card is hidden (progressive
disclosure).

### Step 6 — `SafetyWarningBanner.tsx`

- Renders only when `safety.score_10 < user_threshold`.
- Dismissible per trip (UI state only — does NOT mute the saga).
- Cites two sources by URL.
- Phrasing: "Travel advisories suggest extra caution for {country}.
  Verify with official sources before booking. [Sources]"

### Step 7 — Refresh flow

- UI button posts to `/trips/{id}/intel/refresh?iso=XX`.
- Backend endpoint enqueues a CountryIntelSaga run with `mode=refresh`,
  spends grounded-search credits, persists the new snapshot, returns the
  updated trip.

### Step 8 — Tests

`test_country_intel_saga.py`:
- Activation: destination-just-confirmed (listener) / intel question
  (owner) / unrelated message (no activation).
- Safety score formula: each combination of inputs.
- Threshold derivation: low / mid / high risk_appetite.
- Snapshot merge: prior sections preserved when fetcher returns partial.

## 8. Testing Plan

- **Unit:** safety scoring, threshold logic, snapshot merge.
- **Integration (`-m integration`):** real grounded search against
  "Iceland" — assert the snapshot has `entry`, `safety`, `health`, `money`,
  at least one source URL, and an `advisory_level`.
- **Manual desktop + mobile:** the strip renders correctly with empty,
  partial, and full snapshots. The warning banner renders only for a
  seeded low-score country (e.g., a test trip with manually-inserted
  `score_10=4.0`).

## 9. Conditional Sections

### 9.2 LLM Considerations

- Two-stage fetch: gemini-3.5-flash for grounded research, gemini-3.1-flash-lite
  for JSON extraction.
- Token budget: research ≤ 2 000 tokens; extraction ≤ 1 500 in / 1 500 out.
- Prompt injection: destinations come from the trip data (already user-
  validated). The research prompt is constant; only the country name and
  month are interpolated, validated via a strict regex.
- Output handling: rendered in UI; JSON parse + Pydantic validation; any
  schema mismatch → log WARN + use empty sections.
- Tool versioning: snapshot includes a `fetcher_version` field.

### 9.3 Observability

- Metrics: `country_intel_fetched`, `country_intel_refreshed`,
  `safety_warning_shown`, `country_intel_fetch_failed` (with country code).
- LangSmith `@traceable` on the saga + the fetcher.

### 9.4 Rollback Plan

- Saga deregister from dispatcher.
- Existing snapshots remain in `trips.country_intel[]` — UI hides the
  strip if a frontend feature flag is off.

## 10. Findings & Follow-ups

- Added strict 402 cost-awareness checks directly to `CountryIntelSaga._run_fetch_async` and `/trips/{trip_id}/intel/refresh` to abort execution and prevent charging empty balance users.
- Tracked both `gemini-3.5-flash` search token costs and `gemini-3.1-flash-lite` extraction token costs as part of the _token_records list.
- Implemented exact disclaimer and source references inside `CountryIntelStrip` and `SafetyWarningBanner`.

## 11. Definition of Done

- [ ] ACs 1–8 pass.
- [ ] Unit + integration tests pass.
- [ ] Mobile + desktop verified.
- [ ] README updated with the country intel feature.
- [ ] Every UI card has the disclaimer + source link.

## Manual operations (user, post-implementation)

1. No new manual ops beyond verifying the feature works for at least
   three countries (one safe like Iceland, one with advisory ≥ 2 to
   trigger the warning banner, one with sparse data like a small
   country, to verify graceful degradation).
