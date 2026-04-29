# Task Spec: Firestore → Supabase (Postgres) Migration

## Goal
Replace Firebase Firestore with Supabase-hosted PostgreSQL as the primary database for the Agentic Traveler application.

**Why:**
- The Trip Saga (Task 23) introduces deeply relational data (users → trips → itinerary items → logistics). Postgres handles this natively with foreign keys and JOINs; Firestore requires denormalization and multiple reads.
- Task 25 (Social Matching) will need complex queries ("find users with similar travel profiles") that are impractical in Firestore but trivial with SQL or pgvector.
- Firestore's per-operation billing becomes unpredictable at scale. Supabase's resource-based pricing is flat and predictable.
- Supabase is standard Postgres — zero vendor lock-in, portable, and self-hostable.

---

## Firestore Surface Area Audit

Every file that directly imports or uses Firestore, grouped by concern:

### 1. User Data (Core CRUD)
| File | Firestore Operations | Notes |
|---|---|---|
| [firestore_user.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/tools/firestore_user.py) | Query by `telegramUserId`, query by `submissionId`, `get` by doc ID, `set(merge=True)`, `delete` | **Primary data access layer.** Returns `DocumentReference` objects used downstream. |
| [webhook.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/webhook.py) | Imports `FirestoreUserTool`, calls `get_user_by_telegram_id`, `link_telegram_user`, `get_user_with_ref`, `get_user_ref_by_telegram_id`, `update_user_fields` | Consumer of the user tool. Uses both doc dicts and refs. |
| [agent.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/orchestrator/agent.py) | Imports `FirestoreUserTool`, calls `get_user_with_ref` | Consumer. Stores `user_doc_ref` for downstream use. |

### 2. Conversation History
| File | Firestore Operations | Notes |
|---|---|---|
| [conversation_manager.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/orchestrator/conversation_manager.py) | `user_doc_ref.set({"conversation_history": ...}, merge=True)` | Writes nested JSON under user doc. Reads from `user_doc` dict. |

### 3. Preference Learning
| File | Firestore Operations | Notes |
|---|---|---|
| [preference_learner.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/orchestrator/preference_learner.py) | `user_doc_ref.set({"user_profile": ...}, merge=True)` | Merges structured profile updates. |

### 4. Credits & Promo Codes
| File | Firestore Operations | Notes |
|---|---|---|
| [credit_manager.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/credit_manager.py) | `user_doc_ref.set(merge=True)`, `user_doc_ref.update()` with `transforms.Increment`, `transforms.ArrayUnion` | Uses Firestore atomic increments and array unions. Most complex Firestore-specific logic. |

### 5. Usage Tracking
| File | Firestore Operations | Notes |
|---|---|---|
| [usage_tracker.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/usage_tracker.py) | `user_doc_ref.update()` with `transforms.Increment` | Atomic per-model token counter increments on user doc. |

### 6. Off-Topic Guard
| File | Firestore Operations | Notes |
|---|---|---|
| [off_topic_guard.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/off_topic_guard.py) | `user_doc_ref.update()` for `off_topic.*` fields | Reads from `user_doc` dict, writes via ref. |

### 7. Feedback
| File | Firestore Operations | Notes |
|---|---|---|
| [feedback_tool.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/tools/feedback_tool.py) | `self.db.collection("feedback").add(payload)` | Standalone Firestore client. Writes to separate `feedback` collection. |

### 8. Metrics (Analytics)
| File | Firestore Operations | Notes |
|---|---|---|
| [metrics_tracker.py](file:///d:/Dev/Apps/agentic-traveler/src/agentic_traveler/metrics_tracker.py) | `doc_ref.set(update, merge=True)` with `transforms.Increment`, `transforms.ArrayUnion` | Standalone Firestore client for `analytics` collection. Weekly roll-up documents. |

### 9. Tally Webhook Ingestion (Separate Cloud Function)
| File | Firestore Operations | Notes |
|---|---|---|
| [tally_webhook_v2/main.py](file:///d:/Dev/Apps/agentic-traveler/tally_webhook_v2/main.py) | `db.collection("users").document(response_id).set(flat, merge=True)` | Standalone Cloud Function, creates initial user doc from Tally form. Hardcoded project/database IDs. |

---

## Database Schema Design

### Approach: Hybrid Relational + JSONB
Use proper tables and foreign keys for core entities. Use Postgres `JSONB` columns for semi-structured data that changes frequently (profile scores, conversation history, form responses). This avoids over-normalization while keeping the relational benefits.

### Tables

```sql
-- ============================================================
-- 1. USERS (core identity)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     TEXT UNIQUE,                     -- indexed, used for lookups
    submission_id   TEXT UNIQUE,                     -- Tally form submission ID
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
    -- Structured profile scores and tags (set by ProfileAgent)
    profile_data    JSONB DEFAULT '{}',
    -- Raw Tally form response (preserved for re-processing)
    form_response   JSONB DEFAULT '{}',
    -- Human-readable summary (generated by ProfileAgent)
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
    recent_messages  JSONB DEFAULT '[]',              -- [{role, text, ts}, ...]
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
    user_id                TEXT NOT NULL,             -- telegram user ID
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
    week_ending          DATE PRIMARY KEY,            -- e.g. 2026-04-20
    total_interactions   INT DEFAULT 0,
    new_users            INT DEFAULT 0,
    active_users         TEXT[] DEFAULT '{}',
    agent_calls          JSONB DEFAULT '{}',
    token_usage          JSONB DEFAULT '{}',
    promo_redeemed       JSONB DEFAULT '{}',
    grounding_calls      INT DEFAULT 0,
    flushed_at           TIMESTAMPTZ
);


-- ============================================================
-- 9. TRIPS (Task 23 — new, not a migration)
-- ============================================================
-- This table will be created as part of Task 23 implementation.
-- Included here for completeness as it is the primary motivation.
CREATE TABLE trips (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status          TEXT DEFAULT 'ideation'
                    CHECK (status IN ('ideation','planning','booked','active','past')),
    discovery       JSONB DEFAULT '{}',
    logistics       JSONB DEFAULT '{}',
    itinerary       JSONB DEFAULT '{}',
    scratchpad      JSONB DEFAULT '{}',
    state           JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);
```

---

## Implementation Plan

### Phase 0: Setup & Tooling
1. Create a Supabase project (free tier is sufficient for development).
2. Run the DDL above in the Supabase SQL editor to create all tables.
3. Add `supabase` to `requirements.txt` (replace `google-cloud-firestore`).
4. Add new env vars to `.env` and `DEPLOYMENT.md`:
   - `SUPABASE_URL` — project URL (e.g. `https://xxxx.supabase.co`)
   - `SUPABASE_SERVICE_KEY` — service role key (server-side, not anon)
5. Keep `google-cloud-firestore` temporarily for the data migration script.

### Phase 1: Abstraction Layer (`db_client.py`)
Create a new `src/agentic_traveler/tools/db_client.py` that wraps the Supabase Python client.

```python
# Sketch — not final code
import os
from supabase import create_client, Client

_client: Client | None = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
    return _client
```

### Phase 2: Replace `FirestoreUserTool` → `UserRepository`
Create `src/agentic_traveler/tools/user_repo.py` with the same public API but backed by Supabase.

**Method mapping:**

| Current (Firestore) | New (Supabase) | SQL equivalent |
|---|---|---|
| `get_user_by_telegram_id(tid)` | `get_db().table("users").select("*, user_profiles(*), credits(*), conversations(*), off_topic_state(*)").eq("telegram_id", tid).maybe_single().execute()` | `SELECT * FROM users LEFT JOIN ... WHERE telegram_id = ?` |
| `get_user_ref_by_telegram_id(tid)` | Returns the `user_id` UUID (no more "ref" concept) | — |
| `get_user_with_ref(tid)` | Returns `(user_dict, user_id)` tuple | — |
| `update_user_fields(tid, fields)` | `get_db().table("users").update(fields).eq("telegram_id", tid).execute()` | `UPDATE users SET ... WHERE telegram_id = ?` |
| `get_user_by_id(uid)` | `get_db().table("users").select("*").eq("id", uid).maybe_single().execute()` | `SELECT * FROM users WHERE id = ?` |
| `link_telegram_user(sid, tid)` | Transaction: find by `submission_id`, set `telegram_id`, handle merge | `UPDATE users SET telegram_id = ? WHERE submission_id = ?` |

> [!IMPORTANT]
> **The "ref" pattern disappears.** All downstream code that passes `user_doc_ref` around will instead pass a `user_id: str` (UUID). This is actually cleaner — no more Firestore-specific leaky abstraction.

### Phase 3: Update Downstream Consumers
Each module that currently receives `user_doc_ref` needs to receive `user_id` instead and call the repository directly.

#### 3a. `credit_manager.py`
- Replace `transforms.Increment` with SQL:
  ```sql
  UPDATE credits
  SET balance = GREATEST(0, balance - $1),
      total_spent = total_spent + $1,
      updated_at = now()
  WHERE user_id = $2
  ```
- Replace `transforms.ArrayUnion` with:
  ```sql
  UPDATE credits
  SET used_promos = array_append(used_promos, $1),
      balance = balance + $2,
      updated_at = now()
  WHERE user_id = $3
  ```

#### 3b. `usage_tracker.py`
- Replace `transforms.Increment` with upsert:
  ```sql
  INSERT INTO usage_tracking (user_id, model_name, total_input_tokens, total_output_tokens, call_count)
  VALUES ($1, $2, $3, $4, 1)
  ON CONFLICT (user_id, model_name)
  DO UPDATE SET
      total_input_tokens = usage_tracking.total_input_tokens + EXCLUDED.total_input_tokens,
      total_output_tokens = usage_tracking.total_output_tokens + EXCLUDED.total_output_tokens,
      call_count = usage_tracking.call_count + 1
  ```

#### 3c. `conversation_manager.py`
- Replace `user_doc_ref.set({"conversation_history": ...}, merge=True)` with:
  ```sql
  INSERT INTO conversations (user_id, recent_messages, summary)
  VALUES ($1, $2, $3)
  ON CONFLICT (user_id) DO UPDATE SET
      recent_messages = $2,
      summary = $3,
      updated_at = now()
  ```

#### 3d. `off_topic_guard.py`
- Replace `user_doc_ref.update(...)` with:
  ```sql
  INSERT INTO off_topic_state (user_id, count, last_flagged_ts, restricted_until)
  VALUES ($1, $2, $3, $4)
  ON CONFLICT (user_id) DO UPDATE SET
      count = $2,
      last_flagged_ts = $3,
      restricted_until = $4
  ```

#### 3e. `feedback_tool.py`
- Replace `self.db.collection("feedback").add(payload)` with:
  ```sql
  INSERT INTO feedback (user_id, text, category, conversation_context)
  VALUES ($1, $2, $3, $4)
  ```

#### 3f. `metrics_tracker.py`
- Replace `doc_ref.set(update, merge=True)` with:
  ```sql
  INSERT INTO analytics_weekly (week_ending, total_interactions, new_users, ...)
  VALUES ($1, $2, $3, ...)
  ON CONFLICT (week_ending) DO UPDATE SET
      total_interactions = analytics_weekly.total_interactions + EXCLUDED.total_interactions,
      ...
  ```

#### 3g. `preference_learner.py`
- Replace `user_doc_ref.set({"user_profile": updated}, merge=True)` with:
  ```sql
  UPDATE user_profiles
  SET profile_data = $1, summary = $2, updated_at = now()
  WHERE user_id = $3
  ```

### Phase 4: Update `webhook.py` and `agent.py`
- Replace `FirestoreUserTool` import with `UserRepository`.
- Replace all `user_doc_ref` variables with `user_id` (UUID string).
- Update `OrchestratorAgent.__init__` parameter name.
- Update all downstream calls that pass `user_doc_ref`.

### Phase 5: Tally Webhook Cloud Function
- Rewrite `tally_webhook_v2/main.py` to use the Supabase client directly.
- Use `UPSERT` on `users` table by `submission_id`.
- Write form responses into `user_profiles.form_response`.

### Phase 6: Data Migration Script
Create `scripts/migrate_firestore_to_supabase.py`:
1. Stream all documents from Firestore `users` collection.
2. For each document, insert into `users`, `user_profiles`, `credits`, `conversations`, `off_topic_state` tables.
3. Stream `feedback` collection → insert into `feedback` table.
4. Stream `analytics` collection → insert into `analytics_weekly` table.
5. Log counts and any errors.

> [!WARNING]
> The migration script must be run **once** during a maintenance window. Both systems should be tested in parallel before cutting over.

### Phase 7: Cleanup
1. Remove `google-cloud-firestore` from `requirements.txt`.
2. Delete `firestore_user.py`.
3. Remove `GOOGLE_PROJECT_ID` and `database_id` references where they are Firestore-specific.
4. Update `README.md`, `DEPLOYMENT.md`, and `DEPLOYMENT_local.md`.

---

## User Document Shape: Before → After

### Before (Firestore — Single nested document)
```json
{
  "telegramUserId": "12345",
  "submissionId": "abc",
  "name": "Cristian",
  "user_profile": {
    "form_response": { ... },
    "scores": { ... },
    "tags": [ ... ],
    "summary": "..."
  },
  "credits": { "balance": 450, "initial_grant": 500, "total_spent": 50, "used_promos": [] },
  "conversation_history": { "recent_messages": [...], "summary": "..." },
  "usage": { "gemini-2_5-flash": { "total_input_tokens": 1000, ... } },
  "off_topic": { "count": 0, "last_flagged_ts": null, "restricted_until": null }
}
```

### After (Supabase — Normalized across tables)
```
users          → { id, telegram_id, submission_id, name, location, source, created_at }
user_profiles  → { user_id, profile_data (JSONB), form_response (JSONB), summary }
credits        → { user_id, balance, initial_grant, total_spent, used_promos }
conversations  → { user_id, recent_messages (JSONB), summary }
usage_tracking → { user_id, model_name, total_input_tokens, total_output_tokens, call_count }
off_topic_state→ { user_id, count, last_flagged_ts, restricted_until }
```

---

## Key Differences in Code Patterns

### 1. No more `DocumentReference`
**Before:** Functions pass around opaque Firestore `DocumentReference` objects.
**After:** Functions pass `user_id: str` (UUID). The repository handles all DB calls.

### 2. No more `set(merge=True)`
**Before:** Firestore's `merge=True` upserts nested fields without touching siblings.
**After:** Use SQL `INSERT ... ON CONFLICT DO UPDATE` (upsert) or targeted `UPDATE ... SET column = value`.

### 3. No more `transforms.Increment` / `transforms.ArrayUnion`
**Before:** Firestore SDK provides atomic server-side increment and array union.
**After:** SQL provides the same atomicity natively:
- `balance = balance - $cost` (atomic decrement)
- `used_promos = array_append(used_promos, $code)` (array append)
- `ON CONFLICT DO UPDATE SET count = table.count + EXCLUDED.count` (upsert increment)

### 4. User Fetch returns a flat dict, not a nested Firestore document
**Before:** `user_doc["credits"]["balance"]`
**After:** Use a JOIN or separate query. The `UserRepository` can assemble the same nested shape if needed for backward compatibility during migration.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Data loss during migration | Run migration script with dry-run mode first. Keep Firestore read-only for 24h after cutover. |
| Supabase connection limits | Use connection pooling (Supabase provides PgBouncer). Cloud Run's max-instances=1 helps. |
| Breaking the Tally webhook | Deploy the Tally function update separately and test with a Tally test submission first. |
| Downstream `user_doc_ref` usage | Full codebase grep confirms every usage. No dynamic/reflection-based access. |
| Supabase free tier limits | Free tier: 500MB storage, 2 compute hours/day. More than enough for <1M users in dev. Pro @ $25/mo for prod. |

---

## Out of Scope
- Building the Trip Builder frontend (Task 23 scope).
- Changing the LLM provider or Telegram bot logic.
- Implementing Supabase Realtime subscriptions (future enhancement for the builder UI).
- Setting up Row-Level Security (RLS) policies (can be added later when the web frontend exists).

---

## Verification Plan

### Automated Tests
- Adapt existing tests in `tests/` to use the new `UserRepository`.
- Create integration tests that run against a Supabase test project.
- Verify all CRUD operations: create user, link telegram, update profile, deduct credits, record feedback, flush metrics.

### Manual Verification
- Send a Tally test submission → verify it appears in `users` + `user_profiles`.
- Send `/start <submissionId>` in Telegram → verify linking works.
- Send regular messages → verify conversation history, usage tracking, and credit deduction.
- Send `/promo TESTCODE` → verify promo redemption.
- Trigger off-topic guard → verify state persists.
- Wait for metrics flush → verify `analytics_weekly` row updates.

### Parallel Run (Optional but Recommended)
- For 1-2 weeks, write to **both** Firestore and Supabase simultaneously.
- Compare data in both systems to catch any discrepancies.
- Cut over to Supabase-only once confident.
