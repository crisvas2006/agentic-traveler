# Task 53 — Capability guide: the in-app "manual" page

> Spec per `task_template_v2.md`. Sibling of `task_50_capability_surface.md`:
> task 50 builds the capability **registry** + the ✨ launcher sheet + contextual
> chips; this task renders the SAME registry as a full, browsable, **actionable**
> reference page (the "manual"). It depends on task 50 having shipped the registry
> (`frontend/src/lib/capabilities.ts`, `GROUP_META`) and the `sendCapability`
> launch path. Promoted out of task 50 §10.1 because the flows it documents (all
> sagas, the trip model) have stabilized — the "write the guide once the product
> is real" condition is now met.

---

## 1. Problem Statement [REQUIRED]

The ✨ launcher (task 50) is the *quick, always-at-touch* surface — a thin sheet
the user reaches for mid-conversation. It is deliberately not a place to *read*:
its "how it works" is one expandable line, and it lives inside the composer where
dwelling is awkward. What the product still lacks is a calm, browsable place that
answers "what can this app actually do for me?" in full — grouped intuitively by
where the user is in their journey, with a sentence or two of explanation and a
concrete example per capability, and (critically) a one-tap way to *start* each
flow rather than just read about it. Today a user who wants the big picture has
only the stale public `/how-it-works` and `/features` marketing pages, which
predate the web dashboard and still say "Telegram is the heart, web in
development." This task adds an authenticated in-app manual at `/guide` that
renders the one capability registry as a designed reference page: it is the
destination of the launcher's "See everything →" link, it never duplicates
capability copy (same registry), and every card is actionable — tapping it hands
off to the dashboard and launches the flow. The "why now" is that the registry
and all backing sagas exist after task 50, so the manual can be built against
real, shipped behavior with zero new content system.

## 2. Goals & Non-Goals [REQUIRED]

**Goals**

- G1. A signed-in user can open `/guide` (from the launcher footer, from nav, or
  directly) and see **every generally-useful capability**, grouped by journey
  stage, each with its name, one-liner, a 2–3-sentence "how it works", and an
  example phrasing — laid out for reading, beautiful on mobile and desktop.
- G2. Tapping a capability on the guide **starts its flow**: message/intent-kind
  cards hand off to the dashboard and launch (the user lands in chat with the
  flow already engaged); link-kind cards navigate to their destination.
- G3. The guide renders from the **same registry** as the launcher and chips
  (`frontend/src/lib/capabilities.ts` + `GROUP_META`) — no second copy of
  capability names, copy, grouping, or launch behavior.
- G4. Capabilities that don't apply right now are shown **disabled with the
  reason** (same availability rules as the sheet) — the manual never lies.
- G5. `capability_guide_viewed` and `capability_launched{surface:"guide"}`
  metrics exist from day one (which capabilities the manual actually converts).

**Non-Goals**

- No new capability data, no per-capability long-form guide/tutorial pages, no
  screenshots/video. The manual is the registry rendered well, not a docs site.
- No public/logged-out version. Refreshing the marketing `/features` +
  `/how-it-works` pages into a logged-out showcase remains a separate follow-up
  (task 50 §10.1) that will reuse this page's content.
- No per-user customization (pinning, hiding, reordering), no search, no
  onboarding tour, no "NEW" badges.
- No change to the launcher sheet, the chips, the registry shape, or the backend
  capability route — those are task 50. This task only *consumes* them (plus the
  one dashboard handoff consumer and any `example` copy still missing).

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. GET /guide while signed in renders a page with a hero, the four journey
      groups in fixed order (Plan & discover / During the trip / After the
      trip / Account & setup) using GROUP_META.label + GROUP_META.blurb, and
      every registry entry rendered as a card under its group. A group with
      zero entries does not render.
AC-2. GET /guide while signed OUT redirects to /login (server-component
      getUser() check, mirroring dashboard/page.tsx) AND the route is covered
      by the same auth middleware matcher as /dashboard and /settings.
AC-3. Each capability card shows: lucide icon, name, oneLiner, howItWorks
      (2–3 sentences), the example chip when entry.example is set, and a
      primary action button. No card renders raw/unsanitized HTML.
AC-4. Launching from a card behaves per kind:
      - message: navigate to /dashboard?launch=<id>; the dashboard consumes
        the param exactly once on mount, sends the starter text through the
        normal chat send path (user bubble appears), and clears the param
        from the URL.
      - intent: same handoff; the dashboard calls sendCapability(id, label)
        (task 50) so the orchestrator maps the id to its saga without a
        RouterAgent call.
      - link: client-side navigation straight to launch.href (e.g.
        /settings#telegram); no dashboard handoff, no chat message.
AC-5. Availability: a card whose availability rule fails renders disabled
      (not hidden) with its reason shown ("Needs an active trip"); its action
      button is non-interactive. Rules read the same client state the
      dashboard already exposes (trip presence/phase via the trip adapter,
      telegram_linked via useUserProfile); while that state is still loading,
      cards render enabled (the flow itself handles preconditions — task 50
      E2/E6).
AC-6. The launcher sheet's "See everything →" footer (task 50) navigates here;
      arriving from it and tapping a card returns the user to the dashboard
      with the flow engaged — a coherent round trip.
AC-7. Metrics: capability_guide_viewed (on page view) and
      capability_launched{id, kind, surface:"guide"} (on card tap) emit via
      the existing web analytics path → analytics_events. No double count
      with the dashboard handoff (the guide emits the launch; the dashboard
      consumer does NOT re-emit for a param-driven launch).
AC-8. Mobile 375px AND desktop verified, light + dark + warm-ivory: single
      readable column on mobile, multi-column grid on desktop; no horizontal
      scroll; npm run build green; npm run lint clean.
```

## 4. Files & Modules Touched [REQUIRED]

```
frontend/src/app/guide/page.tsx                                  [create — server: auth check + render guide]
frontend/src/components/guide/CapabilityGuide.tsx                [create — client: hero + grouped cards + launch]
frontend/src/components/guide/GuideCapabilityCard.tsx            [create — one card, enabled/disabled/link variants]
frontend/src/components/dashboard/DashboardShell.tsx             [modify — consume ?launch=<id> once on mount]
frontend/src/utils/supabase/middleware.ts                        [modify — add /guide to the protected matcher]
frontend/src/lib/capabilities.ts                                 [modify — populate `example` copy if not already authored in task 50]
frontend/src/lib/analytics.ts (or task-50 web-metric helper)     [modify — capability_guide_viewed; reuse capability_launched emit]
README.md                                                        [modify — /guide route + "See everything" surface]
```

> Exact auth-matcher location (`middleware.ts` / `proxy.ts` / the config in
> `utils/supabase/middleware.ts`) and the web-metric helper name are confirmed
> against the codebase at implementation and reconciled in §10.2 if they differ.

## 5. Constraints [REQUIRED]

- **One registry, no duplication.** All capability names, copy, icons, grouping,
  availability, and launch behavior come from `frontend/src/lib/capabilities.ts`
  + `GROUP_META`. This page authors none of it except (optionally) the `example`
  strings, which live in the registry so the data stays single-sourced.
- **Reuse the launch path.** message/intent launches go through task 50's
  `sendCapability` via the dashboard handoff — this page must not re-implement
  chat sending or the capability POST. link launches use the router.
- **Availability never drives a new fetch loop.** The page loads the same minimal
  client state the dashboard already exposes (one profile read, one trip-summary
  read at page load is acceptable — it's a navigation, not the sheet's in-place
  rule). It must not poll or fetch per-card.
- **Authenticated only.** Defense-in-depth: server-component `getUser()` redirect
  to `/login` AND middleware matcher coverage. The page must never render for an
  unauthenticated user.
- **Mobile-first** (CLAUDE.md §3): the single-column mobile layout is the primary
  design; the multi-column desktop grid adapts it. Implement both in this task —
  never defer mobile.
- **Pure CSS-token styling** (warm-ivory + dark parity, task 46 compatible);
  reuse `aletheia-card` and existing tokens. No new motion primitives beyond the
  existing `Reveal` fade-up.
- **No new tables, no new realtime channels, no new backend route.** Metrics ride
  the existing analytics path (free-tier discipline, CLAUDE.md §10).
- CLAUDE.md §9 applies (no deploys without approval, no git mutations).

## 6. Edge Cases [REQUIRED]

| # | Case | Intended behavior | Test |
|---|------|-------------------|------|
| E1 | `/guide` hit while signed out | Server `getUser()` → redirect `/login`; middleware also blocks | manual |
| E2 | Registry entry with no `example` | Card renders without the example chip; layout unaffected | manual |
| E3 | Availability state still loading on first paint | Cards render enabled; refine to disabled once state resolves; launching meanwhile is safe (saga handles preconditions) | manual |
| E4 | Whole group filtered to zero applicable entries | Group header + blurb do not render (no empty husk) | manual |
| E5 | `?launch=<unknown id>` arrives at dashboard (stale link) | Dashboard consumer ignores it, clears the param, no chat message, no error | unit |
| E6 | `?launch` present but a reply is already streaming | Consumer defers/no-ops per the composer streaming lock (task 50 §5); param cleared so it doesn't re-fire | manual |
| E7 | Rapid back-button after a card tap (param still in URL) | Param cleared via router.replace on consume, so returning does not re-launch | manual |
| E8 | link-kind card (e.g. link_telegram) tapped | Direct client navigation to href; no dashboard handoff, no metric double count | manual |
| E9 | Theme toggle / warm-ivory while on the page | Pure CSS-token styling; no remount; verified light + dark + ivory | manual |
| E10 | Keyboard + screen reader | Cards are buttons/links with accessible names; disabled cards expose reason via aria; visible focus ring; logical tab order | manual |

## 7. Implementation Plan [REQUIRED]

### Step 1 — Route + auth → verify: signed-out redirect, signed-in render

`frontend/src/app/guide/page.tsx` (server component), mirroring
`dashboard/page.tsx`:

```tsx
import { redirect } from "next/navigation";
import { createClient } from "@/utils/supabase/server";
import { CapabilityGuide } from "@/components/guide/CapabilityGuide";

export default async function GuidePage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  return <CapabilityGuide />;
}
```

Add `/guide` to the auth middleware's protected matcher (same set as
`/dashboard`, `/settings`).

### Step 2 — Guide rendering → verify: AC-1/3/5 + manual E2/E4

`CapabilityGuide.tsx` (client): iterate `GROUP_META` in fixed order; for each
group, render header (`label` + `blurb`) and the registry entries whose `group`
matches, as `GuideCapabilityCard`s; skip a group with zero entries. Availability
read from the existing `useUserProfile` hook (`telegram_linked`) and the trip
summary the dashboard already loads (presence/phase); evaluate each entry's
`availability(state)` exactly as the sheet does (share the predicate helper from
task 50 rather than re-deriving). `GuideCapabilityCard.tsx` renders icon, name,
oneLiner, howItWorks, the `example` chip (when set), and the action button;
disabled variant greys the card, swaps the button for the reason string, and sets
`aria-disabled`. All text comes from the registry (already plain strings — no
HTML; no dangerouslySetInnerHTML).

### Step 3 — Launch handoff → verify: AC-4/6 + unit E5, manual E6/E7

Card action by `launch.kind`:

- `message` / `intent`: emit `capability_launched{...,surface:"guide"}` (Step 4),
  then `router.push("/dashboard?launch=" + id)`.
- `link`: emit the metric, then `router.push(launch.href)` (no dashboard hop).

`DashboardShell.tsx` gains a one-shot consumer (e.g. a small effect reading
`useSearchParams().get("launch")`): on mount, if present and it resolves to a
known registry entry and no reply is streaming, fire the launch via task 50's
path — `message` → existing `send(text)`, `intent` → `sendCapability(id, label)`
— then `router.replace("/dashboard")` to clear the param. Unknown id → just clear
the param (E5). The consumer does NOT emit a metric (the guide already did) to
avoid double counting (AC-7). Guard against double-fire on re-render with a ref.

### Step 4 — Metrics → verify: AC-7

On page view, emit `capability_guide_viewed` via the existing web analytics
helper used by task 50; on card tap, emit `capability_launched{id, kind,
surface:"guide"}`. Reuse task 50's emit plumbing verbatim — this task adds only
the new `surface` value and the page-view event name.

### Step 5 — README → verify: CLAUDE.md §6

Document the `/guide` route, that it is the "See everything →" destination, that
it renders the same registry, and the new metric/surface value.

### Step 6 — Claude Design prompt (the visual direction)

> Paste the following into Claude Design to produce the visual direction; the
> implementation in Steps 1–3 is wired to whatever layout it yields, as long as
> the registry/grouping/launch contract above holds. The prompt is self-contained.

```
Design an in-app "What you can do" reference page for Aletheia, a thoughtful
AI travel companion. The user is already signed in; this page is reached from a
"See everything →" link in the chat composer and from the nav. It is a calm,
browsable manual — and every capability is actionable: tapping one starts that
flow.

BRAND & VISUAL IDENTITY (match exactly — this lives inside an existing app):
- Product feel: literary, warm, unhurried — a companion, not a booking engine.
- Type: Geist (sans). Headings in regular/medium weight, sentence case
  everywhere (never Title Case, never ALL CAPS).
- Accent: a blue→purple gradient (#2563eb → ~#7c3aed) used sparingly for the
  hero accent and primary buttons.
- Surfaces: glassmorphic cards ("aletheia-card") — translucent, soft border,
  subtle blur — floating over a quiet background. On mobile the blur is
  dropped for performance; design must still read well as flat translucent
  cards.
- Theme parity is mandatory: three modes must all look intentional — dark
  (deep indigo #0a1224 bg, light slate text), light (white), and a warm-ivory
  light variant (#faf8f3 paper, warm near-black text, warm beige borders).
  Use CSS variables, never hardcoded colors.
- Motion budget: a single subtle fade-up on scroll (already used elsewhere).
  No carousels, no parallax, no new motion primitives.

PAGE STRUCTURE:
1. Hero: one warm line ("Everything Aletheia can do") + one supporting
   sentence ("Grouped by where you are in the journey — tap anything to
   start."). No giant marketing imagery; this is a manual, not a billboard.
2. Four groups, in this order, each a section with a label and a one-line
   blurb:
   - Plan & discover — "Find a destination and shape the trip."
   - During the trip — "Keep things moving while you travel."
   - After the trip — "Hold on to what mattered."
   - Account & setup — "Preferences, channels, and credits."
3. Under each group, a responsive grid of capability cards: 1 column on
   mobile (375px), 2 on tablet, 3 on desktop. Comfortable reading width;
   generous whitespace.

CAPABILITY CARD (the core unit), with three states:
- Default: a lucide icon, the capability name (medium weight), a ≤60-char
  one-liner, 2–3 plain-language sentences of "how it works", a small
  example chip rendered like a quoted user phrase (e.g. monospace-ish,
  faint surface) — e.g. "somewhere warm in February" — and a primary
  "Start" button.
- Disabled: greyed/translucent, a small lock glyph, and instead of the
  button a quiet reason line ("Needs an active trip"). Still legible.
- Link kind (e.g. "Link Telegram", "Reply length"): the button reads
  "Open settings →" rather than "Start".

THE REAL INVENTORY to design around (use this content, not lorem):
- Plan & discover:
  • Find where to go — "Not sure of the destination yet" — describe a mood
    or season and get places that fit you. ex: "somewhere warm in February"
  • Plan a trip — "Build an itinerary day by day" — a few light questions,
    then a day-by-day plan you fully control. ex: "8 slow days in Kyoto"
  • Country intel — "Visa, safety, money, health" — the practical brief for
    your destination, with sources. ex: "is Mexico safe right now?"
    (disabled when no trip: "Needs an active trip")
  • Check the weather — "How the forecast looks for your trip"
- During the trip:
  • Add a booking — "Paste a flight or hotel, I'll file it" — paste any
    confirmation and it becomes a card on your trip. ex: "LH716, MUC→KIX,
    Dec 15" (needs a trip)
  • Mood check-in — "Tell me how today feels" — and I'll adapt the day's
    plan. (needs a trip that's currently underway)
  • Refresh country intel — "Re-check the latest for your destination"
    (needs a trip)
- After the trip:
  • Journal the trip — "Capture what mattered" — light prompts, never
    insistent. (needs a past trip)
- Account & setup:
  • Reply length — "Make replies terser or richer" (link → settings)
  • Link Telegram — "Chat with me on Telegram too" (link → settings;
    hidden when already linked)
  • Redeem a promo code — "Have a code? Add credits."

ACCESSIBILITY: cards are real buttons/links with accessible names; visible
focus rings; disabled cards expose their reason to screen readers; logical
tab order top-to-bottom, group by group.

DELIVER: React + Tailwind v4 using CSS variables/tokens (no hardcoded
colors), matching an existing component style that uses lucide-react icons
and an "aletheia-card" glass surface. Mobile-first. Show the dark, light, and
warm-ivory renderings.
```

## 8. Testing Plan [REQUIRED]

- **Unit (if a frontend test runner is present; else fold into manual):**
  the `?launch=<id>` consumer — known id fires the matching launch path once and
  clears the param; unknown id clears the param with no send (E5); guarded
  against double-fire. The shared availability predicate (reused from task 50) is
  already covered by task 50's table-driven test — do not duplicate.
- **Build/lint (frontend gate, CLAUDE.md §2):** `npm run build` and
  `npm run lint` clean.
- **Manual (mobile 375px AND desktop, light + dark + warm-ivory):** signed-out
  redirect; signed-in render of all four groups; a card with and without an
  example (E2); a group filtered empty (E4); each launch kind end-to-end —
  `plan_a_trip` (message) lands in chat with the starter sent, `add_booking`
  (intent) engages BookingInputSaga, `link_telegram` (link) goes straight to
  settings (E8); disabled card shows its reason (E5); round trip from the
  launcher's "See everything →" and back (E6/AC-6); back-button after a launch
  does not re-fire (E7); theme toggle mid-page (E9); keyboard + screen-reader
  pass (E10).
- **Sample flow:** from the dashboard, open the ✨ sheet → "See everything →" →
  land on `/guide` → tap "Plan a trip" → arrive at `/dashboard` with "I want to
  plan a trip" sent as a user message and the planning flow engaged; URL no
  longer contains `?launch`.

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL — narrow]

No new prompts, agents, or tools. message/intent launches cost exactly what the
same launch from the sheet costs (intent-kind still skips the RouterAgent call —
task 50). Example/howItWorks strings are fixed registry content, not user input;
nothing new enters any prompt. No special sanitization beyond the existing send
path.

### 9.3 Observability [CONDITIONAL — applies]

`capability_guide_viewed` (page demand) and `capability_launched{id, kind,
surface:"guide"}` (which capabilities the manual converts) → analytics_events
(7-day) + daily rollup, via task 50's existing emitter. Single-emit discipline:
the guide emits the launch; the dashboard `?launch` consumer does not re-emit
(AC-7). No alerts.

### 9.4 Rollback Plan [CONDITIONAL — does not apply]

Code-only, additive, no schema, no new route on the backend. Revert = remove the
`/guide` route + the `?launch` consumer + the matcher line, redeploy. The shared
registry is unaffected.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
- **Public marketing refresh** (`/features`, `/how-it-works`): both predate the
  web dashboard and still frame Telegram as the only surface. Rework into a
  logged-out capability showcase reusing this page's content + a sign-up CTA.
  Priority: medium. (Inherited from task 50 §10.1.)
- **Nav entry point**: add a "Guide" / "What I can do" link in the app nav (not
  just the launcher footer) once the page lands. Priority: low.
- Telegram `/help` generated from the registry. Priority: low. (task 50.)

### 10.2 Spec deviations
*(populated during implementation)*

## 11. Definition of Done [REQUIRED]

- [ ] All §3 ACs pass (tests or §8 manual checks).
- [ ] §6 edge cases tested or accepted as listed.
- [ ] `npm run build` succeeds; `npm run lint` clean.
- [ ] Mobile 375px + desktop verified, light + dark + warm-ivory, incl.
      keyboard/SR pass.
- [ ] No capability copy/grouping/launch logic duplicated — guide renders from
      the task-50 registry; only `example` copy added to it.
- [ ] `?launch` handoff round-trips from the launcher and clears the param; no
      metric double count.
- [ ] README updated (/guide route + "See everything" surface).
- [ ] No file outside §4 modified — or §10.2 explains why.
- [ ] Metrics visible in analytics_events on dev (capability_guide_viewed,
      capability_launched surface="guide").

## 12. Open Questions [OPTIONAL]

- Q1. Exact route name: `/guide` (proposed) vs `/dashboard/guide`. Proposed
  `/guide` — a calm full-width reading page, not the 3-pane dashboard shell.
  Confirm during implementation; reconcile in §10.2 if changed.
- Q2. Should the guide also surface a small "credits remaining" note in the
  Account group? Proposed: no in v1 — keep it a capability manual, not a
  settings dashboard.
