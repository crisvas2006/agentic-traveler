"use client";

import { useCallback, useEffect, useRef, useState, createContext, useContext, ReactNode } from "react";

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

// Sort ascending by ID; negative (optimistic) IDs always trail real ones.
function sortByIdAsc(msgs: ChatMessage[]): ChatMessage[] {
  return [...msgs].sort((a, b) => {
    if (a.id < 0 && b.id >= 0) return 1;
    if (b.id < 0 && a.id >= 0) return -1;
    return a.id - b.id;
  });
}

type HistoryResponse = { messages: ChatMessage[]; has_more: boolean; has_more_newer?: boolean };
type SearchResponse = { results: ChatMessage[] };

const INITIAL_LIMIT = 30;
const PAGE_LIMIT = 50;

const ChatContext = createContext<ReturnType<typeof useChatInternal> | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const chat = useChatInternal();
  return <ChatContext.Provider value={chat}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a ChatProvider");
  return ctx;
}

/**
 * useChatInternal — state, pagination, search, streaming send, and realtime merge for
 * the dashboard chat.
 *
 * Messages are stored ascending (oldest first). Sending streams the reply via
 * `useChatStream` (SSE): the user sees status lines, then the reply types in,
 * then the finalized rows are appended. `useChatRealtime` merges any rows that
 * arrive out-of-band (a dropped SSE turn recovered from the DB, or Telegram /
 * other tabs), de-duplicated against the ids the SSE stream already finalized.
 */

// ── Module-level message cache ────────────────────────────────────────────────
// Survives Next.js client-side navigation (e.g. /dashboard → /guide → back)
// but is cleared on full page reload. ChatProvider reads this on mount so
// messages appear instantly without a loading spinner. The realtime subscription
// keeps the list live once mounted.
type MsgCacheEntry = {
  messages: ChatMessage[];
  hasMore: boolean;
  hasMoreNewer: boolean;
  threadId: string | null;
};
let _msgCache: MsgCacheEntry | null = null;

function useChatInternal() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => _msgCache?.messages ?? []);
  const [loading, setLoading] = useState(() => _msgCache === null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMore, setHasMore] = useState(() => _msgCache?.hasMore ?? false);
  const [loadingNewer, setLoadingNewer] = useState(false);
  const [hasMoreNewer, setHasMoreNewer] = useState(() => _msgCache?.hasMoreNewer ?? false);

  // Ephemeral mood picker: local-only, gone on refresh (Task 50).
  const [ephemeralPicker, setEphemeralPicker] = useState<"mood" | null>(null);
  const injectMoodPicker = useCallback(() => setEphemeralPicker("mood"), []);
  const dismissEphemeral = useCallback(() => setEphemeralPicker(null), []);

  // Composer draft setter: ChatPanel registers its setDraft here so that
  // capability launches with kind="draft" can pre-fill the textarea from outside.
  const composerDraftSetterRef = useRef<((text: string) => void) | null>(null);
  const registerComposerSetter = useCallback((fn: (text: string) => void) => {
    composerDraftSetterRef.current = fn;
  }, []);
  const setComposerDraft = useCallback((text: string) => {
    composerDraftSetterRef.current?.(text);
  }, []);

  // Open-chat-panel: desktop and mobile shells register their opener by key.
  // LaunchFromParamInner calls openChatPanel() after firing a capability so
  // the user sees the panel open automatically on arrival from /guide.
  const openChatPanelFnsRef = useRef<Record<string, () => void>>({});
  const registerOpenChatPanel = useCallback((key: string, fn: () => void) => {
    openChatPanelFnsRef.current[key] = fn;
  }, []);
  const openChatPanel = useCallback(() => {
    const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
    openChatPanelFnsRef.current[isDesktop ? "desktop" : "mobile"]?.();
  }, []);

  const [pendingReply, setPendingReply] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(() => _msgCache?.threadId ?? null);

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

  const hasMoreRef = useRef(false);
  useEffect(() => {
    hasMoreRef.current = hasMore;
  }, [hasMore]);

  const loadingOlderRef = useRef(false);
  useEffect(() => {
    loadingOlderRef.current = loadingOlder;
  }, [loadingOlder]);

  const hasMoreNewerRef = useRef(false);
  useEffect(() => {
    hasMoreNewerRef.current = hasMoreNewer;
  }, [hasMoreNewer]);

  const loadingNewerRef = useRef(false);
  useEffect(() => {
    loadingNewerRef.current = loadingNewer;
  }, [loadingNewer]);

  // ── initial load ────────────────────────────────────────────────────────
  // Always runs — even when _msgCache exists — so the Supabase client makes a
  // request on every mount, keeping the auth session active and ensuring other
  // hooks (useTripList, useUserProfile) aren't broken by a stale session on
  // back-navigation. When cache exists: no spinner, messages update silently.
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
            // Only surface the error when we have no cached data to fall back on.
            if (!cancelled && !_msgCache) setError("Couldn't load your conversation.");
          }
          return;
        }
        const data = (await resp.json()) as HistoryResponse;
        if (!cancelled) {
          // Backend returns DESC; reverse for ascending render order.
          const asc = [...data.messages].reverse();
          setMessages(asc);
          setHasMore(data.has_more);
          setHasMoreNewer(data.has_more_newer ?? false);
          const tid = asc.find((m) => m.thread_id)?.thread_id ?? null;
          if (tid) setThreadId(tid);
          _msgCache = { messages: asc, hasMore: data.has_more, hasMoreNewer: data.has_more_newer ?? false, threadId: tid };
        }
      } catch {
        if (!cancelled && !_msgCache) setError("Network error.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── cache sync ────────────────────────────────────────────────────────────
  // Keep _msgCache current so re-mounts (post-navigation) get the latest state.
  useEffect(() => {
    if (messages.length > 0) {
      _msgCache = { messages, hasMore, hasMoreNewer, threadId };
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, hasMore, hasMoreNewer, threadId]);

  // ── realtime merge (recovery + cross-channel) ─────────────────────────────
  const onRealtimeInsert = useCallback((m: ChatMessage) => {
    // While our own SSE turn is in flight, the backend persists this turn's
    // user (and agent) rows mid-stream, so Realtime echoes them back here
    // before `onDone` can mark their ids finalized — which briefly double-
    // rendered the just-sent bubble. Ignore the web-origin echo; `onDone`
    // reconciles the canonical pair. Telegram / other-tab rows still merge live.
    if (inflightRef.current && m.source === "web") return;
    setMessages((prev) => {
      if (prev.some((x) => x.id === m.id)) return prev;
      return sortByIdAsc([...prev, m]);
    });
  }, []);
  useChatRealtime(threadId, {
    onInsert: onRealtimeInsert,
    isFinalized: (id) => finalizedIdsRef.current.has(id),
  });

  // ── load older page ─────────────────────────────────────────────────────
  const loadOlder = useCallback(async (currentOldestId?: number): Promise<ChatMessage[]> => {
    const oldestId = currentOldestId ?? messagesRef.current[0]?.id;
    if (!oldestId || oldestId <= 0) return []; // optimistic temp ids — never paginate against them
    if (loadingOlderRef.current || !hasMoreRef.current) return [];

    loadingOlderRef.current = true;
    setLoadingOlder(true);
    try {
      const resp = await fetch(
        `/api/chat/messages?before=${oldestId}&limit=${PAGE_LIMIT}`,
      );
      if (!resp.ok) return [];
      const data = (await resp.json()) as HistoryResponse;
      if (data.messages.length === 0) {
        setHasMore(false);
        return [];
      }
      
      const asc = [...data.messages].reverse();
      setMessages((prev) => {
        const newIds = new Set(asc.map(m => m.id));
        const filteredPrev = prev.filter(m => !newIds.has(m.id));
        return sortByIdAsc([...asc, ...filteredPrev]);
      });
      setHasMore(data.has_more);
      return asc;
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }, []);

  // ── load newer page ─────────────────────────────────────────────────────
  const loadNewer = useCallback(async (): Promise<boolean> => {
    if (loadingNewerRef.current || !hasMoreNewerRef.current || messagesRef.current.length === 0) return false;
    const newestId = messagesRef.current[messagesRef.current.length - 1].id;
    if (newestId <= 0) return false;

    loadingNewerRef.current = true;
    setLoadingNewer(true);
    try {
      const resp = await fetch(
        `/api/chat/messages?after=${newestId}&limit=${PAGE_LIMIT}`,
      );
      if (!resp.ok) return false;
      const data = (await resp.json()) as HistoryResponse;
      if (data.messages.length === 0) {
        setHasMoreNewer(false);
        return false;
      }
      
      const asc = [...data.messages].reverse();
      setMessages((prev) => {
        const newIds = new Set(asc.map(m => m.id));
        const filteredPrev = prev.filter(m => !newIds.has(m.id));
        return sortByIdAsc([...filteredPrev, ...asc]);
      });
      setHasMoreNewer(data.has_more_newer ?? false);
      return true;
    } finally {
      loadingNewerRef.current = false;
      setLoadingNewer(false);
    }
  }, []);

  // ── jump to present ───────────────────────────────────────────────────────
  const jumpToPresent = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const resp = await fetch(`/api/chat/messages?limit=${INITIAL_LIMIT}`);
      if (!resp.ok) return;
      const data = (await resp.json()) as HistoryResponse;
      const asc = [...data.messages].reverse();
      setMessages(asc);
      setHasMore(data.has_more);
      setHasMoreNewer(data.has_more_newer ?? false);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── send (streaming) ──────────────────────────────────────────────────────
  const send = useCallback(
    async (text: string): Promise<void> => {
      const body = text.trim();
      if (!body || inflightRef.current) return;
      inflightRef.current = true;
      setPendingReply(true);
      setError(null);

      if (hasMoreNewerRef.current) {
        await jumpToPresent();
      }

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

      if (hasMoreNewerRef.current) {
        await jumpToPresent();
      }

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

  // ── send a tapped capability launch (Task 50) ─────────────────────────────
  // Intent-kind launches go through the non-streaming /chat/send with a
  // `capability` id: the backend maps it straight to its saga (no RouterAgent).
  // The `label` shows as the user bubble; the reply carries any next-prompt ui.
  // Mirrors sendSelection (same optimistic + reconcile shape) — see §10.2 of
  // task_50 for the noted DRY opportunity between the two.
  const sendCapability = useCallback(
    async (capability: string, label: string): Promise<void> => {
      if (inflightRef.current) return;
      inflightRef.current = true;
      setPendingReply(true);
      setError(null);

      if (hasMoreNewerRef.current) {
        await jumpToPresent();
      }

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
          body: JSON.stringify({ body: label, capability }),
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
      // If we already have it in the current slice, do nothing.
      if (messagesRef.current.some((m) => m.id === id)) return;
      
      // Otherwise, discard current slice and fetch a window around the target
      setLoading(true);
      try {
        const resp = await fetch(`/api/chat/messages?around=${id}&limit=${PAGE_LIMIT}`);
        if (!resp.ok) return;
        const data = (await resp.json()) as HistoryResponse;
        const asc = [...data.messages].reverse();
        setMessages(asc);
        setHasMore(data.has_more);
        setHasMoreNewer(data.has_more_newer ?? false);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return {
    messages,
    loading,
    loadingOlder,
    hasMore,
    loadingNewer,
    hasMoreNewer,
    pendingReply,
    error,
    // streaming surface (Task 37)
    streamStatus: stream.status,
    streamingText: stream.streamingText,
    streaming: stream.streaming,
    send,
    sendSelection,
    sendCapability,
    retry,
    loadOlder,
    loadNewer,
    search,
    jumpTo,
    jumpToPresent,
    // Task 50 capability surface
    ephemeralPicker,
    injectMoodPicker,
    dismissEphemeral,
    registerComposerSetter,
    setComposerDraft,
    registerOpenChatPanel,
    openChatPanel,
  };
}
