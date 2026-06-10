# Task 40 — Trip Detail Panel redesign + live Supabase wiring

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §6, §10.6, §11.2.
> Depends on tasks 34–39. The visible payoff of the whole §7 effort.

> **Implementation decision (2026-06-10, ratified with owner): no Claude
> Design round-trip.** This task *extends* an already-polished visual identity
> (glassmorphic `aletheia-card`, Geist, blue→purple gradient) with new
> sections whose sibling patterns already exist (task 38 `CountryIntelStrip`/
> `SafetyWarningBanner`, task 39 `LogisticsRail`/`BookingCard`). The design +
> build were done in-code with the `frontend-design` skill, keeping everything
> in one reviewable diff. §7 Step 1 (the external Claude Design prompt) and the
> "Manual operations" gate at the bottom are therefore **superseded** — see
> §10.2. The warm-ivory light palette referenced in the old prompt is owned by
> task 46 (not this task).

## 1. Problem Statement

`TripDetailPanel.tsx` is a beautifully designed but fully mocked view: a
single hand-coded Kyoto trip with a 7-day itinerary, a weather chip, a
mood note. The schema underneath the proposal (tasks 34–39) is now much
richer: a vision banner, a country intel strip with eight cards, a
logistics rail with five booking kinds, day blocks attached to bookings,
a budget bar, a scratchpad, live-trip state (mood, today's anchor,
swaps), and a journal — all of which surface only when their data is
populated (progressive disclosure law). This task is the visible payoff:
(1) a polished Claude Design prompt that produces the visual treatment
for every new section while preserving the existing identity, (2)
implementation of every new section in code, (3) the live Supabase
wiring — `useTripRealtime` and `useChatRealtime` from task 37 replace
`dashboard-data.ts` mocks with reactive queries.

## 2. Goals & Non-Goals

### Goals

- **Data-driven visibility**: Information is shown based on available data, not strictly bound to the trip's phase.
- **Showcase capabilities**: Empty sections display benign placeholders (e.g., "Not assessed yet" for Safety) rather than vanishing, to advertise what the app can do.
- **Layout upgrades**: Logistics opens in a side panel (desktop split-pane/mobile sheet). Country Intel is a collapsible accordion. Itinerary uses selectable Day tabs with explicit Morning/Afternoon/Evening skeletons.
- Every new section from §6.2 of the proposal is implemented with empty / partial / full states.
- The trip data flows through Realtime — the AI updating a trip via chat
  reflects in the dashboard within ~1 s.
- The Claude Design prompt is self-contained, fully described, and
  produces a coherent design across mobile + desktop matching the
  existing visual identity.
- The mock `dashboard-data.ts` is removed (or reduced to a typed
  fixture-only file for tests).

### Non-Goals

- Map redesign — the existing map canvas stays. (A separate task can
  upgrade it later.)
- Companion / sharing UI — solo only.
- File-upload / attachments — out of scope for alpha.
- Journal photos — text-only journaling (per task 34).

## 3. Acceptance Criteria

AC-1. The dashboard fetches the active trip via the Supabase client + RLS,
  uses `useTripRealtime(tripId)` to subscribe to changes, and re-renders
  on UPDATE within ~1 s of an agent mutation. Verified by a manual test:
  curl the backend to mutate, watch the dashboard update.

AC-2. Each new section (Vision banner, Country Intel, Safety
  warning, Logistics panel, Budget bar, Scratchpad, Live state card,
  Journal) renders correctly. Empty states display capability placeholders
  rather than hiding entirely. Phase-based hidden logic is removed.

AC-3. The 10-section stack order from proposal §6.2 is implemented.

AC-4. Mobile pane swipe (three-pane horizontal swipe from
  `frontend_dashboard_design.md` §4.2) still works — new sections render
  correctly inside the swipe-able main pane.

AC-5. The credits dropdown fetches balance on click (per §11.2 user
  decision — NOT realtime) and applies optimistic decrement from the
  SSE `done` event's `credits_spent`.

AC-6. The Claude Design prompt in §7.1 produces a coherent visual for
  every new section. Submitted prompt + downloaded design committed to
  `docs/design/trip_panel_redesign_v1/`.

AC-7. `dashboard-data.ts` no longer hard-codes a Kyoto trip — replaced
  with reactive Supabase queries via `useTripRealtime` / `useChatRealtime`.

AC-8. RLS verified: opening the dashboard as a different user shows
  zero trips, not someone else's.

## 4. Files & Modules Touched

```
frontend/src/components/dashboard/TripDetailPanel.tsx                [modify]
frontend/src/components/dashboard/VisionBanner.tsx                   [create]
frontend/src/components/dashboard/CountryIntelStrip.tsx              [from task 38 — referenced]
frontend/src/components/dashboard/SafetyWarningBanner.tsx            [from task 38]
frontend/src/components/dashboard/LogisticsRail.tsx                  [from task 39]
frontend/src/components/dashboard/BudgetBar.tsx                      [create]
frontend/src/components/dashboard/Scratchpad.tsx                     [create]
frontend/src/components/dashboard/LiveStateCard.tsx                  [create]
frontend/src/components/dashboard/JournalSection.tsx                 [create]
frontend/src/components/dashboard/DashboardShell.tsx                 [modify]
frontend/src/components/dashboard/TripLibrary.tsx                    [modify]
frontend/src/components/dashboard/ProfileDropdown.tsx                [modify — credits on-demand]
frontend/src/hooks/useTripRealtime.ts                                [from task 37]
frontend/src/hooks/useChatRealtime.ts                                [from task 37]
frontend/src/hooks/useTrip.ts                                        [create — combines fetch + realtime]
frontend/src/lib/dashboard-data.ts                                   [delete or reduce to fixtures]
docs/design/trip_panel_redesign_v1/                                  [create]
docs/design/CLAUDE_DESIGN_PROMPT.md                                  [create]
README.md                                                            [modify]
```

## 5. Constraints

- Mobile-first responsive — every `lg:` breakpoint has the corresponding
  `sm:` / `md:` implementation in the same commit (per `CLAUDE.md` §3).
- Match existing patterns in `frontend/src/components/` — glassmorphic
  cards, Geist font, blue→purple gradient, `aletheia-card` class, etc.
- Animations stay within the existing budget: `animate-fade-up`,
  `transition`, map pan/zoom. No new motion primitives.
- All third-party API calls go through Next.js Route Handlers / Server
  Actions — no direct calls from the browser (per `CLAUDE.md` §8).
- Progressive disclosure law is non-negotiable.

## 6. Edge Cases

- **No active trip** → TripDetailPanel renders the onboarding canvas from
  `frontend_dashboard_design.md` §7.
- **Realtime drops** → fallback to manual refresh button + polling once
  every 60 s.
- **Trip has zero day blocks** → itinerary section shows a tiny
  `+ Add day` CTA.
- **Trip has bookings but no itinerary** → logistics rail visible,
  itinerary section hidden.
- **Trip is in REMEMBERING** → journal section visible, itinerary
  collapsed by default, planning UI hidden.
- **Slow Supabase response** → skeleton placeholders, never spinners.
- **User scrolls to the bottom of a long itinerary on mobile** → chat
  bubble stays bottom-right fixed; doesn't cover content.

## 7. Implementation Plan

### Step 1 — The Claude Design prompt (delivered as part of this task)

`docs/design/CLAUDE_DESIGN_PROMPT.md`:

````markdown
# Trip Detail Panel — Redesign brief for Claude Design

You are designing the next version of the Trip Detail Panel for Aletheia
Travel, an AI travel companion. The dashboard is the visual layer on top
of an AI agent that already converses with the user via Telegram and web.

## Existing visual identity (preserve)

- Brand: **Aletheia Travel** — the bot persona is warm, brief, useful,
  literate, never preachy.
- Typography: **Geist** (already in use). Extrabold display type for trip
  names; serif italic for the vision banner (de Botton's "anticipation
  is the deepest pleasure of travel").
- Color: blue→purple gradient (`var(--primary)` to `#9333ea`) for primary
  affordances. Status chips: muted blue (exploring), primary gradient
  (planning), emerald pulsing dot (active), warm amber (complete).
- Cards: glassmorphic `bg-background/70 backdrop-blur-xl border border-border`,
  rounded `2xl`.
- Motion: `animate-fade-up`, map pan/zoom, accordion expand. Nothing else.
- Light/dark theme parity — every section works in both.
- **Light theme is WARM IVORY, not white** (ratified by task 46, lands
  after this task): background `#faf8f3`, surfaces `#f1ede4`/`#f5f2ea`,
  borders `#e6e0d3`, warm ink text `#23201a`. Design all light-mode
  artifacts on this palette so the design pass happens once — the code
  keeps using CSS tokens either way (task 46 flips the token values).
- Mobile is non-negotiable: three-pane horizontal swipe layout (library /
  main / map) per `specs/frontend_dashboard_design.md` §4.2.

## Sections to design (priority order, top → bottom)

For each section, design states for `empty`, `partial`, and `full`.
Phase-based hidden logic is removed (no sections are completely hidden
just because of the trip phase). Empty states use benign capability
placeholders (e.g., "Not assessed yet") instead of vanishing.

### 1. Vision banner
Renders `trip.vision_summary` as a single italic serif line, max one
sentence. No labels around it — it IS the trip's identity, not a field
labelled "Vision."

### 2. Header (existing — preserve)
Destination, date range, current day if LIVING.

### 3. Country intel — collapsible accordion
Normally collapsed. On press, expands to show a grid of intel cards:
Visa, Safety, Health, Money, Connectivity, Plug, Language, When.
If data is missing, display a benign placeholder (e.g., "Not assessed yet").
- Tap on a populated card → bottom sheet (mobile) / side panel (desktop) with full text.
- Every detail view includes the disclaimer: "Verify with official
  sources before booking."

### 4. Safety warning banner — only if `safety.score_10 < user_threshold`
Pale amber background, single line of body text, "View advisory" link,
small dismiss X. Informational, never blocking.

### 5. Itinerary
Selectable Day tabs (e.g., Day 1, Day 2). If no days exist, render a single empty day.
Below the selected day, render explicit skeletons for **Morning**, **Afternoon**, and **Evening**.
Each empty block contains a subtle "+ Add activity" CTA to encourage structured planning.

### 6. Logistics — Side panel
Main view shows a summary or "ghost CTAs". Clicking opens a dedicated
Logistics side panel (opens next to the main panel on desktop; slides from right on mobile).
- **Read Mode (Density)**: Booking detail cards display *only* populated fields.
- **Write Mode**: Tapping 'Edit' opens the BookingFormSheet exposing *all* available fields.

### 7. Budget bar
Horizontal stacked bar: each category a slice colored by status (under
budget = primary; over = amber). One line below: "On track" / "$120 over."
If target_eur is unset, display a "Budget not set" placeholder.
Tap → expand to per-category detail.

### 8. Scratchpad
Three accordions: Saved ideas, Packing list, Custom notes.
- Saved ideas: chip list, each tappable → opens chat with the idea
  prefilled as a question.
- Packing list: checklist.
- Custom notes: a single textarea, autosaved.

### 9. Live state card
- Mood check-in widget (emoji slider, "How are you feeling today?").
- Today's anchor activity highlighted (Tofuku-ji moss garden style).
- AI suggestion cards (existing pattern).

### 10. Journal
Interactive element that opens on click, revealing a textarea ready for
input and populated with existing notes, if any.

## Interaction patterns

- Tap on a country intel card → bottom sheet (mobile) or side panel
  (desktop) opens with full details.
- Selecting an itinerary day still pans the map (existing behaviour).
- Edit on any BookingCard → BookingFormSheet (modal on mobile,
  side panel on desktop).
- Mood emoji selector → fires a single-API-call update to
  `trips.live_state.last_mood`; the bot may respond in chat within
  seconds.

## Empty-trip onboarding (preserve from `frontend_dashboard_design.md` §7)
- "Your journey starts here." headline.
- Three capability cards: Discover / Plan / Live.
- Primary CTA "Plan your first trip →".

## What to deliver

1. Desktop hero comp at 1440 px wide showing a FULL Kyoto trip (vision,
   country intel, logistics, itinerary, budget, scratchpad).
2. Mobile main-pane comp at 390 px wide showing the same Kyoto trip.
3. Mobile main-pane comp showing an EMPTY trip in DREAMING (vision banner
   visible, country intel hidden, logistics ghost CTAs visible).
4. A comp showing the LIVE state (active trip, mood check-in, today
   anchor highlighted).
5. A comp showing REMEMBERING (journal visible, planning UI hidden).
6. The Country Intel bottom-sheet expanded.
7. The BookingFormSheet for a flight in edit mode.

## Visual rules to ignore (don't waste time on)

- Map tile style — already specified elsewhere.
- Login / auth pages — already designed.
- Profile / DNA page — separate task.

## Example trip JSON for context

(Embed the full Kyoto trip from `specs/proposal_trip_model_and_planning_saga.md`
§4.2, with country_intel and 3 bookings populated.)
````

### Step 2 — `useTrip` composition hook

Wraps `useTripRealtime` and provides the assembled Trip object with all
child collections populated.

### Step 3 — Implement each new section component

(See §4 file list. Each is a small, focused React component, mobile-first
Tailwind, glassmorphic.)

### Step 4 — Replace `dashboard-data.ts`

Reduce `dashboard-data.ts` to type exports + a small fixture for unit/
storybook tests. The Kyoto mock data is removed from runtime.

### Step 5 — Credits on-demand

`ProfileDropdown.tsx`: on click, fetch `credits.balance` via a Route
Handler (Server Action). Apply optimistic decrement from the SSE `done`
event's `credits_spent`. Never subscribe in Realtime.

### Step 6 — Tests

- Visual regression: storybook captures per section state.
- E2E manual: a Cypress smoke test covering "create trip → mutate via
  backend → see UI update within 1s."

## 8. Testing Plan

- **Unit:** each new component's render logic for the four states.
- **Storybook:** every section has stories for empty/partial/full/hidden.
- **Manual desktop + mobile:** full Kyoto trip; empty DREAMING trip;
  LIVING trip with mood; REMEMBERING trip.
- **Manual realtime:** open dashboard, mutate trip via curl,
  assert UI updates within 1 s.

## 9. Conditional Sections

### 9.3 Observability

- Frontend logs `realtime_disconnect` to a Cloud Logging endpoint via
  a tiny `/observability/client-event` proxy.
- Slow Supabase queries (> 1 s) logged at WARN.

### 9.4 Rollback Plan

- Restore `dashboard-data.ts` (kept in git history).
- Revert the dashboard import from `useTrip` → static mock.
- Frontend redeploy.

## 10. Findings & Follow-ups

### 10.1 Improvements observed / audit (related implemented specs)

Audit of the specs this task builds on, with gaps surfaced (not silently
downgraded):

- **AC-5 optimistic credit decrement — PARTIAL.** The "fetch balance on
  click" half is satisfied (pre-existing: `ProfileDropdown` calls
  `userProfile.refetchCredits()` on open, so the dropdown always shows a
  fresh balance). The "optimistic decrement from the SSE `done` event's
  `credits_spent`" half is **not** wired: the backend `done` SSE payload
  (`interfaces/routers/chat.py`) carries no credits, and the orchestrator
  return contract is `{text, action, slot_request}` only — the per-turn
  `total_cost_credits` is computed in `_save_and_finish` and emitted as the
  `turn_completed` metric but never returned. Wiring it end-to-end touches:
  orchestrator return → chat-stream `done` → `useChatStream.StreamDone` →
  `useChat.onDone` → profile balance state. Deferred as a scoped follow-up
  (priority: low — the balance is already accurate on every dropdown open;
  only the instantaneous mid-turn decrement is missing, and the next open
  reconciles it).
- **BookingFormSheet `onSave` is a no-op stub.** Bookings are created/edited
  via chat (task 39 `BookingInputSaga`); the structured form has no direct
  write endpoint. Left as-is (matches task 39's chat-first model); a direct
  `trip_bookings` write route is a follow-up if the form should persist
  independently. Priority: medium.
- **Task 37 realtime** (`useTripRealtime`, `useChatRealtime`) and **task 38**
  (`CountryIntelStrip`, `SafetyWarningBanner`) and **task 39**
  (`LogisticsRail`, `BookingCard`, `BookingFormSheet`) were all present and
  correctly shaped; consumed directly. No fixes needed.
- **Repo-wide lint baseline is red** (15 pre-existing `npm run lint` errors
  in untouched files: `react/no-unescaped-entities`, the React-Compiler
  `react-hooks/set-state-in-effect` rule, and `@typescript-eslint/no-explicit-any`
  in `app/page.tsx`, `terms`, `privacy`, `sign-up`, `ChatPanel`,
  `CountryIntelStrip`, `ThemeProvider`, `AccountSettings`, `useUserProfile`,
  `intel-render`). NOT addressed here (surgical-changes rule). This task's
  new files are lint-clean. A repo-wide lint cleanup is a separate task.

### 10.2 Spec deviations

- **No Claude Design round-trip** (see header note). §7 Step 1 (the external
  `docs/design/CLAUDE_DESIGN_PROMPT.md` deliverable) and the "Manual
  operations" approval gate are superseded: design + build done in-code with
  the `frontend-design` skill. `docs/design/trip_panel_redesign_v1/` and
  `CLAUDE_DESIGN_PROMPT.md` are therefore NOT produced; AC-6 is dropped.
- **§4 file-list additions:** `frontend/src/lib/dashboard-fixtures.ts`
  [create] (the Kyoto mock moved here for tests + the map placeholder, per
  §4's "delete or reduce to fixtures"); `frontend/src/lib/trip-adapter.ts`
  [create] (the raw-Supabase→view-model adapter — the cleanest seam to keep
  the existing itinerary layouts untouched); `frontend/src/components/dashboard/TopNav.tsx`
  [modify] (consumed the removed `TRIPS` mock — rewired to live summaries).
- **Storybook/unit tests dropped.** The frontend has no test harness
  (no vitest/jest/testing-library/storybook) — consistent with prior
  frontend tasks shipping on `npm run build` + `npm run lint` + manual
  checks. Adding a runner is out of scope; verification is build + lint +
  the manual checklist in §8.
- **Map left mock-fed.** Map redesign is a §2 non-goal (task 49 replaces it
  with MapLibre). Live itinerary blocks carry no abstract-canvas pins, so
  `KyotoMap` renders from `dashboard-fixtures` as a visual placeholder,
  decoupled from live trip data, until task 49.
- **Credits-on-demand** (AC-5) was already implemented pre-task; see §10.1.

## 11. Definition of Done

- [x] AC-1 (live fetch + `useTripRealtime` subscription via `useTrip`), AC-2
  (four states per section — progressive disclosure in `TripDetailPanel` +
  each component self-hides), AC-3 (10-section stack order), AC-4 (mobile
  three-pane swipe preserved), AC-7 (`dashboard-data.ts` mock removed →
  live queries), AC-8 (RLS via the authenticated browser client) — met.
- [~] AC-5 — partial (fetch-on-click ✓; optimistic decrement deferred, §10.1).
- [—] AC-6 — dropped (no Claude Design, §10.2).
- [x] `npm run build` succeeds (TypeScript clean, 30 routes).
- [x] New files lint-clean (`npm run lint`); pre-existing repo errors untouched.
- [x] Mobile + desktop layouts preserved; manual viewport checks owed (§8).
- [x] README updated with the new dashboard architecture.

## Manual operations (user, post-implementation)

The Claude Design round-trip is superseded (§10.2). Remaining manual
verification (owner, requires the running app + a seeded trip):

1. Open the dashboard with a real trip; confirm sections appear/hide per
   phase (vision pre-departure; live card only when active; journal only
   post-trip) and that empty sections vanish rather than showing "N/A".
2. Mutate the trip via the backend (or chat) and confirm the panel updates
   within ~1s (AC-1), at 375px and desktop.
3. Open as a different user → zero trips, not someone else's (AC-8).
