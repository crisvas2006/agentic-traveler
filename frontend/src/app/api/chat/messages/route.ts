import { NextResponse } from "next/server";
import { createClient } from "@/utils/supabase/server";

/**
 * GET /api/chat/messages?before=<id>|after=<id>|around=<id>&limit=<n>
 *
 * Cursor-paginated history. Newest-first. Forwards to the FastAPI backend
 * with the user's Supabase access token. All three cursor params must be
 * forwarded: `before` (older page), `after` (newer page — drives loadNewer),
 * and `around` (window centered on an id — drives jump-to-search-result).
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
  const after = url.searchParams.get("after");
  const around = url.searchParams.get("around");
  const limit = url.searchParams.get("limit");
  if (before) params.set("before", before);
  if (after) params.set("after", after);
  if (around) params.set("around", around);
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
