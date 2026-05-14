# Task Spec: Firestore → Supabase (Postgres) Migration

> **Status: ✅ COMPLETED** (2026-05-13)

## 1. Task Overview
**Summary:** Replace Firebase Firestore with Supabase-hosted PostgreSQL as the primary database for the Agentic Traveler backend.
**Background:** The future Trip Saga (Task 23) introduces deeply relational data (users → trips → itinerary items → logistics). Postgres handles this natively with foreign keys and JOINs, whereas Firestore requires complex denormalization. Furthermore, Task 25 (Social Matching) will need queries ("find users with similar travel profiles") that are impractical in Firestore but trivial with SQL or pgvector. Transitioning to Supabase gives us standard Postgres, zero vendor lock-in, and predictable resource-based pricing.
**Primary Owner:** Dev Team

## 2. Objectives & Success Criteria
**Goals:**
- Switch data persistence from NoSQL (Firestore) to a Hybrid Relational + JSONB model (Supabase/PostgreSQL).
- Reduce vendor lock-in.
- Maintain all existing application functionality seamlessly.

**Non-Goals:**
- Implementing the Trip Builder frontend or Trip Saga models.
- Changing LLM providers or agent logic.
- Setting up Row-Level Security (RLS) policies (can be added later).
- Running a data migration script (there are no active users, so migration is out of scope).

**Definition of Done:**
- ✅ All backend code uses the new `UserRepository` instead of `FirestoreUserTool`.
- ✅ Supabase schema is deployed (8 tables as defined in §6).
- ✅ Firestore SDK removed from `requirements.txt`.
- ✅ All 60 unit tests pass with Supabase mocks. Integration tests use real Supabase.
- ✅ `tally_webhook/` still uses Firestore; migration deferred to Task 23.

## 3. System Context
**Repositories / Services Affected:**
- Backend repository (FastAPI).
- Tally Webhook Cloud Function.

**Architecture Notes:**
- **Hybrid Relational + JSONB:** Use proper tables and foreign keys for core entities (users, credits). Use Postgres `JSONB` columns for semi-structured data that changes frequently (profile scores, conversation history, form responses). This avoids over-normalization while keeping relational benefits.

**Relevant Specs / Docs:**
- `AGENTIC_GUIDELINES.md`

### Firestore Surface Area Audit
Every file that currently directly imports or uses Firestore:
- `firestore_user.py`: Primary data access layer. Returns `DocumentReference`.
- `webhook.py`: Consumer of the user tool.
- `agent.py`: Consumer. Stores `user_doc_ref`.
- `conversation_manager.py`: Writes nested JSON under user doc.
- `preference_learner.py`: Merges structured profile updates.
- `credit_manager.py`: Uses Firestore atomic increments and array unions.
- `usage_tracker.py`: Atomic per-model token counter increments.
- `off_topic_guard.py`: Updates `off_topic.*` fields.
- `feedback_tool.py`: Writes to separate `feedback` collection.
- `metrics_tracker.py`: Writes to `analytics` collection.
- `tally_webhook_v2/main.py`: Cloud Function creating initial user doc.

## 4. Constraints & Requirements
**Technical:**
- Target Python 3.13.
- Use the official `supabase` Python client.
- Eliminate the Firestore `DocumentReference` pattern. All downstream code must pass `user_id` (UUID) instead.

**Operational:**
- No data migration is required, as there are no active users.

**Security / Compliance:**
- The Supabase service role key must only be used server-side (stored in Secret Manager or `.env`) because it bypasses RLS.

## 5. Inputs & Resources
**Artifacts Provided:**
- Existing Firestore schema implicitly defined via Python models.

**Assumptions:**
- A Supabase project exists (`Aletheia Travel`) and is accessible.

**Open Questions:**
- None.

## 6. Implementation Plan

### High-Level Steps
1. Setup & Tooling (Dependencies and env vars).
2. Abstraction Layer (`db_client.py`).
3. Replace `FirestoreUserTool` with `UserRepository`.
4. Update Downstream Consumers (SQL rewrites for increments/upserts).
5. Update `webhook.py` and `agent.py`.
6. Cleanup.

### Detailed Tasks

#### Database Schema Design
Deploy the following DDL via the Supabase SQL editor:

```sql
-- ============================================================
-- 1. USERS (core identity)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     TEXT UNIQUE,
    submission_id   TEXT UNIQUE,
    name            TEXT,
    location        TEXT,
    source          TEXT DEFAULT 'tally',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_submission_id ON users(submission_id);

-- ============================================================
-- 2. USER PROFILES (structured travel personality)
-- ============================================================
CREATE TABLE user_profiles (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    profile_data    JSONB DEFAULT '{}',
    form_response   JSONB DEFAULT '{}',
    summary         TEXT DEFAULT '',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 3. CREDITS
-- ============================================================
CREATE TABLE credits (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance         INT NOT NULL DEFAULT 0,
    initial_grant   INT NOT NULL DEFAULT 0,
    total_spent     INT NOT NULL DEFAULT 0,
    used_promos     TEXT[] DEFAULT '{}',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 4. CONVERSATION HISTORY
-- ============================================================
CREATE TABLE conversations (
    user_id          UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    recent_messages  JSONB DEFAULT '[]',
    summary          TEXT DEFAULT '',
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 5. USAGE TRACKING (per-user, per-model)
-- ============================================================
CREATE TABLE usage_tracking (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id               UUID REFERENCES users(id) ON DELETE CASCADE,
    model_name            TEXT NOT NULL,
    total_input_tokens    BIGINT DEFAULT 0,
    total_output_tokens   BIGINT DEFAULT 0,
    call_count            INT DEFAULT 0,
    grounded_prompt_count INT DEFAULT 0,
    UNIQUE (user_id, model_name)
);

-- ============================================================
-- 6. OFF-TOPIC GUARD
-- ============================================================
CREATE TABLE off_topic_state (
    user_id            UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    count              INT DEFAULT 0,
    last_flagged_ts    TIMESTAMPTZ,
    restricted_until   TIMESTAMPTZ
);

-- ============================================================
-- 7. FEEDBACK
-- ============================================================
CREATE TABLE feedback (
    id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                TEXT NOT NULL,
    text                   TEXT NOT NULL,
    category               TEXT NOT NULL,
    conversation_context   JSONB DEFAULT '[]',
    created_at             TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_feedback_user_id ON feedback(user_id);
CREATE INDEX idx_feedback_category ON feedback(category);

-- ============================================================
-- 8. ANALYTICS (weekly roll-ups)
-- ============================================================
CREATE TABLE analytics_weekly (
    week_ending          DATE PRIMARY KEY,
    total_interactions   INT DEFAULT 0,
    new_users            INT DEFAULT 0,
    active_users         TEXT[] DEFAULT '{}',
    agent_calls          JSONB DEFAULT '{}',
    token_usage          JSONB DEFAULT '{}',
    promo_redeemed       JSONB DEFAULT '{}',
    grounding_calls      INT DEFAULT 0,
    flushed_at           TIMESTAMPTZ
);
```

#### Code Updates
- **`db_client.py`**: Create a Supabase client wrapper initializing with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
- **`UserRepository`**: Replace `FirestoreUserTool`. Implement methods like `get_user_by_telegram_id`, replacing `DocumentReference` with `user_id` UUID strings. Use `get_db().table("users").select("...").eq(...)`.
- **`credit_manager.py`**: Replace `transforms.Increment` and `transforms.ArrayUnion` with direct SQL updates:
  ```sql
  UPDATE credits SET balance = GREATEST(0, balance - $1), total_spent = total_spent + $1 WHERE user_id = $2
  ```
- **`usage_tracker.py`**: Replace increments with `INSERT ... ON CONFLICT DO UPDATE SET ...`.
- **`tally_webhook_v2/main.py`**: Rewrite to use the Supabase client directly and `UPSERT` on the `users` table.

**Dependencies:**
- Python `supabase` package.

## 7. Testing & Validation
**Test Strategy:**
Unit tests mock `agentic_traveler.tools.db_client.get_db` to prevent real network calls. Integration tests in `tests/integration/` hit a real Supabase project using rows prefixed with `test_run_` for isolation and clean up via CASCADE delete.

**Acceptance Tests:**
- ✅ Send a Tally test submission → verify it appears in `users` and `user_profiles`.
- ✅ Send `/start <submissionId>` in Telegram → verify linking works.
- ✅ Send regular messages → verify `conversations`, `usage_tracking`, and credit deduction.
- ✅ Send `/promo TESTCODE` → verify promo redemption.
- ✅ Wait for metrics flush → verify `analytics_weekly` updates.

**Unit Test Coverage (60 passing):**
- `test_feedback_tool.py` — Supabase insert payload shape.
- `test_off_topic_guard.py` — counter increment, threshold restriction, auto-reset.
- `test_metrics_tracker.py` — buffer accumulation, `_write_to_supabase` called on flush.
- `test_usage_tracker.py` — no Firestore calls, grounding detection.
- `test_webhook.py` — webhook routing, rate limiting, `/start`, `/promo`.

**Tooling:**
- Pytest.

## 8. Risk Management
**Known Risks:**
- Supabase free tier connection limits.
- Breaking the Tally webhook during cutover.

**Mitigations:**
- Use Cloud Run `max-instances=1` to help with connection pooling.
- Deploy the Tally function update separately and test with a Tally test submission first.

**Rollback Plan:**
- Revert the backend commit and redeploy the previous Docker image that uses Firestore. 

## 9. Delivery & Handoff
**Deliverables:**
- PR containing the `UserRepository`, updated downstream consumers, and removal of Firestore dependencies.
- Updated `requirements.txt`.

**Review Process:**
- Dev Team review.

**Post-Delivery Actions:**
- Update `README.md`, `DEPLOYMENT.md`, and `DEPLOYMENT_local.md` to reflect the new `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` environment variables.

## 10. Communication Plan
**Stakeholders:**
- Dev Team.

**Status Cadence:**
- Updates provided as PRs are merged.

**Escalation Path:**
- N/A.

## 11. Appendix

### User Document Shape: Before → After

**Before (Firestore — Single nested document)**
```json
{
  "telegramUserId": "12345",
  "submissionId": "abc",
  "name": "Cristian",
  "user_profile": { "form_response": { ... }, "scores": { ... }, "tags": [ ... ], "summary": "..." },
  "credits": { "balance": 450, "initial_grant": 500, "total_spent": 50, "used_promos": [] },
  "conversation_history": { "recent_messages": [...], "summary": "..." },
  "usage": { "gemini-2_5-flash": { "total_input_tokens": 1000, ... } },
  "off_topic": { "count": 0, "last_flagged_ts": null, "restricted_until": null }
}
```

**After (Supabase — Normalized across tables)**
```
users          → { id, telegram_id, submission_id, name, location, source, created_at }
user_profiles  → { user_id, profile_data (JSONB), form_response (JSONB), summary }
credits        → { user_id, balance, initial_grant, total_spent, used_promos }
conversations  → { user_id, recent_messages (JSONB), summary }
usage_tracking → { user_id, model_name, total_input_tokens, total_output_tokens, call_count }
off_topic_state→ { user_id, count, last_flagged_ts, restricted_until }
```

### Key Differences in Code Patterns
1. **No more `DocumentReference`**: Functions pass `user_id: str` (UUID) instead of opaque references. The repository handles all DB calls.
2. **No more `set(merge=True)`**: Use SQL `INSERT ... ON CONFLICT DO UPDATE` (upsert) or targeted `UPDATE`.
3. **Native Atomicity**: Firestore's `transforms.Increment` / `transforms.ArrayUnion` are replaced by native SQL (`balance = balance - $cost`, `array_append`, `ON CONFLICT DO UPDATE SET count = table.count + EXCLUDED.count`).
4. **Data Retrieval**: `UserRepository` will assemble nested shapes using JOINs if necessary for backward compatibility during the migration.
