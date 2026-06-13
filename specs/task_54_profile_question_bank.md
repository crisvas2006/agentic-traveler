# Task 54 — Profile question bank + coverage spine

> Derived from `specs/proposal_discovery_and_living_dna.md` §4.1–4.4, §6.
> Foundation task: unblocks tasks 55–60. Follows `task_template_v2.md`.

---

## 1. Problem Statement

The Traveler DNA is built once from a cold Tally form and then never grows
*structurally* from conversation. `PreferenceLearner` captures ad-hoc preferences
and hard-overrides reactively, but nothing models "which facts about a traveler do
we know, which does a given flow need, and which are still missing." This is the
spine of the "living DNA": a question-bank registry, a per-user *answered* set, a
per-saga coverage requirement, a generalisation of the proven tappable-chip write
path so a chip can target the **profile** (not just the trip), and a cheap
incremental DNA update. Without it, every later piece — the elicitation engine
(55), the ExplorationSaga's woven questions (56), the DNA page edits (57), the
expanded content (59), Tally retirement (60) — has nowhere to read or write. This
task ships no user-visible behaviour on its own; it is the data + write layer the
rest stand on.

## 2. Goals & Non-Goals

**Goals (behavioral):**
- A `ProfileQuestion` registry exists as the single source of truth; each entry
  declares `binding` (`profile` | `flow_state`), `prompt`, `choices`, `informs`,
  `category`, `cost`, and an optional `tally_key` for backfill.
- The user profile tracks answered `profile` questions under
  `user_profiles.profile_data.answered_questions`.
- A saga can declare `requires_profile` and `asks_flow_state` id-sets, and the
  system can compute a coverage gap from them.
- A tapped profile chip writes deterministically (zero LLM) into
  `answered_questions` **and** the relevant tag/dimension; a free-text reaction
  ("I don't really like museums") writes via **one** `flash-lite` call.
- `ProfileAgent` can (re)synthesise the DNA summary + dimensions from
  `answered_questions`, not only from a raw Tally submission.
- Existing Tally-built profiles backfill `answered_questions` (via `tally_key`) so
  no current user is re-asked anything Tally already covered.

**Non-Goals:**
- The *selection* logic (which question to ask, pacing) — that is task 55.
- The ExplorationSaga and the authored question *content* — tasks 56 / 59.
- The DNA page UI — task 57.
- Removing the Tally intake — task 60 (this task only *re-points* `ProfileAgent`;
  it leaves the webhook working).
- Context-slimming / preference bundles — post-alpha (this task only *exposes* the
  per-saga relevant-dimension slice; it does not change any agent prompt to use it).

## 3. Acceptance Criteria

```
AC-1.  profile-questions.ts exports a typed CAPABILITIES-style array; importing it
       in a unit test yields >= the seed set (the profile-bound Tally v2 questions +
       the flow_state trio used by tasks 55/56) with no duplicate ids and every
       `choices[].id` unique within its question.
AC-2.  A Python ProfileQuestion bank loads the SAME ids/options as the TS registry;
       a parity test fails if the two drift (mirrors the CAPABILITY_INTENTS test).
AC-3.  Tapping a profile chip (selection target="profile", legal option) writes
       profile_data.answered_questions[qid] = {value, set_at, source:"chat_tap"}
       AND applies the question's `informs` mapping (tag add / dimension set) — with
       ZERO Gemini calls (assert the client mock is never invoked).
AC-4.  A selection with target="profile" and an id NOT in the registry, or a value
       not among that question's legal options, is rejected server-side (HTTP 422,
       no write) — the client registry is never trusted.
AC-5.  A free-text reaction routed through the reaction path extracts a preference
       with exactly one flash-lite call and writes it into the same
       answered/tag structures.
AC-6.  compute_gap(saga) returns {missing_profile, missing_flow_state}; answering a
       shared question inside saga B removes it from saga A's missing_profile too.
AC-7.  A question whose target slot is satisfied by an existing hard_override is
       reported as covered (never "missing").
AC-8.  ProfileAgent.synthesize_from_answers(answered_questions) produces tags +
       personality_dimensions_scores + summary and upserts them, with NO dependence
       on form_response.
AC-9.  Backfill: for a user with a Tally form_response but no answered_questions,
       running the backfill marks every bank question whose `tally_key` is present
       as answered (source:"tally_backfill"); it is idempotent and never overwrites
       a richer chat-sourced answer.
AC-10. build_profile_summary() is unchanged in output for a user with no
       answered_questions (pure backward-compat), and folds a compact answered
       summary in when present.
```

## 4. Files & Modules Touched

```
frontend/src/lib/profile-questions.ts                                   [create]
backend/src/agentic_traveler/orchestrator/profile_questions.py          [create]
backend/src/agentic_traveler/orchestrator/profile_coverage.py           [create]
backend/src/agentic_traveler/orchestrator/profile_write.py              [create]
backend/src/agentic_traveler/orchestrator/sagas/base.py                 [modify]
backend/src/agentic_traveler/orchestrator/agent.py                      [modify]
backend/src/agentic_traveler/orchestrator/profile_utils.py             [modify]
backend/src/agentic_traveler/orchestrator/profile_agent.py             [modify]
backend/src/agentic_traveler/interfaces/routers/chat.py                [modify]
backend/src/agentic_traveler/interfaces/schemas.py                     [modify]
backend/scripts/backfill_answered_questions.py                         [create]
backend/tests/orchestrator/test_profile_questions_parity.py            [create]
backend/tests/orchestrator/test_profile_write.py                       [create]
backend/tests/orchestrator/test_profile_coverage.py                    [create]
backend/tests/orchestrator/test_profile_agent_synthesis.py            [modify]
```

## 5. Constraints

- **No schema migration.** `answered_questions` is a new key *inside* the existing
  `user_profiles.profile_data` JSONB — no DDL, no new table, RLS inherited
  (`auth.uid() = user_id`). Writes go through the existing service-key path.
- **Do not remove any `profile_data` field** (CLAUDE.md §8). Additive only.
- **`build_profile_summary` output must not regress** for existing users (AC-10).
- **The existing trip-slot path must keep working unchanged** — `target` defaults to
  `"trip"`; absence of `target` on the wire behaves exactly as today.
- **No Gemini in unit tests** (mock the client); the tap path must itself make zero
  LLM calls in production (AC-3).
- Leave the Tally webhook functional (its removal is task 60).

## 6. Edge Cases

- **Unknown / illegal selection** → 422, no write (AC-4).
- **Duplicate answer** (user re-taps an already-answered question) → overwrite
  `value` + `set_at`, keep idempotent; never duplicate the tag in `tags`.
- **multiSelect question** (`allow_multi`) → store a list value; the informs mapping
  adds each implied tag once.
- **Free-text reaction with no extractable preference** → flash-lite returns empty;
  no write, no error.
- **Backfill collision** → never overwrite a `chat_tap`/`chat_text` answer with a
  `tally_backfill` one (AC-9).
- **Hard-override present** → question treated as covered (AC-7); a later explicit
  answer still overrides the override per existing precedence.
- **answered_questions absent** (all existing users pre-backfill) → all reads treat
  it as `{}` (AC-10).

## 7. Implementation Plan

### Step 1 — `profile-questions.ts` (TS source of truth)
Create the registry, sibling of `capabilities.ts`. → verify: AC-1 test passes.

```ts
// frontend/src/lib/profile-questions.ts
export type QuestionBinding = "profile" | "flow_state";
export type QuestionCategory = "compass" | "pulse" | "strategy" | "identity" | "state";

export type ProfileChoice = { id: string; label: string; value: string };

export type ProfileQuestion = {
  id: string;                  // stable snake_case, e.g. "travel_company"
  binding: QuestionBinding;    // profile = persist & reuse; flow_state = re-ask each flow run
  prompt: string;              // <= 200 chars, one question
  choices: ProfileChoice[];    // tappable options; [] => free-text only
  allowMulti?: boolean;        // e.g. "what makes a trip feel successful"
  informs: string[];           // DNA dimensions / tag families this answer feeds
  category: QuestionCategory;
  cost: "tap" | "flash_lite";  // tap = deterministic write; flash_lite = text parse
  tallyKey?: string;           // maps to a Tally form_response key, for backfill (task 60 removes Tally, keeps this map)
  hardOverrideSlot?: string;   // if this hard_override slot is set, treat as covered
};

// Seed set only — the nuanced expansion is authored in task 59. The seed MUST
// include the small flow_state set the sagas wire in tasks 55/56
// (trip_intent_this_time, energy_for_this_trip, current_craving) so their
// requires/asks references resolve before task 59 lands.
export const PROFILE_QUESTIONS: ProfileQuestion[] = [
  { id: "travel_company", binding: "profile",
    prompt: "Who's usually in your travel bubble?",
    choices: [
      { id: "solo", label: "Solo", value: "solo" },
      { id: "duo", label: "Partner", value: "duo" },
      { id: "inner_circle", label: "Close friends/family", value: "inner_circle" },
      { id: "socialite", label: "I meet people on the road", value: "socialite" },
    ],
    informs: ["social_energy", "travel_company"], category: "compass", cost: "tap",
    tallyKey: "travel_bubble" },
  // ... remaining seed questions (pace, budget_tier, structure_preference,
  //     immersion, meaning_depth, …) — full seed list authored in this task,
  //     nuanced expansion in task 59.
];

export function profileQuestionById(id: string): ProfileQuestion | undefined {
  return PROFILE_QUESTIONS.find((q) => q.id === id);
}
```

### Step 2 — `profile_questions.py` (Python mirror + parity test)
Mirror the registry as a frozen dataclass list, loaded once. → verify: AC-2 parity
test compares ids + option ids between the JSON-exported TS registry and Python.

```python
# backend/src/agentic_traveler/orchestrator/profile_questions.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ProfileChoiceDef:
    id: str; label: str; value: str

@dataclass(frozen=True)
class ProfileQuestionDef:
    id: str
    binding: str                 # "profile" | "flow_state"
    prompt: str
    choices: tuple[ProfileChoiceDef, ...]
    informs: tuple[str, ...]
    category: str
    cost: str                    # "tap" | "flash_lite"
    allow_multi: bool = False
    tally_key: str | None = None
    hard_override_slot: str | None = None

PROFILE_QUESTIONS: tuple[ProfileQuestionDef, ...] = ( ... )  # mirror of the TS seed

BY_ID = {q.id: q for q in PROFILE_QUESTIONS}

def legal_option_values(qid: str) -> set[str]:
    q = BY_ID.get(qid)
    return {c.value for c in q.choices} if q else set()
```
Parity test: a committed `profile-questions.export.json` (generated by a tiny node
script or hand-kept) is asserted equal to the Python ids/options. Mirrors the
existing `CAPABILITY_INTENTS` sync test.

### Step 3 — `SlotRequest.target` (generalise the chip to write the profile)
Extend `sagas/base.py` `SlotRequest` with `target: str = "trip"` and include it in
`to_wire()`. → verify: existing trip-slot `to_wire` tests still pass; a profile
chip serialises `target:"profile"`.

```python
@dataclass(frozen=True)
class SlotRequest:
    slot: str
    prompt: str
    choices: Optional[list[ChoiceOption]] = None
    allow_multi: bool = False
    target: str = "trip"          # "trip" (default, unchanged) | "profile"

    def to_wire(self) -> dict[str, Any]:
        return { "slot": self.slot, "prompt": self.prompt, "target": self.target,
                 "choices": ([{"id": c.id, "label": c.label, "value": c.value}
                              for c in self.choices] if self.choices else None),
                 "allow_multi": self.allow_multi }
```
Also add the optional saga-coverage attributes to the `BaseSaga` Protocol doc and
to every concrete saga as class defaults:
```python
class BaseSaga(Protocol):
    name: str
    requires_profile: list[str]      # profile question ids needed to personalise well; default []
    asks_flow_state: list[str]       # flow_state question ids re-asked each flow run; default []
```

### Step 4 — `profile_write.py` (deterministic apply + reaction parse)
→ verify: AC-3, AC-5.

```python
# backend/src/agentic_traveler/orchestrator/profile_write.py
from agentic_traveler.orchestrator.sagas.base import SideEffect

def profile_selection_to_side_effect(qid: str, values: list[str]) -> SideEffect | None:
    """Validate qid + values against the bank; return a 'profile_patch' SideEffect
    or None if illegal. Pure, no LLM (sibling of slot_selection_to_side_effect)."""

def apply_profile_patch(user_id: str, payload: dict) -> None:
    """Merge into profile_data.answered_questions[qid] = {value, set_at, source}
    and apply `informs` -> tags/dimensions via UserRepository. Idempotent."""

def reaction_to_profile_patch(user_id: str, text: str, events) -> None:
    """One flash-lite extraction of a volunteered preference ('not big on museums')
    -> the same answered/tag structures. Reuses PreferenceLearner's extractor;
    emits tool_invoked/tool_succeeded. cost: flash_lite."""
```
`answered_questions` entry shape: `{ "<qid>": { "value": <str|list>, "set_at": <iso>,
"source": "chat_tap" | "chat_text" | "tally_backfill" | "dna_page" } }`.
Register a `"profile_patch"` branch in the dispatcher's `apply_side_effect`
(agent.py) alongside the existing `trip_patch` / `destination_upsert` kinds.

### Step 5 — Route profile selections through `_process_selection`
In `agent.py` `_process_selection` (≈ line 503), branch on the wire `target`:
`"profile"` → `profile_selection_to_side_effect` + `apply_profile_patch`;
otherwise the existing trip path, unchanged. Re-validate the option server-side
against `legal_option_values(qid)` before writing. → verify: AC-3, AC-4.
Add `target` to the `/chat/send` selection schema in `interfaces/schemas.py`
(optional, defaults `"trip"`).

### Step 6 — `profile_coverage.py`
→ verify: AC-6, AC-7.

```python
def answered_profile_ids(user_doc: dict) -> set[str]:
    """Ids in profile_data.answered_questions PLUS ids whose hard_override_slot is
    satisfied in profile_data.hard_overrides."""

def compute_gap(saga, user_doc: dict, flow_answered: set[str]) -> dict:
    """{'missing_profile': [...], 'missing_flow_state': [...]} respecting overlap +
    overrides. flow_answered = flow_state ids answered THIS flow run (ephemeral)."""
```
`flow_state` answers are NOT persisted to `profile_data`; they live on
`SagaState`/conversation turn state and are passed in as `flow_answered`.

### Step 7 — `profile_utils` + `profile_agent`
- `build_profile_summary`: when `answered_questions` present, append a compact
  `Answered: company=duo, pace=slow, …` line; otherwise byte-identical output
  (AC-10). Add `relevant_dimensions(saga) -> set[str]` (union of `informs` over the
  saga's `requires_profile`) as the post-alpha context-slice affordance (exposed,
  not yet consumed).
- `profile_agent`: add `synthesize_from_answers(user_id, answered_questions)`
  producing `tags` + `personality_dimensions_scores` + `summary` and upserting via
  the existing path (≈ line 276). The Tally builder becomes one caller of a shared
  synthesis core; this is the second caller. → verify: AC-8.

### Step 8 — Backfill
`backend/scripts/backfill_answered_questions.py`: for each user, if
`answered_questions` is absent/empty, map `form_response[tally_key]` → answered
entries (`source:"tally_backfill"`), never overwriting richer answers; idempotent.
→ verify: AC-9.

## 8. Testing Plan

- **Unit:** `test_profile_questions_parity` (AC-1, AC-2); `test_profile_write`
  (AC-3, AC-4, AC-5 with a mocked client asserting call counts); `test_profile_coverage`
  (AC-6, AC-7); `test_profile_agent_synthesis` (AC-8); a backfill test (AC-9); a
  `build_profile_summary` golden test for the no-answers case (AC-10). Mock Supabase
  + Gemini per `backend/TESTING_STRATEGY.md`.
- **Integration (`-m integration`):** one real `synthesize_from_answers` round-trip
  against Gemini + Supabase on a `_test:true` user.
- **Manual:** none (no UI in this task).
- **Sample apply (happy path):** selection `{slot:"travel_company",
  values:["duo"], target:"profile"}` → `answered_questions.travel_company =
  {value:"duo", set_at:…, source:"chat_tap"}`, tag `couples_travel` added, zero LLM.
- **Sample apply (error path):** `{slot:"travel_company", values:["spaceship"],
  target:"profile"}` → 422, no write.

## 9. Conditional Sections

### 9.1 Data Model & RLS
- No DDL. New key `answered_questions` inside `user_profiles.profile_data` (JSONB).
- RLS unchanged — `user_profiles` already enforces `auth.uid() = user_id`; service
  key used for the deterministic write, as today.
- Backfill: idempotent script (§7 Step 8); safe to re-run; never destructive.

### 9.2 LLM Considerations
- Tap path: **zero** LLM (AC-3).
- Reaction path: **one** `gemini-3.1-flash-lite` call (cheapest tier, CLAUDE.md §10),
  ≤ ~400 input / ~80 output tokens.
- `synthesize_from_answers`: `gemini-3.1-flash-lite` (the Profile tier), occasional
  (threshold-triggered), never on the hot path.
- Prompt-injection surface: the free-text reaction is untrusted — reuse the existing
  `core` sanitisation before it enters the extractor prompt.
- Versioning: registry is code-versioned (git); the synthesis prompt carries a
  `# prompt v1` marker as the other agents do.

### 9.3 Observability
- Metrics (into `analytics_events` via `EventEmitter.emit("metric", …)`):
  `profile_answer_written {id, binding, source, method:"tap"|"text"}`,
  `profile_synthesis_run {trigger}`.
- `@traceable` on `synthesize_from_answers` and `reaction_to_profile_patch`.
- No PII in logs — log `qid`, never the raw reaction text.

### 9.4 Rollback Plan
- Pure-additive + flag-free. Revert = remove the new modules + the `target` field;
  `answered_questions` data is inert if unread. No down-migration (no DDL).

## 10. Findings & Follow-ups
_(populated during/after implementation)_

### 10.1 Improvements observed
- Post-alpha: consume `relevant_dimensions(saga)` in `build_profile_summary` to slim
  prompt context (proposal §5) — filed as `task_living_dna_context_bundles.md`.

### 10.2 Spec deviations
- §7 Step 3: the `requires_profile` / `asks_flow_state` saga attributes are documented
  as a **getattr-convention** in the `BaseSaga` docstring rather than added as Protocol
  members. Reason: `BaseSaga` is `@runtime_checkable`, and adding data members would
  make `isinstance(saga, BaseSaga)` demand them on every existing saga — a breaking
  change. The elicitor (Task 55) reads them via `getattr(saga, "requires_profile", [])`.
- §7 Step 2 / AC-2: full automated TS↔Python byte-parity tooling is deferred; the
  current guard (`test_profile_questions.py`) asserts structural invariants + that all
  saga-required ids exist. A committed contract-JSON parity check is the natural
  follow-up when Task 59 re-touches both registries.
- §7 Step 5 / AC-4: profile chips are applied through a dedicated
  `POST /profile/answer` endpoint (`routers/profile.py`) rather than the `/chat/send`
  selection round-trip with a `target` field. Reason: a profile tap is a silent
  enrichment with no trip and no chat bubble — routing it through `_process_selection`
  would resolve/create a trip and persist a blank agent message. `SlotRequest.target`
  is still added (it tells the frontend which endpoint a chip posts to). The 422
  validation now lives in the endpoint. `SelectionIn` was NOT given a `target` field.
- §7 Step 4: the deterministic tap write records `answered_questions[qid]` only
  (zero-LLM, agent-visible via the compact `Answered:` summary line); human-facing
  tags/dimension scores are (re)derived by `synthesize_from_answers`, not mapped
  per-option on the hot path. AC-3's sample tag is produced by synthesis, not the tap.
- §4 file-list reconciliation (actual vs predicted): ADDED
  `interfaces/routers/profile.py` (the new endpoint), `interfaces/main.py` (router
  include), `tools/user_repo.py` (the `merge_answered_question` method),
  `tests/interfaces/test_profile_routes.py` and `tests/orchestrator/test_profile_utils_answered.py`.
  NOT touched: `interfaces/routers/chat.py` (superseded by the dedicated endpoint).
  Test files named `test_profile_questions.py` / `test_profile_coverage.py` /
  `test_profile_write.py` (the spec's `_parity` suffix folded into the first).

## 11. Definition of Done
- [ ] AC-1…AC-10 pass.
- [ ] §6 edge cases covered or deferred in §10.2.
- [ ] `ruff check` clean; `pytest` unit suite passes; integration where applicable.
- [ ] No file outside §4 modified (or §10.2 explains).
- [ ] `README.md` updated (the answered-questions structure + the chip-targets-profile
      generalisation).
- [ ] No secrets/PII in logs; RLS unchanged and still enforced.

## 12. Open Questions
- TS→Python parity: generate `profile-questions.export.json` via a node script in CI,
  or hand-maintain with a guard test? Default: hand-maintain + guard test (matches the
  existing `CAPABILITY_INTENTS` approach). Confirm if CI generation is preferred.
