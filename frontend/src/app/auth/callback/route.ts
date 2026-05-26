import { createClient } from "@/utils/supabase/server";
import { NextResponse } from "next/server";

/** Validates a `next` query param to ensure it stays on the same origin. */
function safeRedirectPath(next: string | null): string {
  if (!next) return "/dashboard";
  // Allow only single-slash relative paths; reject protocol-relative (//),
  // backslash variants, and anything that looks like an absolute URL.
  if (next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")) {
    return next;
  }
  return "/dashboard";
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeRedirectPath(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_callback_failed`);
}
