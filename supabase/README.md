# Supabase SQL Reference

This folder documents every SQL statement applied to the Supabase project.

## Files

| File | Where to run | What it covers |
|---|---|---|
| `schema_public.sql` | Supabase → SQL Editor | All `public` schema tables, RPCs, and utility functions |
| `auth_hooks.sql` | Supabase → SQL Editor | Trigger + function that auto-provisions rows when a new auth user signs up |
| `rls_policies.sql` | Supabase → SQL Editor | Row-Level Security policies for all user-facing tables |
| `email_templates.md` | Supabase → Auth → Email Templates | Transactional email HTML (confirm signup, reset password) |

## How to apply

Each `.sql` file is **idempotent** (`CREATE OR REPLACE`, `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`)
so it can be re-run safely if you need to recreate an environment.

**Recommended order for a fresh project:**
1. `schema_public.sql`
2. `auth_hooks.sql`
3. `rls_policies.sql`
4. Apply email templates manually from `email_templates.md`

## Notes

- **Service role key** is required for the backend (Python) and for Next.js Route Handlers
  that write to tables (credits, consents). Never expose it client-side.
- **Publishable key** (`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`) is safe for the browser;
  RLS limits what any client can read/write.
- All tables have RLS enabled by default via the `rls_auto_enable` event trigger.
