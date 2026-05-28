# Supabase dev scripts

One-shot SQL utilities for local/dev work. **Not** part of the production schema —
never run these against a real production database without thinking twice.

## `populate_test_messages.sql`

Seeds a specific user's `direct_ai` chat thread with N predictable rows:

- Body of row N is literally `"test message N"`, so `search "message2000"` jumps
  to the 2000th message.
- Rows alternate `sender_type = user / agent`.
- `created_at` is spaced one minute apart so the oldest is `N` minutes in the
  past and the newest is "now".
- Tagged with `metadata = {"seed": true, "n": N}` so `delete_test_messages.sql`
  can find and remove them without touching real messages.

**Usage:** edit the two values at the top of the file (`target_user_id`,
`n_messages`) and run in Supabase → SQL Editor.

## `delete_test_messages.sql`

Removes everything tagged with `metadata.seed = true` from the target user's
`direct_ai` thread. Real Telegram/web messages are never touched.

**Usage:** edit `target_user_id` to match the user that was populated, then run.
