# Task 42 — Curiosity prompts library (research + content + product)

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §3.1, §5.6, §7.7.
> Depends on tasks 34–41.
> Triple-purpose: (a) extend the saga library with literature-grounded
> prompts, (b) ship a research artifact (annotated quotes) that doubles
> as the seed corpus for a future blog, (c) inject the prompts into
> sagas at runtime.

## 1. Problem Statement

Aletheia's strongest differentiator is being a *thoughtful* travel
companion — not a TripAdvisor clone that lists "top 10 Kyoto temples." A
small library of curiosity prompts, grounded in travel literature
(Potts, de Botton, Iyer, Solnit, Steves, Pearce's Travel Career Ladder,
Seneca), gives the AI permission to ask the kinds of questions a wise
travel-loving friend would ask: *"What's the picture in your head when
you imagine being there?"* — at the right moment, sparingly. The
proposal sketches a 7-entry seed library. This task takes that seed and
(a) expands it to 30–40 entries grounded in the same literature plus 5+
additional sources, (b) writes per-source 200-word annotated quotes into
`docs/travel_literature_notes.md` which becomes the seed corpus for a
future Aletheia blog, (c) implements the injection mechanism the sagas
will read.

## 2. Goals & Non-Goals

### Goals

- A YAML library at `backend/src/agentic_traveler/content/curiosity_prompts.yaml`
  with 30–40 entries, each: id, source, trigger criteria, prompt text,
  rationale.
- A `docs/travel_literature_notes.md` with ≥ 12 annotated quotes from
  ≥ 10 sources (the §3.1 list + 5 new), each 200–400 words. Written in
  the brand voice (warm, brief, literate).
- A `CuriosityPromptInjector` Python module that, given saga state and
  user profile, returns zero or one prompt to inject into the saga's
  system prompt as `<curiosity_prompt>{text}</curiosity_prompt>`.
- Injection rules: at most one prompt per session; only in DREAMING /
  SHAPING / REMEMBERING; never if `structure_preference > 0.7`; pick the
  prompt aligned to the user's profile dimensions.

### Non-Goals

- Building the blog publishing pipeline — out of scope.
- LLM-generated prompts — every prompt is human-curated.
- Image / quote-card UI — not in alpha.

## 3. Acceptance Criteria

AC-1. `curiosity_prompts.yaml` exists with 30–40 entries; YAML is valid
  and parseable into a Pydantic `CuriosityPrompt` model.

AC-2. `docs/travel_literature_notes.md` contains ≥ 12 sourced quotes,
  each with a 200–400-word annotation tying the quote to a design choice
  in this project, ≥ 10 distinct sources.

AC-3. `CuriosityPromptInjector.select(state, user_doc, session_state)`
  returns a single prompt OR None, deterministic for the same inputs,
  matching the rules in §7.

AC-4. The PlanningSaga (and any other DREAMING/SHAPING saga) reads the
  injector and embeds the returned prompt into its system prompt.
  (Alignment note, 2026-06-10: task 45 later replaces the slot-question
  leaf with an advisory turn composer. The injector contract —
  `select(state, user_doc, session_state) -> prompt | None` — is stable;
  task 45 §7 wires it into the composer's prompt. Implement AC-4 against
  the current saga; the re-wire is task 45's responsibility.)

AC-5. With `structure_preference > 0.7` in the profile, the injector
  always returns None (high planners → no philosophical detours).

AC-6. With the session-state flag `curiosity_used_this_session=true`,
  the injector returns None.

AC-7. The library covers prompts mapped to all 7 saga states (most
  concentrated in DREAMING and SHAPING).

AC-8. Each YAML entry's `text` is ≤ 200 chars.

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/content/curiosity_prompts.yaml          [create]
backend/src/agentic_traveler/content/__init__.py                     [create]
backend/src/agentic_traveler/orchestrator/curiosity_injector.py      [create]
backend/src/agentic_traveler/orchestrator/sagas/planning.py          [modify — inject]
backend/src/agentic_traveler/orchestrator/sagas/journal.py           [modify — inject]
backend/tests/test_curiosity_injector.py                             [create]
docs/travel_literature_notes.md                                      [create]
README.md                                                            [modify]
```

## 5. Constraints

- Prompts are **human-curated**. No LLM-generated entries.
- Every entry must cite a real source by title and author. No invented
  citations.
- Annotations in `docs/travel_literature_notes.md` must be fair-use
  short quotes (single sentences or short passages), never full
  paragraphs verbatim.
- The library lives in source control — versioned alongside code.
- The injector is **pure Python** — no LLM call.

## 6. Edge Cases

- **No prompt matches the user's profile** → injector returns None.
- **YAML parse fails** → injector returns None + log WARN; the saga
  proceeds without a prompt.
- **User explicitly asks for prompts** ("ask me something interesting")
  → DiscoverySaga can call the injector with `force=true` to pick one
  regardless of the once-per-session rule.

## 7. Implementation Plan

### Step 1 — Source list (research before writing the library)

10 minimum sources to read or re-read before writing:

1. Rolf Potts — *Vagabonding* (2003)
2. Alain de Botton — *The Art of Travel* (2002)
3. Pico Iyer — *The Art of Stillness* (2014)
4. Rebecca Solnit — *Wanderlust: A History of Walking* (2000)
5. Rick Steves — *Travel as a Political Act* (2009)
6. Pico Iyer — *"Why we travel"* (2000 essay, Salon)
7. Seneca — *Letters from a Stoic*, Letter XXVIII
8. Philip L. Pearce — *Travel Career Ladder* (1988 academic paper)
9. Bruce Chatwin — *The Songlines* (1987) — new addition
10. Robert Macfarlane — *The Old Ways* (2012) — new addition
11. Patrick Leigh Fermor — *A Time of Gifts* (1977) — new addition
12. Bill Bryson — *Notes from a Small Island* (1995) — new addition
13. Maya Angelou — *"All God's Children Need Travelling Shoes"* (1986) — new addition

(Library can grow beyond 12 if writing reveals more — but 12 minimum.)

### Step 2 — Quote + annotation format

For `docs/travel_literature_notes.md`, each entry:

```markdown
## de Botton — *The Art of Travel*, Ch.1

> "If our lives are dominated by a search for happiness, then perhaps few
> activities reveal as much about the dynamics of this quest — in all its
> ardour and paradoxes — than our travels."

de Botton opens with an observation that reorders the way Aletheia
introduces planning. The dashboard's "Vision banner" is not a label
("write your vision here") but a sentence we *coax* out of the user
during DREAMING — because the act of articulating what they hope for
is itself part of the trip. ... (~200–400 words ending with one or two
prompt ids in the library this passage seeded.)
```

### Step 3 — `curiosity_prompts.yaml`

Each entry:

```yaml
- id: anticipation
  source:
    author: "Alain de Botton"
    title: "The Art of Travel"
    page: 11
  trigger:
    states: [DREAMING]
    motivation_any: [aesthetic, novelty]
    profile:
      structure_preference_max: 0.7
  text: "What's the picture in your head when you imagine being there?"
  rationale: "Surfaces the visual/emotional anticipation de Botton argues is the trip's deepest pleasure. Used by PlanningSaga in DREAMING."

# ... 30+ more entries.
```

### Step 4 — `CuriosityPromptInjector`

```python
class CuriosityPromptInjector:
    def __init__(self, library_path: Path):
        self._library = load_yaml(library_path)

    def select(self, state: str, user_doc: dict, session_state: dict,
               force: bool = False) -> str | None:
        if not force and session_state.get("curiosity_used_this_session"):
            return None
        profile_scores = (user_doc.get("user_profile", {}) or {}).get(
            "personality_dimensions_scores", {}) or {}
        if profile_scores.get("structure_preference", 0.5) > 0.7 and not force:
            return None
        candidates = [p for p in self._library if state in p["trigger"]["states"]
                      and self._matches_profile(p, profile_scores, user_doc)]
        if not candidates:
            return None
        # Deterministic pick: hash(user_id + state + day) % len(candidates)
        idx = self._stable_index(user_doc, state, len(candidates))
        return candidates[idx]["text"]
```

### Step 5 — Wire into PlanningSaga + JournalSaga

In each saga's `_build_system_prompt` helper, after the static system
prompt, append:

```python
prompt_text = injector.select(saga_state, user_doc, session_state)
if prompt_text:
    system += f"\n<curiosity_prompt>{prompt_text}</curiosity_prompt>\n"
    session_state["curiosity_used_this_session"] = True
```

The LLM is instructed to *consider* the prompt as a possible angle for
the reply, never to read it verbatim.

### Step 6 — Tests

`test_curiosity_injector.py`:

- Each YAML entry parses.
- High-structure-preference profile → always None.
- Once-per-session rule.
- `force=true` bypasses both rules.
- Deterministic across calls with the same inputs.

## 8. Testing Plan

- **Unit:** all entries valid; injector rules; determinism.
- **Manual:** read the library, verify tone is consistent with brand
  voice (warm, brief, literate, never preachy).
- **Manual:** read `docs/travel_literature_notes.md` end-to-end — does
  it read like the start of a real blog?

## 9. Conditional Sections

### 9.2 LLM Considerations

- No new LLM calls — the injector is pure Python.
- The prompt is *injected* into existing saga prompts.

### 9.3 Observability

- Metrics: `curiosity_prompt_injected` (with id), `curiosity_used`.

### 9.4 Rollback Plan

- Set `CURIOSITY_INJECTOR_ENABLED=false` in env; the injector always
  returns None. Library remains in repo for future.

## 10. Findings & Follow-ups

### 10.1 Design note — countering the "AI effect" (per the implementation brief)

A deep, open question that delights from a human friend can fall flat — even
feel intrusive or performative — when an AI asks it cold, and people answer
machines more tersely and ignore anything that smells like a survey. Three
guards, all implemented:

1. **Tuned phrasing.** Every `text` in the library is concrete and low-effort
   (usually a light either/or, answerable in a few words). The literature lives
   in the entry's `rationale` (the *why* we ask); the user-facing line is
   deliberately de-intellectualised. (e.g. de Botton's anticipation →
   *"When you picture this trip, what's the first thing you see — a place, a
   meal, a certain kind of light?"*, not *"What does this journey mean to you?"*)
2. **Optional-aside delivery.** `frame_curiosity_prompt` wraps the text in
   strict rules: the model answers usefully first, then MAY add one short casual
   line at the very end, answerable-or-ignorable, never repeated, dropped if it
   would feel intrusive. The prompt is never the point of the reply.
3. **Earned, not cold-open.** `trigger.requires_destination` keeps the more
   personal prompts (*"why this place?"*, *"what do you hope the first morning
   feels like?"*) from firing until the user has shown commitment (a destination
   on the trip). Plus a once-per-day-per-trip cap and a hard opt-out for
   high-`structure_preference` planners (AC-5).

### 10.2 Spec deviations

- **Profile path corrected.** The spec's injector read
  `user_doc.user_profile.personality_dimensions_scores`. The real location is
  `user_doc.user_profile.profile_data.personality_dimensions_scores` (per
  `profile_utils`/`profile_agent`). Implemented against the real path.
- **`select(...)` gained an optional `trip=` param** (and `force=`), used for the
  `requires_destination` and `motivation_any` gates — the trip carries
  `destinations` and `discovery.motivations`. The documented contract
  (`state, user_doc, session_state → prompt|None`) is preserved.
- **Returns the `CuriosityPrompt` object, not just `str`** — the wiring needs
  `.id` for the `curiosity_prompt_injected` metric. `.text` is the line.
- **"Once per session" → once per day per trip.** There is no session store in
  this codebase (same constraint as tasks 41/43). `session_state.curiosity_used_this_session`
  is computed by the saga from a persisted `scratchpad.curiosity_last_at` marker;
  on injection the saga writes today's date. The injector's documented
  `session_state` gate (AC-6) is unchanged and unit-tested.
- **`journal.py` NOT modified** (spec §4 listed it). JournalSaga's owner reply is
  a deterministic prompt string (no LLM call), so there is no system prompt to
  inject into. REMEMBERING curiosity instead rides PlanningSaga's companion
  delegation to TripAgent (the phase gate includes REMEMBERING), which is where
  the LLM actually replies post-trip. JournalSaga (listener) still captures
  reflections. AC-4 ("PlanningSaga reads the injector") is satisfied.
- **Injection point.** Wired into PlanningSaga's three TripAgent companion
  delegations via `_curiosity_suffix(...)` (appended to `conversation_context`,
  consistent with task 41's mood injection), not a `_build_system_prompt` helper
  (which doesn't exist). It runs at most once per turn (only the taken branch)
  and only on companion turns — never on a slot question.
- **§4 additions:** `backend/requirements.txt` (pinned `PyYAML==6.0.3`, was a
  transitive dep); the rollback env var documented in `.env`-style via §9.4.

### 10.3 Follow-ups

- `force=true` is supported by the injector (for a future "ask me something
  interesting" DiscoverySaga path, edge §6) but not yet wired to a user-facing
  trigger. Priority: low.
- A `live_state.mood_history[]` would let curiosity/journal reference trends;
  today only the latest signal is available. Priority: low.
- After 4+ weeks of data, review `curiosity_prompt_injected{id}` to trim prompts
  that never fire or re-tune ones that do.

## 11. Definition of Done

- [x] AC-1 (34 entries, parse to `CuriosityPrompt`), AC-3 (deterministic select),
  AC-5 (high-structure → None), AC-6 (session gate), AC-7 (all 7 states covered),
  AC-8 (every text ≤200) — covered by `test_curiosity_injector.py` (17 tests).
- [x] AC-2 — `docs/travel_literature_notes.md`: 13 sourced notes (≥12),
  13 distinct sources (≥10), fair-use short passages/paraphrases, brand voice,
  each ending with the prompt ids it seeded. **Founder review still owed**
  (verify exact quotations before any public use — flagged at the top of the file).
- [x] AC-4 — PlanningSaga reads the injector (companion delegations); wiring
  unit-tested.
- [x] `ruff` clean; `pytest` 369 passed (+17 new); YAML parses.
- [x] README updated (curiosity prompts feature + AI-effect guards).

## Manual operations (user, post-implementation)

1. **Founder review of `docs/travel_literature_notes.md`** — founder-voice
   content; verify exact quotations/paraphrases and approve before any blog use.
2. **Tone pass on the library** — read `curiosity_prompts.yaml` end-to-end and
   confirm the prompts feel like a sharp friend, not a chatbot survey.
3. After alpha + 4 weeks of data: review which prompt ids actually fire
   (`curiosity_prompt_injected`); trim or re-tune.
