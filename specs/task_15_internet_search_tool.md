# Task 15: Internet Search / Grounding for the Travel Companion

> **STATUS: COMPLETED**

## Summary

Added Google Search grounding to the three sub-agents (Discovery, Planner, Companion)
so travel responses are anchored in current, real-world data when relevant.

## What Was Implemented

### Approach: Gemini Built-in `google_search` Tool
The Gemini API's native grounding feature was chosen over third-party search APIs
because it requires zero extra infrastructure (no API keys, no parsing) and works
seamlessly within the existing `google-genai` SDK.

### Files Changed

| File | Change |
|---|---|
| `discovery_agent.py` | Added `google_search` tool + light governor + `_grounding_used` return |
| `planner_agent.py` | Same as discovery |
| `companion_agent.py` | Same with a **strict governor** to prevent over-triggering |
| `usage_tracker.py` | Detects `grounding_metadata`, logs `grounding_used`, returns `grounding_cost_credits` |
| `credit_manager.py` | Added `GROUNDING_COST_PER_PROMPT_USD`, `calculate_grounding_cost()`, updated `calculate_cost()` |
| `metrics_tracker.py` | Added `_grounding_calls` counter + `record_grounding_used()` + weekly flush |
| `agent.py` | Accumulates grounding cost in `_token_records` via synthetic records; updated system prompt |

## How It Works

1. Each sub-agent includes `types.Tool(google_search=types.ToolGoogleSearch())` in its config.
2. The model autonomously decides when to trigger search (only for time-sensitive queries).
3. Grounding is detected via `response.candidates[0].grounding_metadata.grounding_chunks`.
4. If grounding fired, a synthetic record `{model_name: "grounding", grounding_cost_credits: N}`
   is appended to `_token_records` and deducted from the user's credits asynchronously.
5. The weekly metrics document gains a `grounding_calls` counter.

## Cost Model

- **Rate**: $35 / 1,000 grounded prompts (gemini-2.5-flash)
- **Credits**: `$0.035 × 0.90 EUR/USD × 100 × 2 markup ≈ 6 credits per grounded call`
- **Min**: 1 credit per grounded call (guaranteed by `max(grounding_count, credits)`)

## Search Governors (Prompt-Level)

| Agent | Governor strength |
|---|---|
| Discovery | Light — triggers for visas, advisories, seasonal conditions, event dates |
| Planner | Light — same as discovery |
| Companion | **Strict** — ONLY live opening hours, transport status, today's events, entry requirements |

The Companion's strict governor prevents search from firing on casual in-trip messages
(mood, food suggestions, cultural context, general advice).
