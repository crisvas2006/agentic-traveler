import { createClient } from "@/utils/supabase/server";
import { NextResponse } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";

/** Validates a `next` query param to ensure it stays on the same origin. */
function safeRedirectPath(next: string | null): string {
  if (!next) return "/dashboard";
  if (next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\")) {
    return next;
  }
  return "/dashboard";
}

// Handles email links for: password recovery, email confirmation, magic link
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const next = safeRedirectPath(searchParams.get("next"));

  if (token_hash && type) {
    const supabase = await createClient();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Invalid or expired link
  return NextResponse.redirect(`${origin}/login?error=link_expired`);
}
