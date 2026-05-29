import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

/**
 * GET /api/chat/search?q=<text>&limit=<n>
 *
 * Full-text search across the authenticated user's chat thread.
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
  const q = url.searchParams.get("q")?.trim() ?? "";
  if (!q) {
    return NextResponse.json({ error: "Missing query" }, { status: 400 });
  }

  const params = new URLSearchParams({ q });
  const limit = url.searchParams.get("limit");
  if (limit) params.set("limit", limit);

  try {
    const resp = await fetch(`${backendUrl}/chat/search?${params.toString()}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
    const payload = await resp.json().catch(() => ({}));
    return NextResponse.json(payload, { status: resp.status });
  } catch (err) {
    console.error("[/api/chat/search] backend call failed:", err);
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}
