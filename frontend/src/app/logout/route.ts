import { createClient } from "@/utils/supabase/server";
import { NextResponse } from "next/server";

/**
 * POST /logout
 *
 * Signs the user out server-side and redirects to /login.
 * Must be POST to prevent CSRF via <img> or prefetcher-triggered logouts.
 */
export async function POST(request: Request) {
  const supabase = await createClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/login", request.url));
}
