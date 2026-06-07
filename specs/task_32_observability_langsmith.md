# Task 44 — Observability bootstrap with LangSmith

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §7.0, §10.
> Standalone — ships independently of the saga work.

## 1. Problem Statement

Today, when an agent turn produces a wrong or weird answer, reconstructing
what happened means splicing logs from `RouterAgent`, `TripAgent`,
`PlannerAgent`, `SearchAgent`, `PreferenceLearner`, and the `messages` row,
then mentally re-assembling the prompt the model actually saw (system prompt
+ profile summary + conversation context + preference-updated block + user
message + tool definitions). This is slow, error-prone, and gets dramatically
worse once the saga model lands (multi-saga turns, status events, tool
chains). LangSmith is the cheapest known fix: a hosted tracing platform
that captures every nested LLM/tool call as one inspectable tree, decoupled
from LangChain/LangGraph (we don't adopt those — only the tracing layer).
Doing this before the saga work means every later task ships already
traceable; doing it after means retrofitting `@traceable` across every file
we touched.

## 2. Goals & Non-Goals

### Goals

- A reviewer can open `https://eu.smith.langchain.com`, filter by user (via a
  privacy-preserving hash), find one turn, drill into the trace, and see
  every prompt/response/tool call from that turn — within ~30 seconds.
- Production prompts and replies leave our infrastructure **only** via
  LangSmith's EU endpoint, with explicit user-facing disclosure and a
  hashed-only correlation identifier.
- Tracing is **toggleable at runtime** by a single env var
  (`LANGSMITH_TRACING=false` → full no-op).
- The privacy policy and README accurately reflect that LangSmith is a
  third-party processor.

### Non-Goals

- Adopting LangChain or LangGraph at runtime — not yet (proposal §10.6 keeps
  the saga interface LangGraph-shaped without the dependency).
- Building any custom dashboard. The LangSmith UI is the dashboard.
- Replacing the Cloud Logging / Supabase log pipeline. LangSmith is the
  *LLM-trace* lens; existing logging stays as the *infra* lens.
- Adding LangSmith-based evals or datasets (deferred; basic tracing is the
  scope here).

## 3. Acceptance Criteria

AC-1. With `LANGSMITH_TRACING=true` and `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com`,
  a single web chat turn produces exactly one trace in the `aletheia-dev`
  project that contains nested child runs for:
  `orchestrator.process_request_for_user` →
  `router.classify` → `gemini.generate_content` →
  (one of) `trip_agent.process_request` / `planner_agent.process_request` /
  `chat_agent.process_request` → `gemini.generate_content`, plus any
  `search_agent.search_web` calls if they happened.

AC-2. Every captured run's metadata contains:
  `{user_id_hash: <64-hex chars>, surface: "web" | "telegram"}` — and **no**
  field whose value matches an email, full name, telegram username, phone
  number, or JWT-shaped token.

AC-3. With `LANGSMITH_TRACING=false`, the same turn produces zero outbound
  HTTPS requests to `*.smith.langchain.com`, verified by mocked client OR by
  packet inspection in a dev shell.

AC-4. With a missing or malformed `LANGSMITH_API_KEY`, the app continues to
  respond to chat turns normally; the only effect is a single WARNING log
  line per process startup. Chat latency does not regress measurably (< 50 ms
  delta P95 vs. tracing fully disabled).

AC-5. `README.md` has a "Third-party data processors" section that names
  LangSmith, the EU residency endpoint, the hashed-correlation policy, the
  14-day rolling retention, and the user-facing kill switch
  (`LANGSMITH_TRACING=false`).

AC-6. `task_consent_recording.md` is updated to mention LangSmith in the
  enumerated data processors, and the consent text includes the line:
  *"Your chat messages are processed by us, by Google (Gemini), and by
  LangChain (LangSmith, EU). Do not paste passwords, credit cards, or other
  secrets into chat."*

## 4. Files & Modules Touched

```
backend/requirements.txt                                              [modify]
backend/.env.example                                                  [modify]
backend/src/agentic_traveler/core/observability.py                    [create]
backend/src/agentic_traveler/orchestrator/agent.py                    [modify]
backend/src/agentic_traveler/orchestrator/router_agent.py             [modify]
backend/src/agentic_traveler/orchestrator/trip_agent.py               [modify]
backend/src/agentic_traveler/orchestrator/planner_agent.py            [modify]
backend/src/agentic_traveler/orchestrator/chat_agent.py               [modify]
backend/src/agentic_traveler/orchestrator/search_agent.py             [modify]
backend/src/agentic_traveler/orchestrator/client_factory.py           [modify]
backend/tests/test_observability.py                                   [create]
backend/DEPLOYMENT.md                                                 [modify]
README.md                                                             [modify]
specs/task_32_consent_recording.md                                    [modify]
```

## 5. Constraints

- Must NOT add LangChain or LangGraph as a runtime dependency. `langsmith`
  alone (PyPI latest 0.8.9 at spec time; pin `>=0.4,<1.0`).
- Must NOT send PII to LangSmith. The hashed `user_id_hash` is the only
  correlatable identifier. Email, full name, phone, telegram handle, JWT
  → never.
- Must use the EU residency endpoint in every environment — no US fallback.
- Must NOT add measurable latency when tracing is enabled and reachable;
  must add zero latency when disabled.
- Per `CLAUDE.md` §9: no auto-deploy; no committing API keys; no logging the
  raw `LANGSMITH_API_KEY` or `LANGSMITH_HASH_KEY`.

## 6. Edge Cases

- **LangSmith API unreachable for 60 s** → app continues, traces buffered
  in-memory by the SDK, dropped if overflow. No user-visible error.
- **Empty / missing `LANGSMITH_HASH_KEY`** → `_hash_user_id` falls back to
  the literal string `"unknown"` and logs a one-time WARNING; no traces lost,
  only correlation degraded. **Never** falls back to raw `user_id`.
- **`LANGSMITH_TRACING` env var unset** → defaults to `false` (no traces).
- **Cloud Run cold start with tracing enabled** → +100 ms one-time SDK init;
  no per-request overhead after warm-up. Acceptable.
- **`@traceable` decorator applied to a function that raises** → the trace
  captures the exception type and message but not stack-trace local
  variables (LangSmith default behaviour).
- **User pastes their email or a credit card** → captured in the trace
  inputs. Mitigated by the privacy disclosure in the consent text; no
  programmatic redaction in v1 (defer regex-based PII scrubbing to a
  follow-up).

## 7. Implementation Plan

### Step 1 — Dependency & env

Add to `backend/requirements.txt`:

```
langsmith>=0.4,<1.0
```

Run `pip install -r requirements.txt` → verify
`backend/.venv/Lib/site-packages/langsmith/__init__.py` reports a version
in the `0.4 ≤ v < 1.0` range. **Verify:** `pip show langsmith | grep Version`.

Add to `backend/.env.example` (the user has already added these to `.env`):

```
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_API_KEY=<from smith.langchain.com>
LANGSMITH_PROJECT=aletheia-dev
LANGSMITH_HASH_KEY=<32+ char random secret>
# Optional in prod once >100 active users/day:
# LANGSMITH_SAMPLE_RATE=0.1
```

### Step 2 — Observability module

Create `backend/src/agentic_traveler/core/observability.py`:

```python
"""LangSmith bootstrap, privacy-preserving identifier hashing, kill switch.

This module is the SINGLE place where we touch LangSmith APIs other than the
`@traceable` decorator imported from `langsmith` directly. Keeps the import
surface tiny and the kill switch local.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_TRACING_ENABLED = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
_HASH_KEY = os.getenv("LANGSMITH_HASH_KEY", "")
_warned_no_hash_key = False


def is_tracing_enabled() -> bool:
    return _TRACING_ENABLED


def hash_user_id(user_id: str | None) -> str:
    """
    HMAC-SHA256 of the internal users.id UUID under LANGSMITH_HASH_KEY.
    Reversible only by us (server-side secret). Safe to send to LangSmith.
    """
    if not user_id:
        return "anonymous"
    if not _HASH_KEY:
        # One-time WARN; subsequent calls silent (rate-limit via module flag).
        global _warned_no_hash_key
        if not _warned_no_hash_key:
            logger.warning(
                "LANGSMITH_HASH_KEY not set — user correlation in LangSmith "
                "degraded to 'unknown'. Tracing still active."
            )
            _warned_no_hash_key = True
        return "unknown"
    return hmac.new(
        _HASH_KEY.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


F = TypeVar("F", bound=Callable[..., Any])

# Re-export `@traceable` from langsmith so callers import from observability,
# not langsmith directly. This keeps `langsmith` swappable/removable in one
# place. When LANGSMITH_TRACING is false the decorator is a no-op pass-through.
if _TRACING_ENABLED:
    try:
        from langsmith import traceable as _traceable  # type: ignore[import-not-found]

        traceable = _traceable
        logger.info("LangSmith tracing enabled.")
    except Exception:
        logger.warning("langsmith import failed; tracing disabled.", exc_info=True)

        def traceable(*dargs, **dkwargs):  # type: ignore[no-redef]
            def _decorator(fn: F) -> F:
                return fn
            return _decorator
else:
    def traceable(*dargs, **dkwargs):  # type: ignore[no-redef]
        def _decorator(fn: F) -> F:
            return fn
        return _decorator


def attach_run_metadata(**kw: Any) -> None:
    """
    Attach NON-PII metadata to the current run, if tracing is on.
    Safe to call when tracing is off (no-op).
    """
    if not _TRACING_ENABLED:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree  # type: ignore[import-not-found]
        rt = get_current_run_tree()
        if rt is not None:
            rt.metadata.update(kw)
    except Exception:
        pass  # never let observability errors break the request
```

**Verify:** import the module from a Python REPL with `LANGSMITH_TRACING=false`;
`traceable` should be a no-op (decorating a function returns the same callable).
With `=true`, it should return the real LangSmith decorator.

### Step 3 — Wrap the Gemini call site

Modify `backend/src/agentic_traveler/orchestrator/client_factory.py` to expose
a single traced wrapper:

```python
from agentic_traveler.core.observability import traceable

@traceable(name="gemini.generate_content")
def gemini_generate(client, *, model: str, contents, config):
    """Single traced wrapper around `client.models.generate_content` — every
    Gemini call goes through here so prompts appear in LangSmith traces."""
    return client.models.generate_content(model=model, contents=contents, config=config)
```

Replace every direct `self._client.models.generate_content(...)` call site in
`router_agent.py`, `trip_agent.py`, `planner_agent.py`, `chat_agent.py`,
`search_agent.py` with `gemini_generate(self._client, model=..., contents=..., config=...)`.

**Verify:** existing unit tests still pass (`pytest backend/tests -v`).

### Step 4 — Decorate orchestrator-level entry points

```python
# agent.py
from agentic_traveler.core.observability import traceable, attach_run_metadata, hash_user_id

class OrchestratorAgent:
    @traceable(name="orchestrator.process_request_for_user")
    def process_request_for_user(self, user_id, message_text, status_callback=None):
        attach_run_metadata(user_id_hash=hash_user_id(user_id), surface="web")
        ...

    @traceable(name="orchestrator.process_request")
    def process_request(self, telegram_user_id, message_text, status_callback=None):
        attach_run_metadata(
            user_id_hash=hash_user_id(telegram_user_id), surface="telegram"
        )
        ...
```

Add `@traceable(name="router.classify")` to `RouterAgent.classify`,
`@traceable(name="<agent>.process_request")` to each of TripAgent /
PlannerAgent / ChatAgent, and `@traceable(name="search_agent.search_web")`
to the SearchAgent's outer call (not the closure passed to AFC).

**Verify:** with `LANGSMITH_TRACING=true` and valid keys, run one local
chat turn against `/chat` and check that one trace appears in the LangSmith
UI with the expected nested children.

### Step 5 — Privacy doc updates

Modify `README.md`. Add section near the top of the existing infrastructure
overview:

```markdown
## Third-party data processors

| Processor | Region | What we send | Retention |
|---|---|---|---|
| Google Vertex AI / Gemini | configurable, EU-pinnable | chat prompts + replies | per Google Gemini terms |
| Supabase | eu-central-1 | user rows, trips, messages | until user deletes account |
| Resend | EU | transactional emails | per Resend retention |
| Telegram | global | message text on the Telegram channel | per Telegram terms |
| LangSmith (LangChain Inc.) | EU (Frankfurt) — `eu.api.smith.langchain.com` | chat prompts + replies + tool calls, tagged with an HMAC-hashed user id only (no email, name, phone, telegram handle, or JWT) | 14-day rolling (free tier) |

Kill switch for LangSmith: set `LANGSMITH_TRACING=false` in the runtime env
and redeploy; the app continues to function with zero outbound traffic to
LangSmith.
```

Modify `specs/task_consent_recording.md`: add LangSmith to the processors
list, and add the user-facing line:

> Your chat messages are processed by us, by Google (Gemini), and by
> LangChain (LangSmith — EU). This allows us to provide and improve our services. Do not paste passwords, credit cards, or
> other secrets into chat.

**Verify:** README renders correctly; the consent text reads naturally.

Update Privacy Policy in frontend (the published one — not just the consent task
   spec) to add the data processors as in the message above.

### Step 6 — Tests

`backend/tests/test_observability.py`:

- `test_hash_is_deterministic`: same input → same output.
- `test_hash_differs_across_users`: two different uuids → two different digests.
- `test_hash_falls_back_when_no_key`: monkeypatch `LANGSMITH_HASH_KEY=""` →
  returns `"unknown"`, logs WARN once.
- `test_traceable_is_noop_when_disabled`: with `LANGSMITH_TRACING=false`, a
  decorated function returns the bare function (identity check on `__wrapped__`
  attribute or call-through behavior).
- `test_attach_run_metadata_safe_when_disabled`: call with `=false` raises
  nothing.
- `test_no_pii_keys_in_metadata` (unit): construct a metadata dict with the
  helper, assert keys ∩ {"email","name","phone","telegram_handle","jwt"} is empty.

`backend/tests/test_router_agent.py` etc. — verify existing tests still pass
after the `gemini_generate` wrapping (the integration is mock-friendly).

## 8. Testing Plan

- **Unit:** `test_observability.py` per Step 6.
- **Integration:** with `LANGSMITH_TRACING=true` and a real key, run
  `pytest backend/tests -m integration -k chat` (the existing /chat test).
  Manually verify in LangSmith UI that the expected trace appears within 30
  seconds with the right shape.
- **Manual kill-switch check:** set `LANGSMITH_TRACING=false`,
  curl `/chat`, check Cloud Run egress logs show no traffic to
  `smith.langchain.com`.
- **Manual PII check:** open one captured run in the LangSmith UI, expand
  metadata, confirm only `user_id_hash` and `surface` appear (no other
  identifiers).

## 9. Conditional Sections

### 9.2 LLM Considerations

- No new prompts or models — purely observability.
- No new prompt-injection surface; LangSmith captures inputs verbatim
  (intentional, for debuggability).
- Output handling unchanged.

### 9.3 Observability

This *is* the observability task. Verifying the verification is meta — see
the integration test in §8.

### 9.4 Rollback Plan

- Revert by setting `LANGSMITH_TRACING=false` in Cloud Run env and
  redeploying the prior revision. No data migration required.
- Optional cleanup: delete the LangSmith project via the LangSmith UI
  Settings → Projects.

## 10. Findings & Follow-ups

(Populated during implementation.)

## 11. Definition of Done

- [ ] ACs 1–6 all pass.
- [ ] Edge cases in §6 either covered by tests or accepted with a §10.2 note. Source and edge cases considered in specs/proposal_trip_model_and_planning_saga.md.
- [ ] `ruff check` clean.
- [ ] `pytest` unit suite passes; integration suite passes when run with
  real LangSmith credentials.
- [ ] `README.md` updated with the third-party processors section.
- [ ] `task_consent_recording.md` updated with LangSmith disclosure.
- [ ] `DEPLOYMENT.md` updated with the kill-switch env var.
- [ ] No `LANGSMITH_API_KEY` or `LANGSMITH_HASH_KEY` value appears in any
  log line or committed file.
- [ ] No secrets in `.env.example` — only placeholder strings.

## Manual operations (user, post-implementation)

1. Create the LangSmith projects in the UI: `aletheia-dev` and
   `aletheia-prod`. Note the API key (same key works across projects).
2. Generate `LANGSMITH_HASH_KEY` (any 32+ char random string,
   e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
   Add to `backend/.env` and to the Cloud Run secret env.
3. Set the same 4 env vars (`LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`,
   `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=aletheia-prod`,
   `LANGSMITH_HASH_KEY`) in the Cloud Run revision env.
4. After deploy: open `https://eu.smith.langchain.com`, switch project to
   `aletheia-dev`, send a test message via the web chat, verify the trace
   appears within 30 seconds.

