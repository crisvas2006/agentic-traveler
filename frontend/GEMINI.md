@AGENTS.md

# Frontend Architecture & Proactive Guidelines

## Design System & Styling
* **Theme:** Implement a seamless Light/Dark mode toggle using `next-themes`.
* **Style:** Minimalist, high-contrast, modern UI. Tailwind CSS (v4) is the primary styling tool.
* **Component library — `shadcn/ui` (suggest, don't assume):**
    * `shadcn/ui` is **not currently installed** in this project. Check `package.json` before importing from it.
    * When a feature would benefit from an accessible primitive (Dialog, Sheet, DropdownMenu, Select, Toast, Tooltip, Tabs, Accordion, Skeleton, Form, Command palette, etc.), **propose** adding the relevant shadcn component rather than hand-rolling it from scratch. shadcn copies source into `components/ui/`, so you own and can edit the code — it does not add a heavy runtime dependency.
    * Why prefer it: built on Radix UI primitives (accessibility, focus management, ARIA correct by default), Tailwind-native (no CSS-in-JS conflict), themeable via CSS variables (fits the blue→purple glassmorphic identity and dark/light theming), and unstyled-by-default (works with our mobile-first `sm:`/`md:`/`lg:` workflow).
    * Don't blanket-install the whole library — add components one at a time as a feature actually needs them.
    * If you decide it isn't a good fit for a specific case (e.g. the primitive is so simple that a 10-line custom component is clearer), say so in the spec / PR and build the minimal thing instead.
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