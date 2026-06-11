# Task 46 — Reading experience: bubble-less agent prose, warm ivory theme, canonical markdown

> Spec per `task_template_v2.md`. Stream D of the 2026-06-10 product-evolution
> brainstorm. Like task 40, this spec embeds a self-contained **Claude Design
> prompt** (§7.6) to produce the visual treatment before implementation.
> **Implementation order (ratified):** this task lands LAST, after task 45.
> Therefore `advisor_turn.py` exists by now and is in scope: §7.3 swaps its
> composer-prompt formatting lines for the shared canonical block, same as
> the other agents. Landing last also lets the §7.1 hardcoded-white sweep
> cover the components task 40 creates.

---

## 1. Problem Statement [REQUIRED]

Agent replies on the web render inside narrow message bubbles, wasting most
of the chat pane's width and making multi-day itineraries feel cramped; the
user's stated expectation is the reading ergonomics of Claude/ChatGPT —
agent text as full-width prose, bubbles reserved for the human side of the
conversation. The light theme is pure `#ffffff`, which is fatiguing; the
dark theme already has a tinted identity (deep navy) while light mode got
none. Formatting is channel-confused: agent prompts still carry
Telegram-era rules ("no headers, no tables", `*bold*` MarkdownV1), and
because the web renderer (react-markdown + remark-gfm) interprets standard
Markdown, Telegram-style `*bold*` actually renders as *italic* on the web —
a live formatting bug. Fixing rendering, theme, and the formatting contract
together is one coherent "reading experience" change, and it must land
before voice-discipline work (stream B) so that better-written replies have
a surface worth reading on.

Design decisions ratified in brainstorm (2026-06-10):
- **Bubble-less agent prose inside the existing chat pane**; user messages
  keep right-aligned bubbles ("a bubble represents a person").
- **One canonical, mobile-first output format on every device and channel**
  — agent output is identical for mobile and desktop; if the same
  already-optimal text benefits from more room on desktop, an **expand
  mode** provides it without changing the markup.
- **Warm ivory / paper tint** for the light theme (travel-journal,
  ink-on-paper feel); dark theme untouched.
- **Curated travel markdown set**: bold, italics, lists, links, ONE heading
  level, blockquote callouts. No tables, no code blocks, no images.
- Interactive cards (task 43 chips, task 45 proposals) **stay cards** —
  they are controls, not prose.

## 2. Goals & Non-Goals [REQUIRED]

**Goals**

- G1. Agent replies read as full-width typographic prose in the chat pane
  on web; itineraries gain visible structure (day headings, callouts).
- G2. The light theme is warm-tinted everywhere (dashboard, auth, settings)
  with no pure-white surfaces, preserving the blue→purple identity and
  WCAG AA contrast.
- G3. One formatting contract: every agent writes standard Markdown from a
  single shared instruction block; Telegram receives a deterministic
  degradation. The `*bold*`→italic web bug disappears.
- G4. Desktop users can expand the chat into a centered reading column;
  the markup is byte-identical between normal and expanded modes.
- G5. A self-contained Claude Design prompt produces the visual treatment
  (theme application, prose typography, attribution row, expand
  transition) before code is written.

**Non-Goals**

- No dark-theme changes.
- No change to user-bubble styling, the composer, or chat search/jump UX.
- No new motion primitives (existing animation budget only).
- No reply-content/voice changes (stream B) and no saga changes (task 45).
- No tables/images/code support — explicitly excluded from the profile.
- No Telegram UI upgrades beyond the degrader (keyboards etc. unchanged).

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. Light theme: --background and all derived surfaces render the warm
      ivory palette (§7.1 exact values) across dashboard, auth, and
      settings; no component shows pure #ffffff. Verified by visual sweep
      + grep for hardcoded whites in src/.
AC-2. Contrast: foreground-on-background and muted-foreground-on-muted
      pairs meet WCAG AA (≥ 4.5:1 normal text), verified with a contrast
      checker for the exact §7.1 values.
AC-3. Dark theme: the .dark CSS block is byte-identical before/after.
AC-4. Agent messages render bubble-less: no background/border, full pane
      width, preceded by an attribution row (brand dot + timestamp). User
      messages and interactive cards (multi_choice / quick_reply /
      proposal) render exactly as before.
AC-5. Markdown profile renders on web: ###-headings (h1–h3 normalized to
      one visual level), bold/italic, bullet+numbered lists, links,
      blockquote callouts. Tables, images, raw HTML and code fences are
      neutralized (flattened to plain text lines), never rendered.
AC-6. 375px viewport: a maximal-profile reply (heading + list + callout +
      long link) renders with zero horizontal overflow.
AC-7. All agent prompts emit standard Markdown via ONE shared formatting
      block (§7.3); no agent prompt retains "Formatting (Telegram)" rules.
      Searching backend/src for "Telegram" in prompt strings yields no
      formatting directives.
AC-8. Telegram degrader: "### T"→"*T*", "**b**"→"*b*", "> q"→"_q_",
      "- i"→"• i", links preserved; idempotent (running twice = once);
      applied in send_telegram_message and edit_telegram_message before
      sanitize_telegram_markdown. Unit tested per rule.
AC-9. Expand mode (lg: and up only): a header toggle expands the chat over
      the dashboard, prose centered in a ~720px column; toggling back (or
      Esc) restores the pane; the rendered message markup is identical in
      both modes (DOM-diff or snapshot assertion). No expand affordance on
      mobile.
AC-10. Streaming: token deltas render into the bubble-less layout without
      layout shift of previous messages; the chat-search flash highlight
      remains visible on a bubble-less message.
AC-11. npm run build succeeds; no new runtime dependency (react-markdown +
      remark-gfm already present).
```

## 4. Files & Modules Touched [REQUIRED]

```
frontend/src/app/globals.css                                    [modify]
frontend/src/components/dashboard/ChatPanel.tsx                 [modify]
frontend/src/components/dashboard/DashboardShell.tsx            [modify]
backend/src/agentic_traveler/core/markdown_profile.py           [create]
backend/src/agentic_traveler/orchestrator/sagas/advisor_turn.py [modify — from task 45]
backend/src/agentic_traveler/orchestrator/trip_agent.py         [modify]
backend/src/agentic_traveler/orchestrator/planner_agent.py      [modify]
backend/src/agentic_traveler/orchestrator/chat_agent.py         [modify]
backend/src/agentic_traveler/interfaces/routers/telegram.py     [modify]
backend/tests/core/test_markdown_profile.py                     [create]
backend/tests/interfaces/test_webhook.py                        [modify]
docs/design/reading_experience_v1/                              [create — submitted prompt + exported design]
README.md                                                       [modify]
```


## 5. Constraints [REQUIRED]

- **One format invariant:** agents never produce channel-specific markup;
  channel adaptation happens only in the channel layer (Telegram degrader).
  Frontend never reformats text content.
- **Mobile-first:** every `lg:` class added ships with its `sm:`/`md:`
  treatment in the same change (CLAUDE.md §3). The markdown profile itself
  is designed for 375px first.
- **Identity preserved:** blue→purple gradient, glass cards, Geist-era
  radius language stay; only surface tints change in light mode.
- **Performance guardrails from globals.css comments are law:** no new
  perpetual animations behind frosted panels; expand mode must not
  reintroduce backdrop-filter churn (the expanded chat uses the `is-solid`
  card variant).
- **No prompt-meaning changes** while swapping formatting blocks — the
  surrounding behavioral prompt text is untouched (stream B owns voice).
- **Backwards compatibility:** historical messages stored with Telegram-ish
  `*bold*` will render as italics on web post-change — accepted (cosmetic,
  decays naturally). The degrader must not corrupt them on Telegram.
- CLAUDE.md §9 applies (no deploys, no git mutations by the agent, mocked
  Telegram in tests).

## 6. Edge Cases [REQUIRED]

| # | Case | Intended behavior | Test |
|---|------|-------------------|------|
| E1 | LLM emits a table anyway | Renderer flattens rows to plain lines (no <table>); degrader strips pipes | unit |
| E2 | LLM emits #### / ## / # | All heading depths normalize to the single visual level (web) and *bold* (Telegram) | unit |
| E3 | Unbroken 200-char string (URL/word) | `break-words` wraps; no horizontal scroll at 375px | manual |
| E4 | Nested lists ≥ 2 levels | Render flattened to one level; profile forbids but renderer tolerates | unit |
| E5 | Blockquote spanning multiple lines | Single callout block, not per-line fragments | unit |
| E6 | Degrader idempotency (edit path re-sends degraded text) | Second pass is a no-op (AC-8) | unit |
| E7 | Historical `*bold*` MarkdownV1 messages | Web: renders as italic (accepted, cosmetic); Telegram: unchanged behavior | accepted |
| E8 | Expand toggled while a reply is streaming | Stream continues into the recentered column; no remount/duplicate | manual |
| E9 | Realtime message arrives while expanded | Appends normally in expanded layout | manual |
| E10 | prefers-reduced-motion | Expand transition is instant (reuses existing reduced-motion switch) | manual |
| E11 | 4096-char Telegram chunking after degradation | Degrade FIRST, then chunk + sanitize (existing), so entities don't straddle chunks worse than today | unit |
| E12 | Mixed RTL text in prose | Out of scope — recorded here as accepted limitation | accepted |

## 7. Implementation Plan [REQUIRED]

### 7.1 Warm ivory palette → verify: AC-1/AC-2/AC-3 + visual sweep

`globals.css` `:root` (light) becomes — exact values, Claude Design may
fine-tune within ±2% lightness but hue family is fixed:

```css
:root {
  --background: #faf8f3;            /* warm ivory paper */
  --foreground: #23201a;            /* warm near-black ink (was cold #020617) */
  --primary: #2563eb;               /* unchanged — ink-blue accent */
  --primary-foreground: #ffffff;
  --secondary: #f1ede4;             /* warm card surface */
  --secondary-foreground: #2a261f;
  --muted: #f5f2ea;
  --muted-foreground: #5b554a;      /* warm slate, AA on --muted */
  --accent: #f1ede4;
  --accent-foreground: #2a261f;
  --border: #e6e0d3;
  --input: #e6e0d3;
  --ring: #3b82f6;                  /* unchanged */
  --radius: 2rem;                   /* unchanged */
}
```

`.dark { … }` untouched (AC-3). Derived surfaces (`.aletheia-card`,
`.grid-bg`, scrollbars) inherit via `var(--background)` / `color-mix` —
no per-component edits expected; sweep for stray `bg-white` / `#fff`
literals in `src/` and replace with tokens.

**UX reasoning:** warm white reduces glare-induced fatigue versus pure
white at equal luminance; pairing a paper-warm ground with the existing
cool blue/purple accents is the classic ink-on-paper contrast and makes
accent elements read MORE saturated without changing them. Foreground
must warm with the ground or text looks blue-grey and dirty on ivory.

### 7.2 Bubble-less agent prose → verify: AC-4/AC-6/AC-10 + manual 375px/desktop

`ChatPanel.tsx`: split message rendering — user messages keep the existing
bubble component; agent messages render as:

```
│ ◈ 12:32                                   ← attribution row: 6px brand-
│ Prose paragraph, full pane width…            gradient dot + muted time,
│ ### Day 2 — Taormina                         text-xs
│ • Morning — Isola Bella at opening
│ ▎ Verify entry rules with official sources
│ ┌────────────────────────────────────┐
│ │ What pace feels right?   [chips]   │    ← SlotChoices card unchanged
│ └────────────────────────────────────┘
```

- Container: `w-full`, no bg/border/shadow; vertical rhythm between
  messages does the separation work (prose spacing > boxes).
- The `chat-md` stylesheet gains: `h3` (single visual heading level —
  `font-semibold`, ~1.05em, extra top margin), callout styling for
  `blockquote` (replace the grey left-border with a warm
  `color-mix(--primary …)` tinted callout), comfortable line-height
  (~1.65) and paragraph spacing for prose reading.
- react-markdown `components` mapping: `h1,h2,h3,h4,h5,h6 → h3 renderer`;
  `table/thead/tbody/tr/td/th → plain-line flattener`; `img → null`;
  `code/pre → plain span` (E1/E2/E4). remark-gfm stays for lists/links.
- Streaming: the existing delta path writes into the same prose container;
  the chat-flash highlight class applies to the prose block (radius kept
  via the existing `.chat-msg-flash` border-radius).

**UX reasoning:** bubbles signal "utterance"; prose signals "document
worth reading". Keeping the human in bubbles and the advisor in prose
makes the conversational roles legible at a glance (the user's stated
mental model), and full-width text raises characters-per-line at 375px
from ~35 to ~45 — fewer wraps, calmer reading. Controls keep borders
because affordance requires containment.

### 7.3 Canonical formatting block + shared constant → verify: AC-7

`core/markdown_profile.py`:

```python
CANONICAL_FORMATTING = """\
FORMATTING (canonical — identical on every device and channel):
- Plain conversational paragraphs by default; Markdown only where it helps.
- **bold** for place names and key facts; *italics* sparingly.
- "- " bullet lists or "1. " numbered lists for options/steps, one line each.
- Exactly one heading level: "### " before day/section titles
  (e.g. "### Day 2 — Taormina"). Never # or ##, never deeper structure.
- "> " blockquote for short callouts: tips, caveats, and the
  verify-with-official-sources disclaimer.
- [text](url) links when citing sources.
- NEVER: tables, code blocks, images, HTML, nested lists.
- Must read perfectly on a small phone screen: short paragraphs
  (≤ 3 sentences), short lines, no wall-of-text.
"""
```

Swap into `trip_agent.py`, `planner_agent.py`, `chat_agent.py`, and
`sagas/advisor_turn.py` (task 45's composer) system prompts, replacing
their formatting sections (length-limit lines stay — they are
voice/budget, not formatting). Planner's "no
headers" rule is removed; its day-by-day output format keeps its content
rules but headings become `###`.

### 7.4 Telegram degrader → verify: test_markdown_profile.py + AC-8/E11

`core/markdown_profile.py`:

```python
def degrade_for_telegram(text: str) -> str:
    """Standard Markdown → Telegram MarkdownV1. Deterministic, idempotent.
    Order matters: headings before bold (### uses no asterisks), bold
    before sanitization. Rules:
      '### Title'            → '*Title*'
      '**bold**'             → '*bold*'
      '> quote'              → '_quote_'   (per contiguous quote block line)
      '- item' / '* item'    → '• item'
      '|' table rows         → cells joined with ' — '
      code fences ``` lines  → removed (content kept verbatim)
      [text](url)            → unchanged (V1 supports inline links)
    Idempotency: patterns only match the standard-Markdown forms, which the
    output no longer contains."""
```

Called in `send_telegram_message` / `edit_telegram_message` (real AND mock)
immediately before `sanitize_telegram_markdown`, so degradation precedes
chunking (E11).

### 7.5 Desktop expand mode → verify: AC-9 + manual E8–E10

- `DashboardShell.tsx`: `chatExpanded` boolean state (component state, not
  persisted); when true, the chat pane container becomes
  `fixed inset-x-0 … lg:static lg:col-span-full` over the dashboard with
  the message list constrained by `max-w-[720px] mx-auto`; map/trip panes
  `hidden`. Chat pane header gains a ⤢/⤡ toggle rendered `hidden lg:flex`.
  Esc key collapses. Transition: simple width/opacity within the existing
  animation budget; instant under prefers-reduced-motion (E10).
- The expanded surface uses `aletheia-card is-solid` (no backdrop-filter
  cost over the map, per the §5 performance constraint).

**UX reasoning:** 720px ≈ 70–80 characters per line at the chat font size —
the optimal long-form measure. Because formatting is canonical-mobile, the
expanded mode is purely a *measure* change; that's why it's safe to bake
in without violating the one-format invariant.

### 7.6 Claude Design prompt → verify: AC-1..AC-4 visuals produced; submitted + export saved to docs/design/reading_experience_v1/

Self-contained prompt to run in Claude Design (embed verbatim):

```
You are designing the "reading experience" update for Aletheia Travel, an
AI travel-advisor web app (Next.js dashboard: left map/trip panel, right
chat panel; glassmorphic cards, 2rem radii, blue #2563eb → purple #9333ea
gradient accents, dark mode deep navy).

Design FOUR artifacts, mobile (375px) and desktop (1440px) for each:

1. WARM IVORY LIGHT THEME. Replace the pure-white light theme with a warm
   paper palette: background #faf8f3, surfaces #f1ede4/#f5f2ea, borders
   #e6e0d3, ink-warm text #23201a. Keep the blue→purple accents exactly —
   they should feel like ink on paper. Show the full dashboard, the auth
   screen, and settings in this theme. No pure #ffffff anywhere. Dark
   theme is out of scope.

2. AGENT PROSE IN CHAT. User messages stay as right-aligned gradient
   bubbles. Agent replies have NO bubble: full-width prose with a small
   attribution row (a 6px gradient dot + muted timestamp) above each
   reply. Typography: comfortable line-height (~1.65), one heading level
   for day/section titles ("Day 2 — Taormina"), bullet lists, and a
   tinted callout style for advisory notes ("Verify entry rules with
   official sources"). Show a long itinerary reply and a short
   conversational reply. Interactive elements (question cards with
   tappable choice chips and a Confirm button) KEEP their bordered card
   look — controls stay cards, prose flows free.

3. ATTRIBUTION & RHYTHM. Show the vertical rhythm of a conversation:
   user bubble → agent prose → question card → user bubble. Separation
   comes from spacing and the attribution rows, not boxes.

4. DESKTOP EXPAND MODE. A toggle in the chat header expands the chat over
   the whole dashboard; the same prose recenters in a ~720px reading
   column. Show collapsed vs expanded side by side, and the toggle's two
   states. The map/trip panel is hidden while expanded.

Constraints: mobile-first; identical text formatting at every size (only
the measure changes); WCAG AA text contrast on every surface; no new
animation styles beyond a simple expand transition; preserve the existing
brand identity (gradient, radii, glass) — this is a re-tint and re-set,
not a redesign.
```

### 7.7 README → verify: CLAUDE.md §6

Update README: canonical markdown profile (single formatting contract +
Telegram degradation), bubble-less reading experience, ivory theme, expand
mode.

## 8. Testing Plan [REQUIRED]

- **Unit (backend):** `test_markdown_profile.py` — every degrader rule
  (AC-8), idempotency (E6), table/code stripping (E1), heading depths
  (E2), multi-line blockquote (E5), degrade-before-chunk ordering (E11
  — via webhook test asserting the mock send received degraded text).
  Prompt-block swap: assert `CANONICAL_FORMATTING` present and "Telegram"
  formatting strings absent from agent system prompts (AC-7).
- **Frontend:** `npm run build`; component snapshot or DOM assertion that
  expanded vs collapsed mode produce identical message markup (AC-9).
- **Manual checks (mobile 375px AND desktop, light AND dark):**
  - Maximal-profile reply at 375px — no horizontal overflow (AC-6/E3).
  - Streaming reply into bubble-less layout; search-flash on prose (AC-10).
  - Expand toggle mid-stream (E8); realtime message while expanded (E9).
  - Theme sweep: dashboard, auth, settings — no white flashes (AC-1).
  - Telegram device check: itinerary with headings/callouts arrives as
    bold lines / italics, links tappable.
- **Sample fixture:** canonical reply
  `"### Day 2 — Taormina\n- **Isola Bella** at opening\n\n> Verify entry rules with official sources"`
  → web renders heading/list/callout; degrader yields
  `"*Day 2 — Taormina*\n• *Isola Bella* at opening\n\n_Verify entry rules with official sources_"`.

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL — applies, narrow]

No model/tier changes; no new calls. Prompt deltas are formatting-only
(behavioral text untouched — stream B owns voice). Token impact: the
canonical block is ±0 vs the blocks it replaces. Versioning: the shared
constant lives in one module; prompts that import it inherit one source of
truth. Output handling: renderer ALLOWLIST (mapped components) is the
sanitization boundary for agent markdown on web — raw HTML never renders
(react-markdown default, asserted by E1 test).

### 9.3 Observability [CONDITIONAL — applies, minimal]

Degrader is pure; log only when it strips a forbidden element
(`markdown_profile_violation` metric with element kind) — this is the
free signal of agents drifting off-profile, useful input for stream B's
judge. No alerts.

### 9.4 Rollback Plan [CONDITIONAL — applies, lightweight]

Pure code change, no schema. Rollback = revert deploy. Theme/CSS rollback
is a single-file revert. Degrader removal restores prior Telegram behavior
unchanged.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
*(seeded)*
- Historical messages stored in MarkdownV1 render italic-for-bold on web
  (E7) — a one-off migration could rewrite stored message text; assess
  only if users notice. Priority: low.
- `body { font-family: Arial }` in globals.css predates the design system —
  typography unification candidate for the Claude Design pass. Priority: low.

### 10.2 Spec deviations
*(populated during implementation)*

## 11. Definition of Done [REQUIRED]

- [ ] All §3 ACs pass (tests or manual checks per §8).
- [ ] All §6 edge cases covered or explicitly accepted as listed.
- [ ] `ruff check` clean (backend changes).
- [ ] `pytest` unit suite passes.
- [ ] `npm run build` succeeds.
- [ ] Mobile (375px) + desktop verified, light + dark, per CLAUDE.md §3.
- [ ] Claude Design prompt submitted; exported design saved under
      `docs/design/reading_experience_v1/`.
- [ ] No file outside §4 modified — or §10.2 explains why.
- [ ] README updated.
- [ ] No new dependencies; no secrets/PII in logs.

## 12. Open Questions [OPTIONAL]

- Q1. Attribution row content: dot + time only, or also a name ("Aletheia")
  on the first reply of a group? Proposed: dot + time; let Claude Design
  explore the name variant visually.
- Q2. Should the expand toggle auto-engage for replies over ~1500 chars?
  Proposed: no — user-initiated only (predictability beats cleverness);
  revisit with usage data.
