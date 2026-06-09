"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useChatRealtime } from "./useChatRealtime";
import { useChatStream } from "./useChatStream";

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
type SearchResponse = { results: ChatMessage[] };

const INITIAL_LIMIT = 30;
const PAGE_LIMIT = 50;

/**
 * useChat — state, pagination, search, streaming send, and realtime merge for
 * the dashboard chat.
 *
 * Messages are stored ascending (oldest first). Sending streams the reply via
 * `useChatStream` (SSE): the user sees status lines, then the reply types in,
 * then the finalized rows are appended. `useChatRealtime` merges any rows that
 * arrive out-of-band (a dropped SSE turn recovered from the DB, or Telegram /
 * other tabs), de-duplicated against the ids the SSE stream already finalized.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [pendingReply, setPendingReply] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);

  const stream = useChatStream();

  // Monotonic counter for optimistic message ids (always negative).
  const tempIdRef = useRef(-1);
  const inflightRef = useRef(false);
  // Ids already rendered via the SSE stream — drop the Realtime echo of these.
  const finalizedIdsRef = useRef<Set<number>>(new Set());

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
          const asc = [...data.messages].reverse();
          setMessages(asc);
          setHasMore(data.has_more);
          const tid = asc.find((m) => m.thread_id)?.thread_id ?? null;
          if (tid) setThreadId(tid);
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

  // ── realtime merge (recovery + cross-channel) ─────────────────────────────
  const onRealtimeInsert = useCallback((m: ChatMessage) => {
    // While our own SSE turn is in flight, the backend persists this turn's
    // user (and agent) rows mid-stream, so Realtime echoes them back here
    // before `onDone` can mark their ids finalized — which briefly double-
    // rendered the just-sent bubble. Ignore the web-origin echo; `onDone`
    // reconciles the canonical pair. Telegram / other-tab rows still merge live.
    if (inflightRef.current && m.source === "web") return;
    setMessages((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
  }, []);
  useChatRealtime(threadId, {
    onInsert: onRealtimeInsert,
    isFinalized: (id) => finalizedIdsRef.current.has(id),
  });

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
      setMessages((prev) => [...[...data.messages].reverse(), ...prev]);
      setHasMore(data.has_more);
    } finally {
      setLoadingOlder(false);
    }
  }, [messages, hasMore, loadingOlder]);

  // ── send (streaming) ──────────────────────────────────────────────────────
  const send = useCallback(
    async (text: string): Promise<void> => {
      const body = text.trim();
      if (!body || inflightRef.current) return;
      inflightRef.current = true;
      setPendingReply(true);
      setError(null);

      const tempId = tempIdRef.current--;
      const createdAt = new Date().toISOString();
      setMessages((prev) => [
        ...prev,
        { id: tempId, sender_type: "user", body, created_at: createdAt },
      ]);

      await stream.run(body, {
        onDone: ({ messageId, userMessageId, threadId: tid, text: replyText, ui }) => {
          if (tid) setThreadId((cur) => cur ?? tid);
          if (userMessageId != null) finalizedIdsRef.current.add(userMessageId);
          if (messageId != null) finalizedIdsRef.current.add(messageId);

          setMessages((prev) => {
            // Drop the optimistic row and any rows Realtime may already have
            // inserted for the same ids, then append the canonical pair.
            const without = prev.filter(
              (m) => m.id !== tempId && m.id !== messageId && m.id !== userMessageId,
            );
            const userRow: ChatMessage = {
              id: userMessageId ?? tempId,
              thread_id: tid ?? undefined,
              sender_type: "user",
              body,
              source: "web",
              created_at: createdAt,
            };
            const out = [...without, userRow];
            if (replyText) {
              out.push({
                id: messageId ?? tempIdRef.current--,
                thread_id: tid ?? undefined,
                sender_type: "agent",
                body: replyText,
                source: "web",
                // Carry any tappable-choice block so the chips render on the
                // just-streamed reply (Task 43).
                metadata: ui ? { ui } : undefined,
                created_at: new Date().toISOString(),
              });
            }
            return out;
          });
        },
        onError: () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempId ? { ...m, metadata: { error: true } } : m,
            ),
          );
          setError("Couldn't send. Please try again.");
        },
      });

      inflightRef.current = false;
      setPendingReply(false);
    },
    [stream],
  );

  // ── send a tapped multiple-choice selection (Task 43) ─────────────────────
  // Deterministic slot fills go through the non-streaming /chat/send: the reply
  // is a quick next prompt (or the itinerary), not heavy token streaming. The
  // chosen `label` is shown as the user bubble; the reply carries the next
  // prompt's `metadata.ui` so the following chips render immediately.
  const sendSelection = useCallback(
    async (slot: string, values: string[], label: string): Promise<void> => {
      if (inflightRef.current || values.length === 0) return;
      inflightRef.current = true;
      setPendingReply(true);
      setError(null);

      const tempId = tempIdRef.current--;
      const createdAt = new Date().toISOString();
      setMessages((prev) => [
        ...prev,
        { id: tempId, sender_type: "user", body: label, source: "web", created_at: createdAt },
      ]);

      try {
        const resp = await fetch("/api/chat/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: label, selection: { slot, values } }),
        });
        if (!resp.ok) throw new Error("send failed");
        const data = (await resp.json()) as {
          user_message: ChatMessage;
          reply: ChatMessage;
        };
        const tid = data.user_message?.thread_id ?? null;
        if (tid) setThreadId((cur) => cur ?? tid);
        if (data.user_message?.id != null) finalizedIdsRef.current.add(data.user_message.id);
        if (data.reply?.id != null) finalizedIdsRef.current.add(data.reply.id);

        setMessages((prev) => {
          const without = prev.filter(
            (m) =>
              m.id !== tempId &&
              m.id !== data.user_message?.id &&
              m.id !== data.reply?.id,
          );
          const out = [...without];
          if (data.user_message) out.push(data.user_message);
          if (data.reply) out.push(data.reply);
          return out;
        });
      } catch {
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, metadata: { error: true } } : m)),
        );
        setError("Couldn't send. Please try again.");
      } finally {
        inflightRef.current = false;
        setPendingReply(false);
      }
    },
    [],
  );

  // ── retry a failed message ──────────────────────────────────────────────
  const retry = useCallback(async (id: number): Promise<void> => {
    const failed = messagesRef.current.find((m) => m.id === id);
    if (!failed) return;
    const errored = !!(failed.metadata as { error?: boolean } | undefined)?.error;
    if (!errored) return;
    setMessages((prev) => prev.filter((m) => m.id !== id));
    setError(null);
    await send(failed.body);
  }, []);

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

  // ── jump to message id ────────────────────────────────────────────────────
  const jumpTo = useCallback(
    async (id: number): Promise<void> => {
      if (messagesRef.current.some((m) => m.id === id)) return;
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
    // streaming surface (Task 37)
    streamStatus: stream.status,
    streamingText: stream.streamingText,
    streaming: stream.streaming,
    send,
    sendSelection,
    retry,
    loadOlder,
    search,
    jumpTo,
  };
}
