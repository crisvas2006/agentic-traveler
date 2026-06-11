# Task 49 — Real map: MapLibre + OpenFreeMap, capture-once geocoding, GMaps deep links

> Spec per `task_template_v2.md`. Stream E of the 2026-06-10 product-evolution
> brainstorm. Lands after task 48 (numbered order). Provider decision
> ratified: MapLibre GL JS + OpenFreeMap tiles now (zero cost, no key, no
> quota), Google Places enrichment recorded as a named post-validation
> follow-up — NOT in this task.

---

## 1. Problem Statement [REQUIRED]

The dashboard's visual centerpiece is a mock: a hand-coded SVG map with
hard-placed pins for a fictional Kyoto trip. Real trips have no coordinates
at all — destinations are stored as text — so nothing about the map can be
real until geocoding exists. The product needs an actual interactive map,
styled for travel (calm roads, emphasized water/terrain/places) rather than
navigation, that renders the user's real trip and hands off to Google Maps
for the capabilities we don't build (navigation, reviews, street view).
Cost reality (researched 2026-06-10): Google's dynamic map loads are free
only to ~10K loads/month per SKU with a billing card on file and automatic
$7/1K overage — an unbounded liability against the free-tier discipline;
MapLibre GL JS + OpenFreeMap vector tiles are free with no key, no card,
and no quota, and give full runtime styling control that Google does not.
"Open in Google Maps" deep links are free and need no API. Doing this now:
task 40 just rebuilt the trip panel around live data, so the map is the
last mocked surface on the dashboard.

Ratified decisions (2026-06-10): MapLibre + OpenFreeMap now, Places later
(hybrid); v1 scope = trip-focused MVP (pins, fit-bounds, tap-card with
GMaps link); geocoding = capture-once server-side Nominatim cached on the
trip; no exploration/drawing/day-routes in v1.

## 2. Goals & Non-Goals [REQUIRED]

**Goals**

- G1. The dashboard map renders real tiles and the ACTIVE trip's real
  destination pin(s), auto-fitted, on web mobile and desktop.
- G2. Every destination written to a trip gets `{lat, lng, bbox}` captured
  once, server-side, at write time — trips become mappable data.
- G3. Tapping a pin shows a small card with the place name, day/kind when
  known, and an "Open in Google Maps" deep link.
- G4. The base style is travel-purposed and theme-aware (warm-ivory light
  per task 46, navy dark), not a default navigation map.
- G5. Idle GPU cost stays at today's near-zero (the globals.css frosted-
  panel lessons are preserved).
- G6. Zero recurring cost: no API key, no billing account, no quota to
  monitor.

**Non-Goals**

- No Google Places / POI data on-map — named follow-up after validation.
- No explore mode (search the map, drop pins, add-to-trip from map).
- No day-route polylines — follow-up once day blocks carry coordinates.
- No offline tiles, no mobile-native map, no Telegram map rendering
  (Telegram gets the GMaps deep link in text where relevant — unchanged).
- No reverse geocoding ("what's at this point").
- No self-hosted tile server (OpenFreeMap public instance; Protomaps
  PMTiles self-hosting recorded as the fallback if OpenFreeMap degrades).

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. Writing a destination to a trip (typed, extracted, or tapped —
      same trigger family as task 45's brief) geocodes it via Nominatim
      server-side and stores {lat, lng, bbox, geocoded_at} on the trip's
      destination entry. Exactly one geocode per (trip, destination)
      string; repeat turns do not re-geocode.
AC-2. Nominatim is called with a project-identifying User-Agent, ≤1
      request/second (serialized), and NEVER from the browser. Failure
      stores nothing, logs a warning, and never blocks the turn; the map
      simply shows no pin for that destination.
AC-3. The dashboard map is MapLibre GL JS with OpenFreeMap tiles; the
      mock SVG map component is removed. maplibre-gl is dynamically
      imported so the initial dashboard JS bundle does not include it.
AC-4. The map auto-fits to the active trip's pins (single pin → sensible
      city-level zoom via bbox); with no geocoded pins it shows a calm
      world/region view, never an error.
AC-5. Tapping/clicking a pin opens a card: place name, optional context
      line, and "Open in Google Maps" linking to
      https://www.google.com/maps/search/?api=1&query=<lat>,<lng>
      opening in a new tab. Card matches existing card styling.
AC-6. Base style is customized (not a stock style verbatim): reduced
      road/admin prominence, emphasized water/terrain/place labels, and
      two variants wired to the app theme (light=ivory-compatible,
      dark=navy-compatible) switching with the theme toggle.
AC-7. OSM/OpenFreeMap attribution is visible on the map per OSM policy.
AC-8. Idle performance: with the dashboard open and untouched, the map
      triggers no continuous repaints (verified via DevTools performance
      recording — no per-frame GPU work at idle, matching today).
AC-9. prefers-reduced-motion: fit-bounds and camera movements jump
      without easing animation.
AC-10. Mobile: the map remains the third swipe pane, full-bleed,
      gesture-correct (one-finger pan does not hijack vertical page
      scroll on the swipe container edges); desktop unchanged layout.
AC-11. RLS holds: the map only ever receives trip data already fetched
      through the user's authenticated client (no new data path).
AC-12. npm run build succeeds; backend suite + ruff clean.
```

## 4. Files & Modules Touched [REQUIRED]

```
backend/src/agentic_traveler/tools/geocoder.py                   [create — Nominatim client]
backend/src/agentic_traveler/orchestrator/sagas/planning.py      [modify — geocode side-effect on destination write]
backend/src/agentic_traveler/tools/trip_repo.py                  [modify — coords persisted in destination entries]
backend/tests/tools/test_geocoder.py                             [create]
backend/tests/orchestrator/sagas/test_planning_saga.py           [modify — geocode trigger/idempotency]
frontend/package.json                                            [modify — add maplibre-gl (pinned)]
frontend/src/components/dashboard/TripMap.tsx                    [create — MapLibre wrapper]
frontend/src/components/dashboard/<mock map component>.tsx       [delete — exact name resolved at impl]
frontend/src/components/dashboard/DashboardShell.tsx             [modify — mount TripMap]
frontend/src/lib/map-style.ts                                    [create — travel style variants light/dark]
README.md                                                        [modify]
```

(The mock map's exact filename and any globals.css `.map-*` utility
cleanup are resolved at implementation; record removals in §10.2.)

## 5. Constraints [REQUIRED]

- **Zero recurring cost** is an invariant of this task: no provider that
  requires an API key or billing account. If OpenFreeMap is unavailable,
  the map degrades gracefully (themed empty canvas + pins hidden) — it
  does NOT fall back to a paid provider.
- **Nominatim usage policy compliance** (it's a shared free service):
  identifying User-Agent, ≤1 req/s serialized, results cached
  permanently, no bulk geocoding. Geocoding happens only at
  destination-write time — never per page view.
- **Browser never calls Nominatim/external APIs** (CLAUDE.md §8); coords
  come down with trip data through the existing authenticated path.
- **Idle-static rendering discipline** (globals.css lessons): no
  continuous map animations, no marker pulse loops; MapLibre repaints
  only on camera change so the frosted panels' cached blur stays valid.
- **Bundle discipline:** maplibre-gl enters via dynamic import; the
  dashboard's first paint must not wait on it.
- **Mobile-first** (CLAUDE.md §3): every layout change ships mobile +
  desktop together.
- **Do not remove fields from models** — coords are additive keys inside
  existing destination entries (JSONB), no schema migration.
- CLAUDE.md §9 applies (no deploys without approval, no git mutations,
  mocked external calls in tests — Nominatim is mocked like Telegram).

## 6. Edge Cases [REQUIRED]

| # | Case | Intended behavior | Test |
|---|------|-------------------|------|
| E1 | Ambiguous destination ("Springfield") | Take Nominatim's top result; the pin card shows the resolved display name so the user can spot a mismatch; correction = user renames destination (re-geocodes, new string) | unit |
| E2 | Nominatim 0 results / timeout / 5xx / 429 | Store nothing, warn-log, turn proceeds; no retry storm (single attempt + one retry with backoff) | unit |
| E3 | Destination renamed/changed on trip | New string → one new geocode; old coords replaced | unit |
| E4 | Multiple destinations on a trip | All geocoded (serialized ≤1 rps); fit-bounds spans them | unit |
| E5 | Trip with destination but no coords yet (geocode failed earlier) | Map shows region/world default (AC-4); no error chrome | manual |
| E6 | Non-Latin / diacritic destination names ("Kraków", "東京") | Passed through UTF-8; Nominatim handles natively | unit |
| E7 | Theme toggled while map mounted | Style variant swaps without remount/flash of unstyled tiles | manual |
| E8 | OpenFreeMap tile outage at runtime | MapLibre error event → themed fallback panel ("map unavailable"), pins list still accessible in trip panel; no console error spam | manual |
| E9 | Realtime trip update adds a destination while map is visible | New pin appears + re-fit (existing useTripRealtime subscription; no new channel — free-tier WebSocket budget per CLAUDE.md §8) | manual |
| E10 | Very close pins (hotel + restaurant same block) | Default MapLibre rendering acceptable at v1 (no clustering); recorded as follow-up if bookings get coords | accepted |
| E11 | GMaps link with no coords (shouldn't happen — card only on pins) | Card renders only for geocoded pins; assert | unit |
| E12 | Two concurrent turns write destinations simultaneously | Geocoder serialization is in-process per worker; worst case two geocodes ~1s apart — within policy | accepted |

## 7. Implementation Plan [REQUIRED]

### Step 1 — Geocoder tool → verify: test_geocoder.py

`tools/geocoder.py`:

```python
def geocode_destination(name: str) -> Optional[dict]:
    """One Nominatim /search call (format=jsonv2, limit=1).
    Returns {"lat": float, "lng": float, "bbox": [s, n, w, e],
    "display_name": str, "geocoded_at": iso} or None on any failure.
    Policy: User-Agent "AletheiaTravel/1.0 (contact: <env ADMIN_EMAIL>)",
    module-level lock + min-interval 1.1s between calls, timeout 5s,
    single retry with backoff on 5xx/timeout. Never raises."""
```

One tool = one action (AGENTIC_GUIDELINES). Emits `tool_invoked` /
`tool_succeeded|tool_failed` with latency per §7.1 conventions.

### Step 2 — Capture-once wiring → verify: planning saga tests

In the same place task 45's `ensure_brief` hooks destination writes
(`planning.py` post-extraction / post-selection), add `ensure_coords`:
if the trip's destination entry lacks coords for its current string,
geocode and stage a `trip_patch` SideEffect merging
`destinations[i].coords = {...}`. Idempotent by (destination string ==
coords.source_name). If task 45 is not yet merged when this task starts,
hook the existing destination-write path directly (§10.2 note).

### Step 3 — Travel style → verify: AC-6 visual check both themes

`lib/map-style.ts`: start from OpenFreeMap "liberty" style JSON; override
layers: demote motorway/trunk saturation and minor-road visibility at low
zooms, raise water/landcover/park presence, keep place labels prominent,
recolor ground tones to harmonize with ivory (light) / navy (dark).
Export `getMapStyle(theme: "light" | "dark")`. (Claude Design optional
here — the style is code-tuned; screenshots reviewed manually.)

### Step 4 — TripMap component → verify: AC-3/4/5/8/9/10 + build

`TripMap.tsx` (client component):
- `const maplibregl = await import("maplibre-gl")` inside a mount effect;
  skeleton placeholder until loaded.
- Props: `destinations: {name, coords?}[]` from the existing trip hook.
- Markers: brand-gradient pin (existing identity); popup/card on tap with
  display name + "Open in Google Maps" (`target="_blank"
  rel="noopener noreferrer"`).
- `fitBounds` on data change; `{animate: false}` under reduced motion;
  single pin → `fitBounds(bbox)` for city-level zoom.
- Attribution control enabled (compact).
- No animation loops; `map.repaint` stays event-driven (default).
- Replace the mock component in `DashboardShell`; delete the mock + its
  dead `.map-pin-pulse`/`.map-here-blink` utilities if unused (§10.2).

### Step 5 — README + docs → verify: CLAUDE.md §6

README: map stack (MapLibre + OpenFreeMap, free/no-key), geocoding
(capture-once Nominatim + policy), GMaps deep links, follow-ups list.

## 8. Testing Plan [REQUIRED]

- **Unit (backend, Nominatim mocked):** geocoder happy path, E1 top-result
  + display_name, E2 failure family (0 results, timeout, 429, 5xx, bad
  JSON), rate-limit serialization (two calls ≥1.1s apart via patched
  clock), E6 unicode; saga wiring: capture-once idempotency, E3
  rename→re-geocode, E4 multi-destination, never blocks turn.
- **Frontend:** `npm run build`; type-check of TripMap props from the trip
  hook.
- **Manual checks (mobile 375px AND desktop, light AND dark):**
  - Real trip → pin(s) at correct city, fit-bounds sane (AC-4), single +
    multi destination.
  - Pin card + GMaps deep link opens correct location in new tab (AC-5).
  - Theme toggle live-swaps style (E7).
  - Idle DevTools performance recording: no per-frame work (AC-8).
  - Swipe-pane gestures on mobile (AC-10).
  - Attribution visible (AC-7).
- **Sample fixtures:** Nominatim jsonv2 response for "Taormina" embedded
  in tests; failure fixture (empty array).

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL — does not apply]

No LLM calls added or changed. (Geocoding is deliberately deterministic —
coords from the destination brief LLM were considered and rejected:
Nominatim is exact, free, and non-hallucinating.)

### 9.3 Observability [CONDITIONAL — applies]

`tool_invoked/succeeded/failed` for the geocoder with latency;
`geocode_failed{reason}` metric to spot Nominatim degradation; frontend
map tile-error count via the existing client log path if present, else
console-only (no new infra). No alerts.

### 9.4 Rollback Plan [CONDITIONAL — applies, lightweight]

Code-only; coords are additive JSONB keys old code ignores. Revert =
redeploy prior revision + (optionally) leave coords in place — harmless.
No data migration either way.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
*(seeded — the ratified follow-up list)*
- Google Places enrichment (place details/photos on pin tap) — the
  ratified "Places later" half of the hybrid decision. Post-validation;
  has its own free cap; needs key + billing decision. Priority: medium.
- Day-route polylines once day blocks/bookings carry coords. Priority: low.
- Explore mode (search map, add-to-trip from pin). Priority: low.
- Marker clustering if bookings get coords (E10). Priority: low.
- Protomaps PMTiles self-host as tile-outage hedge (E8). Priority: low.

### 10.2 Spec deviations
*(populated during implementation)*

## 11. Definition of Done [REQUIRED]

- [ ] All §3 ACs pass (tests or the §8 manual checks).
- [ ] §6 edge cases tested or accepted as listed.
- [ ] `ruff check` clean; backend unit suite green.
- [ ] `npm run build` succeeds; maplibre-gl pinned in package.json.
- [ ] Mobile + desktop verified, light + dark themes.
- [ ] Mock map component deleted; no dead map CSS left (or §10.2 notes).
- [ ] OSM attribution visible.
- [ ] README updated.
- [ ] No new keys/billing anywhere; no browser calls to external APIs.

## 12. Open Questions [OPTIONAL]

- Q1. Should bookings with addresses (task 39) geocode too in v1?
  Proposed: no — destinations only; bookings join when day-routes do.
- Q2. World-view default when no trip/coords: static themed canvas vs
  interactive globe at low zoom. Proposed: interactive at low zoom,
  costless either way; final call at implementation with a screenshot.
