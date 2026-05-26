/**
 * Server-side Supabase client — uses the SERVICE ROLE KEY.
 *
 * This client bypasses Row-Level Security entirely.
 * ONLY import this file from:
 *   - Next.js Route Handlers  (src/app/api/**)
 *   - Server Components       (files that do NOT have "use client")
 *
 * Never import from client components — the service role key would leak into
 * the browser bundle. The absence of NEXT_PUBLIC_ prefix enforces this at
 * build time (Next.js will refuse to bundle non-public env vars client-side).
 */
import { createClient } from "@supabase/supabase-js";

export function createServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. " +
        "Add them to .env.local and to the Vercel project environment."
    );
  }

  return createClient(url, key, {
    auth: {
      // Service clients don't need session management
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}
