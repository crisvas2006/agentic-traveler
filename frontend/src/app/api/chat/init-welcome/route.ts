import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";
import { createServiceClient } from "@/utils/supabase/service";

/**
 * POST /api/chat/init-welcome
 *
 * Triggered on dashboard mount if the user does not have traveler DNA tags.
 * Idempotently checks if the welcome message with the onboarding link
 * has already been inserted into the user's direct_ai chat thread.
 * If not, generates a 7-day tally submission link token and inserts
 * a personalized welcome message.
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



    // ── 2. Check if the user already has a completed form response ─────────
    const { data: profile, error: profileErr } = await service
      .from("user_profiles")
      .select("form_response")
      .eq("user_id", user.id)
      .maybeSingle();

    if (profileErr) {
      console.error("[init-welcome] failed to fetch profile:", profileErr);
      return NextResponse.json({ error: "Database error" }, { status: 500 });
    }

    // If form_response is present and non-empty, they already have Traveler DNA
    if (
      profile?.form_response &&
      typeof profile.form_response === "object" &&
      Object.keys(profile.form_response).length > 0
    ) {
      return NextResponse.json({ status: "already_onboarded" });
    }

    // ── 3. Resolve or create direct_ai chat thread ─────────────────────────
    let threadId: string | null = null;
    const { data: existingThread, error: threadErr } = await service
      .from("chat_threads")
      .select("id")
      .eq("owner_user_id", user.id)
      .eq("kind", "direct_ai")
      .maybeSingle();

    if (threadErr) {
      console.error("[init-welcome] failed to select chat thread:", threadErr);
      return NextResponse.json({ error: "Database error" }, { status: 500 });
    }

    if (existingThread) {
      threadId = existingThread.id;
    } else {
      const { data: newThread, error: createThreadErr } = await service
        .from("chat_threads")
        .insert({
          owner_user_id: user.id,
          kind: "direct_ai",
        })
        .select("id")
        .single();

      if (createThreadErr || !newThread) {
        console.error("[init-welcome] failed to create chat thread:", createThreadErr);
        return NextResponse.json({ error: "Failed to initialize thread" }, { status: 500 });
      }
      threadId = newThread.id;
    }

    // ── 4. Idempotency Check — has any message already been sent in this thread? ──
    const { count, error: countErr } = await service
      .from("messages")
      .select("*", { count: "exact", head: true })
      .eq("thread_id", threadId);

    if (countErr) {
      console.error("[init-welcome] failed to check messages count:", countErr);
      return NextResponse.json({ error: "Database error" }, { status: 500 });
    }

    if (count !== null && count > 0) {
      return NextResponse.json({ status: "already_initialized" });
    }

    // ── 5. Generate a 7-day tally_submission token ─────────────────────────
    let idToken: string | null = null;
    const { data: activeTokens, error: activeTokenErr } = await service
      .from("link_tokens")
      .select("token")
      .eq("user_id", user.id)
      .eq("kind", "tally_submission")
      .gt("expires_at", new Date().toISOString())
      .limit(1);

    if (activeTokenErr) {
      console.error("[init-welcome] failed to check active tokens:", activeTokenErr);
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
        console.error("[init-welcome] failed to generate tally token:", newTokenErr);
        return NextResponse.json({ error: "Failed to generate token" }, { status: 500 });
      }
      idToken = newToken.token;
    }

    // ── 6. Insert pre-populated welcome message ────────────────────────────
    const tallyBaseUrl = process.env.TALLY_FORM_URL;
    if (!tallyBaseUrl) {
      throw new Error("TALLY_FORM_URL environment variable is not set");
    }
    const onboardingUrl = `${tallyBaseUrl}?idToken=${idToken}`;
    const welcomeBody = 
      `👋 Welcome to Aletheia Travel! I'm your AI travel companion, ready to help you plan your next adventure, discover hidden gems, and curate seamless itineraries.\n\n` +
      `💡 *A Thoughtful Recommendation for Your Travels*\n\n` +
      `To help me provide highly personalized recommendations tailored to your traveler style, ` +
      `you might enjoy taking 3 minutes to fill out our onboarding questionnaire! It maps out your unique Traveler DNA.\n\n` +
      `Here is your personalized link (valid for 7 days, and you can always generate a new one in website settings):\n` +
      `${onboardingUrl}`;

    const { error: welcomeInsertErr } = await service
      .from("messages")
      .insert({
        thread_id: threadId,
        sender_type: "agent",
        sender_user_id: null,
        body: welcomeBody,
        source: "web",
        metadata: {},
      });

    if (welcomeInsertErr) {
      console.error("[init-welcome] failed to insert welcome message:", welcomeInsertErr);
      return NextResponse.json({ error: "Failed to save welcome message" }, { status: 500 });
    }

    return NextResponse.json({ status: "initialized" });
  } catch (err) {
    console.error("[init-welcome] unhandled error:", err);
    return NextResponse.json(
      { error: "Internal server error." },
      { status: 500 }
    );
  }
}
