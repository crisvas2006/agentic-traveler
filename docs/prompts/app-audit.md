Systematic Codebase Audit Request
Perform a comprehensive, read-only audit of the entire codebase. Do NOT make any code changes. Analyze the code against the following pillars and provide an ordered list of actionable recommendations, categorized from Critical to Optional:

1. Security & Zero Trust (Critical Priority):

Scan the frontend for any leaked secrets or sensitive logic running on the client ("use client" files).

Verify that all external API calls are securely wrapped in server-side routes or Edge Functions.

Confirm that authentication checks are strictly enforced on all server-side data mutations.

2. Architecture & Modularity:

Identify misplaced logic (e.g., database calls directly inside UI components instead of extracted services).

Evaluate the separation of concerns between data fetching, UI rendering, and state management.

Highlight any tightly coupled components that violate clean architecture.

3. Best Practices & Optimization:

Identify overly complex functions that should be refactored.

Ensure Next.js App Router conventions (RSC vs. Client components) are utilized correctly.