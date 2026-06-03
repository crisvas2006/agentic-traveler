import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";
import { createServiceClient } from "@/utils/supabase/service";

/**
 * POST /api/account/onboarding-link
 *
 * Generates or retrieves a 7-day tally_submission token and returns
 * the personalized Tally onboarding URL for the user.
 */
export async function POST(request: Request) {
  try {
    // ── 0. Origin check for CSRF defense ────────────────────────────────────
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

    const service = createServiceClient();

    // ── 2. Generate or retrieve 7-day tally_submission token ────────────────
    let idToken: string | null = null;
    const { data: activeTokens, error: activeTokenErr } = await service
      .from("link_tokens")
      .select("token")
      .eq("user_id", user.id)
      .eq("kind", "tally_submission")
      .gt("expires_at", new Date().toISOString())
      .limit(1);

    if (activeTokenErr) {
      console.error("[onboarding-link] failed to check active tokens:", activeTokenErr);
    }

    if (activeTokens && activeTokens.length > 0) {
      idToken = activeTokens[0].token;
    } else {
      const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      const { data: newToken, error: newTokenErr } = await service
        .from("link_tokens")
        .insert({
          user_id: user.id,
          kind: "tally_submission",
          expires_at: expiresAt,
        })
        .select("token")
        .single();

      if (newTokenErr || !newToken) {
        console.error("[onboarding-link] failed to generate tally token:", newTokenErr);
        return NextResponse.json({ error: "Failed to generate token" }, { status: 500 });
      }
      idToken = newToken.token;
    }

    const tallyBaseUrl = process.env.TALLY_FORM_URL;
    if (!tallyBaseUrl) {
      throw new Error("TALLY_FORM_URL environment variable is not set");
    }
    const onboardingUrl = `${tallyBaseUrl}?idToken=${idToken}`;
    return NextResponse.json({ url: onboardingUrl });
  } catch (err) {
    console.error("[onboarding-link] unhandled error:", err);
    return NextResponse.json(
      { error: "Internal server error." },
      { status: 500 }
    );
  }
}
