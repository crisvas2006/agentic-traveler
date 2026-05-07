@AGENTS.md

# Frontend Architecture & Proactive Guidelines

## Design System & Styling
* **Theme:** Implement a seamless Light/Dark mode toggle using `next-themes`. 
* **Style:** Minimalist, high-contrast, modern UI. Use Tailwind CSS and `shadcn/ui` components. 
* **Responsiveness:** Mobile-first design is mandatory.

## Proactive Completeness (The "Opinionated" Rule)
You are an expert, proactive engineer. When asked to build a feature, you must implement the complete lifecycle:
* If asked for "Login", you MUST automatically include "Logout", "Forgot Password", and robust loading/error states in the UI.
* If asked to fetch data, you MUST implement Skeleton loaders for the loading state and error boundaries for failures.
* Never leave a feature half-finished requiring me to prompt you for the obvious next steps.

## Development Routine
1. Plan -> 2. Write Spec in `/frontend/docs/specs` -> 3. Wait for approval -> 4. Implement -> 5. Update CHANGELOG.md.

## Security & Data Access (Zero Trust)
* **Never Trust the Client:** All data validation and critical logic MUST happen server-side (Next.js Route Handlers, Server Actions, or GCP Python Backend).
* **No Secrets in Browser:** Never prefix a sensitive environment variable with `NEXT_PUBLIC_`. 
* **External APIs:** The Next.js client MUST NEVER call external APIs (like Stripe or GCP) directly. The client calls a Next.js Server Route, which securely attaches the secret and forwards the request.
* **Supabase RLS Mandate:** When creating a new Supabase table, you MUST proactively write the RLS policies in SQL. Apply these standard patterns:
    1. Personal: `auth.uid() = user_id`
    2. Team/Org: `EXISTS (SELECT 1 FROM user_roles WHERE user_roles.user_id = auth.uid() AND user_roles.org_id = target.org_id)`
    3. Public Read / Private Write: `true` for SELECT, `auth.uid() = owner_id` for INSERT/UPDATE/DELETE.