# Task 34: Distributed Rate Limiting & Session Affinity

> Harden the per-user rate limiter so it survives container restarts and works correctly across multiple instances. Optionally explore session affinity (sticky sessions) so a single user's requests always land on the same Cloud Run instance.

## 1. Task Overview

- **Summary:** The current in-memory rate limiter (`_user_timestamps` dict in `webhook.py`) is process-local. It resets on every container restart and gives independent, uncorrelated counts when more than one instance is running. This task evaluates and implements a resilient rate limiting strategy.
- **Background:** Cloud Run can run multiple concurrent instances and restarts containers on deploy, scaling events, or crashes. The Tally webhook and background LLM threads also call `SIGTERM`, which terminates the process abruptly. The current setup means a user who hits the limit can bypass it by waiting for the next container restart (though at current scale of `--max-instances 1` this is acceptable).
- **Primary Owner:** Engineering.

## 2. Objectives & Success Criteria

- **Goals:**
    1. Rate limit state persists across container restarts.
    2. Rate limits apply correctly when more than one instance is running.
    3. (Optional) Evaluate Cloud Run's session affinity as a simpler alternative to distributed state.
- **Definition of Done:**
    - A user who sends 11 messages in 60 seconds is rate-limited even if the container restarts mid-sequence.
    - If session affinity is used, document its limitations (Cloud Run does not guarantee 100% affinity).

## 3. System Context

- **Repositories:** `agentic-traveler/backend`.
- **Architecture Notes:** Flask app served via Gunicorn on Cloud Run. One instance currently (`--max-instances 1`). The Telegram webhook sends one update per HTTP request. There is no long-lived connection.
- **Relevant Specs:** `DEPLOYMENT.md`, `webhook.py`.

## 4. Constraints & Requirements

- **Technical Constraints:** Python 3.13, Cloud Run managed platform, no external process (no Redis installed by default).
- **Operational Constraints:** Must not add significant latency to the webhook response path (rate limit check < 10 ms).
- **Cost Constraint:** Avoid adding a permanently running Redis instance unless scale warrants it — that would eliminate the cost benefits of Cloud Run's scale-to-zero.

## 5. Options Analysis

### Option A: Supabase-backed Rate Limiting (Recommended)

Store `(user_id, window_type, count, window_start)` in a Supabase table with a short TTL enforced by a `pg_cron` job or manual cleanup. Use an atomic `INSERT ... ON CONFLICT UPDATE` to increment the counter.

**Pros:** No new infrastructure. Consistent across all instances and restarts.
**Cons:** One extra DB round-trip per message (~5-15ms). Potential for DB contention at scale.

**Schema:**
```sql
CREATE TABLE rate_limits (
    user_id     TEXT NOT NULL,
    window      TEXT NOT NULL,   -- 'minute' or 'hour'
    count       INT  DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, window)
);
```

**Stored procedure (atomic increment):**
```sql
CREATE OR REPLACE FUNCTION check_and_increment_rate_limit(
    p_user_id TEXT,
    p_window TEXT,        -- 'minute' or 'hour'
    p_max_count INT,
    p_window_seconds INT
) RETURNS BOOL AS $$
DECLARE
    v_now TIMESTAMPTZ := NOW();
    v_count INT;
    v_window_start TIMESTAMPTZ;
BEGIN
    SELECT count, window_start INTO v_count, v_window_start
    FROM rate_limits WHERE user_id = p_user_id AND window = p_window FOR UPDATE;

    -- Reset if window expired
    IF NOT FOUND OR v_now - v_window_start > make_interval(secs := p_window_seconds) THEN
        INSERT INTO rate_limits (user_id, window, count, window_start)
        VALUES (p_user_id, p_window, 1, v_now)
        ON CONFLICT (user_id, window)
        DO UPDATE SET count = 1, window_start = v_now;
        RETURN TRUE;
    END IF;

    IF v_count >= p_max_count THEN
        RETURN FALSE;
    END IF;

    UPDATE rate_limits SET count = count + 1
    WHERE user_id = p_user_id AND window = p_window;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

### Option B: Cloud Run Session Affinity

Enable sticky sessions via the Cloud Run header `X-Goog-Session-Affinity`. Cloud Run will *try* to route repeat requests from the same client to the same instance.

**Pros:** Zero code changes to rate limiting logic.
**Cons:** Cloud Run does **not guarantee** affinity — it is best-effort only. Affinity is client-IP-based, not user-ID-based, so all users behind the same Telegram server IP (common for Telegram's webhook delivery) would share affinity, defeating the purpose.

**Verdict:** Not suitable for Telegram webhook workloads.

### Option C: Keep Current Behavior (Acceptable at Scale=1)

Document explicitly that the rate limiter is process-local and intentionally resets on restart. Keep `--max-instances 1`.

**Pros:** Zero complexity. No extra latency.
**Cons:** Not robust if `--max-instances` is ever increased.

## 6. Implementation Plan (Option A)

1. Create Supabase migration: `rate_limits` table + `check_and_increment_rate_limit` stored procedure.
2. Replace `_check_rate_limit()` in `webhook.py` with a call to the stored procedure via `get_db().rpc(...)`.
3. Keep the existing `_user_timestamps` dict as a **fast path**: check in-memory first; only call Supabase if the in-memory check passes (reduces DB calls for the common case, only goes to DB near the threshold).
4. Add a 30-second TTL cleanup job (use pg_cron in Supabase, or just clean up old rows at check time).
5. Update `DEPLOYMENT.md` with the new env requirements.

## 7. Testing & Validation

- **Unit test:** Mock `get_db().rpc` and verify `_check_rate_limit` returns `False` after the configured limit is reached.
- **Integration test:** Submit 11 messages in rapid succession; verify the 11th is rejected even after a process restart.
- **Load test:** Verify DB round-trip adds < 15ms median overhead.

## 8. Risk Management

- **Risk:** DB latency during rate limit check adds to webhook response time.
  - **Mitigation:** The in-memory fast path (Option A step 3) means the DB is only queried for users close to their limit.
- **Risk:** DB connection pool exhaustion under high concurrency.
  - **Mitigation:** The rate limit RPC is a very short transaction. At current scale (concurrency=10), this is not a concern.

## 9. Delivery & Handoff

- **Deliverables:** `rate_limits` Supabase table, stored procedure, updated `webhook.py`, updated `DEPLOYMENT.md`.
- **Prerequisite:** This is lower priority than current features. Implement when `--max-instances` is increased above 1 or when abuse is observed.
