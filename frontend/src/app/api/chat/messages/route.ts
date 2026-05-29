import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

/**
 * GET /api/chat/messages?before=<id>&limit=<n>
 *
 * Cursor-paginated history. Newest-first. Forwards to the FastAPI backend
 * with the user's Supabase access token.
 */
export async function GET(request: Request) {
  const supabase = await createClient();
  const {
    data: { session },
    error: authError,
  } = await supabase.auth.getSession();

  if (authError || !session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json({ error: "BACKEND_URL not configured" }, { status: 500 });
  }

  const url = new URL(request.url);
  const params = new URLSearchParams();
  const before = url.searchParams.get("before");
  const limit = url.searchParams.get("limit");
  if (before) params.set("before", before);
  if (limit) params.set("limit", limit);

  try {
    const resp = await fetch(`${backendUrl}/chat/messages?${params.toString()}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    const payload = await resp.json().catch(() => ({}));
    return NextResponse.json(payload, { status: resp.status });
  } catch (err) {
    console.error("[/api/chat/messages] backend call failed:", err);
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}
