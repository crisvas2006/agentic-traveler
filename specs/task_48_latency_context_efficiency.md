# Task 48 — Latency & context efficiency: measure, audit, trim, parallelize

> Spec per `task_template_v2.md`. Stream C of the 2026-06-10 product-evolution
> brainstorm. Lands after task 47 (consumes `BudgetPolicy`); the §7.1
> instrumentation phase has no dependencies and MAY be implemented early as a
> standalone slice if latency investigation becomes urgent.

---

## 1. Problem Statement [REQUIRED]

Plan/trip-mode responses take 30+ seconds, and nobody can say precisely
where the time goes. The per-turn pipeline runs up to three LLM calls in
sequence (RouterAgent classify → slot extraction → heavy agent) plus tool
round-trips (search, weather) inside the heavy call, and every call carries
a generously assembled context (full profile summary, conversation history,
whole trip JSON) that has never been audited — the product owner's
hypothesis, almost certainly correct, is that some calls get more context
than they need, making them slower, costlier, and more error-prone, while
others may get too little. Separately, thinking-capable Gemini 3.x models
spend unbounded thinking tokens unless steered (`thinking_level`), which
task 47's BudgetPolicy now controls — this task turns that knob
deliberately and verifies the effect. The guiding principle (owner,
verbatim intent): *agents should be as lean as possible, specialized to a
good extent — not maximally specialized, or the orchestration becomes too
complex — and efficient, while keeping the architecture open and easy to
grasp.* The method is strictly measure → audit → trim → verify: no
optimization lands without a before/after number, and no trim lands if
task 47's judge scores regress.

## 2. Goals & Non-Goals [REQUIRED]

**Goals**

- G1. Every turn records stage timings and per-call token usage; the
  question "where do the 30 seconds go" is answerable from metrics_daily
  for any day. This instrumentation is PERMANENT and always-on (not a
  temporary measuring build) and adds no cost: no extra LLM calls,
  free-tier event windows, LangSmith within existing sampling.
- G2. A context inventory exists for every agent/LLM call: what it
  receives, measured median tokens, and a keep/trim/cut verdict — the
  audit artifact lives in this spec's §10.1 at close.
- G3. Router and slot-extractor no longer run serially when both are
  needed.
- G4. Conversational calls run with `thinking_level: LOW` (via task 47's
  BudgetPolicy) and the latency delta is measured and reported.
- G5. Targets met or consciously re-baselined: web time-to-first-token
  P50 ≤ 3 s; conversational turns P50 ≤ 8 s; full itinerary P50 ≤ 15 s.
- G6. No quality regression: judge dimension means (task 47) within
  noise of the pre-trim baseline.

**Non-Goals**

- No model downgrades (flash→flash-lite swaps) in this task — candidates
  are recorded for a follow-up once judge data can arbitrate.
- No response caching / no abandoning the stateless-reconstruction design
  (CLAUDE.md §10) — trims make reconstruction cheaper, not cached.
- No Cloud Run config changes (concurrency, CPU, instances) — billing
  decisions get their own conversation; candidates recorded in §10.1.
- No streaming protocol changes (task 37's SSE machinery stays).
- No prompt-voice changes (task 47 owns wording).

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. Each completed turn emits turn_stage_timings
      {router_ms, extractor_ms, agent_ms, tools_ms, persist_ms, total_ms,
       ttft_ms|null} into analytics_events; metrics_daily rolls up P50/P95
      per stage per day. ttft_ms is populated for streamed web turns.
AC-2. Every gemini_generate call records {call_type, input_tokens,
      output_tokens, thinking_tokens, latency_ms} from response usage
      metadata, emitted as llm_call_usage. (call_type from BudgetPolicy.)
AC-3. A 7-day baseline is captured BEFORE any optimization lands
      (deploy instrumentation alone first), summarized in §10.1: per-stage
      P50/P95 and per-call-type median tokens. Optimizations merge only
      after the baseline exists.
AC-4. Context inventory completed for: RouterAgent, slot_extractor,
      TripAgent, PlannerAgent, ChatAgent, SearchAgent (+ advisor_turn and
      destination_brief if task 45 is live). For each: context elements
      received, median input tokens, verdict keep/trim/cut with one-line
      rationale. Recorded in §10.1.
AC-5. Router classify and slot extraction execute concurrently on turns
      where both run (PLAN/TRIP with text); turn traces show overlapping
      spans; combined pre-agent stage P50 drops accordingly.
AC-6. Conversation history passed to agents is capped by a measured
      policy (e.g. last N messages + rolling summary if the audit
      supports it); the cap value is decided FROM the audit, not guessed,
      and documented in §10.1.
AC-7. Trip JSON sent to agents is pruned to the sections the receiving
      agent uses (e.g. PlannerAgent doesn't receive journal/live_state
      history; exact pruning map decided from the audit).
AC-8. thinking_level LOW active on all conversational call types;
      before/after latency delta per call type reported in §10.1.
AC-9. Post-optimization verification: targets in G5 met per metrics_daily
      over ≥3 days, OR a re-baseline decision is recorded in §10.2 with
      reasons; judge dimension means within ±0.2 of baseline (G6).
AC-10. ruff clean; unit suite green; no behavioral test regressions.
```

## 4. Files & Modules Touched [REQUIRED]

```
backend/src/agentic_traveler/orchestrator/agent.py               [modify — stage timers, parallel router+extractor]
backend/src/agentic_traveler/orchestrator/client_factory.py      [modify — usage metadata capture]
backend/src/agentic_traveler/orchestrator/conversation_manager.py [modify — history cap policy]
backend/src/agentic_traveler/orchestrator/profile_utils.py       [modify — summary tightening per audit]
backend/src/agentic_traveler/orchestrator/sagas/planning.py      [modify — pruned trip view to agents]
backend/src/agentic_traveler/orchestrator/trip_agent.py          [modify — context assembly]
backend/src/agentic_traveler/orchestrator/planner_agent.py       [modify — context assembly]
backend/src/agentic_traveler/analytics/<rollup module>           [modify — stage/usage rollups]
backend/tests/orchestrator/test_orchestrator.py                  [modify]
backend/tests/orchestrator/test_timings.py                       [create]
README.md                                                        [modify]
```

(Exact trim targets in conversation_manager/profile_utils/trip-view depend
on the §7.2 audit — the deviation protocol applies if the audit points at
different files; update this list via §10.2.)

## 5. Constraints [REQUIRED]

- **Measure before optimize** — AC-3 ordering is mandatory. Any PR that
  trims context must cite the audit line that justifies it.
- **Quality floor:** judge means within ±0.2 of baseline (AC-9); a trim
  that buys speed by making replies worse is reverted.
- **Owner's architecture principle (verbatim constraint):** agents stay
  lean and specialized *to a good extent* — do not split agents further
  or add orchestration layers for efficiency's sake; the architecture
  must remain open and easy to grasp.
- **Stateless invariant stays** (CLAUDE.md §10): no cross-request caches;
  trims reduce what is reconstructed, not when.
- **Parallelism stays simple:** the existing thread pool; no asyncio
  rewrite, no new concurrency primitives. Two concurrent flash-lite calls
  per turn maximum.
- **Free-tier discipline:** llm_call_usage and turn_stage_timings live in
  the 7-day analytics_events window; only daily rollups persist.
- **Selection turns stay zero-LLM** (task 43) — instrumentation must not
  add calls to them.
- CLAUDE.md §9 applies (no deploys without approval, no git mutations,
  mocked LLMs in tests).

## 6. Edge Cases [REQUIRED]

| # | Case | Intended behavior | Test |
|---|------|-------------------|------|
| E1 | Usage metadata absent on a response (older mock/stream) | Emit nulls, never crash; rollup skips nulls | unit |
| E2 | Parallel extractor finishes after router says CHAT (extraction unused) | Result discarded; cost accepted (flash-lite, ~300 tokens); counted via llm_call_usage so the waste is visible | unit |
| E3 | One of the parallel calls raises | Other proceeds; failed one degrades exactly as today (router fallback / empty slots) | unit |
| E4 | History cap cuts the message containing the open proposal/slot context | pending_* state lives in SagaState (task 45), NOT history — assert independence | unit |
| E5 | Pruned trip view drops a field an agent prompt references | Pruning map is per-agent allowlist derived from prompt audit; test asserts each agent's prompt placeholders ⊆ its allowlist | unit |
| E6 | Streaming turn: ttft measured but stream aborts mid-way | timings emitted with total up to abort + aborted flag | unit |
| E7 | Clock skew / timer nesting double-counts tool time inside agent time | tools_ms measured inside agent span; rollup documents that agent_ms INCLUDES tools_ms (no subtraction games) | doc + unit |
| E8 | Turn with no extraction (chip slot tap path) | No extractor span; timings shape stable with zeros/nulls | unit |
| E9 | Baseline week includes a deploy/incident outlier day | §10.1 baseline notes exclusions explicitly | manual |

## 7. Implementation Plan [REQUIRED]

### 7.1 Instrumentation (PERMANENT — first-deployed, never removed) → verify: test_timings.py + AC-1/2/3

> Clarification (owner, 2026-06-10): this is not a temporary measuring
> build. The instrumentation is a permanent, always-on part of the app —
> "slice" refers only to delivery order: it ships first and alone so a
> clean baseline accumulates before optimizations land, and it stays on
> forever for ongoing verification and analysis. It is cost-neutral by
> construction: zero additional LLM calls, metric rows ride the existing
> 7-day analytics_events window + daily rollups (free-tier discipline),
> and LangSmith stays within the free plan via the existing sampling
> rules (CLAUDE.md §10). Any observability component that WOULD add cost
> (alerting infra, --no-cpu-throttling, longer raw retention) is
> explicitly out of scope and recorded in §10.1 as a later, separately
> approved implementation.

1. `client_factory.gemini_generate` / `generate_maybe_stream`: wrap with
   timing + usage extraction (`usage_metadata.prompt_token_count`,
   `candidates_token_count`, `thoughts_token_count`); emit
   `llm_call_usage` via the EventEmitter already threaded through.
   **Shared hook with task 51:** task 51's billing accumulator intercepts
   the same point — whichever task lands first builds the ONE wrapper,
   the other adds its consumer. Parallel thread-pool submissions (7.3
   step 1) must use `contextvars.copy_context().run(...)` so task 51's
   contextvar accumulator sees usage from parallel calls.
2. Orchestrator: stage timers around router / extractor / agent / persist;
   ttft captured in the SSE driver (first delta timestamp − request
   start). Emit `turn_stage_timings` on `_save_and_finish`.
3. Rollup: extend metrics_daily with P50/P95 per stage and median tokens
   per call_type. Verify in Supabase with a dev query.
4. **Deploy this slice alone (with approval) and let it run ≥7 days →
   AC-3 baseline.** LangSmith traces corroborate the numbers.

### 7.2 Context audit → verify: AC-4 table in §10.1

For each agent/call: read the prompt-assembly code, list every context
element (profile summary, history, trip JSON, tool results, extras),
join with measured median tokens from 7.1, and rule keep / trim / cut.
Strong candidates to examine (hypotheses, not verdicts):
- conversation history depth per agent (today: unbounded? cap candidates
  8–16 messages);
- full trip JSON vs per-agent section allowlist (E5 mechanism);
- profile summary length vs what each agent's personalization actually
  uses;
- search/weather tool result verbosity re-entering the prompt.

### 7.3 Optimization slice → verify: AC-5–AC-8 + suite

1. Parallel router + extractor via the existing thread pool (E2/E3
   semantics). Skip entirely on selection turns (already zero-LLM).
2. Apply audit verdicts: history cap policy in conversation_manager;
   per-agent trip-view allowlists; profile-summary tightening.
3. thinking_level LOW via BudgetPolicy across conversational call types
   (MEDIUM stays on itinerary).

### 7.4 Verification slice → verify: AC-9

≥3 days of post-optimization metrics_daily vs baseline: stage P50s,
ttft, judge means. Write the before/after table into §10.1; re-baseline
decisions (if targets unmet) into §10.2. README updated (observability
section: new metrics and what they mean).

## 8. Testing Plan [REQUIRED]

- **Unit:** timing emission shape (all paths: sync, streaming, selection,
  no-extraction E8); usage extraction incl. missing metadata (E1);
  parallel execution overlap + failure isolation (mock slow calls, E3);
  history cap (boundaries, E4 independence); trip-view allowlists vs
  prompt placeholders (E5, one test per agent); thinking_level set per
  call type (config inspection on mocked client).
- **Integration:** one live turn writes both metric kinds; rollup query
  returns stages (`_test: true`).
- **Manual:** LangSmith trace of one PLAN turn before/after showing
  overlapping router/extractor spans; dashboard ttft sanity check on dev.
- **Fixtures:** a canonical PLAN-turn timing payload and an llm_call_usage
  payload as documented examples in the test file.

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL — applies]

No new LLM calls; one *wasted* flash-lite extraction accepted on some
CHAT turns (E2) — measured, and bounded by flash-lite pricing. Thinking
steering: LOW for conversational types, expected to cut both latency and
token cost; itinerary keeps MEDIUM (multi-day coherence). Model-downgrade
candidates (composer flash→flash-lite?) recorded in §10.1 for a
judge-arbitrated follow-up.

### 9.3 Observability [CONDITIONAL — applies, is the point]

`turn_stage_timings`, `llm_call_usage` (7-day raw + daily rollup);
LangSmith corroboration; no alerts in this task (latency alerting is a
follow-up once the baseline defines "abnormal").

### 9.4 Rollback Plan [CONDITIONAL — applies, lightweight]

All slices are code-only. Instrumentation slice is additive and safe.
Each optimization (parallelism, history cap, trip pruning, thinking
level) ships behind its own small code path — revert = redeploy prior
revision; no data migration. If judge means drop >0.2, revert the most
recent trim first (they land as separate commits for bisectability).

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed / audit artifacts
*(populated during implementation: AC-3 baseline table, AC-4 context
inventory, AC-8 thinking-level deltas, AC-9 before/after table,
model-downgrade and Cloud Run config candidates.)*

### 10.2 Spec deviations
*(populated during implementation; re-baseline decisions land here.)*

## 11. Definition of Done [REQUIRED]

- [ ] All §3 ACs pass, including the AC-3 baseline-first ordering.
- [ ] §6 edge cases tested or accepted as listed.
- [ ] `ruff check` clean; unit suite green; integration under flag.
- [ ] §10.1 contains: baseline, context inventory, before/after table.
- [ ] Judge means within ±0.2 of baseline (or reverted per §9.4).
- [ ] README updated (new metrics documented).
- [ ] No file outside §4 modified — or §10.2 explains why.
- [ ] No caching introduced; stateless invariant intact.

## 12. Open Questions [OPTIONAL]

- Q1. Rolling conversation summary (instead of a plain history cap) —
  worth a flash-lite call per N turns? Proposed: decide from the audit;
  if history beyond ~12 messages is rarely referenced, a plain cap wins
  and costs nothing.
- Q2. Should ttft become a user-visible SLO on the status line ("thinking…"
  → first words)? Proposed: out of scope; UX polish for stream D's
  follow-ups.
