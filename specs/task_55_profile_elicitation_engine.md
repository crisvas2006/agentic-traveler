# Task 55 — Just-in-time profile elicitation engine

> Derived from `specs/proposal_discovery_and_living_dna.md` §4.2–4.3, §6.
> Depends on task 54. Follows `task_template_v2.md`.

---

## 0. Adaptation — real users are erratic (2026-06-13)

Implemented with a model that does NOT block the user in a rigid Q&A:
- The elicitor weaves at most ONE optional question into an already-useful reply;
  the user can ignore it, answer it, or deviate — the owner saga always handles
  whatever they actually say.
- **Skips are SOFT and per-run** (re-askable in a future run), NOT a permanent
  sentinel. A question is offered at most once per run (tracked in `asked`);
  "skip this" / a deviation simply moves on. **"go on without questions" mutes** the
  rest of the run. A permanent "never ask me X" stays the `hard_overrides` path.
- Per-run state lives on the trip (`trip.live_state.elicitation`), so it survives
  across turns and resets for a new trip/run.
- Wired centrally in the orchestrator (`OrchestratorAgent._maybe_elicit_profile`,
  best-effort) rather than per-saga, so one integration covers every owner that
  declares `requires_profile` / `asks_flow_state`.

---

## 1. Problem Statement

Task 54 gives us a question bank, a per-user answered set, and a chip write path,
but nothing *decides* which missing question to ask, when, and how gently. Today
the only DNA intake is the cold Tally form; in-chat enrichment doesn't exist. This
task adds the `ProfileElicitor` — a pure-Python, no-LLM selector (the architectural
twin of the shipped `CuriosityPromptInjector`) that, given the active saga's
coverage gap and pacing budget, returns at most one tappable profile question for
the owner saga to append to an already-useful reply. It is what makes the DNA
"living": the profile deepens exactly where the user spends time, one light tap at
a time, never as a wall of forms. It must feel like a friend's natural follow-up,
not an interrogation — so the value (the answer/suggestion) always comes first and
the question is a skippable aside.

## 2. Goals & Non-Goals

**Goals:**
- A `ProfileElicitor.next_question(...)` returns a single `SlotRequest`
  (`target="profile"`) or `None`, deterministically and with no LLM call.
- Pacing guardrails are enforced: ≤ 1 woven question per turn; always skippable;
  never emitted on a turn that has no useful primary content; suppressed when a
  hard-override already covers it; suppressed for high-`structure_preference` users
  on exploratory turns; honours `reply_length_preference` (terse → ask less often).
- `profile` vs `flow_state` bindings are handled differently: `profile` questions
  are skipped once answered (persisted); `flow_state` questions are asked once per
  flow run regardless of history.
- Wired into `PlanningSaga`, `ExplorationSaga` (task 56), and `CountryIntelSaga` so
  every flow elicits through the same component.
- A tapped/skip answer is consumed via the task-54 write path; a `skip` writes a
  sentinel so a `profile` question is never re-asked.

**Non-Goals:**
- The question content/registry (tasks 54 / 59).
- The write/apply mechanics (task 54).
- Choosing *destinations* or composing replies (that's the sagas/agents).
- Re-synthesising the DNA summary (task 54's `synthesize_from_answers`).

## 3. Acceptance Criteria

```
AC-1.  ProfileElicitor.next_question returns None when the active saga's
       missing_profile and missing_flow_state are both empty.
AC-2.  Given a non-empty gap and a turn that produced primary content, it returns
       exactly ONE SlotRequest with target="profile", prompt <= 200 chars, and the
       question's choices attached. It makes ZERO Gemini calls (assert).
AC-3.  Prioritisation: a flow-critical question outranks a merely most-informative
       one; ties break toward the question whose `informs` covers the most still-
       unknown dimensions, then toward `cost:"tap"`.
AC-4.  A `flow_state` question is returned on flow (re)entry even if it was answered
       in a previous flow run; a `profile` question answered previously is never
       returned.
AC-5.  When the owner saga's reply is itself a slot request (the saga is already
       asking something), the elicitor returns None — never two questions in one turn.
AC-6.  For a user with profile_data.personality_dimensions_scores.structure_preference
       > 0.7, the elicitor returns None on exploratory (DREAMING/SHAPING) turns.
AC-7.  reply_length_preference == "terse" reduces elicitation frequency
       (probabilistic skip or every-Nth-turn gate) vs "default"/"verbose".
AC-8.  Skips are SOFT (per-run): an asked question is recorded in the trip run-state
       `asked` and not re-offered THIS run, but IS re-askable in a future run. No
       permanent answered_questions sentinel is written for a skip.
AC-9.  The profile question rides only turns with real content and no pending trip
       slot (the trip slot is always asked first) — existing planning slot behaviour
       is unchanged.
AC-10. A typed reply while a question is pending is classified: "go on without
       questions" / "no more questions" MUTES the run; "skip this" / "I dunno" moves
       on to the next question; anything else is an answer/deviation handled normally.
AC-11. The user is never blocked: deviating to an unrelated topic while a question is
       pending is always allowed; each question is offered at most once per run.
```

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/profile_elicitor.py          [create]  (ProfileElicitor + classify_elicitation_reply + run-state helpers)
backend/src/agentic_traveler/orchestrator/agent.py                     [modify]  (central _maybe_elicit_profile + _is_exploratory at the owner-result seam)
backend/src/agentic_traveler/orchestrator/sagas/planning.py            [modify]  (declare requires_profile / asks_flow_state)
backend/tests/orchestrator/test_profile_elicitor.py                    [create]
backend/tests/orchestrator/test_orchestrator_elicitation.py            [create]
# NOT modified: country_intel.py / discovery.py — elicitation is central, so wiring
# a saga is just declaring its two attrs (deferred until they reliably have a trip).
```

## 5. Constraints

- **No LLM call** in the elicitor — selection is deterministic (mirrors
  `CuriosityPromptInjector`). Adding an LLM here would violate the cost design.
- **Never block the value.** The profile chip is appended to a reply that already
  answered the user; it is never the sole content of a turn that had real content.
- **One question per turn, globally.** The elicitor and the curiosity injector must
  not both fire — when a `CuriosityPrompt` is injected this turn, the elicitor yields
  (single shared "one aside per turn" budget; see §7 Step 4).
- **Respect hard-overrides and `reply_length_preference`** (existing fields).
- Existing planning slot-fill flow must be unchanged (AC-9).

## 6. Edge Cases

- **Gap present but turn is a pure slot-fill** (saga is asking a trip slot) → None
  (AC-5).
- **Curiosity prompt already chosen this turn** → None (shared aside budget).
- **All remaining questions are `flow_state` and already asked this run** → None.
- **User keeps skipping** → each skip persists; the gap shrinks to only flow_state;
  no nagging.
- **Owner saga produced an error/fallback reply** → None (don't tack a question onto
  a failure).
- **Multiple equally-ranked questions** → deterministic tiebreak by id (stable, so
  tests are reproducible).

## 7. Implementation Plan

### Step 1 — `ProfileElicitor` (pure-Python)
→ verify: AC-1, AC-2, AC-3, AC-4.

```python
# backend/src/agentic_traveler/orchestrator/profile_elicitor.py
from agentic_traveler.orchestrator.sagas.base import SlotRequest, ChoiceOption
from agentic_traveler.orchestrator.profile_questions import BY_ID
from agentic_traveler.orchestrator.profile_coverage import compute_gap

class ProfileElicitor:
    """Deterministic, no-LLM selector of the next profile question to weave in.
    Twin of CuriosityPromptInjector. Returns one SlotRequest(target='profile') or
    None. NEVER mutates state; the caller owns persistence."""

    def next_question(
        self,
        saga,                       # the owner saga (reads requires_profile / asks_flow_state)
        user_doc: dict,
        state,                      # SagaState (phase, flow_answered, etc.)
        *,
        turn_has_primary_content: bool,
        aside_budget_available: bool,   # False if a curiosity prompt already fired
    ) -> SlotRequest | None: ...
```
Selection algorithm:
1. If not `turn_has_primary_content` or not `aside_budget_available` → None.
2. If `state.pending_slot` (a trip slot is being asked) → None (AC-5).
3. If `_suppressed(user_doc, state)` (structure_preference > 0.7 on DREAMING/SHAPING;
   terse-frequency gate not satisfied) → None (AC-6, AC-7).
4. `gap = compute_gap(saga, user_doc, state.get("flow_answered", set()))`.
5. Candidate order: `missing_flow_state` first when the phase makes them relevant,
   else `missing_profile`; within a list, rank by (flow_critical desc,
   informs-coverage-of-unknown-dimensions desc, cost=="tap" desc, id asc).
6. Build the `SlotRequest` from `BY_ID[qid]` with `target="profile"`, attach a
   mutually-exclusive `Skip` `ChoiceOption(id="skip", label="Skip", value="__skip__")`.

### Step 2 — Skip-sentinel write
In task-54's `apply_profile_patch` (called from `_process_selection`), a value of
`"__skip__"` writes `answered_questions[qid] = {value:"__skip__", source:"chat_tap"}`
so `answered_profile_ids` counts it as covered. `flow_state` skips are recorded on
the conversation/`flow_answered` set only (ephemeral). → verify: AC-8.

### Step 3 — Wire into the sagas
Each owner saga, after composing its primary reply (and after the curiosity injector
runs), calls the elicitor and, if a question returns, attaches it as the turn's
`SagaResult.slot_request` (only when the saga isn't already returning one).
→ verify: AC-9.

```python
# inside PlanningSaga.run / ExplorationSaga.run / CountryIntelSaga.run, near the end:
if result.slot_request is None:
    pq = self._elicitor.next_question(
        self, user_doc, state,
        turn_has_primary_content=bool(result.text),
        aside_budget_available=not curiosity_injected,
    )
    if pq is not None:
        result.slot_request = pq
        events.emit("metric", {"name": "profile_question_asked",
                               "id": pq.slot, "binding": BY_ID[pq.slot].binding,
                               "saga": self.name})
```
Declare each saga's `requires_profile` / `asks_flow_state` (the seed sets):
- `PlanningSaga.requires_profile = ["travel_company","pace","budget_tier","structure_preference"]`,
  `asks_flow_state = ["trip_intent_this_time","energy_for_this_trip"]`.
- `ExplorationSaga.requires_profile = ["travel_company","meaning_depth","immersion"]`,
  `asks_flow_state = ["current_craving"]`.
- `CountryIntelSaga.requires_profile = ["risk_appetite"]`, `asks_flow_state = []`.
(Exact ids finalised against the task-59 content; these are the seed wiring.)

### Step 4 — Shared "one aside per turn" budget
The owner saga passes `aside_budget_available=False` to the elicitor when the
curiosity injector already added a prompt this turn, and vice-versa (curiosity
injector yields if an elicitation question is mandatory for a near-complete flow).
Default precedence: a flow-critical profile question outranks a curiosity prompt;
otherwise the curiosity prompt wins (it's lighter). → verify: AC-5 + the single-aside
rule.

## 8. Testing Plan

- **Unit (`test_profile_elicitor`):** AC-1…AC-7 with hand-built `user_doc`/`state`
  fixtures and a fake saga exposing `requires_profile`/`asks_flow_state`; assert zero
  client calls.
- **Saga integration (`test_planning_elicitation`):** a planning turn with a pending
  trip slot yields no profile chip; a planning turn with all trip slots filled and a
  gap yields exactly one (AC-9, AC-5).
- **Manual:** none (UI rendering of the chip is the existing task-43 path, already
  covered).
- **Sample (happy path):** PlanningSaga, all trip slots filled, gap=["pace"],
  default reply-length → reply text + one chip "What pace suits this trip?" with
  Slow/Medium/Fast/Skip, `target:"profile"`.
- **Sample (suppressed):** same gap but `structure_preference=0.82`, phase DREAMING
  → no chip.

## 9. Conditional Sections

### 9.2 LLM Considerations
- **Zero LLM** in this task — the whole point. No tokens, no model tier.
- Prompt-injection surface: none added (no untrusted text enters a prompt here).

### 9.3 Observability
- Metrics: `profile_question_asked {id, binding, saga}` (emitted in Step 3);
  `profile_question_skipped {id}` from the write path; `elicitor_suppressed {reason}`.
- `profile_coverage_reached {saga}` emitted when a saga's `missing_profile` becomes
  empty for a user — the headline KPI for the living-DNA design.
- No `@traceable` needed (no LLM call); the host saga's `run` is already traced.

### 9.4 Rollback Plan
- Flagged by `PROFILE_ELICITOR_ENABLED` (default true, mirrors
  `CURIOSITY_INJECTOR_ENABLED`). Setting it false makes `next_question` return None
  everywhere — instant, safe disable. No data implications.

## 10. Findings & Follow-ups

### 10.1 Remaining (frontend pairing — clearly scoped follow-up)
- The elicitation question renders via the existing task-43 chip path. **Tapping** an
  option currently posts to `/chat/send` (the trip-slot path), which gracefully
  rejects a profile qid (no crash, re-asks). The frontend should route a chip whose
  `slot_request.target == "profile"` to `POST /profile/answer` (task 54) — a small,
  well-scoped change that pairs naturally with task 57 (the DNA page). Until then the
  **typed** path (answer / skip / "go on") — the user's actual scenario — is fully
  functional.
- **flow_state answer-value capture**: a tapped flow_state answer isn't yet written
  into `trip.live_state.elicitation.answered_flow` (needs the same frontend routing +
  a flow-answer endpoint). The elicitation *cycle* (ask once per run, skip/mute/
  deviate) works today purely via `asked`; only the captured value is pending.

### 10.2 Spec deviations
- **Skip model**: changed from the original permanent `__skip__` sentinel to SOFT
  per-run skips on the trip (`asked` set), per the founder's "don't block the user;
  re-asking next run is fine". Permanent suppression stays the `hard_overrides` path.
- **Integration point**: wired CENTRALLY in `OrchestratorAgent._maybe_elicit_profile`
  (called once at the owner-result seam, best-effort try/except) instead of editing
  each saga's `run`. One integration covers every owner declaring the two attrs; the
  hot path can never be broken by an elicitation error.
- **Run-state location**: `trip.live_state.elicitation` (uncontended during planning/
  discovery) rather than `SagaState`/conversation — SagaState is rebuilt per turn, so
  it can't carry cross-turn run-state; the trip persists and resets per run.
- **Added** `classify_elicitation_reply` (mute / skip / other) — the erratic-reply
  handler the original spec lacked (AC-10/AC-11).
- **PlanningSaga requirements** set to COMPLEMENT trip slots
  (`requires_profile=[meaning_depth, immersion]`, `asks_flow_state=[trip_intent_this_time,
  energy_for_this_trip]`) rather than the spec's draft set (which duplicated the
  pace/budget/structure/travelers trip slots). Other sagas not wired yet (see §10.1).
- **Test files**: `test_orchestrator_elicitation.py` (the glue) instead of the spec's
  `sagas/test_planning_elicitation.py`, since the integration is orchestrator-level.

## 11. Definition of Done
- [ ] AC-1…AC-9 pass.
- [ ] §6 edge cases covered or deferred.
- [ ] `ruff check` clean; `pytest` unit suite passes.
- [ ] No file outside §4 modified (or §10.2 explains).
- [ ] `README.md` updated (the living-DNA elicitation paragraph + the kill-switch env).
- [ ] `PROFILE_ELICITOR_ENABLED` documented in `.env.example` + `DEPLOYMENT.md`.

## 12. Open Questions
- Terse-frequency gate: probabilistic (e.g. 35% chance) vs deterministic every-3rd-turn?
  Default: deterministic every-3rd eligible turn (testable). Confirm if a
  probabilistic feel is preferred.
