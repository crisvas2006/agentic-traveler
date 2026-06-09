# Agentic Traveler — Claude Instructions

This is the **single entry point** for AI coding agents working in this repo.
It is auto-loaded by Claude Code from the project root. Other guideline files
(`AGENTIC_GUIDELINES.md`, `backend/TESTING_STRATEGY.md`, `backend/DEPLOYMENT.md`,
`frontend/GEMINI.md`, `frontend/AGENTS.md`) are referenced from here — do not
duplicate their content.

---

## 1. Repo Layout (monorepo)

```
agentic-traveler/
├── backend/                    # Python FastAPI + Google GenAI on Cloud Run
│   ├── src/agentic_traveler/
│   │   ├── analytics/          # EventEmitter metric sink → analytics_events (7-day) + metrics_daily rollup
│   │   ├── core/               # Sanitization, shared utilities
│   │   ├── economy/            # Credit manager + promo codes
│   │   ├── guards/             # Off-topic guard, input filters
│   │   ├── interfaces/         # FastAPI entrypoints
│   │   │   ├── main.py         # ASGI app — uvicorn target
│   │   │   └── routers/        # /webhook, /tally-webhook, /chat, /credits…
│   │   ├── orchestrator/       # Coordinator + Router + Chat/Trip/Planner/Search/Profile agents
│   │   └── tools/              # UserRepository, weather, search, etc.
│   ├── tests/                  # Unit (default) + integration (-m integration)
│   ├── scripts/                # register_webhook.py, setup_alerts.py, …
│   ├── .venv/                  # Python virtualenv (lives INSIDE /backend)
│   ├── pyproject.toml          # pytest config + setuptools packages
│   ├── requirements.txt        # Pinned runtime + dev dependencies (pytest, ruff, etc.)
│   ├── Dockerfile              # Python 3.13 — source of truth for prod version
│   ├── .env                    # Secrets (gitignored) — see DEPLOYMENT.md for keys
│   ├── .env.example            # Template — copy to .env and fill in
│   ├── TESTING_STRATEGY.md
│   └── DEPLOYMENT.md           # Cloud Run deploy + ngrok local webhook
├── frontend/                   # Next.js 16 / React 19 / TS / Tailwind v4 on Vercel
│   ├── src/
│   │   ├── app/                # App Router — (auth), dashboard, settings, api/*
│   │   ├── components/         # auth/, dashboard/, settings/, layout/, ui/
│   │   ├── hooks/              # useUserProfile, useChat, …
│   │   ├── lib/  utils/        # Supabase clients in utils/supabase/
│   │   └── emails/             # React Email templates (Resend)
│   ├── .env.local              # NEXT_PUBLIC_* + server-only Supabase keys
│   ├── .env.local.example      # Template — copy to .env.local and fill in
│   ├── package.json
│   ├── GEMINI.md               # Frontend-specific rules — READ for UI work
│   └── AGENTS.md               # Next.js 16 breaking-change warning — READ first
├── supabase/                   # schema_public.sql (reference snapshot, NOT runnable migrations),
│                               # rls_policies.sql, auth_hooks.sql, dev_scripts/
├── specs/                      # Task specs (task_<name>.md following task_template_v2.md)
├── docs/                       # Performance testing guide, prompt notes
├── .claude/                    # Slash-command prompts (/spec, /review, /ship)
├── CLAUDE.md                   # This file — auto-loaded by Claude Code
├── GEMINI.md                   # Original philosophy doc — superseded by this file
├── AGENTIC_GUIDELINES.md       # Agent architecture rules — READ before touching agents
├── task_template_v2.md         # Canonical spec template for new tasks
├── task_template.md            # Legacy template — kept for old specs only
└── README.md                   # Product overview + setup
```

**Monorepo isolation rule:** Frontend code stays in `/frontend`, backend in
`/backend`. Never mix dependencies.

---

## 2. Build, Run, Test — How to verify your work

The Python virtualenv lives at **`backend/.venv/`** (inside the backend folder,
not at the repo root). All commands below assume PowerShell on Windows.

### Backend (Python 3.13)

```powershell
# Activate venv (once per shell)
.\backend\.venv\Scripts\Activate

# Install / update deps. Note: backend/pyproject.toml does NOT declare a
# [project.optional-dependencies] block, so `pip install -e ".[dev]"` does
# NOT install pytest / ruff / black — they live in requirements.txt.
cd backend
pip install -r requirements.txt
pip install -e .
cd ..

# Lint — required gate before considering code complete
.\backend\.venv\Scripts\python -m ruff check backend\src backend\tests

# Unit tests (default — integration marker deselected via pyproject)
.\backend\.venv\Scripts\python -m pytest backend\tests -v

# Integration tests (real Supabase + real Gemini API)
$env:_INTEGRATION_TESTS="1"
.\backend\.venv\Scripts\python -m pytest backend\tests -m integration -v

# Run the FastAPI app locally (uvicorn target = interfaces.main:app)
$env:SKIP_IP_CHECK="1"   # disables Telegram IP whitelist for local dev
.\backend\.venv\Scripts\uvicorn agentic_traveler.interfaces.main:app --reload --port 8080
```

See `backend/TESTING_STRATEGY.md` for mocking policy and `backend/DEPLOYMENT.md`
for Cloud Run + ngrok flows.

### Frontend (Next.js 16, React 19)

```powershell
cd frontend
npm install
npm run dev      # next dev
npm run build    # next build — run before declaring UI work done
npm run lint     # eslint via eslint-config-next
```

**Before writing Next.js code:** read `frontend/AGENTS.md`. Next.js 16 has
breaking changes vs. older training data; consult
`frontend/node_modules/next/dist/docs/` when uncertain.

### Required gates before marking any task done

1. `ruff check` clean (backend changes)
2. `pytest` passes (backend changes — unit suite at minimum)
3. `npm run build` succeeds (frontend changes)
4. `README.md` updated if behavior or setup changed (mandatory — see §6)

---

## 3. Tech Stack & Conventions

| Layer         | Stack                                                                                                                                                 |
| ---------------| -------------------------------------------------------------------------------------------------------------------------------------------------------|
| Backend       | Python 3.13, FastAPI, Google GenAI SDK, Pydantic                                                                                                      |
| Agents        | Gemini 3.x flash / flash-lite per agent (see README §Current Model Stack)                                                                             |
| DB            | Supabase (PostgreSQL) — JSONB profiles, RPC for atomic credit ops, RLS enforced                                                                       |
| Frontend      | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4                                                                                        |
| Auth          | Supabase Auth (`@supabase/ssr`), Google OAuth (PKCE), Cloudflare Turnstile                                                                            |
| Email         | React Email templates rendered, sent via Resend                                                                                                       |
| Hosting       | Cloud Run (backend), Vercel (frontend)                                                                                                                |
| Channels      | Telegram Bot webhook → Cloud Run; Tally form → `/tally-webhook`                                                                                       |
| Realtime      | Supabase Realtime (postgres_changes) on parent tables; child writes bump parent `updated_at` via Postgres trigger                                     |
| Streaming     | Server-Sent Events (FastAPI `StreamingResponse`) for web; debounced `editMessageText` for Telegram                                                    |
| Observability | LangSmith (`@traceable` on orchestrator + sagas + agents); structured metric events into `analytics_events` (7-day window) + `metrics_daily` (rollup) |

**Python:** Target 3.13 (must match `backend/Dockerfile`). Pin versions in
`requirements.txt`. Test syntax-sensitive changes against the Docker version.

**TypeScript / React:** Match existing patterns in `frontend/src/components/`
and `frontend/src/app/`. Mobile-first responsive design is **non-negotiable** —
when you implement a `lg:` breakpoint, implement the `sm:`/`md:` equivalent in
the same task. Never defer mobile.

**Logging:** Include meaningful context (user IDs, intent, timing). Never log
secrets, full API keys, phone numbers, or PII.

---

## 4. How to Think (philosophy — preserved from GEMINI.md)

### Think before coding
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.

### Simplicity first
- Minimum code that solves the problem. No features beyond what was asked.
- No abstractions for single-use code. No "flexibility" that wasn't requested.
- No error handling for impossible scenarios.
- Prefer a library when it reduces surface area to test and maintain.
- Ask: *"Would a senior engineer say this is overcomplicated?"* If yes, simplify.

**Proactive suggestions:** When you spot a meaningful improvement beyond scope,
surface it — don't silently implement, don't silently discard.
- High confidence + clear win: include in the plan; user removes if unwanted.
- Lower confidence / non-trivial tradeoff: propose and ask before implementing.

### Surgical changes (with eyes open)
- Touch only what the task requires.
- Don't "improve" adjacent code, comments, or formatting.
- Match existing style, even if you'd do it differently.
- **Notice and surface** unrelated dead code or refactor opportunities you
  observe in the working context — record them in the spec's §10.1 Findings
  (or in your turn summary if there's no spec). Don't act on them silently,
  don't discard them silently.
- Remove orphan imports/variables that **your** changes made unused. Don't
  remove pre-existing dead code unless asked.

### Goal-driven execution
Transform tasks into verifiable goals before coding:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a failing test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks state a brief plan as `[Step] → verify: [check]`.

---

## 5. Task Specs

Create `specs/task_<feature_name>.md` **before writing code** when a task:
- Touches more than one module, OR
- Is expected to take more than ~2 hours, OR
- Introduces non-trivial mechanisms (new async patterns, state machines,
  external integrations, security boundaries, data migrations).

**MANDATORY:** Follow the structure in `task_template_v2.md` verbatim. Do not
invent your own structure. Specs must be self-contained — embed prompts,
schemas, and tool definitions inline, not by reference.

`task_template_v2.md` adds explicit slots for edge cases, files touched,
LLM considerations, RLS, observability, and a **Findings & Follow-ups**
section for noticed-but-not-changed items. The old `task_template.md` is
kept for reference only — do not use it for new specs.

---

## 6. Documentation

- **MANDATORY:** When you add or change a feature, update `README.md` in the
  same task. There must never be discrepancies between the codebase and README.
- Comments only where code is not self-explanatory or cognitive load is high.
- **Do not create new `*.md` docs unless the user explicitly asks** — prefer
  updating existing files.

---

## 7. Agentic Architecture

For all agent routing, prompt design, memory, and tool changes you MUST follow
`AGENTIC_GUIDELINES.md`. Key invariants reproduced here:

- Keep agents small and specialized; each tool = one clear action.
- Control what goes into the LLM (minimal, relevant context).
- Plan before acting on multi-step tasks; check the whole sequence, not just the answer.
- Session = short-term memory; MemoryService = long-term. Keep memory small; summarize often.
- Store large outputs **outside** context; return references only.
- Grant minimal permissions. Sanitize LLM output shown in any UI.
- Keep runtime stateless; externalize all state to Supabase.
- Version prompts and tools. Make tools safe to retry.

### 7.1 Saga conventions (ratified by `specs/proposal_trip_model_and_planning_saga.md`)

Once the proposal lands and §7.x of it ships, these apply to every new
saga / agent / tool change:

- **Sagas are slot-filling skills with state-as-data.** Never store conversation
  state on `self` — always read from / return updates to the `SagaState`
  TypedDict. This is the rule that keeps a future LangGraph migration
  mechanical.
- **Slot-fill is a return value, not an exception.** Return
  `SagaResult(slot_request=SlotRequest(slot, prompt))`. Never raise.
- **Every saga / agent / tool accepts an `EventEmitter`** and calls
  `events.emit(phase, payload)` at three kinds of moment:
  - `phase="status"` — user-facing progress strings, before each tool call
    and at major phase boundaries (drives SSE + Telegram message-edit UX).
  - `phase="delta"` — token-by-token output during streaming (final agents
    only).
  - `phase="metric"` — structured analytics rows (see §10 cost rules below).
- **`@traceable` (LangSmith) on every orchestrator-level function:**
  orchestrator entry points, `RouterAgent.classify`, every saga's `run`,
  every heavy-agent `process_request`, the SearchAgent, and the Gemini-call
  wrapper. Sample 100 % in dev, configurable in prod.
- **Metric emission by default.** Every saga emits at minimum:
  `saga_entered`, `saga_exited`, `slot_filled`, `error_raised`. Every tool
  wrapper emits `tool_invoked` + `tool_succeeded` / `tool_failed` with
  `latency_ms`. The orchestrator emits `turn_completed` per turn with
  `{latency_ms, credits_charged, intent, owner_saga, tools_used}`.
- **No booking engine.** All bookings are user-input (paste / PDF / chat
  text); the `BookingInputSaga` is the canonical parser. Schema for bookings
  must accept partial entries.
- **Country / safety / health / money intel are cached world facts, never
  authoritative.** Every render carries a "verify with official sources"
  disclaimer. Snapshot is captured once on destination-confirmed; refresh
  is **explicit user request only** (never silent on view, to avoid
  burning grounded-search credits). Never claim authority on visa, medical,
  or legal matters.
- **Conciseness is a product invariant.** Every user-facing agent reply
  carries an explicit length budget per step. Bake the cap into the saga's
  system prompt and assert it in tests (`len(SagaResult.text) <= cap`).
  Defaults: chat ack ≤ 320 chars; slot-fill question ≤ 200 chars (one
  question per turn); destination suggestions ≤ 1 200 chars / 3 options;
  country intel summary line ≤ 280 chars (details unfold in card UI);
  full itinerary ≤ 3 500 chars. User-overridable via
  `user_profiles.profile_data.reply_length_preference ∈ {terse, default,
  verbose}`.
- **Hard overrides cross saga boundaries.** When the user says "never ask
  me X, it's always Y" the answer is stored in
  `user_profiles.profile_data.hard_overrides` and **every** saga checks
  it during slot-fill. Not just the saga that originally heard the rule.

Read `AGENTIC_GUIDELINES.md` before proposing new agents, changing prompts,
or adding tools.

---

## 8. Security & Data

- **Never hardcode secrets.** Always use env vars. Verify `.env` is gitignored.
- **Never log** secrets, full tokens, phone numbers, or PII.
- **Sanitize user input** before injecting into LLM prompts (prompt injection).
- **Supabase RLS is mandatory** for every new table — write the policy in the
  same PR. Standard patterns: `auth.uid() = user_id` (personal),
  RPC + service key (atomic ops like credit deduction).
- **Realtime subscription pattern:** for any parent table with child
  collections, the frontend subscribes to the **parent only**; child writes
  bump the parent's `updated_at` via a `touch_*` Postgres trigger. RLS on the
  parent governs visibility — child tables inherit the security model
  transparently. Goal: one WebSocket per active dashboard tab, never more
  than ~4 multiplexed channels (free-tier discipline).
- **Never call external APIs from the browser.** Client → Next.js Route Handler /
  Server Action / Python backend → external. Never prefix sensitive env vars
  with `NEXT_PUBLIC_`.
- **Do not remove fields from models** without explicit approval.

### Required env vars (see `backend/DEPLOYMENT.md` for full reference)

Backend `.env`: `GOOGLE_API_KEY`, `GOOGLE_PROJECT_ID`, `GEMINI_REGION`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_SECRET_TOKEN`, `SUPABASE_URL`,
`SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`, `FRONTEND_ORIGIN`,
`TALLY_WEBHOOK_TOKEN`, `APP_ADMIN_API_KEY`.

Frontend `.env.local`: `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, server-only Supabase + Resend keys.

---

## 9. Things to NEVER Do in This Repo

- **Never auto-deploy** to Cloud Run or Vercel. Approval required every time.
- **Never run modifying git commands** (such as `git add`, `git commit`, `git restore`, `git reset`, `git checkout`). The agent must never modify git state or stage/unstage files; only read-only git operations (e.g., `git status`, `git diff`, `git log`) are allowed.
- **Never amend commits** — always create a new commit. Never `--no-verify`.
- **Never apply Supabase migrations manually** in prod. Use `supabase/schema_public.sql`
  + migration tooling. Schema/RLS lives in source control.
- **Never bypass Supabase RLS** in application code (no raw service-key reads
  for user-scoped data unless there's a documented reason).
- **Never mix frontend and backend dependencies.**
- **Never call the Gemini API or Telegram API from automated tests** — mock
  them (see `backend/TESTING_STRATEGY.md`).
- **Never log Telegram bot tokens, Supabase service keys, JWTs, or user PII.**
- **Never use real production data in integration tests** — use the `_test: true`
  marker convention so cleanup works.

---

## 10. Cost Awareness

- Prefer lightweight models (`flash-lite`) for non-critical tasks (classification,
  summarization). Reserve `flash` for reasoning-heavy work.
- Note Cloud Run billing implications of config changes (max-instances,
  concurrency, memory, `--no-cpu-throttling`).
- Backend is stateless by design — reconstruct context per request rather than
  caching, unless cost analysis says otherwise.
- **Free-tier discipline (Supabase, target: ≤1 000 users on the free plan):**
  - No event/log table grows unbounded. Every such table has a `pg_cron`
    "truncate after N days" companion job. Long-term answers live in a
    daily roll-up (e.g. `metrics_daily`), not in the raw event log.
  - Every new user-growing table ships **with** at least one canonical
    `vw_<topic>_growth` SQL view in the same migration, so capacity can be
    queried from day one.
  - Watch the two free-tier gates that fire first under our usage profile:
    (a) Realtime monthly event count (cap 2 M / mo) and (b) LangSmith trace
    quota (cap 5 k / mo) — both visible via `vw_capacity_today`. Sample
    LangSmith at < 1.0 in prod once traffic warrants.
- **LangSmith trace volume scales with traffic.** Default to 100 % in dev,
  intend to sample (`LANGCHAIN_TRACING_SAMPLE_RATE=0.1`) in prod past ~100
  active users / day.

---

## 11. Quick Reference — File Locations

| Need | File |
|---|---|
| Build/test commands | this file §2 |
| Deploy to Cloud Run | `backend/DEPLOYMENT.md` |
| Local webhook with ngrok | `backend/DEPLOYMENT.md` §"Local Development with ngrok" |
| Testing policy + mocking rules | `backend/TESTING_STRATEGY.md` |
| Agent design rules | `AGENTIC_GUIDELINES.md` |
| Frontend UI rules + RLS patterns | `frontend/GEMINI.md` |
| Next.js 16 breaking-change warning | `frontend/AGENTS.md` |
| DB schema + RLS | `supabase/schema_public.sql`, `supabase/rls_policies.sql` |
| Task spec structure | `task_template_v2.md` (canonical); `task_template.md` retained for legacy reference only |
| Product / architecture overview | `README.md` |
| Trip data model, saga state machine, realtime + streaming + metrics conventions | `specs/proposal_trip_model_and_planning_saga.md` (in review; ratified rules surfaced in §3, §7.1, §8, §10 above) |
