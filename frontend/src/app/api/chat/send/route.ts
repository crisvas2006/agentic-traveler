import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

/**
 * POST /api/chat/send
 *
 * Forwards a chat message to the FastAPI backend with the user's Supabase
 * access token. Backend handles persistence, orchestrator dispatch, and reply.
 *
 * We never expose BACKEND_URL to the client; all backend traffic goes through
 * this Next.js Route Handler.
 */
export async function POST(request: Request) {
  // ── 1. Validate session ─────────────────────────────────────────────────
  const supabase = await createClient();
  const {
    data: { session },
    error: authError,
  } = await supabase.auth.getSession();

  if (authError || !session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // ── 2. Forward to backend ───────────────────────────────────────────────
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json({ error: "BACKEND_URL not configured" }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  try {
    const resp = await fetch(`${backendUrl}/chat/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(body),
    });

    const payload = await resp.json().catch(() => ({}));
    return NextResponse.json(payload, { status: resp.status });
  } catch (err) {
    console.error("[/api/chat/send] backend call failed:", err);
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}
