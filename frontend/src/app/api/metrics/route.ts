import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

/**
 * POST /api/metrics
 *
 * Proxies an allowlisted client UI metric (Task 50 capability surface) to the
 * FastAPI backend with the user's Supabase token. Called fire-and-forget from
 * the client; failures here are non-fatal — analytics must never break the UI.
 */
export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

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
    const resp = await fetch(`${backendUrl}/metrics/event`, {
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
    console.error("[/api/metrics] backend call failed:", err);
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}
