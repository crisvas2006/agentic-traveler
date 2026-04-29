# Task 26 — Per-User Credit System & Promo Codes

**Status:** ✅ Completed

## Goal

Implement a credit-based usage control system so each user has a finite
balance that is consumed by LLM operations, keeping API costs under control
and enabling monetisation later.

## Scope

### New modules

| File | Purpose |
|---|---|
| `credit_manager.py` | Balance checks, async deduction, promo redemption, cost calculation |
| `promo_codes.py` | Python dict mapping promo code names to credit values |

### Modified modules

| File | Change |
|---|---|
| `agent.py` | Credit gate before LLM call; token record accumulation; async deduction after response |
| `webhook.py` | `/promo` Telegram command; `POST /admin/add-credits` (X-Admin-Key header); `POST /promo/redeem`; credit init on new user signup |
| `usage_tracker.py` | Return `model_name` in result dict |
| `.env` | `DEFAULT_USER_CREDITS`, `ADMIN_API_KEY`, `USD_TO_EUR_RATE` |

### Firestore schema (per user doc)

```
credits:
  balance: int           # current credit balance (≥ 0)
  initial_grant: int     # credits given at signup
  total_spent: int       # lifetime credits consumed
  used_promos: [str]     # promo codes already redeemed
```

## Design decisions

1. **1 credit = 1 eurocent.** Default new-user grant = 500 credits (€5).
2. **Cost formula:** raw USD cost (input + output tokens × model pricing)
   → convert to EUR → multiply by 100 → apply markup → ceil to int → min 1 per successful interaction.
3. **Grounding (Search) cost:** Flat $0.035 per call (grounded prompt).
4. **Async deduction:** credit subtraction happens in a background thread
   so it never delays the Telegram response.
5. **Balance floor:** balance never goes below 0. Deduction caps at current balance.
6. **Credit gate:** checked before any LLM call. If balance < 1, a
   hardcoded message is returned without touching the API.
7. **Promo codes:** stored in a Python dict (`promo_codes.py`); each code
   can only be used once per user (tracked via `credits.used_promos` array).
8. **Admin endpoint:** `POST /admin/add-credits` authenticated via
   `X-Admin-Key` header.

## Pricing table

| Model | Input ($/1M) | Output ($/1M) |
|---|---|---|
| gemini-2.5-flash | $0.30 | $2.50 |
| gemini-2.5-flash-lite | $0.10 | $0.40 |
| gemini-3.0-flash | $0.50 | $3.00 |
| **Google Search (Grounding)** | $0.015 / prompt | (flat) |

## User-facing commands

- `/promo <CODE>` — redeem a promo code from Telegram chat.
- Credits are deducted automatically; when exhausted, a friendly message
  explains options (promo codes, contacting the team).

## Endpoints

- `POST /admin/add-credits` — body: `{"user_id": "<telegramUserId>", "amount": <int>}`, header: `X-Admin-Key: <secret>`
- `POST /promo/redeem` — body: `{"user_id": "<telegramUserId>", "code": "<PROMO_CODE>"}`
