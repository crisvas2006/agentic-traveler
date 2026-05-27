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
| early access (preferred) / in alpha (acceptable when context is technical) | "beta," "in development," "MVP," "soft launch" | Default to "early access" — it reads clearly to non-technical visitors. "In alpha" is fine in release notes, technical pages, or when explicitly talking about phase. Avoid mixing both on the same page. |

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
