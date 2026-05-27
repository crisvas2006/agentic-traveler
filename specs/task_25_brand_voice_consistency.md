# Task 38 — Brand Voice Consistency & Alpha Waitlist Gating

> **Status:** ✅ All 7 phases complete (2026-05-27) — task ready for sign-off
> **Owner:** Cristian (product/owner)
> **Created:** 2026-05-27
>
> ### Progress log
> - 2026-05-27 — Spec created.
> - 2026-05-27 — Phase 1 started: writing `specs/brand_voice.md`.
> - 2026-05-27 — ✅ **Phase 1 complete.** `specs/brand_voice.md` written.
> - 2026-05-27 — Owner directive: soften "alpha" language to "early access" as default. Brand voice doc §7 and Phase 2/3 embedded copy updated to reflect this before implementation began.
> - 2026-05-27 — Phase 2 started: applying landing-page rewrites in `frontend/src/app/page.tsx`.
> - 2026-05-27 — ✅ **Phase 2 complete.** All 12 review issues resolved in `page.tsx`. Hero collapsed to H1 + subhead, Traveler DNA introduced early, ProofSection H2 reframed, all feature card copy rewritten, CTA fully rewritten with privacy-policy link, `tripGenie_lastSignup` → `aletheia_lastSignup`, button labels in sentence case, curly apostrophes throughout display copy. `npm run build` passes. Ready for owner review at the deployed/local-dev URL.
> - 2026-05-27 — Phase 3 started: alpha cap mechanism + RLS for anon count.
> - 2026-05-27 — ✅ **Phase 3 code complete.** Created `frontend/src/lib/alpha-config.ts` (`ALPHA_CAP = 100`). Rewrote `frontend/src/app/actions.tsx` to: (a) use service-role client (fixes pre-existing latent bug where status updates were silently blocked by RLS); (b) insert-then-position lookup using `created_at` ordering; (c) email only when position ≤ ALPHA_CAP; (d) introduce `status = 'waitlisted'` for over-cap rows; (e) all return messages rewritten in voice. Amended `supabase/rls_policies.sql` to add `waitlist_count_anon` policy + column-level `GRANT SELECT (id, created_at)` to anon. Build passes. **DB migration step is manual**: the owner must run the new RLS lines in the Supabase SQL editor for the count to work for the anon client in Phase 4.
> - 2026-05-27 — DB migration confirmed by owner (Supabase SQL editor returned OK on both statements).
> - 2026-05-27 — Phase 4 started: wiring live count into the CTA.
> - 2026-05-27 — ✅ **Phase 4 complete.** CTASection now fetches `count(*)` from `waitlist` via the anon browser client on mount, with a `null` state for loading/failure that falls back to the static copy. Three render branches: (a) loading/failed → static "100 seats" copy; (b) under cap → "{N} of 100 seats taken — {ALPHA_CAP - N} left. Drop your email and you're in."; (c) at/over cap → "Aletheia early access is full. 100 of 100 seats taken. ...you'll join the waitlist...". Uses `ALPHA_CAP` from `frontend/src/lib/alpha-config.ts` for single-source-of-truth. Build passes.
> - 2026-05-27 — Phase 5 started: marketing page sweep.
> - 2026-05-27 — ✅ **Phase 5 complete.** Rewrote `how-it-works/page.tsx`, `pricing/page.tsx`, `faq/page.tsx`, `about/page.tsx`, `features/page.tsx`. All H1s in sentence case. Forbidden terms removed ("transform," "seamlessly," "state-of-the-art," "ecosystem," "agentic system"). Pricing concretized with €0 + 500-credit specifics. FAQ Q3 reframed honestly ("Auto-booking is on the roadmap"). About page tightened, pull quote uses curly quotes. Features page descriptions rewritten with concrete examples in the same voice as the landing. Build passes.
> - 2026-05-27 — Phase 6 started: auth page sweep.
> - 2026-05-27 — ✅ **Phase 6 complete.** Auth pages were mostly already in voice (the most-recently-built surface). Minor tweaks only: (1) `login/page.tsx` — eyebrow "Alpha · Welcome back" → "Early access · welcome back"; success message "Signed in — redirecting to your journeys…" → "Signed in. Taking you to your journeys…"; (2) `sign-up/page.tsx` — eyebrow "Alpha Access · Free" → "Early access · free"; success message exclamation removed ("Account created!" → "Account created."); (3) `forgot-password/page.tsx` — replaced "no waiting, no friction" (forbidden) with "usually in under a minute"; ASCII apostrophes in display H1 (`&apos;`) → curly (`&rsquo;`); (4) `reset-password/page.tsx` — no changes needed, already in voice. AuthShell — no changes needed. Build passes.
> - 2026-05-27 — Phase 7 started: in-app copy sweep.
> - 2026-05-27 — ✅ **Phase 7 complete.** Touched 5 files: (1) `WelcomeGrantModal.tsx` — H2 exclamation dropped, body para reframed without "AI-powered" buzzword, three bullets rewritten ("Build itineraries shaped by your Traveler DNA" replaces generic "Generate personalised itineraries"), error messages rewritten in voice. (2) `ProfileDropdown.tsx` — "My Account" → "My account" (sentence case); credit low/critical warnings now point to settings instead of "upgrade your plan" (which doesn't exist). (3) `dashboard-data.ts` — "Slow traveller" → "Slow traveler" (US-spelling consistency with Traveler DNA). (4) `AccountSettings.tsx` TopUpModal — "Alpha phase" → "Early access"; body paragraphs softened; MiscSection language note "Other languages will be available in a future release." → "Other languages are on the way. English for now." (5) `AlphaWelcomeEmail.tsx` — substantial rewrite: preview text, headline subhead, three step intros all in voice; signed off as "Cristian — Aletheia Travel" (first-person founder voice) replacing "The Aletheia Travel Team"; footer cleaned up; "Start your journey" CTA button in sentence case. **Drift sweep clean**: no remaining "transform", "seamless", "effortless", "transform your X" patterns in user-facing strings (CSS class names excluded). Terms page intentionally left with "Alpha Phase" wording since formal legal documents keep technical terminology per brand voice doc §6. TripDetailPanel "AI" callouts left untouched — they are the in-app exemplars of the voice. Build passes.
> - 2026-05-27 — ✅ **Task 38 complete.** All 7 phases done. Files changed: ~20 across `frontend/src/app/`, `frontend/src/components/`, `frontend/src/lib/`, `frontend/src/emails/`, and `supabase/rls_policies.sql`. Two new files: `specs/brand_voice.md` (durable voice doc) and `frontend/src/lib/alpha-config.ts` (cap constant).

---

## 1. Task Overview

- **Summary:** Define Aletheia Travel's brand voice as a durable, self-contained document, then sweep every user-facing surface (landing, marketing pages, auth pages, in-app copy) to make the voice consistent end-to-end. Resolve every issue flagged in the 2026-05-27 landing-page brand review, including replacing unsubstantiated scarcity claims with a real alpha cap (100 seats, configurable) and pulling the live waitlist count from Supabase to use as social proof.
- **Background:** A `/marketing:brand-review` audit on 2026-05-27 found 12 voice/style/claim issues on the landing page. The hero ("Don't book a trip. Architect a journey.") has a distinctive bold-contrarian voice but the CTA and several headlines collapse into generic SaaS copy. The owner wants the voice fixed everywhere, documented, and the "limited alpha access" line backed by a real gating mechanism.
- **Primary Owner:** Cristian.

---

## 2. Objectives & Success Criteria

### Goals
1. A **brand voice doc** lives at `specs/brand_voice.md` and is detailed enough that future Claude sessions (or human writers) can produce in-voice copy without re-deriving the rules.
2. **Landing page** (`frontend/src/app/page.tsx`) addresses all 12 issues from the review.
3. **Every other user-facing page** (marketing, auth, in-app) reads in the same voice — no surface where the prose contradicts the brand voice doc.
4. **Alpha waitlist is actually gated**: only the first 100 signups receive the welcome email with sign-up instructions; the cap is a single configurable constant.
5. **Live signup count** is read from Supabase (anonymous role) and surfaced in the CTA copy as honest social proof.

### Non-Goals
- Redesign or layout changes. Copy and copy-driven prop changes only. Card structures, spacing, gradients, and animations stay as they are unless an issue specifically requires it (e.g. hero H1+H2 consolidation).
- New marketing pages or sections.
- Backend agent prompt rewrites (Gemini system prompts) — out of scope; this is web-frontend voice only.
- A11y / SEO sweep — out of scope, separate task.
- Translation / i18n — `MiscSection` already lists 5 languages as "coming soon"; this task ships English only.

### Definition of Done
- [ ] `specs/brand_voice.md` exists and follows the structure in §6.1 below.
- [ ] Landing page: all 12 issues from the brand review are resolved (see §6.2 issue checklist).
- [ ] `frontend/src/app/(how-it-works|pricing|faq|about|features)/page.tsx` — each reviewed against the brand voice doc and any voice violations fixed.
- [ ] `frontend/src/app/(auth)/(login|sign-up|forgot-password|reset-password)/page.tsx` — marketing-side copy (page headers, subheads, helper text, button labels, success/error toasts) aligned to the brand voice doc.
- [ ] In-app copy sweep: `DashboardShell`, `ProfileDropdown`, `WelcomeGrantModal`, `AccountSettings`, empty-states, chat placeholders, dashboard chips, error toasts.
- [ ] **Alpha cap mechanism** ships: `ALPHA_CAP = 100` constant exists, `signupForAlpha` server action checks the count *before* sending the email, and over-cap users are still recorded in `waitlist` but receive a different "you're on the waitlist" response (no welcome email).
- [ ] **Live count read**: anonymous RLS `SELECT count(*)` on `waitlist` works; CTA copy reflects the live number with a sensible fallback when the fetch fails.
- [ ] Build passes (`npm run build` in `/frontend`).
- [ ] Manual smoke test of the signup flow at both <100 and ≥100 simulated states (covered in §7).

---

## 3. System Context

### Repositories / Services Affected
- `frontend/` — every page, several components, the `signupForAlpha` server action.
- `backend/` — **none.** No Python changes.
- `supabase/` — one RLS policy addition on `public.waitlist` to allow anonymous `SELECT count(*)`. Documented in `supabase/rls_policies.sql`.
- `specs/` — new file: `specs/brand_voice.md`.

### Architecture Notes
- The landing page CTA already writes to `waitlist` via `signupForAlpha` (`frontend/src/app/actions.tsx`). That action also sends a welcome email via Resend.
- After this task, `signupForAlpha` becomes a **gated** action: it always inserts into `waitlist`, but the welcome email only sends if the row is within the first `ALPHA_CAP` rows.
- The live count is read **client-side** in the CTA section from Supabase with the public anon key. No new API route is needed.
- Cap is a single TypeScript constant exported from a shared module so future phase transitions (alpha→beta with cap=1000) are a one-line change.

### Relevant Specs / Docs
- `specs/brand_voice.md` (produced by Phase 1 of this task — see §6.1 for the full contents).
- `supabase/rls_policies.sql` (existing — to be amended).
- Brand review output (embedded in §6.2 issue table below for self-containment).

---

## 4. Constraints & Requirements

### Technical
- **Framework:** Next.js 16 App Router, React 19, Tailwind v4, Supabase (`@supabase/ssr`).
- **No new dependencies.** Use Supabase clients already wired up.
- **No layout changes** beyond what the copy mandates (the hero H1+H2 consolidation in issue #7 is the only structural change).
- **Sentence case everywhere** — headings, buttons, chips, eyebrow labels. See `specs/brand_voice.md` §6 for the exact rule.
- **Curly apostrophes / quotes** in display-size copy (≥24px). Use Unicode characters (`’`, `“`, `”`) directly in JSX or `&rsquo;` / `&ldquo;` / `&rdquo;` entities.

### Operational
- Per project rules: surgical changes, no auto-deploy, no auto-commit. Each phase concludes with a checkpoint where the user reviews and approves before the next phase begins.
- Mobile responsiveness is non-negotiable per `project_guidelines.md` — any copy that wraps differently at mobile width must be checked at the 375px viewport.

### Security / Compliance
- The new anonymous `SELECT count(*)` policy on `waitlist` must **not** expose row contents (emails). Use a `count()` aggregate only — Supabase RLS plus a constrained policy is fine, but verify with a curl that anon role cannot `SELECT *`.
- Cap-enforcement logic runs on the server in `signupForAlpha`, never trusts client-supplied count.
- No PII in error messages or logs.

---

## 5. Inputs & Resources

### Artifacts Provided
- Landing page source: `frontend/src/app/page.tsx` (read on 2026-05-27 — content embedded in §6.2).
- Brand review output (12 issues + 4 revised sections + legal flags — embedded in §6.2).
- Existing Supabase schema: `public.waitlist` table (id, email, created_at, source).

### Assumptions
- The `waitlist` table has a `created_at` column suitable for `ORDER BY created_at ASC` to determine the first-100 ordering.
- The user wants `ALPHA_CAP` to be a TypeScript constant in `frontend/`, not an env var (no infra change needed for the cap value itself).
- The Resend welcome email template stays the same — only the *trigger condition* changes.
- The brand voice doc is English-only.

### Open Questions
- None at spec-write time. All clarifying questions were resolved before this spec was created:
  - Voice direction: **bold/contrarian**
  - Case style: **sentence case everywhere**
  - Scope: **landing + marketing + auth + in-app**
  - Cap: **100**
  - Count source: **live from Supabase anon role**

---

## 6. Implementation Plan

This task ships in **7 phases with explicit approval gates between each**. The owner reviews the deliverables at the end of each phase and either approves (proceed to next) or requests revisions. No phase auto-starts.

```
Phase 1: Brand voice doc                                    ← writing only
   ↓ APPROVAL GATE
Phase 2: Landing page copy rewrites                         ← code + copy
   ↓ APPROVAL GATE
Phase 3: Alpha waitlist gating (cap + email split)          ← server logic + RLS
   ↓ APPROVAL GATE
Phase 4: Live signup count in CTA                           ← client read
   ↓ APPROVAL GATE
Phase 5: Other marketing pages                              ← copy sweep
   ↓ APPROVAL GATE
Phase 6: Auth pages                                         ← copy sweep
   ↓ APPROVAL GATE
Phase 7: In-app copy sweep                                  ← copy sweep
   ↓ DONE
```

---

### Phase 1 — Brand Voice Doc

**Deliverable:** `specs/brand_voice.md`

**Contents (embedded verbatim below — write this file as-is):**

```markdown
# Aletheia Travel — Brand Voice

> The durable rulebook for how Aletheia Travel speaks. Any copy that goes
> in front of a user — marketing, in-app, error messages, emails — should
> read like the same voice wrote it. When in doubt, the contrarian hero
> line is the north star: **"Don't book a trip. Architect a journey."**

---

## 1. Brand Personality

If Aletheia Travel were a person, they would be a **well-traveled friend with
strong opinions** — the one you call before booking because they'll tell you
the truth about whether that "perfect" itinerary actually fits who you are.
They've been everywhere, they don't dress up the trade-offs, and they
remember that your tired Tuesday self is the same person planning the trip.

They are NOT:
- A booking concierge politely helping you check boxes
- A growth-hacky SaaS product yelling "Transform Your Experience"
- A travel influencer selling aspiration

---

## 2. Voice Attributes

The voice sits on four spectrums. Below are the locked positions and what
they mean in practice.

### Bold (we lean bold; never bland)
- **We are:** declarative, willing to take a position, comfortable rejecting
  the mainstream framing. We say "Don't book a trip. Architect a journey,"
  not "Plan smarter trips."
- **We are not:** macho, hyperbolic, or contrarian for sport. We don't write
  in ALL CAPS. We don't promise the world.
- **Sounds like:** "Built for the trip only you would take."
- **Doesn't sound like:** "The best AI travel planner. Ever."

### Personal (we lean personal; never anonymous)
- **We are:** writing to one reader. "Your trip," not "trips." "Tell us
  you're tired" — second person, present tense, low distance.
- **We are not:** sycophantic, over-familiar, or fake-casual. No "Hey there,
  bestie." No "we know you better than you know yourself."
- **Sounds like:** "You said you felt tired. Plan's dialled down — indoor
  temples, no long walks."
- **Doesn't sound like:** "Our intelligent assistant has reviewed your
  preferences and made adjustments."

### Concrete (we lean concrete; never fuzzy)
- **We are:** specific. We say "indoor temples," "café-hop, no hills,"
  "covered approach," "energy: 2 of 5." Real nouns, real numbers, real
  trade-offs.
- **We are not:** technical for its own sake. We don't talk about
  "personalization vectors" or "n=15 personality dimensions" in user-facing
  copy. The fact that the system has 15 dimensions is plumbing — the user
  feels it through specific suggestions.
- **Sounds like:** "Three days in Kyoto. Slow temples, rivers, alleys."
- **Doesn't sound like:** "Optimized cultural-immersion sequences."

### Warm (we lean warm; never corporate)
- **We are:** human. We acknowledge that you're tired, that the weather
  turned, that the plan needs to bend. Empathetic without being saccharine.
- **We are not:** cold or robotic. We don't say "Operation failed" — we say
  "Something went sideways on our end."
- **Sounds like:** "Rain's in for the afternoon — want me to pull the
  garden walk forward and tuck the museum to the end?"
- **Doesn't sound like:** "Weather event detected. Replanning."

---

## 3. Audience

### Primary
**Independent travelers, late-20s to mid-40s**, who already know they don't
fit the "10 best things to do in X" template. They've done a few trips that
ended up over-scheduled or weather-wrecked. They want help that listens.

They care about:
- Trips that match their actual energy and mood, not a generic schedule
- Honest trade-offs, not aspirational marketing
- Privacy — they don't want their travel preferences sold

They are NOT:
- First-time travelers needing hand-holding
- Luxury concierge buyers (different category)
- Budget backpackers optimizing for cheapest-anything

### Secondary
Partners and family of the primary user — people who get pulled into a trip
someone else planned. The copy should be understandable to them on first
read even if they didn't sign up.

---

## 4. Core Messaging Pillars

Every page should reinforce at least one of these. If a page reinforces
none, the page is off-brand.

### Pillar 1 — "For the individual, not the average"
The product is a tool for people whose trip doesn't match the listicle.
Mainstream travel platforms optimize for the median; Aletheia optimizes for
you. This is the contrarian backbone. Use it in hero copy, value props,
about pages.

### Pillar 2 — "Plans that bend, not break"
Trips never go as planned. Energy fades, weather turns, museums close. The
product adapts in real time — that's the differentiator vs. static
itineraries. Use this in feature descriptions, support copy, anywhere we
talk about live adaptation.

### Pillar 3 — "We know who you are, and we use it gently"
The Traveler DNA + 15 personality dimensions are the unique IP. But we
never brag about the model — we surface it through suggestions that *feel*
personal. Mention Traveler DNA by name (it's a proprietary term, capitalize
it). Don't quote the underlying dimensions in user copy.

### Pillar 4 — "Architect, don't book"
A reframing pillar: the product positions travel planning as design work,
not transactional booking. This is what justifies the time the user spends
in onboarding (Odyssey Onboarding → Traveler DNA). Use in onboarding,
welcome flows, and any moment we ask for user input.

---

## 5. Tone Adaptation

The voice is constant; tone dials up and down by context.

| Surface | Tone dial | Example |
|---|---|---|
| Landing hero | Boldness UP, warmth steady | "Don't book a trip. Architect a journey." |
| Landing body / feature cards | Boldness DOWN, concreteness UP | "Input vague requests like 'five days in late spring, feeling tired, want nature and culture.'" |
| Auth pages (login/signup) | Warmth UP, boldness DOWN | "Welcome back. Sign in to pick up where your journey paused." |
| Welcome / onboarding | Warmth UP, personal UP | "Tell us how you actually like to travel. Takes about 4 minutes." |
| Dashboard chips / micro-copy | Concrete UP, all others DOWN | "Day 3 of 7", "+5 alternatives" |
| Error messages | Warmth UP, boldness OFF | "Something went sideways on our end. Try again — we kept your draft." |
| Empty states | Personal UP, warmth UP | "No trips yet. Start with where you'd actually want to go." |
| Marketing email (welcome) | Bold + warm, conversational | See `frontend/emails/alpha-welcome.tsx` |

---

## 6. Style Rules

### Case
- **Sentence case everywhere** — headings, subheads, buttons, chips,
  eyebrow labels. Proper nouns stay capitalized: `Aletheia Travel`,
  `Traveler DNA`, `Odyssey Onboarding`, `Kyoto`, `Telegram`.
- Eyebrow labels (`text-[10px] font-mono uppercase tracking-[0.18em]`) are
  fine — that's a typographic treatment, not a casing rule. They read as
  UPPERCASE due to CSS `uppercase`, but the underlying string is sentence
  case.

### Punctuation
- **Em dashes** with no spaces: `journey—not a checklist`. Use `—`.
- **Curly apostrophes and quotes** in display copy (≥24px / `text-2xl` and
  up): `Don’t book a trip`. Smaller body copy may use straight ASCII
  since browsers anti-alias them well, but display is mandatory curly.
- **No exclamation marks** in marketing or in-app copy. (Reserved for
  genuinely celebratory moments — e.g. the welcome email subject and the
  alpha credits grant success toast.)
- **Oxford comma** — yes. "Trips that bend, adapt, and remember."
- **Ellipses** — avoid. If a thought trails, end it.

### Contractions
- **Use them.** "Don't," "we're," "you'll." Contractions reduce distance.
- Exceptions: formal pages (privacy, terms) where they read odd.

### Numbers
- Spell out **one through nine**, numerals for **10+**. Exception: when
  the number is doing UI work (a count, a price, a credit balance) use
  numerals always. "Five travel preferences" but "100 alpha seats" and
  "100 credits."

### Emoji
- **None in marketing or in-app copy.** The welcome email subject line is
  the one allowed exception (and only because the previous designer put one
  there — review whether to keep).

---

## 7. Terminology

### Proprietary terms (always exactly like this)
| Term | Capitalization | Notes |
|---|---|---|
| Aletheia Travel | Both words capitalized | Full product name on first mention per surface. After that, "Aletheia" is fine. |
| Traveler DNA | Both words capitalized | Never "traveller DNA" (UK spelling), never lowercase. |
| Odyssey Onboarding | Both words capitalized | The 15-dimension intake flow. Used in onboarding copy and the about page. |

### Preferred terms

| Use this | Not this | Why |
|---|---|---|
| journey | trip, vacation, getaway | "Journey" matches the architect pillar. "Trip" is OK in body but never in a CTA. |
| companion | assistant, AI, bot, agent | "Companion" is warmer and on-brand. "AI" is acceptable when explaining the tech (e.g. "AI travel companion" — first mention). |
| architect (verb) | plan, book, organize | The hero verb. Use in CTAs and value props. |
| adapt | adjust, modify, change | "Adapt" carries the live-adjustment pillar. |
| your | the | "Your trip" not "the trip." Always second person. |
| in alpha | beta, in development, MVP | The product is in alpha — state it plainly. |

### Avoid

- "Perfect trip" / "best trip" — anti-positioning. We argue against the
  perfect-trip framing.
- "Transform your X" — generic SaaS-speak.
- "Effortless," "seamless," "frictionless" — overused, mean nothing.
- "Smart" as a standalone adjective ("travel planning made smart") — say
  what *kind* of smart.
- "Hassle," "headache," "pain point" — corporate.
- "Limited time," "limited spots" without a real number — feels like a
  growth-hack tactic. State the cap or drop the framing.
- "Click here" link text — always descriptive: "See pricing," "Read the
  privacy policy."

---

## 8. Voice Checks (one-line tests)

Before shipping any copy, run it past these:

1. **Would a friend with strong opinions say this?** (Not too polished, not
   too marketing-y.)
2. **Could you swap "Aletheia Travel" for any other travel SaaS without
   changing meaning?** If yes, the line is too generic.
3. **Does it use "you" or "your" at least once?** If no, ask why not.
4. **Is there a real noun, number, or place name in here somewhere?** Or is
   it all abstractions?
5. **Would the line still work read aloud?** (Headlines and CTAs especially.)
```

**Verification:** File exists, follows the structure above verbatim, opens
cleanly in a markdown viewer.

**⏹️ APPROVAL GATE — owner reads the brand voice doc. Adjustments here are
cheap; later phases will all reference this document, so it's worth getting
right before proceeding.**

---

### Phase 2 — Landing Page Copy Rewrites

**Files:**
- `frontend/src/app/page.tsx` (all four sections)

**Issue resolution checklist (from the 2026-05-27 brand review):**

| # | Issue | Resolution |
|---|---|---|
| 1 | CTA voice collapse | Rewrite hero/body — see "Final landing copy" below |
| 2 | "Everything You Need for the Perfect Trip" contradicts positioning | Replace with "Built for the trip only you would take" |
| 3 | "Start Planning" button mislabel | Rename to "Get alpha access" |
| 4 | "Join other travelers who are already planning smarter" — vague | Replaced with live count from Supabase (Phase 4) |
| 5 | "Travel planning made smart" — flat, unsubstantiated | Replace H2 entirely; consolidate hero (issue #7) |
| 6 | "Limited alpha access" — unsubstantiated scarcity | State the cap: "100 alpha seats — first come, first invited" |
| 7 | Hero H1+H2 visually competing | Collapse into one H1 + one short subhead |
| 8 | Button case inconsistency | All buttons → sentence case |
| 9 | Straight apostrophe in hero | Replace with curly `’` |
| 10 | Traveler DNA introduced late | Add to hero subhead |
| 11 | "Fuzzy desires" abstract | Concretize the problem-statement paragraph |
| 12 | `tripGenie_lastSignup` localStorage key | Rename to `aletheia_lastSignup` |

**Final landing copy (embed verbatim — do not paraphrase during implementation):**

#### HeroSection
- Eyebrow chip: `Early access — 100 seats`
- H1: `Don’t book a trip. Architect a journey.`
- Subhead (single line): `Travel planning that adapts to who you actually are — built around your Traveler DNA, not the average.`
- Primary button: `Get early access` (kept scroll-to-form behavior)
- Secondary button: `See how it works` (unchanged behavior — scrolls to ProofSection)

#### ProofSection
- H2: `Built for the trip only you would take`
- Body paragraph:
  > Most platforms solve for the cheapest flight or the trendiest hotel. Aletheia solves for the person. A travel companion that reads your energy, your motivations, and the season of life you’re in — and plans accordingly.
- Roadmap card phases unchanged (`Current Alpha`, `Upcoming`, `Future vision` — note the lowercase "vision").
- Roadmap card descriptions: rewrite each in voice (concrete, second-person where it helps):
  - Current Alpha: `Vague requests in, real itineraries out. Realtime weather and events baked in.`
  - Upcoming: `Day-by-day plans with alternates for tired days, rainy days, and second-wind days.`
  - Future Vision: `Trips with friends. Auto-booking. Quiet matching for travelers who fit.`

#### FeaturesSection
- H2: `How the companion works`
- Subhead: `Planning that adapts to you, not the other way around.`
- Feature cards (titles unchanged, descriptions rewritten in voice):
  - **Intuitive Discovery** → `Say "five days in late spring, feeling tired, want nature and culture." Get back a shortlist that fits.`
  - **Flexible Itineraries** → `Day-level plans with alternates for low-energy mornings, weather curveballs, and unexpected second winds.`
  - **Live Adaptation** → `Mid-trip, message us on Telegram. Plans bend in real time — no replanning your whole week.`
  - **Traveler DNA** → `Odyssey Onboarding builds your Traveler DNA — 15 dimensions of how you actually like to travel. Every suggestion runs through it.`
- Problem statement card:
  - H3: `The problem with static planning`
  - Body: `Hours lost across blogs, Reddit threads, and booking sites — and the trip you end up with was picked for price, not fit. By day three, you’re overscheduled, the weather turned, and there’s no plan B.`

#### CTASection
- H2: `Stop planning trips. Start architecting journeys.`
- Body (with live count — see Phase 4 for the dynamic part):
  > Aletheia is opening early access. **{N} of 100 seats** taken. Drop your email — if you’re in the first 100, you’ll get sign-in details within 24 hours. Either way, you’re on the list.
  >
  > (Note: until Phase 4 lands, embed a static fallback: `Aletheia opens with 100 early-access seats. Drop your email and we’ll send sign-in details to the first 100.`)
- Email input placeholder: `your@email.com` (lowercase, owns the format)
- Submit button: `Request access` (replaces "Get Started")
- Submit pending: `Joining…` → `Saving you a seat…`
- Footer text: `No credit card. We’ll only use your email to send your sign-in details and rare product updates. [Privacy policy](/privacy).`

**Other code-level fixes in this phase:**
- Replace localStorage key `tripGenie_lastSignup` → `aletheia_lastSignup` (lines 241, 280 of `page.tsx`)
- Update the rate-limit error message: `Hold up — wait {N}s and try again.`

**Verification:**
- Manual: read the full page top-to-bottom on desktop and at 375px mobile. Should feel like one voice end-to-end.
- Run `npm run build` — must pass.
- Confirm the curly apostrophe renders correctly in the hero (no `’` literal showing).

**⏹️ APPROVAL GATE — owner views the deployed (or local-dev) landing page and confirms the voice lands before moving to the gating mechanism.**

---

### Phase 3 — Alpha Waitlist Gating

**Files:**
- `frontend/src/lib/alpha-config.ts` *(new)*
- `frontend/src/app/actions.tsx` *(modified)*
- `supabase/rls_policies.sql` *(amended)*

**New file: `frontend/src/lib/alpha-config.ts`:**
```typescript
/**
 * Alpha-phase gating configuration.
 *
 * `ALPHA_CAP` controls how many people receive the welcome email with
 * sign-in instructions. Beyond the cap, signups are still recorded in the
 * `waitlist` table — they just get a "you’re on the list" response
 * instead of the email.
 *
 * To open beta, bump this number (e.g. 1000) and update the landing copy
 * accordingly.
 */
export const ALPHA_CAP = 100;
```

**`actions.tsx` modification (high level — implement in the file's existing style):**

Before sending the Resend email:
1. Query `waitlist` for the count of rows with `created_at < (this insert's created_at)`.
   Use a Supabase `count: 'exact', head: true` SELECT.
2. If `count < ALPHA_CAP`, send the welcome email and return:
   ```ts
   { success: true, message: "You’re in. Check your inbox for sign-in details — should arrive within a minute." }
   ```
3. If `count >= ALPHA_CAP`, **do not send the email** and return:
   ```ts
   { success: true, message: "You’re on the waitlist — seat #{position}. We’ll email you when access expands." }
   ```
   Where `position` is `count + 1`.

The action MUST always insert the row first, then read the count. Use the row's own `created_at` (already in the insert response) for the ordering window.

**RLS change in `supabase/rls_policies.sql`:**
Add a policy allowing the `anon` role to run `SELECT count(*)` on `waitlist` without exposing row contents:

```sql
-- Allow anon role to read row count for the landing-page "X of 100 seats" UI.
-- Anon must NOT be able to SELECT email or any PII — only aggregate counts.
-- Implementation: grant SELECT on a single non-sensitive column (id), which
-- is enough for count(*) but never returns email values to the client.
CREATE POLICY "waitlist_count_anon" ON public.waitlist
  FOR SELECT
  TO anon
  USING (true);

-- Revoke SELECT on email from anon explicitly (column-level grant)
REVOKE SELECT ON public.waitlist FROM anon;
GRANT  SELECT (id, created_at) ON public.waitlist TO anon;
```

> Note: if the column-level revoke breaks `count(*)` queries (some Postgres
> versions need at least one column granted), confirm the count query in
> Phase 4 uses `select('id', { count: 'exact', head: true })` so it only
> touches the granted `id` column.

**Verification:**
- Run the action with `ALPHA_CAP = 2` (temporary, in a dev branch) and 3 test signups. First 2 receive email; 3rd does not.
- Use the Supabase SQL editor to confirm anon `SELECT email FROM waitlist` is blocked but `SELECT count(*) FROM waitlist` works.

**⏹️ APPROVAL GATE — owner verifies the cap logic and email-sending split work as expected.**

---

### Phase 4 — Live Signup Count in CTA

**Files:**
- `frontend/src/app/page.tsx` (`CTASection` component)

**Implementation:**
- Fetch the count client-side on mount using the anon Supabase client:
  ```ts
  const { count } = await supabase
    .from('waitlist')
    .select('id', { count: 'exact', head: true });
  ```
- Hold the count in state. Fallback to `null` on error; render the static copy (`100 alpha seats`) when the count is null.
- Once loaded, render: `{count} of 100 seats taken. {100 - count} left.` (Don't show negative numbers — if `count >= 100`, render `100 of 100 seats taken — you’ll join the waitlist.`)
- The number itself should be visually emphasized (e.g. `<strong>` or the existing primary-color span pattern) so the live data feels alive without being shouty.

**Verification:**
- Manually insert a few rows into `waitlist` via Supabase SQL editor; reload the landing page; confirm the count updates.
- Throw a network error in DevTools; confirm the fallback copy renders without breaking the page.

**⏹️ APPROVAL GATE.**

---

### Phase 5 — Other Marketing Pages

**Files:**
- `frontend/src/app/how-it-works/page.tsx`
- `frontend/src/app/pricing/page.tsx`
- `frontend/src/app/faq/page.tsx`
- `frontend/src/app/about/page.tsx`
- `frontend/src/app/features/page.tsx`

**Process per page:**
1. Read the page in full.
2. List every user-visible string (headings, body copy, CTAs, helper text, FAQ Q&As).
3. Run each string past the brand voice doc's §8 voice checks.
4. Rewrite anything that fails — flag in a per-page summary the owner sees before edits land.
5. Apply sentence case across all headings/buttons.
6. Replace any forbidden terms ("perfect," "seamless," "transform," etc.) per §7 of the brand voice doc.

**No mockups embedded here** — the existing pages haven't been audited in detail yet. Per-page rewrites will be proposed inline at execution time, with the owner approving each page before edits land.

**⏹️ APPROVAL GATE PER PAGE — five sub-gates inside Phase 5.**

---

### Phase 6 — Auth Pages

**Files:**
- `frontend/src/app/(auth)/login/page.tsx`
- `frontend/src/app/(auth)/sign-up/page.tsx`
- `frontend/src/app/(auth)/forgot-password/page.tsx`
- `frontend/src/app/(auth)/reset-password/page.tsx`
- `frontend/src/components/auth/AuthShell.tsx` (marketing rail content)

**Specific items to address (from prior review):**
- Login page H2: `Welcome back.` — keep, on brand.
- Login subhead: `Sign in to continue architecting your journey.` — keep, on brand.
- Sign-up page: review against brand voice doc; expect changes to button labels and microcopy.
- Forgot-password / Reset-password: warmth dial UP (per Tone Adaptation table), no boldness — these are friction moments.
- Status/error messages on all four pages: rewrite in the "Something went sideways" tone (warmth UP, boldness OFF).

**⏹️ APPROVAL GATE.**

---

### Phase 7 — In-App Copy Sweep

**Files (non-exhaustive — implementer surveys at execution time):**
- `frontend/src/components/dashboard/DashboardShell.tsx`
- `frontend/src/components/dashboard/ProfileDropdown.tsx`
- `frontend/src/components/dashboard/TripDetailPanel.tsx` (chips, AI hint lines, empty states)
- `frontend/src/components/dashboard/ChatPanel.tsx` (placeholder, send button, empty state)
- `frontend/src/components/dashboard/WelcomeGrantModal.tsx`
- `frontend/src/components/settings/AccountSettings.tsx` (section subtitles, footer)
- Error toasts and success toasts throughout

**Specific known fixes:**
- WelcomeGrantModal headline currently reads "Welcome to Aletheia Travel!" — drop the exclamation per style rules. Rewrite in voice.
- ProfileDropdown subtitles (e.g. "Profile, credits, security") — check against concreteness rule.
- AccountSettings section subtitles — already polished but worth a final pass.
- TripDetailPanel "AI" callouts ("You said you felt tired. Plan is dialled down...") — already strongly on brand; keep as exemplars.

**⏹️ FINAL APPROVAL GATE — task complete when this phase ships.**

---

## 7. Testing & Validation

### Test Strategy
- **Static review** — owner reads every changed surface end-to-end before each gate. Voice is a human-judgment metric; no automated test replaces this.
- **Build gate** — `npm run build` must pass after every phase.
- **Manual smoke test** of the signup flow at the end of Phase 3 and Phase 4:

| Scenario | Expected behavior |
|---|---|
| Signup #1 (cap=100, current count = 0) | Row inserted, welcome email sent, success message: "You’re in. Check your inbox..." |
| Signup #100 | Same as above |
| Signup #101 | Row inserted, NO email sent, message: "You’re on the waitlist — seat #101..." |
| Anon `SELECT count(*)` on waitlist via curl | Returns the count |
| Anon `SELECT email FROM waitlist` via curl | Returns 0 rows or permission error |
| Landing page with network blocked to Supabase | Falls back to static copy, doesn’t white-screen |
| Landing page after the count crosses 100 | Renders "100 of 100 seats taken — you’ll join the waitlist." |

### Acceptance Tests
- All 12 issues from the landing-page brand review are fixed (issue-by-issue checklist in §6.2 above ticks).
- A teammate not on this project reads the full marketing surface (landing + how-it-works + pricing + faq + about + features) and reports the voice feels like one writer.
- Three random in-app error/empty-state strings, taken at random, pass the §8 voice checks in the brand voice doc.

### Tooling
- No new CI. The build gate is the existing `npm run build`.

---

## 8. Risk Management

### Known Risks
1. **Voice doc disagreement after Phase 1** — the brand voice doc locks in tradeoffs (bold vs. quiet, contractions, no emoji). If the owner later disagrees, multiple phases need revisits.
   - **Mitigation:** Phase 1 has its own dedicated approval gate. Push back hard on any "let's just start writing and figure it out" — the doc is what makes phases 5/6/7 tractable.
2. **Live count exposes signup velocity** — competitors can see how fast you’re filling the alpha.
   - **Mitigation:** Acceptable for now (alpha is small). If this becomes a concern in beta, swap the live count for a bucketed string ("almost full," "filling up") — single-file change in CTASection.
3. **Cap mis-counts under race conditions** — two simultaneous signups at count=99 could both pass the `count < ALPHA_CAP` check.
   - **Mitigation:** Acceptable for an alpha — at worst, 101 emails go out. If precise gating matters later, move the check into a Postgres function with an advisory lock.
4. **Scope creep in Phase 7** — the in-app copy surface is large and the sweep can balloon.
   - **Mitigation:** Phase 7 ships in two sub-passes: known-fix items first (WelcomeGrantModal, ProfileDropdown subtitles), then a "drift catcher" pass at end of phase. Anything contentious gets deferred to a follow-up task.

### Rollback Plan
- All copy changes are reversible via git revert per phase.
- The RLS change is reversible via `DROP POLICY "waitlist_count_anon"` + restore the prior column grants.
- The `ALPHA_CAP` constant is reversible by raising it to `Infinity` if the gating logic itself misbehaves in production.

---

## 9. Delivery & Handoff

### Deliverables
- `specs/brand_voice.md` (Phase 1)
- Modified `frontend/src/app/page.tsx` (Phase 2)
- New `frontend/src/lib/alpha-config.ts` (Phase 3)
- Modified `frontend/src/app/actions.tsx` (Phase 3)
- Modified `supabase/rls_policies.sql` (Phase 3)
- Modified marketing pages (Phase 5 — five files)
- Modified auth pages (Phase 6 — four pages + AuthShell)
- Modified in-app components (Phase 7 — list TBD at execution time)

### Review Process
Each phase ends with an explicit approval gate. The owner reviews:
1. The deployed (or local-dev) result.
2. Any new copy strings that landed.
3. Build status.

Sign-off is plain English ("looks good, go to phase N+1") — no formal ticket.

### Post-Delivery Actions
- Update `memory/project_overview.md` to note the brand voice doc and cap mechanism are live.
- Update `README.md` if it references any marketing copy that changed.
- Commit and push (manual; per project rules, do not auto-deploy or auto-commit).

---

## 10. Communication Plan

- **Stakeholder:** Cristian (sole reviewer).
- **Cadence:** End-of-phase summary in chat with a list of files changed and any open questions; owner reviews and approves.
- **Escalation:** If the brand voice doc itself gets stuck in revisions, pause the task and ship the landing-page fixes (Phase 2) only — those don’t depend on the full doc.

---

## 11. Appendix

### Glossary
- **Traveler DNA** — Aletheia’s proprietary structured user-preference profile, derived from the Odyssey Onboarding flow. 15 personality dimensions plus tags.
- **Odyssey Onboarding** — the intake flow (currently a Tally form) that produces the Traveler DNA.
- **Companion** — preferred user-facing term for the product’s AI behavior. "Travel companion" beats "AI assistant" in our voice.
- **Alpha cap** — the maximum number of signups that receive the welcome email with sign-in details. After the cap, signups are still recorded in `waitlist` but only get a "you’re on the list" response.

### Reference Materials
- `task_template.md` (project root) — the template this spec follows.
- Brand review output dated 2026-05-27 — the source for the 12 issues fixed in Phase 2.
- `memory/project_guidelines.md` — non-negotiable project rules referenced throughout.

### Change Log
- **2026-05-27** — Initial spec written.
