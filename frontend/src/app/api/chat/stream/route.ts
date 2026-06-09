import { createClient } from "@/utils/supabase/server";

/**
 * POST /api/chat/stream  (Task 37)
 *
 * Streaming counterpart of /api/chat/send. Validates the Supabase session,
 * forwards the message to the FastAPI `/chat/stream` SSE endpoint with the
 * user's access token, and pipes the `text/event-stream` body straight back to
 * the browser without buffering. BACKEND_URL is never exposed to the client.
 */

// Streaming requires the Node runtime; never cache a live stream.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function POST(request: Request): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { session },
    error: authError,
  } = await supabase.auth.getSession();

  if (authError || !session) {
    return jsonError("Unauthorized", 401);
  }

  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return jsonError("BACKEND_URL not configured", 500);
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return jsonError("Invalid JSON", 400);
  }

  let resp: Response;
  try {
    resp = await fetch(`${backendUrl}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    console.error("[/api/chat/stream] backend call failed:", err);
    return jsonError("Backend unreachable", 502);
  }

  if (!resp.ok || !resp.body) {
    const detail = await resp.text().catch(() => "");
    console.error("[/api/chat/stream] backend returned", resp.status, detail);
    return jsonError("Streaming failed", resp.status || 502);
  }

  // Pipe the upstream SSE stream straight through to the client.
  return new Response(resp.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
