# Task 50 — Capability surface: registry, ✨ launcher, contextual suggestions

> Spec per `task_template_v2.md`. Stream F of the 2026-06-10 product-evolution
> brainstorm — the final stream. Lands after task 49 (numbered order).
> Capability inventory below references flows from tasks 38–45; entries whose
> backing task hasn't shipped yet are simply omitted from the registry until
> it does (the registry is data — adding an entry later is one object).

---

## 1. Problem Statement [REQUIRED]

The product hides its value. Planning a trip, importing a booking, country
intel, mood check-ins, journaling, promo codes, Telegram linking — all of it
exists, but almost none of it is visible: a user discovers features only by
happening to ask the right thing in chat. The owner's philosophy is "deliver
more than promised — hidden delights are fine, but nothing *generally
useful* should be hidden." There is currently no place in the web app (and
especially on mobile) where a user can see what Aletheia can do and engage a
flow with one tap. This task adds that surface the way AI products expose
skills/connectors: a single capability registry rendered as a ✨ launcher
sheet in the chat composer and as contextual suggestion chips in exactly two
moments (empty chat, no-trip dashboard). The launcher carries a thin
expandable "how it works" per entry; the full, browsable in-app manual is a
sibling spec (`task_53_capability_guide_page.md`) that renders the SAME
registry as an actionable reference page. The manual is no longer deferred:
the flows it documents (all sagas, the trip model) have shipped, so the
"write the guide once the product is real" rationale is satisfied now. Only
the logged-out marketing/landing page (today's stale `/features` +
`/how-it-works`) remains a later follow-up.

Ratified decisions (2026-06-10, extended 2026-06-12): one registry, now
feeding THREE surfaces (launcher + contextual chips + in-app manual page —
the manual lives in sibling spec `task_53`); the launcher is a single
grouped sheet with every available entry visible (not a two-level
drill-down); hybrid launch per entry (starter message | structured intent |
link).

## 2. Goals & Non-Goals [REQUIRED]

**Goals**

- G1. A user can open one sheet from the chat composer — on mobile and
  desktop — and see every generally-useful capability, grouped by journey
  stage, with a one-liner and an expandable 2–3-sentence "how it works".
- G2. Tapping a capability starts its flow in one step: a canonical chat
  message, a deterministic backend route, or a navigation link.
- G3. New users see 2–3 relevant suggestions in the empty chat state and
  on the no-trip dashboard — the same registry, filtered, not a separate
  content system.
- G4. Capabilities that don't apply right now (no trip, trip not LIVING,
  Telegram already linked) are hidden or shown disabled with the reason —
  the sheet never lies.
- G5. `capability_launched` metrics exist from day one — first real data
  on which features users actually want.

**Non-Goals**

- No full guide pages *in this task* — the in-app manual is its own sibling
  spec (`task_53_capability_guide_page.md`), built against the same registry.
  The logged-out marketing/landing page remains a later follow-up.
- No dashboard "features" tab (ratified: launcher + contextual only).
- No notification/tips engine, no onboarding tour, no badges/"NEW" labels.
- No Telegram surface in v1 — a `/help` generated from the registry is
  recorded as a follow-up.
- No per-user capability customization (pinning, hiding).

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. frontend/src/lib/capabilities.ts exports the typed registry; every
      entry has id, name, icon, oneLiner, howItWorks, launch, availability,
      contexts, group, and an optional example (illustrative user phrasing).
      The module also exports GROUP_META (group → {label, blurb}) so every
      surface shares one set of group labels. TypeScript exhaustively types
      launch kinds ("message" | "intent" | "link").
AC-2. A ✨ button in the chat composer opens the capability sheet: bottom
      sheet on <lg viewports, anchored popover on lg+. Grouped by journey
      stage (Plan & discover / During the trip / After the trip / Account),
      every available entry visible as a row under its group header (no
      drill-down). A footer "See everything →" link navigates to the manual
      page (task_53 route) — the only cross-surface link in the sheet.
      Esc / tap-outside / swipe-down closes. Keyboard navigable, focus
      trapped while open.
AC-3. Each row expands inline to its howItWorks text (one open at a time);
      expanding does not launch.
AC-4. Launch kinds behave per contract:
      - message: the starter text is sent through the normal chat send
        path exactly as if typed; sheet closes; the message appears as a
        user bubble.
      - intent: POST /chat/send {body: <label>, capability: <id>} — the
        orchestrator maps the id directly to its owning saga (no Router
        LLM call), the label persists as the user message.
      - link: client-side navigation (e.g. /settings#telegram); no chat
        message is created.
AC-5. Availability rules evaluated from already-loaded client state (trip
      presence/phase, telegram_linked) hide or disable entries; a disabled
      entry shows its reason ("Needs an active trip"). No new data
      fetching is introduced for availability.
AC-6. Empty chat state renders ≤3 suggestion chips from registry entries
      whose contexts include "empty_chat", availability-filtered; no-trip
      dashboard renders its ≤3 from "no_trip" context. Tapping behaves
      exactly like the same entry in the sheet.
AC-7. Backend: an unknown capability id in /chat/send is rejected 422
      with no side effects; a known id routes to its saga without a
      RouterAgent call (asserted via mock call counts) and is re-validated
      server-side against the backend's own capability→intent map (the
      client registry is NOT trusted).
AC-8. Metrics: capability_sheet_opened{surface}, capability_launched
      {id, kind, surface} emitted (web analytics path → analytics_events).
AC-9. Mobile 375px AND desktop verified: sheet ergonomics, chip layout,
      no composer layout regression; npm run build green; backend suite +
      ruff clean.
AC-10. With zero applicable contextual entries, empty states render their
      current (pre-task) content — the chips section disappears entirely,
      no empty husk.
```

## 4. Files & Modules Touched [REQUIRED]

```
frontend/src/lib/capabilities.ts                                 [create — registry + types]
frontend/src/components/dashboard/CapabilitySheet.tsx            [create]
frontend/src/components/dashboard/CapabilityChips.tsx            [create — contextual chips]
frontend/src/components/dashboard/ChatPanel.tsx                  [modify — ✨ button, empty-state chips]
frontend/src/components/dashboard/TripDetailPanel.tsx            [modify — no-trip state chips]
frontend/src/hooks/useChat.ts                                    [modify — sendCapability(id, label)]
backend/src/agentic_traveler/interfaces/schemas.py               [modify — capability field]
backend/src/agentic_traveler/interfaces/routers/chat.py          [modify — pass-through]
backend/src/agentic_traveler/orchestrator/agent.py               [modify — capability→saga map, router skip]
backend/tests/orchestrator/test_orchestrator.py                  [modify]
backend/tests/interfaces/test_chat_router.py                     [modify]
README.md                                                        [modify]
```

## 5. Constraints [REQUIRED]

- **One registry.** The sheet, the chips, the in-app manual page (task_53),
  and (future) Telegram /help all derive from `capabilities.ts` — capability
  copy and launch behavior are never duplicated per surface. The backend
  keeps its OWN minimal capability→intent map for intent-kind entries (trust
  boundary, AC-7) — the two are kept in sync by a test fixture listing
  intent-kind ids.
- **Two contextual moments only** (empty chat, no-trip dashboard). Adding
  more contexts requires its own decision — no quiet growth into a tips
  engine.
- **Availability never fetches.** Rules read state the dashboard already
  holds; a capability that can't be evaluated client-side cheaply doesn't
  get an availability rule (it stays visible and the flow itself handles
  preconditions conversationally).
- **Message-kind starters are user-visible text** — they must read like
  something a person would type ("Help me figure out where to go"), not
  like commands, because they persist in history.
- **No new realtime channels, no new tables** — registry is code; metrics
  ride the existing analytics path (free-tier discipline).
- **Mobile-first** (CLAUDE.md §3): the bottom sheet is the primary design;
  the desktop popover adapts it.
- Sheet/launch UI must not interfere with streaming: launching is
  disabled while a reply is streaming (same rule as the composer).
- CLAUDE.md §9 applies (no deploys without approval, no git mutations,
  mocked LLMs in tests).

## 6. Edge Cases [REQUIRED]

| # | Case | Intended behavior | Test |
|---|------|-------------------|------|
| E1 | Unknown/stale capability id posted (old client) | 422, no side effects (AC-7) | unit |
| E2 | Intent-kind capability for a saga needing a trip, with no trip | Backend routes to the saga; the saga's normal no-trip behavior answers (e.g. BookingInputSaga asks which trip / suggests creating one) — preconditions live in sagas, not the launcher | unit |
| E3 | Launch tapped while reply is streaming | Launch disabled (composer rule); sheet can stay open | manual |
| E4 | Credits exhausted | message/intent launches go through the existing credit gate and get the existing friendly message; link-kind unaffected | existing |
| E5 | Registry entry whose backing feature isn't deployed (spec not yet implemented) | Entry simply isn't in the registry yet (§ header note); no feature-flag machinery | design |
| E6 | telegram_linked unknown (profile still loading) | Account-group entries render enabled-default; worst case the flow itself says "already linked" | unit |
| E7 | Rapid double-tap on a capability | Single send (disabled-after-tap), idempotent UI state | unit |
| E8 | Sheet open during theme toggle / expand mode (task 46) | Pure CSS-token styling; no remount issues; verified manually | manual |
| E9 | Keyboard-only user | Tab order: composer → ✨ → sheet rows → expand/launch; Esc closes; focus returns to composer | manual |
| E10 | Screen reader | Sheet labelled (aria-modal, aria-expanded on rows); chips are buttons with accessible names | manual |

## 7. Implementation Plan [REQUIRED]

### Step 1 — Registry → verify: type-check + registry fixture test

```typescript
export type CapabilityLaunch =
  | { kind: "message"; text: string }
  | { kind: "intent";  intent: string }   // backend capability id
  | { kind: "link";    href: string };

export type CapabilityGroup = "plan" | "during" | "after" | "account";

export type Capability = {
  id: string;            // stable, snake_case
  name: string;          // "Plan a trip"
  icon: string;          // lucide icon name, matching existing usage
  oneLiner: string;      // ≤ 60 chars — launcher row + chip label
  howItWorks: string;    // 2–3 sentences — feeds BOTH the launcher inline
                         // expand AND the manual card body (task_53)
  example?: string;      // optional illustrative user phrasing, e.g.
                         // "somewhere warm in February" — rendered on the
                         // manual page; ignored by the launcher
  group: CapabilityGroup;
  launch: CapabilityLaunch;
  contexts?: ("empty_chat" | "no_trip")[];
  availability?: (s: AvailabilityState) => true | string; // string = disabled reason
};

// Shared group labels + one-line blurbs — the launcher section headers and
// the manual page group headers both read this, so they never disagree.
export const GROUP_META: Record<CapabilityGroup, { label: string; blurb: string }> = {
  plan:    { label: "Plan & discover", blurb: "Find a destination and shape the trip." },
  during:  { label: "During the trip", blurb: "Keep things moving while you travel." },
  after:   { label: "After the trip",  blurb: "Hold on to what mattered." },
  account: { label: "Account & setup", blurb: "Preferences, channels, and credits." },
};
```

Initial inventory (final copy at implementation; launch kinds fixed):

```
plan:    find_where_to_go   message  "Help me figure out where to go"     [empty_chat, no_trip]
         plan_a_trip        message  "I want to plan a trip"              [empty_chat, no_trip]
         country_intel      message  "Give me the country intel for my trip"   (needs trip)
         check_weather      message  "How's the weather looking for my trip?"
during:  add_booking        intent   booking_input                        (needs trip)
         mood_checkin       message  "Here's how I'm feeling today"       (needs LIVING trip)
         refresh_intel      message  "Refresh my country intel"           (needs trip)
after:   journal_trip       message  "I want to journal about my trip"    (needs past trip)
account: reply_length       link     /settings  (preference section)
         link_telegram      link     /settings#telegram                   (hidden if linked)
         redeem_promo       message  "I have a promo code"
         what_can_you_do    sheet-open (special: renders the sheet itself; in chips contexts only)
```

### Step 2 — Backend intent launch → verify: orchestrator + router tests

`ChatSendRequest` gains `capability: str | None`. Orchestrator: a module
map `CAPABILITY_INTENTS: dict[str, RouterIntent]` maps each intent-kind
capability id to the router output (intent + minimal entities) that makes
its owning saga win — e.g. `"booking_input"` → `{intent: "TRIP",
entities: {booking_shaped: True}}`. When `capability` is present and known,
skip the RouterAgent LLM call and feed this synthesized router output into
the EXISTING `SagaDispatcher` (do NOT build a parallel dispatch path), so
`should_activate()` / ownership behave identically to a typed turn; the
label persists as the user message. Unknown id → 422 at the route
(AC-7/E1), no side effects. Emit `capability_launched` server-side for
intent-kind (web emits for message/link kinds — one emitter per kind,
no double counting; document in code).

### Step 3 — CapabilitySheet → verify: AC-2/3/5 + manual E8–E10

Bottom sheet (<lg) / popover (lg+). Single grouped sheet with EVERY
available entry visible — groups render as section headers
(GROUP_META.label), capabilities as rows beneath; no two-level drill-down
(visibility serves the discovery goal). One-at-a-time inline howItWorks
expansion. Availability evaluated from props (trip, phase, telegram_linked);
disabled rows show their reason. Footer "See everything →" links to the
manual route (task_53). Pure CSS tokens (task 46 compatible). Focus trap +
aria per E9/E10.

### Step 4 — Surfaces wiring → verify: AC-4/6/10 + build

✨ button in the ChatPanel composer row; `sendCapability` in useChat
(message kind → existing send; intent kind → POST with capability; link
kind → router push). Empty-chat chips in ChatPanel; no-trip chips in
TripDetailPanel's no-trip state — both via `CapabilityChips
context="…"` reading the registry.

### Step 5 — README → verify: CLAUDE.md §6

README: capability surface (registry location, two surfaces, launch
kinds, how to add an entry), metrics. Record the guides/landing
follow-up in §10.1.

## 8. Testing Plan [REQUIRED]

- **Unit (backend):** capability routing skips router (mock call count),
  unknown id 422 no-side-effects, label persisted as user message,
  metrics emitted, E2 saga-handles-preconditions.
- **Unit (frontend-adjacent):** registry fixture test — every intent-kind
  id exists in the backend map (sync guard, §5); availability functions
  (table-driven); type exhaustiveness compiles.
- **Manual (mobile 375px AND desktop, light + dark):** sheet open/close/
  expand ergonomics both form factors; each launch kind end-to-end (one
  message, add_booking intent, link_telegram link); chips in both empty
  states + AC-10 disappearance; E3 streaming lock; E9/E10 keyboard +
  screen-reader pass.
- **Sample fixtures:** POST /chat/send {body:"Add a booking",
  capability:"booking_input"} → 200, BookingInputSaga owns the turn;
  {capability:"nonexistent"} → 422.

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL — applies, narrow]

Intent-kind launches REMOVE a RouterAgent flash-lite call per launch;
message-kind launches cost exactly what a typed message costs. No new
prompts. Starter texts are fixed strings (not user input) but still pass
through the normal sanitization path — no special casing.

### 9.3 Observability [CONDITIONAL — applies]

`capability_sheet_opened{surface}`, `capability_launched{id, kind,
surface}` → analytics_events (7-day) + daily rollup. This is the
feature-demand signal; no alerts.

### 9.4 Rollback Plan [CONDITIONAL — does not apply]

Code-only, additive, no schema. Revert = redeploy.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
*(seeded — the ratified follow-ups)*
- **In-app manual page** — PROMOTED out of this list into its own sibling
  spec `task_53_capability_guide_page.md` (flows have stabilized; built
  against the same registry).
- **Public marketing/landing refresh** (logged-out): the existing
  `/features` + `/how-it-works` pages still say "Telegram is the heart, web
  in development" — stale now that the web dashboard ships. Rework them into
  a capability showcase + sign-up CTA reusing task_53's content. Priority:
  medium. The remaining half of the original "guides & landing" follow-up.
- Telegram `/help` generated from the registry. Priority: low.
- Capability usage data (AC-8) → reorder groups by actual demand.
  Priority: low, needs data first.

### 10.2 Spec deviations

Implementation choices that diverged from or extended the spec (per Golden Rule #2 /
the "register improvements" directive):

- **Registry type refinements** (vs §7 Step 1 sketch): the `intent` launch kind
  carries a `label` (AC-4 needs the persisted user-message text); added an optional
  `hideWhen(s) => boolean` so `link_telegram` can hide when linked while
  `availability` stays `true | string`. `what_can_you_do` is NOT a registry entry —
  it is a chip-only "open the sheet" affordance in `CapabilityChips` (it has no
  message/intent/link launch, keeping the union exhaustive per AC-1). `check_weather`
  was given a needs-trip availability rule (its copy references "my trip").
- **Backend trust-boundary module**: `CAPABILITY_INTENTS` lives in a new
  `orchestrator/capabilities.py` (dependency-free) rather than inside `agent.py`
  (§4), so the chat route can validate ids without importing the model client on
  cold start. Only intent-kind id today: `booking_input`. The orchestrator feeds the
  synthesized router output into the EXISTING `SagaDispatcher` (no parallel path).
- **Client metrics path added** (not in §4) — there was no client→analytics_events
  route. New: `interfaces/routers/metrics.py` (`POST /metrics/event`, JWT-auth'd,
  name-allowlisted, reuses `emit_metric_now`), `app/api/metrics/route.ts` (proxy),
  `lib/metrics.ts` (`track`). Emits `capability_sheet_opened` and, for message/link
  kinds, `capability_launched` (intent-kind is emitted server-side — no double
  count). Task 53 reuses this for `capability_guide_viewed`.
- **Extra shared frontend modules** (not enumerated in §4): `capabilityIcons.ts`
  (registry icon-name → lucide component) and `useCapabilityLaunch.ts` (the single
  place launch behavior lives, shared by sheet + chips).
- **Launcher form factor**: a bottom sheet on every viewport (content
  max-width-centered on desktop) reusing the a11y-complete `@base-ui` Dialog-based
  Sheet primitive, rather than a true button-anchored popover on lg+ (AC-2). Gives
  focus-trap / aria-modal / Esc / tap-outside for free; true anchoring deferred.
- **No-trip surface**: `EmptyTripCanvas`'s single "Plan your first trip →" button
  was replaced by the `no_trip` `CapabilityChips` (which include "Plan a trip" +
  "Find where to go"). Launching opens the chat (desktop → drawer, mobile → full),
  preserving the prior onStart behavior.
- **DRY note (not acted on)**: `useChat.sendCapability` duplicates `sendSelection`'s
  optimistic-send + reconcile shape (~40 lines). Left as parallel functions to avoid
  risk to the tested selection path; a future extraction (`postDeterministic(label,
  extra)`) would de-duplicate both. Priority: low.
- **`/guide` footer link** points at the Task 53 route, which ships separately; the
  link 404s until task 53 lands (acceptable during pre-release).

## 11. Definition of Done [REQUIRED]

- [ ] All §3 ACs pass (tests or §8 manual checks).
- [ ] §6 edge cases tested or accepted as listed.
- [ ] `ruff check` clean; backend unit suite green.
- [ ] `npm run build` succeeds.
- [ ] Mobile + desktop verified, light + dark, incl. keyboard/SR pass.
- [ ] Registry⇄backend sync test in place (intent-kind ids).
- [ ] README updated (how to add a capability).
- [ ] No file outside §4 modified — or §10.2 explains why.
- [ ] Metrics visible in analytics_events on dev.

## 12. Open Questions [OPTIONAL]

- Q1. Should `what_can_you_do` also exist as a chat behavior (the agent
  answering "what can you do?" with the capability list)? Proposed: yes
  but trivially — the ChatAgent prompt gains one line pointing users to
  the ✨ sheet; full registry-aware answers join the guides follow-up.
- Q2. Sheet entry ordering within groups: fixed curated order v1;
  demand-based reordering is the §10.1 data follow-up.
