import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";
import { createServiceClient } from "@/utils/supabase/service";

/**
 * POST /api/credits/welcome-grant
 *
 * Issues the one-time welcome credit grant to the authenticated user.
 * Amount is controlled by the DEFAULT_USER_CREDITS server-side env var
 * (same name used by the Python backend — default 500).
 *
 * Idempotency: UPDATE only fires when welcome_credits_claimed_at IS NULL.
 *
 * Responses:
 *   200 { status: "granted",        balance: number }
 *   200 { status: "already_claimed" }
 *   401 { error: "Unauthorized" }
 *   500 { error: string }
 */
export async function POST(request: Request) {
  try {
    // ── 0. Origin check — defence-in-depth against same-origin CSRF ──────
    // SameSite cookies are the primary protection; this is a secondary guard.
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (siteUrl) {
      const origin = request.headers.get("origin");
      if (origin && origin !== siteUrl) {
        return NextResponse.json({ error: "Forbidden" }, { status: 403 });
      }
    }

    // ── 1. Validate session ────────────────────────────────────────────────
    const supabase = await createClient();
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // ── 2. Resolve the public.users row ───────────────────────────────────
    // We use the service client here: auth.getUser() already validated the JWT,
    // so filtering by user.id is safe without relying on RLS / auth.uid().
    const service = createServiceClient();

    const { data: publicUser, error: userError } = await service
      .from("users")
      .select("id")
      .eq("auth_id", user.id)
      .maybeSingle();

    if (userError) {
      console.error("[welcome-grant] users lookup failed:", userError);
      return NextResponse.json({ error: "DB lookup failed." }, { status: 500 });
    }
    if (!publicUser) {
      console.error("[welcome-grant] no public.users row for auth_id:", user.id);
      return NextResponse.json(
        { error: "User record not found." },
        { status: 500 }
      );
    }

    // ── 3. Read grant amount (server-side env only — no NEXT_PUBLIC_) ──────
    const creditAmount = parseInt(
      process.env.DEFAULT_USER_CREDITS ?? "100",
      10
    );

    // ── 4. Atomic UPDATE — only fires if not yet claimed ──────────────────
    const { data: updated, error: updateError } = await service
      .from("credits")
      .update({
        balance: creditAmount,
        initial_grant: creditAmount,
        welcome_credits_claimed_at: new Date().toISOString(),
      })
      .eq("user_id", publicUser.id)
      .is("welcome_credits_claimed_at", null) // idempotency guard
      .select("balance")
      .maybeSingle();

    if (updateError) {
      console.error("[welcome-grant] credits update failed:", updateError);
      return NextResponse.json(
        { error: "Failed to grant credits." },
        { status: 500 }
      );
    }

    if (!updated) {
      return NextResponse.json({ status: "already_claimed" });
    }

    return NextResponse.json({ status: "granted", balance: updated.balance });
  } catch (err) {
    // Catch-all: ensures the response is always valid JSON.
    // Typical cause: missing SUPABASE_SERVICE_ROLE_KEY env var.
    console.error("[welcome-grant] unhandled error:", err);
    return NextResponse.json(
      { error: "Internal server error." },
      { status: 500 }
    );
  }
}
