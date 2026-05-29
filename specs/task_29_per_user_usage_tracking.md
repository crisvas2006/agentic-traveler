# Task Spec: Per-User LLM Usage and Cost Tracking in Supabase

- **Summary:** Implement real-time, per-user and per-model token usage logging and accumulation in the Supabase `usage_tracking` table. Every time an LLM call finishes, update the user's aggregate usage for that specific model.
- **Background:** Cost management and usage tracking are critical for our unit economics. While we currently buffer and roll up global weekly metrics into the `analytics_weekly` table, our database schema defines a per-user `usage_tracking` table that is currently empty and unpopulated. We need to wire this table up to our active logging pipeline.
- **Primary Owner:** Lead Developer

---

## 1. Objectives & Success Criteria
### Goals
- Resolve the human traveler's database `users.id` (UUID) from the `user_id` string passed to `log_and_accumulate()` (which can be a Telegram ID string or a Web user UUID).
- Automatically upsert and atomically increment input/output tokens, call counts, grounding queries, and **estimated credit cost** in the `usage_tracking` Supabase table.
- Track estimated credit costs (where `1 credit = 1 eurocent`, i.e., `100 credits = 1 EUR`) per LLM call using `credit_manager.py` pricing formulas with **dynamic turn-level model markups**:
  - **`5x` markup** for cheap models containing `"lite"` (e.g. `gemini-3.1-flash-lite`), providing a safe operational buffer for very low-cost transactions.
  - **`3x` markup** for standard models (e.g. `gemini-3.5-flash`), balancing rich reasoning value with credit balance longevity.
  - **`2x` markup** for search grounding operations, reflecting the higher API costs of Google Search.
- Enhance the global weekly analytics pipeline in `metrics_tracker.py` to aggregate total credits cost per model in the `token_usage` JSONB structure, as well as a top-level `total_cost_credits` weekly column in the `analytics_weekly` table.
- Maintain absolute robustness: any database communication failure during metrics accumulation must be caught and logged as a warning, and must **never** block or fail the primary user conversation webhook.
- Implement comprehensive unit tests confirming exact increment accumulation and cost calculations under both standard and dynamic markup configurations.

### Non-Goals
- We are not implementing in-memory caching or batch flushing of per-user metrics in this task. Capping network traffic via buffer flushing is deferred to a future task when database write performance degrades.

### Definition of Done
- [x] A Postgres migration script creating the necessary table changes, unique constraint, and updated RPC function.
- [x] A Postgres RPC function `accumulate_user_usage` supporting the cost parameter successfully added in the database schema.
- [x] Internal UUID resolution logic integrated inside `usage_tracker.py` to handle both Web and Telegram channels.
- [x] Turn-level credit cost estimation calculated dynamically (5x for lite, 3x for others, 2x for grounding) using `credit_manager.calculate_cost()`.
- [x] Database upserts successfully executed turn-wide when `total_tokens > 0` or grounding is used.
- [x] Weekly analytics summary modified in `metrics_tracker.py` to aggregate `total_cost_credits` into both `token_usage` JSONB and a top-level `total_cost_credits` column in the `analytics_weekly` table.
- [x] Fail-safe try/except blocks wrapped around all database writes with clear error logs.
- [x] Unit tests written in `tests/analytics/test_usage_tracker.py` and `tests/analytics/test_metrics_tracker.py` verifying full token/cost tracking accumulation and error resilience.

---

## 2. System Context
- **Services Affected:** `/backend`
- **Files Modified:**
  - `backend/src/agentic_traveler/analytics/usage_tracker.py`
  - `backend/src/agentic_traveler/analytics/metrics_tracker.py`
  - `backend/tests/analytics/test_usage_tracker.py`
  - `backend/tests/analytics/test_metrics_tracker.py`
- **Database Tables:**
  - `public.usage_tracking`
  - `public.analytics_weekly`

### Database Schema Reference (`public.usage_tracking`):
```sql
CREATE TABLE IF NOT EXISTS public.usage_tracking (
  id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id               uuid   REFERENCES public.users(id) ON DELETE SET NULL,
  model_name            text   NOT NULL,
  total_input_tokens    bigint DEFAULT 0,
  total_output_tokens   bigint DEFAULT 0,
  call_count            integer DEFAULT 0,
  grounded_prompt_count integer DEFAULT 0,
  total_cost_credits    bigint DEFAULT 0
);
```

### Database Schema Reference (`public.analytics_weekly`):
```sql
CREATE TABLE IF NOT EXISTS public.analytics_weekly (
  week_ending         date PRIMARY KEY,
  total_interactions  integer DEFAULT 0,
  new_users           integer DEFAULT 0,
  active_users        text[]  DEFAULT '{}',
  agent_calls         jsonb   DEFAULT '{}',
  token_usage         jsonb   DEFAULT '{}', -- enhanced: {model: {input, output, call_count, total_cost_credits}}
  promo_redeemed      jsonb   DEFAULT '{}',
  grounding_calls     integer DEFAULT 0,
  total_cost_credits  bigint  DEFAULT 0, -- new top-level column for total weekly cost
  flushed_at          timestamptz
);
```

---

## 3. Constraints & Requirements
- **Atomic Operations:** Because multiple web chats or webhook calls could process requests concurrently for a single user, we must ensure that updating token and cost values is **atomic** to prevent race conditions or overwritten updates. 
- **Graceful Failures:** Metrics tracking is non-essential telemetry. A database connection timeout, temporary network error, or invalid user ID must **never** trigger an exception that crashes the parent conversational pipeline.
- **Python Compatibility:** All Python code must be written in Python 3.13 and use our established `get_db()` client helper from `agentic_traveler.tools.db_client`.

---

## 4. Inputs & Resources
- **Repository codebase:** `/backend`
- **Supabase RPC pattern:** We can leverage standard Supabase RPC calls from the Python library:
  `get_db().rpc("function_name", {params}).execute()`

---

## 5. Implementation Plan

### Step 1: Create Postgres Migration for Tables, Unique Constraint, and RPC
To handle atomic updates safely in a single database roundtrip, we will create a dedicated Postgres RPC function in our schema, add unique constraints, and add the cost columns.

Add the following SQL migration definition (to be applied to the Supabase database):
```sql
-- 1. Alter usage_tracking to add cost column if not present
ALTER TABLE public.usage_tracking 
  ADD COLUMN IF NOT EXISTS total_cost_credits bigint DEFAULT 0;

-- 2. Alter analytics_weekly to add cost column if not present
ALTER TABLE public.analytics_weekly
  ADD COLUMN IF NOT EXISTS total_cost_credits bigint DEFAULT 0;

-- 3. Add the unique constraint on (user_id, model_name) to support ON CONFLICT
ALTER TABLE public.usage_tracking 
  DROP CONSTRAINT IF EXISTS usage_tracking_user_model_uniq;
ALTER TABLE public.usage_tracking 
  ADD CONSTRAINT usage_tracking_user_model_uniq UNIQUE (user_id, model_name);

-- 4. Create or replace the accumulate_user_usage RPC function
CREATE OR REPLACE FUNCTION public.accumulate_user_usage(
  p_user_id uuid,
  p_model_name text,
  p_input_tokens bigint,
  p_output_tokens bigint,
  p_is_grounded integer,
  p_cost_credits bigint
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO public.usage_tracking (
    user_id,
    model_name,
    total_input_tokens,
    total_output_tokens,
    call_count,
    grounded_prompt_count,
    total_cost_credits
  )
  VALUES (
    p_user_id,
    p_model_name,
    p_input_tokens,
    p_output_tokens,
    1,
    p_is_grounded,
    p_cost_credits
  )
  ON CONFLICT (user_id, model_name)
  DO UPDATE SET
    total_input_tokens  = public.usage_tracking.total_input_tokens + EXCLUDED.total_input_tokens,
    total_output_tokens = public.usage_tracking.total_output_tokens + EXCLUDED.total_output_tokens,
    call_count          = public.usage_tracking.call_count + 1,
    grounded_prompt_count = public.usage_tracking.grounded_prompt_count + EXCLUDED.grounded_prompt_count,
    total_cost_credits  = public.usage_tracking.total_cost_credits + EXCLUDED.total_cost_credits;
END;
$$;
```
> **⚠️ Critical Constraint:** For this upsert to trigger correctly, a **unique constraint** on `(user_id, model_name)` is required. We must add it:
> ```sql
> ALTER TABLE public.usage_tracking 
>   ADD CONSTRAINT usage_tracking_user_model_uniq UNIQUE (user_id, model_name);
> ```

---

### Step 2: Implement Real-Time Logging in `usage_tracker.py`
Inside `backend/src/agentic_traveler/analytics/usage_tracker.py`, we will add user UUID resolution and the database call:

#### 1. Add User ID Resolver:
```python
import uuid
from typing import Optional
from agentic_traveler.tools.user_repo import UserRepository

def _resolve_user_uuid(user_id_str: str) -> Optional[str]:
    """
    Resolve the internal user UUID from the provided ID string.
    Works for both Web users (valid UUID) and Telegram users (telegram_id string).
    """
    if not user_id_str:
        return None
        
    # Check if already a valid UUID (Web User)
    try:
        uuid.UUID(user_id_str)
        return user_id_str
    except ValueError:
        pass
        
    # Otherwise treat as telegram_id string and resolve from DB
    try:
        user_repo = UserRepository()
        return user_repo.get_user_ref_by_telegram_id(user_id_str)
    except Exception:
        logger.warning("Failed to resolve user UUID for telegram_id %s", user_id_str)
        return None
```

#### 2. Wire it into `log_and_accumulate()`:
```python
    # Calculate credit cost using credit_manager formulas
    records = [{"model_name": model_name, "input_tokens": input_tokens, "output_tokens": output_tokens}]
    if grounding_used:
        records.append({
            "model_name": "grounding",
            "grounding_cost_credits": grounding_cost_credits
        })
    cost_credits = _credit_manager.calculate_cost(records)

    # Accumulate directly ONLY for system/background calls (like compaction)
    # which do not go through agent._save_and_finish. User request turns
    # are aggregated and saved at the turn level in agent.py.
    if user_id == "system" and (total_tokens > 0 or grounding_used):
        # 1. Weekly Global Summary buffer
        try:
            from agentic_traveler.analytics import metrics_tracker
            metrics_tracker.record_token_usage(
                agent_name=agent_name,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_cost_credits=cost_credits,
            )
        except Exception:
            logger.exception("Failed to record token usage in metrics_tracker.")

        if grounding_used:
            try:
                from agentic_traveler.analytics import metrics_tracker
                metrics_tracker.record_grounding_used()
            except Exception:
                logger.exception("Failed to record grounding metric.")
```

---

### Step 4: Turn-Level Cost and Credit Consolidation in `agent.py`
To avoid overcharging users on multi-agent turns (e.g. going through both `router` and `chat` using the same cheap model), we perform the per-user metrics tracking and metrics_tracker records at the **end of the turn** inside `_save_and_finish` rather than per LLM call. This ensures tokens for the same model are consolidated first, so the credit ceiling/markup calculations are applied turn-wide.

Inside `backend/src/agentic_traveler/orchestrator/agent.py`, modify `_save_and_finish`:
```python
    if token_records and user_id:
        cost = credit_manager.calculate_cost(token_records)
        if cost > 0:
            credit_manager.deduct_credits_async(user_id, cost)

        # Group token records by model_name to aggregate tokens & grounding
        by_model = {}
        for rec in token_records:
            model = rec.get("model_name")
            if not model:
                continue
            if model not in by_model:
                by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "grounding_used": False,
                    "grounding_cost_credits": 0,
                }
            by_model[model]["input_tokens"] += rec.get("input_tokens", 0)
            by_model[model]["output_tokens"] += rec.get("output_tokens", 0)
            if rec.get("grounding_used"):
                by_model[model]["grounding_used"] = True
                by_model[model]["grounding_cost_credits"] += rec.get("grounding_cost_credits", 0)

        # For each model, calculate the exact aggregated cost for the turn and record it
        for model_name, usage in by_model.items():
            # Build list of records for this model to pass to calculate_cost
            recs = [{
                "model_name": model_name,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            }]
            if usage["grounding_used"]:
                recs.append({
                    "model_name": "grounding",
                    "grounding_cost_credits": usage["grounding_cost_credits"]
                })
            
            # Calculate exact turn-level aggregated cost for this model
            model_cost = credit_manager.calculate_cost(recs)
            
            # 1. Record in weekly global metrics_tracker
            try:
                metrics_tracker.record_token_usage(
                    agent_name="orchestrator",
                    model_name=model_name,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_cost_credits=model_cost,
                )
            except Exception:
                logger.exception("Failed to record aggregated token usage in metrics_tracker.")

            # Record grounding used globally if any
            if usage["grounding_used"]:
                try:
                    metrics_tracker.record_grounding_used()
                except Exception:
                    logger.exception("Failed to record grounding metric in metrics_tracker.")

            # 2. Record in per-user usage_tracking table
            resolved_uuid = usage_tracker._resolve_user_uuid(telegram_user_id)
            if resolved_uuid:
                try:
                    from agentic_traveler.tools.db_client import get_db
                    get_db().rpc("accumulate_user_usage", {
                        "p_user_id": resolved_uuid,
                        "p_model_name": model_name,
                        "p_input_tokens": usage["input_tokens"],
                        "p_output_tokens": usage["output_tokens"],
                        "p_is_grounded": 1 if usage["grounding_used"] else 0,
                        "p_cost_credits": model_cost
                    }).execute()
                except Exception:
                    logger.warning(
                        "Telemetry warning: Failed to accumulate usage in usage_tracking table "
                        "for user_id=%s model=%s. Bypassing.",
                        resolved_uuid, model_name, exc_info=True
                    )
```

---

### Step 3: Implement Weekly Aggregated Cost in `metrics_tracker.py`
We will update `record_token_usage` to accept `total_cost_credits` and accumulate it in `_token_usage` JSONB structure, which gets rolled up into the `analytics_weekly` database table upon Sunday closing.

1. **Update `record_token_usage`**:
```python
def record_token_usage(
    *,
    agent_name: str,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    total_cost_credits: int = 0,
) -> None:
    ...
    with _lock:
        ...
        if safe_model not in _token_usage:
            _token_usage[safe_model] = {"input": 0, "output": 0, "call_count": 0, "total_cost_credits": 0}
        _token_usage[safe_model]["input"] += input_tokens
        _token_usage[safe_model]["output"] += output_tokens
        _token_usage[safe_model]["call_count"] += 1
        _token_usage[safe_model]["total_cost_credits"] += total_cost_credits
```

2. **Update `_write_to_supabase` in `metrics_tracker.py`**:
Aggregate individual model credit costs and write the sum into the new top-level `total_cost_credits` column in the `analytics_weekly` table.
```python
        # Merge token_usage
        merged_token_usage = dict(existing.get("token_usage") or {})
        for model, tokens in snapshot["token_usage"].items():
            existing_model = merged_token_usage.get(model, {"input": 0, "output": 0, "call_count": 0, "total_cost_credits": 0})
            merged_token_usage[model] = {
                "input": existing_model.get("input", 0) + tokens["input"],
                "output": existing_model.get("output", 0) + tokens["output"],
                "call_count": existing_model.get("call_count", 0) + tokens.get("call_count", 0),
                "total_cost_credits": existing_model.get("total_cost_credits", 0) + tokens.get("total_cost_credits", 0),
            }
        merged["token_usage"] = merged_token_usage

        # Aggregate total cost credits globally for the week
        total_cost_credits = sum(
            model_data.get("total_cost_credits", 0)
            for model_data in merged_token_usage.values()
        )
        merged["total_cost_credits"] = total_cost_credits
```

---

## 6. Testing & Validation
### Test Strategy
- **Database Unit Tests:** Add tests inside `backend/tests/analytics/test_usage_tracker.py` that mock the Supabase client calls, verifying that `log_and_accumulate` issues the correct RPC call with exact parameters, including `p_cost_credits`.
- **Metrics Tracker Tests:** Add tests inside `backend/tests/analytics/test_metrics_tracker.py` to verify that global weekly roll-ups properly accumulate `total_cost_credits` under `token_usage` JSONB and set the top-level `total_cost_credits` column.
- **Integration Validation:** Start the local FastAPI server, make an LLM call via the webhook, and verify using the Supabase studio/CLI that a row has been successfully created or updated in both `usage_tracking` and `analytics_weekly` tables with accurate credit calculations.

### Acceptance Test Case (Mock Verification):
```python
def test_usage_tracking_database_accumulation():
    """log_and_accumulate issues correct RPC call to Supabase for usage tracking."""
    resp = _mock_response(prompt_tokens=150, candidates_tokens=70)
    
    with patch("agentic_traveler.tools.db_client.get_db") as mock_get_db, \
         patch("agentic_traveler.analytics.usage_tracker._resolve_user_uuid", return_value="test-uuid-123"):
        
        mock_rpc = MagicMock()
        mock_get_db.return_value.rpc = mock_rpc
        
        log_and_accumulate(
            agent_name="trip",
            model_name="gemini-3.5-flash",
            user_id="user_telegram_id",
            response=resp,
            latency_ms=250,
        )
        
        # Verify the correct RPC was called with accurate parameters (including calculated credits)
        # For gemini-3.5-flash: input=1.50/M, output=9.00/M. Total USD raw = (150*1.5 + 70*9)/1M = 0.000855
        # EUR raw = 0.000855 * 0.9 = 0.0007695
        # credits_used = max(1, ceil(0.0007695 * 100 * 3)) = 1 credit.
        mock_rpc.assert_called_once_with("accumulate_user_usage", {
            "p_user_id": "test-uuid-123",
            "p_model_name": "gemini-3.5-flash",
            "p_input_tokens": 150,
            "p_output_tokens": 70,
            "p_is_grounded": 0,
            "p_cost_credits": 1
        })
```

---

## 7. Risk Management
- **Performance Impact:** Running a database write operation synchronously on every request adds overhead.
  - *Mitigation:* The write is fast and simple, but if latency degrades, we can safely defer this call to a FastAPI `BackgroundTasks` thread.
- **Missing Unique Constraint:** If the unique constraint is missing on the target table, the `ON CONFLICT` clause in the RPC function will fail.
  - *Mitigation:* The unique constraint script MUST be applied to the database before launching this code in production.

---

## 8. Delivery & Handoff
- **PR Deliverables:**
  - Database migration SQL script (`supabase/migrations/002_usage_tracking_cost.sql`).
  - Code changes in `usage_tracker.py` and `metrics_tracker.py`.
  - Comprehensive unit tests in `test_usage_tracker.py` and `test_metrics_tracker.py`.
- **Sign-off:** Approved by Cristian.
