# Task 54 — Orchestrator reliability & cost fixes (tracing, client reuse, TRIP latency/concision)

## 1. Problem Statement [REQUIRED]

A live web `/chat/send` trace (a TRIP request: *"how is the weather there next
week? and what are some events…"*) surfaced several issues around an otherwise
healthy request path. First, LangSmith silently drops the inputs of every
tool-using agent: `gemini_generate()` is `@traceable`, and LangSmith cannot
serialize a `GenerateContentConfig` whose `tools=[...]` are raw Python
functions (`PydanticSerializationError: Unable to serialize unknown type:
<class 'function'>`), so the prompt + config never reach the trace for
TripAgent / PlannerAgent / SearchAgent — exactly the heavy agents task_32
(LangSmith observability) was meant to illuminate. Second, the run initializes
the Vertex AI client twice because `RouterAgent` constructs `ProfileAgent()`
without forwarding the shared client, violating the single-client invariant
from task_16. Third, the TripAgent turn took ~14.5 s and produced a ~3000-char,
ornate reply with no concision control and a `thinking_budget` (512) larger than
this class of request needs — hurting latency, cost, and UX. Doing these now is
cheap, low-risk, and directly improves observability fidelity and per-turn cost
ahead of scaling to more users.

Background: the RouterAgent was refactored earlier this session from Automatic
Function Calling (AFC) + forced JSON to pure structured-output classification,
because combining AFC with `response_mime_type="application/json"` on flash-lite
caused unstable tool-call loops. This task finishes that hardening (explicitly
disabling AFC on the router) and addresses the orchestrator-wide issues above.

## 2. Goals & Non-Goals [REQUIRED]

**Goals**
- LangSmith traces for tool-using agents retain their inputs (prompt + a
  serializable config summary including tool names).
- The orchestrator initializes exactly one `genai.Client` per process.
- TRIP replies respect a reply-length budget, defaulting to concise when the
  user has no stored preference.
- TRIP turns spend less time/tokens on reasoning that the case doesn't require.
- The router never enables AFC (single, loop-free model turn guaranteed).

**Non-Goals**
- Router context-size trimming (issue #3 in the log analysis) — deferred; needs
  more thought (the bulk is verbose agent replies bleeding into the next turn).
- Grounding "verify with official sources" disclaimer (issue #5) — not in scope
  for this task (recorded in §10.1).
- Streaming the TripAgent response over SSE (issue #4 proper) — separate, larger
  change; only the `thinking_budget` portion is done here.
- Any change to credit pricing, routing logic, or the structured-output schema.

## 3. Acceptance Criteria [REQUIRED]

```
AC-1. A traced gemini_generate() call whose config carries function tools
      produces a JSON-serializable inputs payload: the `client` arg is absent,
      `config` is a dict, and `config.tools` is a list of tool NAME strings.
      (No PydanticSerializationError for that call's inputs.)
AC-2. Constructing OrchestratorAgent results in a single get_client()/Vertex
      client initialization; RouterAgent forwards its client to ProfileAgent.
AC-3. TripAgent.process_request injects a <response_style> directive whose text
      is chosen from reply_length_preference; an unset/unknown preference yields
      the "default" (concise) directive, "terse"/"verbose" yield their variants.
AC-4. The router's GenerateContentConfig sets
      automatic_function_calling.disable = True.
AC-5. TripAgent's thinking_budget is 256 (down from 512).
AC-6. ruff clean; full unit suite passes; router integration suite still green.
```

## 4. Files & Modules Touched [REQUIRED]

```
backend/src/agentic_traveler/orchestrator/client_factory.py   [modify]  # trace reducer
backend/src/agentic_traveler/orchestrator/router_agent.py     [modify]  # share client, disable AFC
backend/src/agentic_traveler/orchestrator/trip_agent.py       [modify]  # thinking_budget, concision
backend/tests/orchestrator/test_trace_inputs.py               [create]  # unit tests for the new helpers
specs/task_54_orchestrator_reliability_fixes.md               [create]  # this spec
```

No README change: these are internal behavior/observability fixes with no
user-facing setup or feature change. (The earlier router structured-output
refactor already updated README §2.)

## 5. Constraints [REQUIRED]

- MUST NOT change the structured-output schema or the `classify()` return shape.
- MUST NOT alter routing decisions, credit math, or tool behavior.
- MUST keep observability failures non-fatal — a trace reducer error must never
  break a request (it runs inside LangSmith's input processing, which is itself
  wrapped; the reducer uses only safe `getattr` access).
- MUST NOT call Gemini/Telegram from unit tests (CLAUDE.md §9); real-API checks
  stay under `-m integration`.
- TRIP reply hard ceiling remains 3500 chars (existing system-prompt rule);
  concision directives tighten, never raise, that ceiling.
- No secrets/PII added to logs or traces (the reducer drops the client and emits
  only model, prompt, and config metadata — no credentials).

## 6. Edge Cases [REQUIRED]

- **Config without tools** (router, chat, compaction): `_summarize_config`
  simply omits the `tools` key. Covered by smoke check.
- **Config is None**: `_summarize_config` returns None; `_trace_inputs` leaves
  it. Safe.
- **Tool is a non-function** (e.g. a `types.Tool` grounding object): reducer
  falls back to `type(t).__name__`. Safe.
- **user_doc missing user_profile/profile_data**: `_length_guidance` uses
  `(… or {})` chains and defaults to "default". Safe.
- **reply_length_preference set to an unknown string**: `.get(pref, default)`
  falls back to concise. Safe.
- **Tracing disabled** (`LANGSMITH_TRACING=false`): `traceable` is a no-op that
  ignores `process_inputs`; reducer is never invoked. Safe.
- **Two requests for the same user concurrently**: unaffected — all changes are
  per-call/stateless.

## 7. Implementation Plan [REQUIRED]

1. **Trace reducer** in `client_factory.py` → verify: smoke test builds a config
   with a function tool and asserts `json.dumps(_trace_inputs(...))` succeeds and
   `config.tools == ["check_weather"]`.

   Added helpers (verbatim intent):
   - `_summarize_config(config)` keeps `max_output_tokens`, `response_mime_type`,
     `temperature`, `thinking_config.thinking_budget`, and maps `tools` →
     `[t.__name__ or type(t).__name__]`.
   - `_trace_inputs(inputs)` drops `client`, summarizes `config`, keeps `model`
     and `contents`.
   - Decorator becomes
     `@traceable(name="gemini.generate_content", process_inputs=_trace_inputs)`.

2. **Share client** in `router_agent.py` → verify: `RouterAgent(client=c)._profile_agent._client is c`.
   `self._profile_agent = ProfileAgent(client=self._client)`.

3. **Disable router AFC** in `router_agent.py` → verify: integration logs no
   longer show "AFC is enabled" for the router call; config has
   `automatic_function_calling=AutomaticFunctionCallingConfig(disable=True)`.

4. **TripAgent concision** in `trip_agent.py` → verify: `_length_guidance` unit
   logic returns the right directive per preference; injected as a
   `<response_style>` block in `user_content`.

   ```
   _LENGTH_GUIDANCE = {
     "terse":   "Reply length: VERY BRIEF. … (~600 characters). …",
     "default": "Reply length: CONCISE. … Aim for under ~1500 characters.",
     "verbose": "Reply length: … fuller … within the 3500-character ceiling.",
   }
   # pref = profile_data.reply_length_preference or "default"
   ```

5. **Lower thinking budget** in `trip_agent.py` → verify: `thinking_budget=256`.

6. **Gates** → verify: `ruff check` clean; `pytest backend/tests` green;
   `pytest -m integration -k test_router_agent` green.

## 8. Testing Plan [REQUIRED]

- **Unit:** full existing suite must stay green, plus a new file
  `backend/tests/orchestrator/test_trace_inputs.py` (9 tests) covering the new
  pure helpers — `_summarize_config` / `_trace_inputs` (function-tool config is
  JSON-serializable, `tools` reduced to names, `client` dropped, None/no-tools/
  non-function-tool edge cases) and `_length_guidance` (explicit prefs,
  case-insensitivity, concise default on unset/unknown/missing profile). These
  are pure functions — no Gemini/network. Suite total: 138 passed.
- **Integration (`-m integration`):** router suite (`test_router_agent`) must
  remain green — confirms the shared-client and AFC-disable changes don't alter
  classification. A manual live TRIP turn confirms (a) no PydanticSerialization
  error in logs, (b) one Vertex client init, (c) a visibly more concise reply.
- **Smoke checks (run during implementation, not committed):**
  - Trace: `json.dumps(_trace_inputs({client, model, contents, config-with-tool}))`
    succeeds; `config.tools == ["check_weather"]`, `client` key absent.
  - Concision: `_length_guidance({})` → contains "CONCISE";
    `_length_guidance({"user_profile":{"profile_data":{"reply_length_preference":"terse"}}})`
    → contains "VERY BRIEF".

## 9. Conditional Sections

### 9.2 LLM Considerations [CONDITIONAL]
- **Model tier:** unchanged — router `flash-lite`, TripAgent `flash`.
- **Token budget:** TripAgent reasoning reduced (thinking_budget 512→256) and
  output tightened via `<response_style>`; both reduce per-turn output tokens
  and latency. Router unchanged this task.
- **Prompt-injection surface:** `<response_style>` text is server-controlled
  (constant map), not user free-text — no new injection surface. The
  `reply_length_preference` value is used only as a dict key with a safe default,
  never interpolated into the prompt.
- **Output handling:** unchanged; TripAgent output already rendered through the
  existing Telegram/web formatting path.
- **Versioning:** prompts versioned via git; no separate registry.

### 9.3 Observability [CONDITIONAL]
- **Logs:** no new log lines; the AFC-disable removes a misleading
  "AFC is enabled with max remote calls: 10" line for the router.
- **Traces:** tool-using agents now retain inputs (prompt + config summary with
  tool names) instead of dropping them — the core win of this task.
- **Alerts:** none changed.

## 10. Findings & Follow-ups [CLOSING]

### 10.1 Improvements observed (not done in this task)
- **Router input tokens ~2954/turn** (`router_agent.py` / `conversation_manager.py`)
  — the slim router context still includes full ~3000-char agent replies;
  truncating each history entry (~300 chars) for classification and passing a
  compact prefs list would cut routing cost materially. Priority: **medium**.
  Likely a small follow-up, not a full spec.
- **Grounding disclaimer missing** (`trip_agent.py` / `search_agent.py`) — TRIP
  replies state dated, grounded facts with no "verify with official sources"
  caveat, contrary to CLAUDE.md §7.1. Priority: **medium**. Small prompt change.
- **SSE streaming for TRIP** (`interfaces/routers` + frontend) — the 8.4 s final
  generation dominates perceived latency; streaming would cut it dramatically.
  Priority: **medium**. Warrants its own spec (touches route + frontend + the
  Telegram message-edit path).
- **Stale MockGenAIClient JSON** (`client_factory.py`) — emits the old
  `preference_raw` key; harmless (router ignores it, still returns CHAT) but
  worth refreshing to the new schema fields next time the mock is touched.
  Priority: **low**.

### 10.2 Spec deviations
- §4/§8: added `backend/tests/orchestrator/test_trace_inputs.py`. The first draft
  relied on offline smoke checks only; per the project rule "tests exist for new
  behavior (unit at minimum)" (and a /review WARN), the smoke checks were
  promoted to committed unit tests for the pure helpers. No production code
  changed as a result.
- Otherwise implemented exactly the subset the user approved (tracing, client
  reuse, TRIP thinking_budget + concision, router AFC-disable); router context
  trim and grounding disclaimer explicitly excluded per the user and recorded in
  §10.1.

## 11. Definition of Done [REQUIRED]
- [x] All §3 acceptance criteria pass (AC-1..AC-5 by smoke/inspection; AC-6 by gates).
- [x] §6 edge cases handled in code (safe getattr/defaults) — no deferrals.
- [x] `ruff check` clean (backend changes).
- [x] `pytest` unit suite passes (138 passed, incl. 9 new); router integration suite green.
- [ ] `npm run build` — N/A (no frontend changes).
- [ ] Mobile + desktop — N/A (no UI changes).
- [x] No file outside §4 modified.
- [x] README — no update needed (internal fixes; router refactor already documented).
- [x] §10.1 follow-ups captured.
- [x] No secrets/PII added to logs or traces.
- [ ] RLS — N/A (no new tables).
