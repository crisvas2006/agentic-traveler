# Task 52 — Trip Context Sync, Greedy-Intel Fix & Relaxed Trip Creation

> Spec lineage: `specs/task_36_trip_saga_orchestrator.md` (saga dispatch +
> `resolve_active_trip` + state-as-data) and **`specs/task_44_trip_focus_and_
> direction_switching.md`**, which already shipped the spine this task extends:
> the router's `trip_directive ∈ {continue,new,unspecified}`,
> `resolve_trip_focus(summaries, message, entities, directive)` + `is_established()`
> in `trip_resolver.py`, the `SagaState` fields `trip_directive` /
> `superseded_trip_title`, the PlanningSaga confirmation-gate pattern, and the
> `trip_focus_resolved` metric. **Extend these — do not re-derive them.**
> Depends on tasks 34 (trips data model), 36, 37 (SSE streaming), 38
> (CountryIntelSaga), 43 (tappable chips), 44.

---

## 1. Problem Statement [REQUIRED]

A user typing an ordinary travel question — "what is a trip in Romania like?" —
gets the agent stuck in a loop replying *"I can look up travel facts for you.
Which country are you planning to visit?"*. This is a **greedy saga-ownership
bug**, not a missing feature: `CountryIntelSaga.should_activate`
(`backend/src/agentic_traveler/orchestrator/sagas/country_intel.py:25-46`) returns
`(True, True)` whenever the router sets `entities["intel_question"]`, and the saga
sits at **dispatcher position #2** (`sagas/dispatcher.py:33-42`), ahead of
PlanningSaga and DiscoverySaga. CountryIntelSaga is a *background fetcher* that
populates the trip's intel strip — it cannot converse. With no confirmed-destination
trip in focus, its `_answer_question` (`country_intel.py:67-96`) returns the static
fallback string verbatim, and because it greedily owns the turn the conversational
DiscoverySaga (which would answer via TripAgent and let the trip take shape) never
runs. The loop repeats every turn the router re-flags the message as an intel
question.

Two further weaknesses compound the problem. First, the backend has **no idea which
trip the user is looking at** in the dashboard TripPanel, so the user's visual
context and the agent's conversational context drift apart; the resolver can only
match a trip by **title substring** (`resolve_active_trip`,
`trip_resolver.py:57-90`) because `list_trip_summaries`
(`tools/trip_repo.py:204-225`) doesn't even select destinations — so "what can I
see in Barcelona?" can never resolve to a *Spain* trip. Second, the orchestrator
**eagerly creates a `DREAMING` trip** on every casual travel question
(`agent.py:656-666` fires whenever `trip is None` and the owner is PlanningSaga or
DiscoverySaga, and DiscoverySaga owns *all* `TRIP + trip=None` turns), violating
the "saga freedom" spirit — a user idly asking about Rome should not silently
acquire a trip object.

Doing this now unblocks reliable conversation (the reported loop disappears), gives
every saga a correct trip anchor to act on (so logistics like "I'll take the bus
from Madrid to Barcelona on day 2 at 10am" land on the right trip), and makes the
TripPanel a first-class, closable context surface the user controls.

## 2. Goals & Non-Goals [REQUIRED]

### Goals
- **The loop is gone.** A general travel question with no established trip is
  answered conversationally (via TripAgent), never by CountryIntelSaga's fallback
  string. CountryIntelSaga only *owns* a turn when it can do a real grounded
  refresh (the resolved trip has a confirmed destination with an ISO country).
- **The backend knows the focused trip.** The frontend sends `focused_trip_id`
  (the trip open in the TripPanel, or `null` when closed) on every chat message;
  the orchestrator uses it as the strong default anchor for trip resolution.
- **Best-effort drift, zero added token cost.** When the user's message clearly
  references a *different* trip (by destination), the backend switches focus to it
  using the router's **already-extracted** `entities.destinations` matched against
  destination-enriched trip summaries — **no trip list is added to any LLM prompt,
  no second LLM call**. If nothing matches, the turn is answered without forcing a
  trip into focus.
- **The UI follows the backend.** The reply carries `metadata.focus_trip_id`; the
  frontend opens/switches the TripPanel to it **only when it differs** from the
  current focus, so a same-trip echo never remounts the panel or resets its scroll.
- **A subtle, clickable focus indicator** ("📍 Kyoto") sits in the chat header next
  to the Aletheia identity, teaching the user that the selected trip drives context.
  Its **X clears focus and closes the panel**.
- **Relaxed, consented trip creation.** Casual `TRIP` questions create nothing. A
  trip is created only on `PLAN` intent / an explicit go-signal; when intent is
  merely suspected, the agent asks a one-line confirmation before creating.

### Non-Goals
- **No schema migration.** `focused_trip_id` is ephemeral (per request);
  destinations already live in `trip_destinations`. Persisting "last focused trip"
  across reloads (a `user_profiles.profile_data` field) is explicitly out of scope.
- **No LLM trip selection.** We do **not** pass trip summaries into the RouterAgent
  prompt or add a dedicated selection call (rejected: per-turn token cost on every
  turn even when no trip is referenced — see §9.2).
- **No rewrite of `resolve_active_trip`'s existing heuristic** (active → ready →
  most-recent); we add destination-match + `focused_trip_id` *above* it.
- **No full trip details rendered inside chat bubbles** — that stays the TripPanel's job.
- **No change to Telegram** — it sends no `focused_trip_id`; the resolver tolerates
  `None` and falls back to the existing heuristic.
- **No general fix of PlannerAgent destination grounding** (carried from task 44 §10.1).

## 3. Acceptance Criteria [REQUIRED]

AC-1. **(Loop fix)** With `entities["intel_question"]=True` and **no** resolved trip
  carrying a confirmed destination with an `iso_country`, `CountryIntelSaga.
  should_activate(...)` returns `(False, False)` — it does **not** own the turn, and
  the static string "I can look up travel facts for you. Which country are you
  planning to visit?" is never returned as a reply.

AC-2. **(Intel still works)** With a resolved trip that has ≥1 `confirmed`
  destination with an `iso_country`, an `intel_question` turn is owned by
  CountryIntelSaga, which triggers the async grounded refresh and returns its
  "I'll check the latest facts for <name>…" acknowledgement (existing behavior
  preserved).

AC-3. **(Listener preserved)** CountryIntelSaga still activates as a **listener**
  (`(True, False)`) when this turn confirms a destination (`destination_upsert` /
  `destination_just_confirmed`), so the intel strip refresh still fires — without
  owning the reply.

AC-4. **(Focus field, plumbed)** `ChatSendRequest` accepts optional
  `focused_trip_id: str | None`; the `/api/chat/send` and `/api/chat/stream` Next.js
  route handlers forward it to the backend (verified: they forward the whole JSON
  body), and the orchestrator receives it.

AC-5. **(Summaries carry destinations)** `TripRepository.list_trip_summaries`
  returns each trip's destinations (`name`, `iso_country`, `status`) and a
  tie-break date, via the existing `trip_destinations` relation — no schema change.

AC-6. **(Best-effort destination match)** Given the user's `entities.destinations`
  match a single trip's destination name (case-insensitive) that is **not** the
  `focused_trip_id`, `resolve_trip_focus` returns that trip (drift switch). Given a
  match to the focused trip or no destination in the message, the `focused_trip_id`
  trip is chosen. Given destinations that match **no** trip, the result is the
  pre-existing heuristic outcome (which may be `None`) — the turn is answered
  without forcing focus.

AC-7. **(Tie-break)** When `entities.destinations` match **multiple** trips, the
  chosen trip is: an `active` trip whose date range contains today → else the trip
  with the nearest upcoming date → else the most recent past trip.

AC-8. **(Hallucination-safe focus)** If `focused_trip_id` is not among the user's
  trips (stale/forged), it is ignored and resolution falls through to the heuristic.

AC-9. **(Focus echoed to UI)** The reply's `ChatMessageOut.metadata` includes
  `focus_trip_id: <resolved trip id or null>` on **both** the streaming `done` event
  and the non-streaming `/send` response.

AC-10. **(No-jolt UI)** The frontend updates the TripPanel to `metadata.focus_trip_id`
  **only when it differs** from the currently open trip; an identical id is a no-op
  (no remount, no scroll reset, no `useTrip` resubscribe).

AC-11. **(Header chip)** The chat header shows a subtle, clickable chip with the
  focused trip's primary destination (e.g. "📍 Kyoto") when a trip is focused, and
  nothing when focus is null. Implemented for **mobile and desktop** (CLAUDE.md §3).

AC-12. **(Chip X clears focus + closes panel)** Tapping the chip's X closes the
  TripPanel and clears `focused_trip_id`, so the next message carries
  `focused_trip_id=null`; the panel is reopenable via the TopNav switcher, the trip
  library, or a chip that returns when focus is re-established.

AC-13. **(Casual question creates nothing)** "What is a trip in Rome like?" with no
  prior trip context returns a TripAgent answer, creates **no** trip row, stages
  **no** `considering` destination, and does **not** change the TripPanel.

AC-14. **(Consented creation)** A trip is created when `intent == "PLAN"` or an
  explicit go-signal is present; when intent is only suspected, the saga returns a
  one-line confirmation (≤ 200 chars, CLAUDE.md §7.1 slot-fill budget) and creates
  nothing until the user confirms (stateless — the next turn's directive/intent
  drives creation).

## 4. Files & Modules Touched [REQUIRED]

> Every path below was verified to exist (or is tagged `[create]`). Paths that
> spec drafts commonly get wrong are annotated.

```
# Backend
backend/src/agentic_traveler/interfaces/schemas.py                      [modify]  # ChatSendRequest.focused_trip_id
backend/src/agentic_traveler/interfaces/routers/chat.py                 [modify]  # read focused_trip_id; embed metadata.focus_trip_id in /send + /stream
backend/src/agentic_traveler/orchestrator/agent.py                      [modify]  # thread focused_trip_id; relax auto-create; surface resolved trip id
backend/src/agentic_traveler/orchestrator/sagas/trip_resolver.py        [modify]  # destination match + focused_trip_id priority + tie-break
backend/src/agentic_traveler/tools/trip_repo.py                         [modify]  # list_trip_summaries select + TripSummary destinations/date
backend/src/agentic_traveler/orchestrator/sagas/country_intel.py        [modify]  # should_activate ownership fix; drop fallback-owner string
backend/src/agentic_traveler/orchestrator/sagas/discovery.py            [modify]  # no creation on casual TRIP
backend/src/agentic_traveler/orchestrator/sagas/planning.py             [modify]  # confirm-before-create gate
backend/tests/orchestrator/sagas/test_country_intel.py                  [create]  # AC-1..AC-3
backend/tests/orchestrator/sagas/test_trip_resolver.py                  [modify]  # AC-6..AC-8
backend/tests/orchestrator/sagas/test_discovery_saga.py                 [modify]  # AC-13, AC-14
backend/tests/orchestrator/test_orchestrator.py                         [modify]  # focus threading, metadata, relaxed creation

# Frontend  (NOTE: there is NO frontend/src/interfaces/schemas.ts and NO ChatHeader.tsx;
#            chat types are inline in hooks, and the header lives inside ChatPanel.tsx)
frontend/src/app/api/chat/send/route.ts                                 [verify]  # forwards whole body — confirm no field stripped (no change expected)
frontend/src/app/api/chat/stream/route.ts                               [verify]  # forwards whole body — confirm no field stripped (no change expected)
frontend/src/hooks/useChat.tsx                                          [modify]  # send focused_trip_id; consume metadata.focus_trip_id
frontend/src/hooks/useChatStream.ts                                     [modify]  # stream POST body + done-event focus_trip_id
frontend/src/components/dashboard/ChatPanel.tsx                         [modify]  # header chip + props
frontend/src/components/dashboard/DashboardShell.tsx                    [modify]  # thread focus into chat; closable panel; apply focus switches
frontend/src/components/dashboard/DashChips.tsx                         [modify]  # FocusedTripChip
frontend/src/components/dashboard/DashIcons.tsx                         [modify]  # MapPinIcon (or 📍 glyph)

# Docs
README.md                                                               [modify]  # trip-context-sync + relaxed creation
specs/task_52_trip_context_sync.md                                      [this spec]
```

No schema migration; no new table; no RLS change (see §9.1).

## 5. Constraints [REQUIRED]

- **No per-turn token cost.** Trip matching uses the router's already-extracted
  `entities.destinations` and a backend SELECT/Python match. **Do not** inject trip
  summaries into the RouterAgent prompt or add a second LLM call (CLAUDE.md §10).
- **Stateless (task 36 §4.1).** No persisted "awaiting confirmation" or "last focus"
  state; `focused_trip_id` arrives per request, the resolved id is echoed back per
  reply. Nothing stored on `self`.
- **No schema change** (CLAUDE.md §8: don't migrate prod manually). Reuse
  `trip_destinations`; `focused_trip_id` is ephemeral.
- **Don't break the existing resolver heuristic** or task-44 directive behavior —
  destination-match + `focused_trip_id` are layered *above* `resolve_active_trip`;
  `directive == "new"` still overrides everything.
- **Conciseness (CLAUDE.md §7.1):** the create-confirmation ≤ 200 chars (one
  question/turn); assert in a test.
- **Mobile-first (CLAUDE.md §3):** the chip and the closable/reopenable panel ship
  for `sm`/`md` and `lg+` in the same change — never deferred.
- **No secrets/PII in logs** (CLAUDE.md §8); **Gemini/Telegram mocked in tests**
  (CLAUDE.md §9); **no auto-deploy**.
- **Proxy integrity:** confirm the `/send` and `/stream` route handlers forward the
  new field end-to-end (this session proved the `messages` GET handler silently
  dropped a param it didn't explicitly forward).

## 6. Edge Cases [REQUIRED]

- **Panel closed → `focused_trip_id` absent/null.** Resolver relies on
  destination-match then heuristic. Intended; covered by AC-6/AC-8.
- **Stale/forged `focused_trip_id`** (not in the user's trips): ignored (AC-8).
- **Destination matches multiple trips:** tie-break rules (AC-7); if still tied,
  most-recently-updated wins (deterministic).
- **Destination matches a trip ≠ focused trip:** drift switch to the matched trip
  (AC-6); reply echoes the new id so the panel follows (AC-9/AC-10).
- **Casual destination question while a trip is open** ("what is a trip in Rome
  like?" with Barcelona focused): Rome matches no trip → focus stays Barcelona, no
  Rome trip created, panel unchanged (AC-13).
- **Many trips (100+):** `list_trip_summaries` already returns all rows ordered by
  recency; matching is O(n) string compare over a small enriched list — no prompt
  growth, no token impact. (No truncation needed since nothing goes to an LLM.)
- **Concurrency / re-entry:** focus resolution is pure per-turn; two rapid messages
  each carry their own `focused_trip_id`; the echoed id is idempotent (same id → UI
  no-op per AC-10).
- **Same-trip echo mid-scroll:** AC-10 diff-guard prevents remount/scroll reset.
- **Router omits `entities` / malformed JSON:** resolver treats missing destinations
  as "no drift signal" and uses `focused_trip_id`/heuristic (no crash).
- **CountryIntelSaga refresh fails** (network): unchanged from task 38 — async,
  best-effort, never blocks the reply.
- **Auth/RLS:** `focused_trip_id` only *selects* context; all trip reads remain
  RLS-scoped to the user. A focus id for another user's trip simply fails to match
  the user's summary list and is ignored (AC-8) — no cross-tenant read.

## 7. Implementation Plan [REQUIRED]

### Step 1 — Loop fix: CountryIntelSaga ownership (`country_intel.py`)
Rewrite `should_activate` so ownership requires a real grounded answer. Keep the
listener branch; remove the dead owner-fallback.
```python
def should_activate(self, intent, entities, trip, state) -> Tuple[bool, bool]:
    """(can_act, wants_to_own). Owns ONLY when it can do a real grounded
    refresh: the resolved trip has a confirmed destination with an iso_country.
    Otherwise it never owns — conversational sagas handle the turn."""
    side_effects = entities.get("side_effects_seen", [])
    if any(s.get("kind") == "destination_upsert"
           and s.get("payload", {}).get("status") == "confirmed" for s in side_effects):
        return True, False                       # listener: refresh strip, don't own
    if any(s.get("destination_just_confirmed") for s in side_effects):
        return True, False

    if entities.get("intel_question") and self._has_confirmed_destination(trip):
        return True, True                        # owner: a real intel answer exists
    return False, False

@staticmethod
def _has_confirmed_destination(trip) -> bool:
    if not trip:
        return False
    return any(d.get("status") == "confirmed" and d.get("iso_country")
               for d in (trip.get("destinations") or []))
```
Delete the `return SagaResult(text="I can look up travel facts for you. Which
country are you planning to visit?")` fallback in `_answer_question` (it is now
unreachable as an owner reply; if defensive code remains, it must never be a turn
reply).
→ verify: `test_country_intel.py` — AC-1 (no confirmed dest → `(False,False)`),
AC-2 (confirmed dest → `(True,True)` + refresh ack), AC-3 (listener on confirm).

### Step 2 — Destination-enriched summaries (`trip_repo.py`)
Extend the select and `TripSummary`:
```python
class TripSummary(BaseModel):
    id: str
    title: str | None = None
    status: str
    reference_date: str | None = None
    vision_summary: str | None = None
    updated_at: str
    destinations: list[dict] = []   # [{"name","iso_country","status"}] from relation

# list_trip_summaries select:
.select("id, title, status, reference_date, vision_summary, updated_at, "
        "trip_destinations(name, iso_country, status)")
# map the nested relation into TripSummary.destinations
```
`reference_date` (already selected) is the tie-break date; no extra date query.
→ verify: a repo/unit test asserts summaries include destinations (mock the DB
client per `backend/TESTING_STRATEGY.md`).

### Step 3 — Resolver: destination match + focus + tie-break (`trip_resolver.py`)
Layer above the existing heuristic; `directive == "new"` still short-circuits first.
```python
def resolve_trip_focus(summaries, message, entities, directive, focused_trip_id=None):
    """Returns (chosen_summary | None, superseded_title | None, create_new: bool)."""
    if directive == "new":
        established = [s for s in summaries if is_established(s)] if summaries else []
        prior = _most_recent(established) if established else None
        return None, (prior.get("title") if prior else None), True

    dests = [d.lower() for d in ((entities or {}).get("destinations") or []) if isinstance(d, str)]
    if dests:
        matches = [s for s in summaries if _summary_matches_destinations(s, dests)]
        if matches:
            return _tiebreak(matches), None, False     # AC-6 drift / AC-7 tie-break

    if focused_trip_id:
        focused = next((s for s in summaries if s.get("id") == focused_trip_id), None)
        if focused:                                     # AC-8: ignored if not found
            return focused, None, False

    return resolve_active_trip(summaries, message, entities), None, False  # heuristic

def _summary_matches_destinations(summary, dests_lower) -> bool:
    names = [(d.get("name") or "").lower() for d in (summary.get("destinations") or [])]
    title = (summary.get("title") or "").lower()
    return any(d in title or title in d or any(d in n or n in d for n in names) for d in dests_lower)

def _tiebreak(matches):
    """active(today in range) -> nearest upcoming -> most recent past -> most-recent-updated."""
    # use reference_date vs today; ties fall back to _most_recent(matches)
    ...
```
Update the one caller in `agent.py` to pass `focused_trip_id`.
→ verify: `test_trip_resolver.py` — AC-6 (single match / focused / no-match→heuristic),
AC-7 (multi-match tie-break), AC-8 (stale focus ignored).

### Step 4 — Orchestrator wiring + relaxed creation + metadata (`agent.py`)
- Thread `focused_trip_id` from the request into `_dispatch_sagas` and into
  `resolve_trip_focus(...)`.
- **Relax auto-create:** narrow the `agent.py:656-666` block so a `DREAMING` trip is
  created only when `intent == "PLAN"`, `directive == "new"`, or an explicit
  go-signal — **not** for DiscoverySaga casual `TRIP` turns. (Casual turns run with
  `trip=None`; DiscoverySaga answers via TripAgent and stages nothing.)
- Surface the resolved trip id in the returned result dict (e.g.
  `result["focus_trip_id"] = trip.get("id") if trip else None`) so the router can
  embed it.
→ verify: `test_orchestrator.py` — focus threading; casual TRIP → no `upsert_trip`;
PLAN/new → `upsert_trip` called; result carries `focus_trip_id`.

### Step 5 — Confirm-before-create gate (`planning.py`, `discovery.py`)
Reuse task 44's stateless confirmation pattern: when intent is *suspected* (not a
clear PLAN/go-signal) but the user seems to want to start a trip, return a
`SagaResult` whose text is a ≤ 200-char one-line confirm ("Want me to start a trip
for <place>?") with **no** side effects and **no** trip creation. The next turn's
router classification (PLAN / affirmative) drives the actual creation.
→ verify: `test_discovery_saga.py` — AC-13 (casual → no trip, no side effect),
AC-14 (suspected → confirm text ≤ 200, no creation; explicit PLAN → creates).

### Step 6 — Chat router: read focus, embed focus (`chat.py`)
- Read `payload.focused_trip_id` and pass it to `process_request_for_user(...)`.
- Extend `_reply_metadata(...)` (or its call sites) to include
  `"focus_trip_id": agent_result.get("focus_trip_id")` for both `/chat/send` and the
  `/chat/stream` `done` event (which already carries `ui`, `message_id`, etc.).
→ verify: orchestrator/route unit test asserts `metadata.focus_trip_id` present
(mock orchestrator).

### Step 7 — Frontend: send focus, consume focus (`useChat.tsx`, `useChatStream.ts`)
- Add `focused_trip_id` to the POST bodies: `useChat.sendSelection` (`/api/chat/send`)
  and `useChatStream.run` (`/api/chat/stream`). Source it from a value threaded in
  from `DashboardShell.activeTripId` (see Step 9).
- In `useChatStream` `onDone`, read `data.focus_trip_id` and add `focusTripId` to
  `StreamDone`; in `useChat`, attach it to the message metadata alongside `ui`, and
  expose an `onFocusTrip(id)` effect/callback.
- **Verify** `send/route.ts` and `stream/route.ts` forward the whole body (they do
  today via `JSON.stringify(body)`) — add `focused_trip_id` to the body and confirm
  it reaches the backend; **no handler edit expected** (contrast the `messages` GET
  handler, which had to be patched to forward params this session).
→ verify: `npm run build`; manual network check that the POST body includes
`focused_trip_id` and the `done` event includes `focus_trip_id`.

### Step 8 — Frontend chip + icon (`DashChips.tsx`, `DashIcons.tsx`, `ChatPanel.tsx`)
- Add `MapPinIcon` to `DashIcons.tsx` (or use the 📍 glyph) and a `FocusedTripChip`
  to `DashChips.tsx` following the existing `StatusChip` pill pattern (rounded-full,
  `var(--primary)` tint, icon + label, `cursor-pointer hover`).
- Render it in the `ChatPanel.tsx` header after the Aletheia identity block (~line
  910) when `focusedTrip` is set; include a small X. New ChatPanel props:
  `focusedTrip?: { id: string; destination: string } | null`,
  `onOpenTrip?: () => void`, `onClearFocus?: () => void`.
→ verify: `npm run build`; render on mobile (`sm`) and desktop (`lg`) viewports.

### Step 9 — Dashboard wiring: closable panel + apply focus (`DashboardShell.tsx`)
- Pass `activeTripId` (and the trip's primary destination, from the loaded `trip`)
  into the chat layer so it rides outgoing messages; pass `setActiveTripId` so a
  reply's `focus_trip_id` can switch the panel.
- Apply focus echoes with a **diff guard**: `if (newId && newId !== activeTripId)
  setActiveTripId(newId)` (AC-10) — never set the same id (avoids remount/scroll
  reset; the panel has no `key=` so prop-only updates are safe).
- Add panel open/close state + an X on `TripDetailPanel`; chip X →
  `setActiveTripId(null)` + close (AC-12); reopen via existing TopNav switcher /
  TripLibrary.
→ verify: `npm run build`; manual — open Spain trip, ask "what can I see in
Barcelona?" → panel stays/switches correctly; close via X → next message sends
`focused_trip_id=null`; same-trip echo → no scroll reset.

### Step 10 — Docs
Update `README.md` (trip-context-sync, relaxed creation, the loop fix).
→ verify: README reflects the new behavior; no stale claim about auto-created trips.

## 8. Testing Plan [REQUIRED]

**Unit (backend, Gemini/Telegram mocked):**
- `test_country_intel.py` [create]: AC-1 `(False,False)` with no confirmed dest;
  AC-2 `(True,True)` + refresh ack with a confirmed dest; AC-3 listener on
  `destination_upsert`/`destination_just_confirmed`; assert the fallback string is
  never returned as an owner reply.
- `test_trip_resolver.py` [modify]: AC-6 single destination match (drift to non-
  focused), focused-trip selection, no-match→heuristic(`None` ok); AC-7 multi-match
  tie-break (active-today / nearest-upcoming / most-recent-past); AC-8 stale
  `focused_trip_id` ignored; `directive=="new"` still overrides.
- `test_discovery_saga.py` [modify]: AC-13 casual TRIP → no `upsert_trip`, no
  `destination_upsert` side effect, TripAgent delegated; AC-14 suspected intent →
  confirm text ≤ 200 chars, no creation; explicit PLAN/go → creation.
- `test_orchestrator.py` [modify]: `focused_trip_id` threaded into resolution;
  result dict carries `focus_trip_id`; casual TRIP does not create; PLAN/new does;
  `metadata.focus_trip_id` populated on the reply path.

**Frontend:** `npm run build` (type-check). Manual flows below stand in for
component tests (no RTL harness in repo).

**Manual checks (mobile + desktop):**
1. Casual: open a Barcelona/Spain trip, ask "what is a trip in Rome like?" → answer
   only; no Rome trip; panel unchanged; no chip change. (AC-13)
2. Drift: with Spain focused ask "what can I see in Barcelona?" → resolver matches
   the Spain trip (Barcelona destination), reply echoes its id, panel stays/sharpens
   on Spain; ask about a *different* trip's city → panel switches. (AC-6/AC-9/AC-10)
3. Loop regression: with **no** trips, ask "do I need a visa for Japan?" → a real
   conversational answer (TripAgent), never the fallback string. (AC-1)
4. Same-trip echo: scroll the TripPanel, send a message about the same trip →
   reply's `focus_trip_id` equals current → no scroll reset. (AC-10)
5. Chip: focused trip shows "📍 <destination>" in the header on `sm` and `lg`;
   tapping it opens/scrolls the panel; X closes panel and clears focus; next message
   carries `focused_trip_id=null`. (AC-11/AC-12)

**Sample payloads:**
- Send (web): `POST /api/chat/send { "body": "what can I see in Barcelona?",
  "focused_trip_id": "<spain-trip-uuid>" }` → reply `ChatMessageOut.metadata`
  includes `{"focus_trip_id": "<spain-trip-uuid>", "action": "RESPONSE", ...}`.
- Casual: `POST /api/chat/stream { "body": "what is a trip in Rome like?",
  "focused_trip_id": null }` → `done` event `focus_trip_id: null`; no trip created.

## 9. Conditional Sections

### 9.1 Data Model & RLS [CONDITIONAL]
**No migration.** Decision recorded because the user explicitly asked whether new
fields are needed: they are not. `focused_trip_id` is ephemeral (request field, not
stored). Destinations already exist in `public.trip_destinations` (`name`,
`iso_country`, `status`); §3 AC-5 only widens a `SELECT` over that existing relation,
which inherits the parent trip's RLS (reads are service-role in the repo layer but
scoped by `user_id` filter, unchanged). If "persist last focused trip across reloads"
is later wanted, that would add a `user_profiles.profile_data.last_focused_trip_id`
key (JSONB, no DDL) — out of scope here.

### 9.2 LLM Considerations [CONDITIONAL]
- **No new prompt input, no new call.** Trip matching consumes the router's existing
  `entities.destinations` output; the match itself is pure Python over a DB result.
  **Per-turn token delta: 0.** This is the deliberate choice over an LLM trip-
  selection approach (which would add ~150–200 input tokens to *every* turn,
  including the majority that reference no trip) — rejected per CLAUDE.md §10.
- The create-confirmation text (Step 5) is model-authored where it already is today;
  no new prompt-injection surface (the directive/intent values steer deterministic
  Python branches, never re-enter a prompt verbatim).
- RouterAgent model tier unchanged (`gemini-3.1-flash-lite`).

### 9.3 Observability [CONDITIONAL]
- Extend the existing `trip_focus_resolved` metric (task 44) with
  `resolution_source ∈ {destination_match, frontend_focus, heuristic, new_directive}`
  so we can see how often each path drives focus, and a `confirmed_destination` flag
  on CountryIntel ownership decisions.
- Log at INFO (no PII): `user_id`, resolved `trip_id`, `resolution_source`,
  `created_trip: bool`. Never log message bodies.
- No new alerts; the loop regression is covered by AC-1's unit test, not a runtime
  alert.

### 9.4 Rollback Plan [CONDITIONAL]
Additive + behavioral; **no schema/data migration to undo**. Revert the diff: the
frontend stops sending `focused_trip_id`, the resolver loses the destination/focus
layers (falls back to `resolve_active_trip`), CountryIntelSaga regains its prior
(buggy) ownership, and creation re-eagers. No data recovery needed. Backend and
frontend are independently revertible (an old frontend simply omits the field; the
backend treats it as `None`).

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
- **City→country alias map** (already flagged): "Barcelona" cannot match a trip
  stored only as "Spain" with no Barcelona destination. Deferred — current trips
  store cities, so direct name match suffices.
- **§9.3 `resolution_source` metric enrichment deferred.** Adding
  `resolution_source ∈ {destination_match, frontend_focus, heuristic,
  new_directive}` to `trip_focus_resolved` would require `resolve_trip_focus` to
  return the source (a 4-tuple), churning every call site + test. The ACs (§3)
  and DoD (§11) don't require it; the new `trip_create_confirm_offered` metric
  was added, and the focus path is unit-covered. Left for a follow-up that does
  the return-shape change deliberately.
- **Pre-existing destination-staging bleed (out of scope, §2 Non-Goals):** a
  casual destination question asked *while a different trip is focused* (e.g.
  "what is Rome like?" with Barcelona open) can still let the slot extractor
  stage "Rome" as a `considering` destination on the **focused** trip, because
  PlanningSaga owns the `TRIP + trip≠None` turn and runs extraction. This is the
  PlannerAgent destination-grounding issue carried from task 44 §10.1, not the
  trip-*creation* relaxation this task targets. No regression introduced (it
  predates this task); flagged for the grounding follow-up.

### 10.2 Spec deviations
- **Extended `test_country_intel_saga.py` instead of creating
  `test_country_intel.py`.** The file the spec marked `[create]` already existed;
  creating a second file would duplicate fixtures. The existing
  `test_saga_activation_as_owner` encoded the *buggy* `(True, True)` ownership —
  it was rewritten to the AC-1 behavior, which was the loop fix itself.
- **`planning.py` not modified.** Step 5 lists planning.py for the
  confirm-before-create gate, but on reflection no change is needed there: a
  `PLAN` turn is already explicit consent (it creates), and the only ambiguous
  create case (a soft "I'm thinking of going…") arrives as a `TRIP` turn owned by
  `DiscoverySaga`, where the confirmation now lives. PlanningSaga's task-44
  `_confirm_switch` already covers the *different* ambiguity (continue-vs-new on a
  complete trip). Adding a second gate to planning.py would be redundant.
- **Default-trip adoption made once-only (`DashboardShell`).** AC-12 (chip X
  clears focus + closes panel) was impossible with the original
  adjust-state-during-render adoption, which re-adopted `defaultActiveId` on every
  render where `activeTripId === null` — so clearing focus bounced straight back.
  Guarded with a ref so the default is adopted exactly once on first load; an
  explicit clear-to-null now sticks. (Within §4's `DashboardShell.tsx` scope.)
- **Frontend `focused_trip_id` wiring is via a ref bridge, not prop-drilling.**
  `useChat` exposes `registerFocusBridge(getFocusedTripId, applyFocus)`; the
  shells register the current `activeTripId` getter + a diff-guarded applier,
  mirroring the existing `registerOpenChatPanel` / `registerComposerSetter`
  pattern. (Within §4's `useChat.tsx` + `DashboardShell.tsx` scope.)

## 11. Definition of Done [REQUIRED]

- [x] AC-1…AC-14 pass (unit tests for AC-1..AC-9/AC-13/AC-14; AC-10..AC-12 are
      UI behaviors — build-verified + reasoned, no RTL harness in repo).
- [x] §6 edge cases covered by tests or deferred in §10.1/§10.2.
- [x] `ruff check` clean (backend); `pytest` unit suite passes (542 passed).
- [x] `npm run build` succeeds; chip + closable panel implemented for `sm`/`md`
      and `lg+` (same change). Live mobile/desktop click-through still recommended.
- [x] The reported loop cannot recur (AC-1 test is the guard).
- [x] `README.md` updated (CLAUDE.md §6).
- [x] No file outside §4 modified — except the two extra test files updated by the
      new field (`test_chat_stream.py`, `test_country_intel_saga.py`) + the
      middleware→proxy rename (separate user request); §10.2 explains the rest.
- [x] No secrets/PII in logs; Gemini/Telegram mocked in tests.
- [x] No schema migration introduced (confirm §9.1 still holds).

## 12. Open Questions [OPTIONAL]

- None blocking. (Resolved with the user: deterministic best-effort matching with
  zero added token cost; lazy + confirm creation; chip-X clears focus and closes the
  panel; focus is not persisted across reloads.)
