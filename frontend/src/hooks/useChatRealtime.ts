"use client";

import { useEffect, useRef } from "react";

import { createClient } from "@/utils/supabase/client";
import type { ChatMessage } from "./useChat";

/**
 * useChatRealtime (Task 37) — subscribes to INSERTs on `messages` for one
 * thread and forwards new rows to the caller, de-duplicated against rows the
 * SSE stream already finalized.
 *
 * This is the recovery + cross-channel path: if an SSE turn drops before its
 * `done`, the persisted reply still arrives here; Telegram messages and other
 * tabs/devices show up live too. One WebSocket per active tab.
 */

type Options = {
  /** Append a new message row (caller owns the message list + ordering). */
  onInsert: (m: ChatMessage) => void;
  /** True if this id was already rendered via the SSE stream (drop the echo). */
  isFinalized: (id: number) => boolean;
};

function toMessage(row: Record<string, unknown>): ChatMessage | null {
  if (typeof row.id !== "number") return null;
  return {
    id: row.id,
    thread_id: row.thread_id as string | undefined,
    sender_type: row.sender_type as "user" | "agent",
    body: (row.body as string) ?? "",
    source: (row.source as "web" | "telegram" | null) ?? null,
    metadata: (row.metadata as Record<string, unknown>) ?? {},
    created_at: (row.created_at as string) ?? new Date().toISOString(),
  };
}

export function useChatRealtime(threadId: string | null, opts: Options) {
  // Keep the latest callbacks in a ref so changing them never resubscribes.
  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
  }, [opts]);

  useEffect(() => {
    if (!threadId) return;
    const supabase = createClient();
    const channel = supabase
      .channel(`messages:${threadId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "messages",
          filter: `thread_id=eq.${threadId}`,
        },
        (payload) => {
          const msg = toMessage(payload.new as Record<string, unknown>);
          if (!msg) return;
          if (optsRef.current.isFinalized(msg.id)) return; // already shown via SSE
          optsRef.current.onInsert(msg);
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [threadId]);
}
