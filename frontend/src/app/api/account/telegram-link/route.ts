import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

export async function POST(request: Request) {
  // Origin check
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (siteUrl) {
    const origin = request.headers.get("origin");
    if (origin && origin !== siteUrl) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  // Ensure authenticated session
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Resolve and validate bot username from environment
  let botUsername = process.env.TELEGRAM_BOT_USERNAME || "";
  if (!botUsername) {
    console.error("[telegram-link] TELEGRAM_BOT_USERNAME is not configured");
    return NextResponse.json(
      { error: "Server Configuration Error: TELEGRAM_BOT_USERNAME is missing." },
      { status: 500 }
    );
  }
  if (botUsername.startsWith("@")) {
    botUsername = botUsername.substring(1);
  }

  try {
    // Insert a short-lived UUID token into the DB.
    // The UUID (36 chars) + "link_" prefix = 41 bytes — safely inside Telegram's
    // 64-byte hard limit for the ?start= deep-link parameter.
    // (A JWT would be ~160 chars and gets silently dropped by Telegram.)
    const { data, error } = await supabase
      .from("link_tokens")
      .insert({ user_id: user.id })
      .select("token")
      .single();

    if (error || !data) {
      console.error("[telegram-link] Failed to create link token:", error);
      return NextResponse.json(
        { error: "Failed to create link token." },
        { status: 500 }
      );
    }

    const token: string = data.token;
    const launchUrl = `https://t.me/${botUsername}?start=link_${token}`;

    return NextResponse.json({ success: true, token, launchUrl });
  } catch (error) {
    console.error("[telegram-link] Unexpected error:", error);
    return NextResponse.json({ error: "Internal Server Error." }, { status: 500 });
  }
}
