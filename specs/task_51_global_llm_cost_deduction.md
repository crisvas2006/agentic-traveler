# Task 51 — Global LLM Cost Deduction

> Alignment notes (2026-06-10, roadmap pass):
> - **Shared interception with task 48.** Task 48's `llm_call_usage`
>   instrumentation hooks the same `gemini_generate` / streaming wrapper
>   lines. Whichever task lands FIRST builds the single interception
>   point; the second consumes it (one hook, two consumers: this task's
>   billing accumulator + task 48's per-call metric). Do not create two
>   parallel wrappers.
> - **Thread-pool propagation hazard.** LLM calls run on worker threads,
>   and task 48 adds parallel router+extractor submissions. Raw
>   `ThreadPoolExecutor.submit` does NOT propagate contextvars — every
>   submission that may generate billable LLM calls must be wrapped with
>   `contextvars.copy_context().run(...)` (note: a context COPY means
>   appends inside the thread mutate the SAME list object, which is the
>   desired behavior — assert this in a test). Starlette's
>   `run_in_threadpool` already copies context; manual pool usage does not.
> - **Exclusions from billing.** Task 47's offline judge call and any
>   other platform-overhead calls (not user-serving) must NOT enter the
>   user's deduction. Mechanism: the judge runs outside the request
>   context (background, fresh context) — assert with a test that a judge
>   call never lands in `current_turn_usage`. Task 45's brief capture and
>   composer ARE user-serving and bill normally.

## 1. Problem Statement [REQUIRED]

Currently, the `Agentic Traveler` orchestrator manually gathers token usage records from specific agent calls (e.g., `RouterAgent` and the main `PlanningSaga` or `TripAgent`) to deduct user credits at the end of a turn. However, if a specialized tool or nested saga (such as the newly added `booking_parser.py`) directly invokes the Gemini API via the SDK, its token usage is lost. This causes a strategic gap in the economy system: the user is not accurately charged for all LLM operations performed on their behalf. Fixing this decouples the billing logic from agent return signatures and guarantees that any LLM interaction securely tracks its cost, protecting the platform's free-tier viability.

## 2. Goals & Non-Goals [REQUIRED]

**Goals:**
- Every LLM call triggered during a request lifecycle, regardless of which tool or agent makes it, contributes to the user's total token consumption for the turn.
- The `agent.py` orchestrator successfully reads the global context and bills the aggregated cost at the end of the operation.

**Non-Goals:**
- We are *not* changing the logic for how much a credit costs or the pricing formulas in `credit_manager.py`.
- We are *not* persisting raw API response JSON logs into Supabase—only updating the aggregated token billing and existing `turn_completed` metric.

## 3. Acceptance Criteria [REQUIRED]

1. AC-1. A tool calling `gemini_generate` directly without returning its usage metadata to the orchestrator still results in the tokens being added to the final deduction payload.
2. AC-2. If an LLM call fails and an exception is raised, or if the turn explicitly falls back to an error response, credits are *not* deducted (preserving existing safeguard logic).
3. AC-3. The `BookingInputSaga` extraction costs (from `booking_parser.py`) are successfully deducted from the user's balance.

## 4. Files & Modules Touched [REQUIRED]

```text
backend/src/agentic_traveler/orchestrator/client_factory.py     [modify]
backend/src/agentic_traveler/orchestrator/agent.py              [modify]
backend/tests/orchestrator/test_client_factory.py               [create]
```

## 5. Constraints [REQUIRED]

- Must use `contextvars` to avoid passing a `usage_list` parameter deep into every function signature in the codebase.
- The context variable must be safely isolated per request to prevent cross-contamination between concurrent requests (which FastAPI naturally supports via contextvars).
- Must adhere to the "Never log secrets, full API keys, or PII" constraint in `CLAUDE.md`.

## 6. Edge Cases [REQUIRED]

- **Concurrent Async Requests:** Since we are using standard `contextvars`, concurrent FastAPI requests will naturally isolate the token lists.
- **Empty or Failed Calls:** If an LLM call fails without returning usage metadata, the tracking list gracefully ignores it.
- **Streaming Calls:** The streaming wrapper `gemini_generate_stream` yields usage metadata in the last chunk. This must also be appended to the global context.

## 7. Implementation Plan [REQUIRED]

1. **[Step 1] Update Client Factory** → verify: Context variable accumulates usage
   - Define a new `ContextVar` named `current_turn_usage` in `client_factory.py`.
   - Update `gemini_generate` and `gemini_generate_stream` to intercept the returned `usage_metadata`, convert it to a standard dictionary using `usage_tracker.log_and_accumulate` (or a similar standardized format), and append it to the active `current_turn_usage` list.

2. **[Step 2] Update Orchestrator** → verify: `agent.py` pulls from context instead of `agent_result`
   - In `agent.py`'s `_process_user_doc`, initialize the `current_turn_usage` variable at the start of the turn: `current_turn_usage.set([])`.
   - Remove the manual `agent_result.get("_raw_response")` scraping logic.
   - During `_save_and_finish`, pass the aggregated `current_turn_usage.get()` list to the credit manager.

## 8. Testing Plan [REQUIRED]

- **Unit tests:** Create `test_client_factory.py` to test that mocked `gemini_generate` calls append to the `current_turn_usage` context variable.
- **Integration tests:** Run existing integration tests to ensure that the total token count is correct after a standard planner invocation.
- **Manual checks:** Perform a Booking Paste operation in the web UI, checking the backend logs to confirm that `deduct_credits` includes the tokens spent by `booking_parser.py`.

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL]
- **Tracking:** No new LLM models or prompts are introduced, but the *tracking* of all existing prompts is centralized.

### 9.3 Observability [CONDITIONAL]
- The standard `turn_completed` metric will now accurately reflect the true total cost of the turn, automatically accounting for hidden tool calls.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)

- **Per-agent attribution in usage logs is reduced.** The funnel logs
  `model + tokens` per call but cannot know which agent called it; the old
  per-agent `📊 LLM usage | agent=…` lines for router/trip/planner/search
  are gone (LangSmith traces retain full attribution). Task 48's
  `call_type` (from BudgetPolicy) restores structured attribution
  properly. Priority: low — superseded by task 48.
- `RouterAgent.classify` still accepts a now-vestigial `token_records`
  parameter (it never used it). Remove in a future router change.
  Priority: low.
- `SagaResult._raw_response` / `_search_responses` plumbing is now
  write-only (no consumer after de-scraping). Candidate for removal once
  nothing else grows a use; left untouched per "do not remove fields
  without approval". Priority: low.
- The country-intel background fetch stays correctly un-captured because
  `loop.run_in_executor` does not propagate contextvars. If it ever moves
  to `asyncio.to_thread` (which copies context), wrap it in
  `suppress_usage_capture()` — it bills itself. Priority: note only.
- Grounding is now billed wherever it occurs (previously only the
  SearchAgent path built grounding records) — strictly more accurate.

### 10.2 Spec deviations

- **§4 file list extended (+2 files, justified):**
  - `backend/src/agentic_traveler/orchestrator/conversation_manager.py` —
    compaction (`_summarise`) runs INSIDE the request context with
    `user_id="system"`; without explicit `suppress_usage_capture()` the
    funnel would have started billing users for compaction (a regression
    the original §4 couldn't foresee).
  - `backend/src/agentic_traveler/tools/booking_parser.py` — it called
    `client.models.generate_content` directly, bypassing the wrapper
    entirely (this is the §12 open question answered "yes"); routed
    through `gemini_generate`, which also restores its LangSmith tracing.
- **§7 step 2 nuance:** `_save_and_finish` keeps its `token_records`
  parameter rather than reading the contextvar itself — call sites pass
  the captured list (or `[]` on error turns), preserving AC-2's
  "no billing on error" semantics with zero churn at the call sites.
  `begin_usage_capture()` (turn start) returns the same list object the
  funnel appends to, so the existing variable name and flow survive.
- Tests were placed in `backend/tests/orchestrator/test_client_factory.py`
  (per §4) plus two turn-level tests appended to the existing
  `backend/tests/orchestrator/test_orchestrator.py` (AC-1/AC-2 at
  orchestrator level).
- `README.md` updated per CLAUDE.md §6 (not listed in §4).

## 11. Definition of Done [REQUIRED]
- [x] All acceptance criteria in §3 pass — AC-1: orchestrator test
      `test_turn_bills_usage_captured_by_nested_calls`; AC-2:
      `test_error_turn_is_not_billed_even_with_captured_usage`; AC-3:
      `test_booking_parser_usage_is_captured` (unit) — manual web
      booking-paste check still owed (requires running stack).
- [x] All §6 edge cases covered: concurrency/threading (copied-context
      and plain-thread tests), failed calls, missing usage metadata,
      streaming last-chunk capture, reused-thread reset.
- [x] `ruff check` clean.
- [x] `pytest` unit suite passes (333 passed, integration deselected).
- [x] No file outside §4 modified — except the two §10.2-justified
      additions and README.

## 12. Open Questions [OPTIONAL]
- ~~Are there any legacy agents that bypass `client_factory.py`?~~
  RESOLVED during implementation: `booking_parser.py` was the one direct
  caller (fixed — §10.2). `profile_agent.py`, `router_agent.py`,
  `search_agent.py`, `country_intel_fetcher.py`, `slot_extractor.py`,
  `conversation_manager.py`, and `interfaces/routers/tally.py` all
  already use `gemini_generate` / `generate_maybe_stream`.
