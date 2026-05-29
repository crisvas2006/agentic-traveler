"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* eslint-disable react-hooks/exhaustive-deps */

export type ChatMessage = {
  id: number;
  thread_id?: string;
  sender_type: "user" | "agent";
  body: string;
  source?: "web" | "telegram" | null;
  metadata?: Record<string, unknown>;
  created_at: string;
};

type HistoryResponse = { messages: ChatMessage[]; has_more: boolean };
type SendResponse = { user_message: ChatMessage; reply: ChatMessage };
type SearchResponse = { results: ChatMessage[] };

const INITIAL_LIMIT = 30;
const PAGE_LIMIT = 50;

/**
 * useChat — encapsulates state, pagination and search for the dashboard chat.
 *
 * Messages are stored in **ascending** order (oldest first) for rendering;
 * the backend returns DESC, we reverse on insert.
 *
 * Optimistic send: appends a temporary message with a negative id; on success
 * replaces it with the server row and appends the agent reply. On failure the
 * temporary row is marked errored (body kept, optional retry).
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [pendingReply, setPendingReply] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Monotonic counter for optimistic message ids (always negative).
  const tempIdRef = useRef(-1);
  const inflightRef = useRef(false);

  // Mirror of `messages` for closures that need a synchronous read.
  const messagesRef = useRef<ChatMessage[]>([]);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // ── initial load ────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(`/api/chat/messages?limit=${INITIAL_LIMIT}`);
        if (!resp.ok) {
          if (resp.status === 403) {
            // profile_not_provisioned — surface a friendly error
            const body = await resp.json().catch(() => ({}));
            const msg =
              body?.detail?.message ?? "Complete your travel profile to start chatting.";
            if (!cancelled) setError(msg);
          } else {
            if (!cancelled) setError("Couldn't load your conversation.");
          }
          return;
        }
        const data = (await resp.json()) as HistoryResponse;
        if (!cancelled) {
          // Backend returns DESC; reverse for ascending render order.
          setMessages([...data.messages].reverse());
          setHasMore(data.has_more);
        }
      } catch {
        if (!cancelled) setError("Network error.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── load older page ─────────────────────────────────────────────────────
  const loadOlder = useCallback(async () => {
    if (loadingOlder || !hasMore || messages.length === 0) return;
    const oldestId = messages[0].id;
    if (oldestId <= 0) return; // optimistic temp ids — never paginate against them
    setLoadingOlder(true);
    try {
      const resp = await fetch(
        `/api/chat/messages?before=${oldestId}&limit=${PAGE_LIMIT}`,
      );
      if (!resp.ok) return;
      const data = (await resp.json()) as HistoryResponse;
      if (data.messages.length === 0) {
        setHasMore(false);
        return;
      }
      // Prepend in ascending order.
      setMessages((prev) => [...[...data.messages].reverse(), ...prev]);
      setHasMore(data.has_more);
    } finally {
      setLoadingOlder(false);
    }
  }, [messages, hasMore, loadingOlder]);

  // ── send ────────────────────────────────────────────────────────────────
  const send = useCallback(
    async (text: string): Promise<void> => {
      const body = text.trim();
      if (!body || inflightRef.current) return;
      inflightRef.current = true;
      setPendingReply(true);

      // Optimistic append.
      const tempId = tempIdRef.current--;
      const optimistic: ChatMessage = {
        id: tempId,
        sender_type: "user",
        body,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      try {
        const resp = await fetch("/api/chat/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body }),
        });

        if (!resp.ok) {
          // Mark the optimistic row as errored; keep the body for retry.
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempId ? { ...m, metadata: { error: true } } : m,
            ),
          );
          setError("Couldn't send. Please try again.");
          return;
        }

        const data = (await resp.json()) as SendResponse;
        // Replace temp with server row, then append reply.
        setMessages((prev) => {
          const without = prev.filter((m) => m.id !== tempId);
          return [...without, data.user_message, data.reply];
        });
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempId ? { ...m, metadata: { error: true } } : m,
          ),
        );
        setError("Network error.");
      } finally {
        inflightRef.current = false;
        setPendingReply(false);
      }
    },
    [],
  );

  // ── retry a failed message ──────────────────────────────────────────────
  // Removes the failed optimistic row and re-sends its body, reusing send().
  const retry = useCallback(
    async (id: number): Promise<void> => {
      const failed = messagesRef.current.find((m) => m.id === id);
      if (!failed) return;
      const errored = !!(failed.metadata as { error?: boolean } | undefined)
        ?.error;
      if (!errored) return; // only retry rows we marked as errored
      // Drop the failed row, then re-send.
      setMessages((prev) => prev.filter((m) => m.id !== id));
      setError(null);
      await send(failed.body);
    },
    // send is stable (no deps)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // ── search ──────────────────────────────────────────────────────────────
  const search = useCallback(async (q: string): Promise<ChatMessage[]> => {
    const trimmed = q.trim();
    if (!trimmed) return [];
    const resp = await fetch(
      `/api/chat/search?q=${encodeURIComponent(trimmed)}&limit=25`,
    );
    if (!resp.ok) return [];
    const data = (await resp.json()) as SearchResponse;
    return data.results ?? [];
  }, []);

  // ── jump to message id ──────────────────────────────────────────────────
  // Walks loadOlder until the target id is present in the local window.
  const jumpTo = useCallback(
    async (id: number): Promise<void> => {
      if (messagesRef.current.some((m) => m.id === id)) return;
      // Walk backwards until we find it. Bounded to avoid infinite loops.
      for (let i = 0; i < 20; i++) {
        if (!hasMore) break;
        await loadOlder();
        if (messagesRef.current.some((m) => m.id === id)) break;
      }
    },
    [hasMore, loadOlder],
  );

  return {
    messages,
    loading,
    loadingOlder,
    hasMore,
    pendingReply,
    error,
    send,
    retry,
    loadOlder,
    search,
    jumpTo,
  };
}
