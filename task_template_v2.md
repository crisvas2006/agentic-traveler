# Task Spec Template (v2)

> Use this template for any task that meets the threshold in `CLAUDE.md` §5
> (multi-module, >~2h, or non-trivial mechanism). File the spec at
> `specs/task_<feature_name>.md`. This file supersedes `task_template.md`.

---

## Golden Rules

1. **Self-contained.** The spec must be executable from this file alone — no
   cross-references to chat logs, planning docs, or external artifacts.
   If something was designed during planning (prompts, schemas, configs, tool
   definitions), **embed it verbatim** here, not by reference.

2. **Deviation protocol.** If, during implementation, you discover that the
   spec is wrong, ambiguous, or contradicted by the codebase: **stop.**
   Surface the discrepancy, propose a spec amendment in §10.2, and wait for
   approval — do not silently re-interpret. The spec is a hypothesis; the
   codebase is truth.

3. **Surgical with eyes open.** Touch only what the spec requires, but record
   improvement and refactor opportunities you observe in §10.1 — do not
   silently discard them, and do not silently act on them.

---

## Section legend

- **[REQUIRED]** — must be filled for every spec.
- **[CONDITIONAL]** — fill only when the task touches that area.
- **[CLOSING]** — populated during and after implementation, not at planning time.

---

## 1. Problem Statement [REQUIRED]

One paragraph minimum (≥3 sentences). Cover:

- The user pain or technical gap that motivates this task.
- The current behavior and where it falls short.
- The strategic "why now" — what's unblocked, derisked, or enabled by doing it.

Avoid one-liners ("Add support for X"). A reviewer should understand from
this paragraph alone why the task exists, without reading anything else.

## 2. Goals & Non-Goals [REQUIRED]

- **Goals:** measurable outcomes — capabilities delivered, KPIs moved, bugs
  closed. State them in behavioral terms ("user can do X"), not implementation
  terms ("we add column Y").
- **Non-Goals:** explicitly out of scope. State the things a well-meaning
  agent might *assume* but shouldn't do. This is the safety rail against scope creep.

## 3. Acceptance Criteria [REQUIRED]

Numbered, independently testable list. Each item must be verifiable by a test
or a concrete manual check.

Example:

```
AC-1. POST /tally-webhook with a valid bearer token and a valid `idToken`
      query param merges the submission into the existing user row
      (no duplicate `users` row created).
AC-2. POST /tally-webhook with an expired `idToken` returns HTTP 410 and
      leaves `public.users` unchanged.
AC-3. After a successful Traveler DNA build, the user receives exactly one
      acknowledgment message on their primary channel (web or Telegram).
```

If you can't write a test or concrete check for an AC, it isn't a real AC —
rewrite it. Each AC maps to an entry in §8.

## 4. Files & Modules Touched [REQUIRED]

List the exact files you expect to create or modify, with absolute repo paths
and a `[create]` / `[modify]` / `[delete]` tag.

This is the surgical-changes anchor: at review, any file outside this list
is either a missed prediction (note it in §10.2) or scope creep (stop and
ask). Update this list when the deviation protocol triggers — don't quietly
edit extras.

Example:

```
backend/src/agentic_traveler/interfaces/routers/tally.py        [modify]
backend/src/agentic_traveler/tools/link_token_repo.py           [modify]
backend/tests/test_tally_webhook.py                             [create]
supabase/schema_public.sql                                      [modify]
```

## 5. Constraints [REQUIRED]

What this change must **NOT** do. Equally important as goals.

Cover the relevant subset of:

- Hard "must not" rules (don't break public API X, don't change response shape Y, don't rename a Supabase column).
- Performance ceilings (e.g., agent latency budget, Cloud Run cold-start impact).
- Backwards compatibility (live users, in-flight Telegram webhooks, existing rows).
- Security boundaries (Supabase RLS, secret handling, no PII in logs — per `CLAUDE.md` §8).
- Project-wide rules from `CLAUDE.md` §9 that apply to this task (deploy gates, no auto-commit, no Gemini calls in tests, etc.).

## 6. Edge Cases [REQUIRED]

Enumerate the boundary conditions, partial failures, and adversarial inputs
this change must handle — or explicitly accept as out of scope (and say so).

Categories to walk through:

- **Inputs:** empty, null, oversized, non-UTF-8, whitespace-only, very long.
- **Concurrency:** two requests for the same user, retried Telegram webhooks, duplicate Tally submissions.
- **External failures:** Supabase 5xx, Gemini timeout, Telegram API unreachable, partial network failure mid-write.
- **Partial writes:** what if the user row commits but the credit row insert fails?
- **Auth / RLS:** request with missing JWT, JWT for a different user, RLS-denied select, service-key bypass attempts.
- **Malformed external payloads:** Telegram update with no `message`, Tally submission with missing fields, LLM JSON that doesn't parse.
- **Idempotency / re-entry:** is calling this twice safe? does Tally retry on 5xx?

For each: state the intended behavior and whether it has a test in §8.

## 7. Implementation Plan [REQUIRED]

Ordered steps. For each step include the action and a verification check
in the `[Step] → verify: [check]` format from `CLAUDE.md` §4.

Embed designed artifacts **inline at the relevant step**:

- LLM system prompts — full text, not a summary.
- JSON schemas / output formats — exact schema.
- Tool / function definitions — full signature and docstring.
- Data models / config values — exact field names and types.
- Behavioral rules (personalization, routing, safety) — verbatim.

If a step depends on a conditional section (§9.x), reference it explicitly
in the step.

## 8. Testing Plan [REQUIRED]

- **Unit tests:** which modules, which behaviors, which mocks. Mocking policy
  per `backend/TESTING_STRATEGY.md` (never call Gemini or Telegram from tests).
- **Integration tests:** which flows need real Supabase / Gemini under
  `-m integration` and `_INTEGRATION_TESTS=1`.
- **Manual checks:** for UI changes, list the screens and viewports —
  mobile AND desktop, per `CLAUDE.md` §3 (mobile is non-negotiable, not
  deferrable).
- **Sample inputs / expected outputs:** for any agent, webhook, or API
  endpoint, include at least one canonical happy-path example and one
  error-path example with concrete payloads. These double as integration
  test fixtures.

## 9. Conditional Sections — fill only if applicable

### 9.1 Data Model & RLS [CONDITIONAL]
*Required if the task touches `supabase/schema_public.sql` or RLS policies.*

- Schema diff (SQL — additive where possible).
- New / updated RLS policies (SQL). Per `CLAUDE.md` §8, every new table
  needs a policy in the same PR.
- Migration ordering and idempotency notes (`IF NOT EXISTS`, safe-to-rerun).
- Data backfill plan, if any.

### 9.2 LLM Considerations [CONDITIONAL]
*Required if the task adds or modifies an agent, prompt, or tool call.*

- **Model tier and rationale:** flash vs. flash-lite per `CLAUDE.md` §10.
  Default to flash-lite unless reasoning quality demands flash.
- **Estimated token budget** per call (input / output) and per-user
  per-month if the call is frequent.
- **Prompt-injection surface:** identify every place untrusted user text
  enters the prompt; describe sanitization.
- **Output handling:** if the output is rendered in any UI, describe
  escaping / sanitization. Per `CLAUDE.md` §7.
- **Tool definitions** (if any new tools): full signature, docstring, side
  effects, idempotency. Per `AGENTIC_GUIDELINES.md`: one tool = one clear action.
- **Versioning:** how is this prompt or tool version recorded?

### 9.3 Observability [CONDITIONAL]
*Required if the task adds a code path that can fail in production.*

- **Logs to add:** events, structured fields. Include user_id and intent;
  exclude secrets, full tokens, phone numbers, and PII per `CLAUDE.md` §8.
- **Metrics:** latency, success rate, cost — what to track and where it lands
  (analytics_weekly, Cloud Run metrics, custom log-based metric).
- **Alerts:** wire up now, or explicitly defer to a follow-up.

### 9.4 Rollback Plan [CONDITIONAL]
*Required for schema migrations, deploy-impacting changes, or anything
gated by a feature flag.*

- Concrete revert steps (SQL down-migration, redeploy of prior revision,
  flag flip).
- Data-recovery procedure if a rollback happens after writes.
- Compatibility window if old and new code must coexist during rollout.

## 10. Findings & Follow-ups [CLOSING]

Populated **during and after** implementation. This is the sanctioned place
to record what was noticed without violating surgical-changes.

### 10.1 Improvements observed (not done in this task)

Things noticed while working but intentionally left alone. For each:

- File and area.
- One-sentence description of the issue or improvement.
- Suggested priority (low / medium / high).
- Whether it warrants its own task spec, or is small enough to fix inline
  in a future related change.

This list is the input for future `simplify` / refactor / tech-debt passes.
Do not act on these items in the current task — record and move on.

### 10.2 Spec deviations

If the implementation diverged from any prior section, record what changed
and why. Examples:

- "§3 AC-2 reworded after discovering the Supabase RPC returns 200 with an
  empty body on expired tokens, not 410."
- "§4 added `backend/src/agentic_traveler/core/time_utils.py` — required by
  the new TTL check and reused enough to justify extraction."

Every divergence here should have been preceded by a stop-and-flag per
Golden Rule #2.

## 11. Definition of Done [REQUIRED]

A checklist the implementer self-verifies before claiming completion.

- [ ] All acceptance criteria in §3 pass (tests or manual checks).
- [ ] All §6 edge cases either covered by tests or explicitly deferred in §10.2.
- [ ] `ruff check` clean (backend changes).
- [ ] `pytest` unit suite passes; integration suite passes when applicable.
- [ ] `npm run build` succeeds (frontend changes).
- [ ] Mobile + desktop both verified (UI changes), per `CLAUDE.md` §3.
- [ ] No file outside §4 was modified — or §10.2 explains why.
- [ ] `README.md` updated if behavior or setup changed, per `CLAUDE.md` §6.
- [ ] §10.1 reviewed — any high-priority items captured as follow-up tasks.
- [ ] No secrets, full tokens, or PII added to logs.
- [ ] Supabase RLS policies present for any new user-scoped table.

## 12. Open Questions [OPTIONAL]

If anything is genuinely unclear at write time, list it here rather than
guessing. Block implementation on any question whose answer would change §3
or §6 — surface and resolve before coding.

---

## What's NOT in this template (and why)

The original `task_template.md` included Communication Plan, Stakeholders,
Status Cadence, Escalation Path, Change Log, and Glossary. Those are removed
in v2 — they're PM ceremony for a solo-dev / AI-paired workflow, and they
dilute the sections that actually affect code quality. Git history and §10.2
cover the same ground for change tracking.

If a future task genuinely needs one of those sections (e.g., a multi-team
migration), add it inline for that spec — don't reinstate it as a default.
