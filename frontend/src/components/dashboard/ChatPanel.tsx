"use client";

import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import dynamic from "next/dynamic";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import TextareaAutosize from "react-textarea-autosize";

import { useChat, type ChatMessage } from "@/hooks/useChat";
import type { UiBlock, UiOption } from "@/hooks/useChatStream";
import {
  SparklesIcon,
  ChatIcon,
  MapIcon,
  LibraryIcon,
  DNAIcon,
  RefreshIcon,
  ChevronDownIcon,
  SendIcon,
} from "./DashIcons";

// emoji-picker-react references `window`. Load on demand.
// next/dynamic loses the wrapped component's prop types; declare a permissive
// shape covering only the props we actually use.
type EmojiPickerProps = {
  onEmojiClick: (emojiData: { emoji: string }) => void;
  theme?: "light" | "dark" | "auto";
  width?: number | string;
  height?: number | string;
  searchPlaceholder?: string;
  skinTonesDisabled?: boolean;
  lazyLoadEmojis?: boolean;
  previewConfig?: { showPreview?: boolean };
};
const EmojiPicker = dynamic(
  () => import("emoji-picker-react").then((m) => m.default),
  { ssr: false },
) as unknown as React.ComponentType<EmojiPickerProps>;

const SOFT_LIMIT = 3000;
const WARN_LIMIT = 3500;
const HARD_LIMIT = 4000;

/* ── Single bubble ─────────────────────────────────────────────────────── */

function ChatBubble({
  msg,
  highlight,
  registerRef,
  onContextMenu,
}: {
  msg: ChatMessage;
  highlight: boolean;
  registerRef: (id: number, el: HTMLDivElement | null) => void;
  onContextMenu: (e: React.MouseEvent, msg: ChatMessage) => void;
}) {
  const isMe = msg.sender_type === "user";
  const errored = !!(msg.metadata && (msg.metadata as { error?: boolean }).error);
  const time = useMemo(() => {
    try {
      return new Date(msg.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }, [msg.created_at]);

  return (
    <div
      ref={(el) => registerRef(msg.id, el)}
      className={`flex ${isMe ? "justify-end" : "justify-start"} ${
        highlight ? "chat-msg-flash" : ""
      }`}
    >
      <div
        onContextMenu={(e) => onContextMenu(e, msg)}
        className={`chat-bubble-interactive max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isMe ? "text-white" : "text-foreground"
        }`}
        style={
          isMe
            ? {
                background: errored
                  ? "linear-gradient(135deg, #b91c1c, #7f1d1d)"
                  : "linear-gradient(135deg, var(--primary), #9333ea)",
                borderBottomRightRadius: 6,
              }
            : {
                background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
                border: "1px solid var(--border)",
                borderBottomLeftRadius: 6,
              }
        }
      >
        {isMe ? (
          <div className="whitespace-pre-wrap break-words">{msg.body}</div>
        ) : (
          <div className="chat-md break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
                  <a {...props} target="_blank" rel="noopener noreferrer" />
                ),
              }}
            >
              {msg.body}
            </ReactMarkdown>
          </div>
        )}
        <div
          className={`text-[10px] mt-1 font-mono select-none ${
            isMe ? "text-white/60" : "text-muted-foreground"
          }`}
          aria-hidden="true"
        >
          {errored ? "failed to send" : time}
        </div>
      </div>
    </div>
  );
}

/* ── Tappable slot choices (Task 43) ───────────────────────────────────── */

/** Extract a valid tappable-choice block from an agent message, or null. */
function getUiBlock(msg: ChatMessage): UiBlock | null {
  const ui = (msg.metadata as { ui?: UiBlock } | undefined)?.ui;
  if (!ui || !Array.isArray(ui.options) || ui.options.length === 0) return null;
  if (ui.kind !== "multi_choice" && ui.kind !== "quick_reply") return null;
  return ui;
}

const SKIP_ID = "skip";

function formatTime(createdAt: string): string {
  try {
    return new Date(createdAt).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

/**
 * Renders a multiple-choice slot prompt as a single, self-contained agent card:
 * the question and its tappable options live in one bubble (not a message plus
 * detached chips). `multi_choice` options fire a deterministic selection —
 * single tap for single-select, or checkboxes + Confirm when `allow_multi`
 * (with "Skip for now" mutually exclusive). `quick_reply` options send their
 * text as a normal message. Once answered (or superseded by a newer prompt) the
 * options render disabled, with the chosen one(s) marked. Mobile-first: options
 * stack on phones, inline-wrap from `sm:` up (CLAUDE.md §3).
 */
function SlotChoices({
  ui,
  time,
  interactive,
  answeredLabels,
  onSelect,
  onQuickReply,
}: {
  ui: UiBlock;
  time: string;
  interactive: boolean;
  /** Chosen labels once answered (comma-joined for multi-select). */
  answeredLabels: string | null;
  onSelect: (values: string[], label: string) => void;
  onQuickReply: (sendText: string, label: string) => void;
}) {
  const [picked, setPicked] = useState<Set<string>>(() => new Set());
  const multi = ui.allow_multi && ui.kind === "multi_choice";
  // Single-select stores exactly one label (which may itself contain a comma);
  // multi-select joins chosen labels with ", " — only then do we split.
  const answeredSet = useMemo(() => {
    if (!answeredLabels) return new Set<string>();
    return multi
      ? new Set(answeredLabels.split(", ").filter(Boolean))
      : new Set([answeredLabels]);
  }, [answeredLabels, multi]);

  const handleTap = useCallback(
    (opt: UiOption) => {
      if (!interactive) return;
      if (ui.kind === "quick_reply") {
        onQuickReply(opt.send ?? opt.label, opt.label);
        return;
      }
      if (multi) {
        setPicked((prev) => {
          const next = new Set(prev);
          if (next.has(opt.id)) {
            next.delete(opt.id);
            return next;
          }
          // "Skip" is exclusive: it clears everything else, and any other pick
          // clears a pending "Skip".
          if (opt.id === SKIP_ID) return new Set([SKIP_ID]);
          next.delete(SKIP_ID);
          next.add(opt.id);
          return next;
        });
        return;
      }
      onSelect([opt.id], opt.label);
    },
    [interactive, multi, ui.kind, onSelect, onQuickReply],
  );

  const handleConfirm = useCallback(() => {
    if (!interactive) return;
    const ids = [...picked];
    const labels = ui.options
      .filter((o) => picked.has(o.id))
      .map((o) => o.label)
      .join(", ");
    // Zero selections + Confirm → treated as skip (spec §6).
    onSelect(ids.length ? ids : [SKIP_ID], labels || "Skip for now");
  }, [interactive, picked, ui.options, onSelect]);

  const canConfirm = multi && interactive;

  return (
    <div className="flex justify-start">
      <div
        className="chat-bubble-interactive max-w-[85%] sm:max-w-[78%] px-3.5 py-3 rounded-2xl text-sm leading-relaxed text-foreground"
        style={{
          background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
          border: "1px solid var(--border)",
          borderBottomLeftRadius: 6,
        }}
      >
        <div className="whitespace-pre-wrap break-words">{ui.prompt}</div>

        <div
          className="mt-3 flex flex-col sm:flex-row sm:flex-wrap gap-2"
          role="group"
          aria-label={ui.prompt}
        >
          {ui.options.map((opt) => {
            // While interactive only multi-select shows persistent marks (the
            // user's in-progress picks); once answered, marks come from the
            // recorded labels (robust if the card remounts).
            const active = interactive
              ? multi && picked.has(opt.id)
              : answeredSet.has(opt.label);
            return (
              <button
                key={opt.id}
                type="button"
                disabled={!interactive}
                onClick={() => handleTap(opt)}
                aria-pressed={multi ? active : undefined}
                className={`text-left text-sm px-3.5 py-2 rounded-xl border transition disabled:cursor-default ${
                  active
                    ? "text-white border-transparent"
                    : "border-border bg-background/40 hover:border-primary/50 hover:bg-foreground/5 disabled:opacity-50 disabled:hover:bg-background/40"
                }`}
                style={
                  active
                    ? { background: "linear-gradient(135deg, var(--primary), #9333ea)" }
                    : undefined
                }
              >
                {active ? "✓ " : ""}
                {opt.label}
              </button>
            );
          })}
        </div>

        {canConfirm ? (
          <button
            type="button"
            onClick={handleConfirm}
            className="mt-3 self-start text-sm px-4 py-2 rounded-xl text-white transition hover:scale-[1.02]"
            style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
          >
            {picked.size > 1 ? `${ui.submit_label ?? "Confirm"} (${picked.size})` : ui.submit_label ?? "Confirm"}
          </button>
        ) : null}

        <div
          className="text-[10px] mt-2 font-mono select-none text-muted-foreground"
          aria-hidden="true"
        >
          {time}
        </div>
      </div>
    </div>
  );
}

/* ── Collapsed strip (icon column) — unchanged ─────────────────────────── */

export function ChatStripIcons({ onExpand }: { onExpand: () => void }) {
  const items = [
    { Icon: MapIcon, label: "Map" },
    { Icon: LibraryIcon, label: "Library" },
    { Icon: DNAIcon, label: "DNA" },
    { Icon: RefreshIcon, label: "Sync" },
  ];

  return (
    <aside className="aletheia-card is-solid h-full w-14 flex flex-col items-center py-4 gap-2">
      <button
        type="button"
        onClick={onExpand}
        className="w-10 h-10 rounded-xl grid place-items-center text-white relative transition hover:scale-105"
        style={{
          background: "linear-gradient(135deg, var(--primary), #9333ea)",
          boxShadow:
            "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)",
        }}
      >
        <ChatIcon width={18} height={18} />
      </button>

      <div className="flex-1 flex flex-col gap-1 mt-2">
        {items.map((it, i) => (
          <button
            key={i}
            type="button"
            title={it.label}
            className="w-10 h-10 rounded-xl grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
          >
            <it.Icon width={16} height={16} />
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onExpand}
        className="w-10 h-10 rounded-xl grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
      >
        <ChevronDownIcon width={16} height={16} className="-rotate-90" />
      </button>
    </aside>
  );
}

/* ── Full chat panel ───────────────────────────────────────────────────── */

export function ChatPanel({ onCollapse }: { onCollapse?: () => void }) {
  const {
    messages,
    loading,
    loadingOlder,
    hasMore,
    pendingReply,
    error,
    streamStatus,
    streamingText,
    send,
    sendSelection,
    retry,
    loadOlder,
    search,
    jumpTo,
  } = useChat();

  const [draft, setDraft] = useState("");
  // Slot prompts the user has answered this session (id → chosen label), so the
  // tapped chips immediately render as answered before the next reply lands.
  const [answered, setAnswered] = useState<Map<number, string>>(() => new Map());
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ChatMessage[]>([]);
  const [searching, setSearching] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [flashId, setFlashId] = useState<number | null>(null);
  const [colorScheme, setColorScheme] = useState<"light" | "dark">("light");
  const [menu, setMenu] = useState<{
    x: number;
    y: number;
    msg: ChatMessage;
    /** Text selected inside the right-clicked bubble, if any. */
    selectedText: string | null;
  } | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const prevScrollHeightRef = useRef<number>(0);
  const prevMessageCountRef = useRef<number>(0);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  // Detect system theme to skin the emoji picker.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setColorScheme(mq.matches ? "dark" : "light");
    const handler = (e: MediaQueryListEvent) =>
      setColorScheme(e.matches ? "dark" : "light");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Register a per-message ref so we can scroll to it on jumpTo.
  const registerRef = useCallback(
    (id: number, el: HTMLDivElement | null) => {
      if (el) messageRefs.current.set(id, el);
      else messageRefs.current.delete(id);
    },
    [],
  );

  // Preserve scroll anchor when older messages prepend; auto-stick to bottom on send.
  useLayoutEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const grew = messages.length > prevMessageCountRef.current;
    const prependLikely =
      grew &&
      prevScrollHeightRef.current > 0 &&
      container.scrollHeight > prevScrollHeightRef.current &&
      container.scrollTop < 120;

    if (prependLikely) {
      const delta = container.scrollHeight - prevScrollHeightRef.current;
      container.scrollTop = container.scrollTop + delta;
    } else if (grew) {
      // Newest message arrived — stick to bottom if we were near it.
      const nearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 200;
      if (nearBottom) {
        bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }

    prevScrollHeightRef.current = container.scrollHeight;
    prevMessageCountRef.current = messages.length;
  }, [messages]);

  // Initial scroll to bottom after the first load completes.
  useEffect(() => {
    if (!loading && messages.length > 0) {
      bottomAnchorRef.current?.scrollIntoView({ behavior: "auto" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // Keep the streaming reply / status line in view as it grows (only when the
  // user is already near the bottom, so we never yank them up while scrolling).
  useEffect(() => {
    if (!streamingText && !streamStatus) return;
    const c = scrollRef.current;
    if (!c) return;
    const nearBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 240;
    if (nearBottom) bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamingText, streamStatus]);

  // Infinite scroll up — trigger when within 80px of top.
  const onScroll = useCallback(() => {
    const c = scrollRef.current;
    if (!c) return;
    if (c.scrollTop < 80 && hasMore && !loadingOlder) {
      void loadOlder();
    }
  }, [hasMore, loadingOlder, loadOlder]);

  // ── send handlers ──────────────────────────────────────────────────────
  const handleSend = useCallback(() => {
    const trimmed = draft.trim();
    if (!trimmed || pendingReply || trimmed.length > HARD_LIMIT) return;
    setDraft("");
    setShowEmoji(false);
    void send(trimmed);
  }, [draft, pendingReply, send]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // ── slot-choice handlers (Task 43) ──────────────────────────────────────
  // Only the latest agent prompt is interactive; older ones (and ones already
  // answered) render disabled.
  const lastAgentId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender_type === "agent") return messages[i].id;
    }
    return null;
  }, [messages]);

  const handleSelect = useCallback(
    (msgId: number, slot: string, values: string[], label: string) => {
      setAnswered((prev) => new Map(prev).set(msgId, label));
      void sendSelection(slot, values, label);
    },
    [sendSelection],
  );

  const handleQuickReply = useCallback(
    (msgId: number, sendText: string, label: string) => {
      setAnswered((prev) => new Map(prev).set(msgId, label));
      void send(sendText);
    },
    [send],
  );

  // ── search handlers ────────────────────────────────────────────────────
  const runSearch = useCallback(
    async (q: string) => {
      setSearchQuery(q);
      if (!q.trim()) {
        setSearchResults([]);
        return;
      }
      setSearching(true);
      try {
        const results = await search(q);
        setSearchResults(results);
      } finally {
        setSearching(false);
      }
    },
    [search],
  );

  const onSearchKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setSearchOpen(false);
        setSearchQuery("");
        setSearchResults([]);
      }
    },
    [],
  );

  const handleJumpTo = useCallback(
    async (id: number) => {
      await jumpTo(id);
      // wait a tick for the row to render
      requestAnimationFrame(() => {
        const el = messageRefs.current.get(id);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          setFlashId(id);
          setTimeout(() => setFlashId(null), 1600);
        }
      });
      setSearchOpen(false);
    },
    [jumpTo],
  );

  // ── context menu (right-click on a bubble) ─────────────────────────────
  const openContextMenu = useCallback((e: React.MouseEvent, msg: ChatMessage) => {
    e.preventDefault();
    // Capture any text the user has highlighted inside THIS bubble.
    // Selections that originated outside the bubble are ignored.
    let selectedText: string | null = null;
    const sel = typeof window !== "undefined" ? window.getSelection() : null;
    if (sel && sel.rangeCount > 0) {
      const raw = sel.toString();
      if (raw.trim()) {
        const range = sel.getRangeAt(0);
        const bubbleEl = e.currentTarget as HTMLElement;
        if (bubbleEl.contains(range.commonAncestorContainer)) {
          selectedText = raw;
        }
      }
    }
    // Position menu inside the viewport — flip if too close to right/bottom.
    const MENU_W = 168;
    const MENU_H = 88;
    const x = Math.min(e.clientX, window.innerWidth - MENU_W - 8);
    const y = Math.min(e.clientY, window.innerHeight - MENU_H - 8);
    setMenu({ x, y, msg, selectedText });
  }, []);

  const closeContextMenu = useCallback(() => setMenu(null), []);

  // Close on outside click, scroll, ESC, or window resize.
  useEffect(() => {
    if (!menu) return;
    const onDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (target?.closest("[data-chat-menu]")) return;
      closeContextMenu();
    };
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") closeContextMenu();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", closeContextMenu);
    scrollRef.current?.addEventListener("scroll", closeContextMenu);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", closeContextMenu);
      scrollRef.current?.removeEventListener("scroll", closeContextMenu);
    };
  }, [menu, closeContextMenu]);

  const handleCopy = useCallback(async (text: string, msgId: number) => {
    if (!text) {
      closeContextMenu();
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(msgId);
      setTimeout(() => setCopiedId((c) => (c === msgId ? null : c)), 1200);
    } catch {
      // older browsers / insecure origins — fall back to a hidden textarea
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        setCopiedId(msgId);
        setTimeout(() => setCopiedId((c) => (c === msgId ? null : c)), 1200);
      } catch {
        /* swallow */
      }
      document.body.removeChild(ta);
    }
    closeContextMenu();
  }, [closeContextMenu]);

  const handleResend = useCallback(async (msg: ChatMessage) => {
    closeContextMenu();
    await retry(msg.id);
  }, [retry, closeContextMenu]);

  // ── emoji ──────────────────────────────────────────────────────────────
  const onEmojiClick = useCallback((emojiData: { emoji: string }) => {
    if (!emojiData?.emoji) return;
    setDraft((d) => {
      const next = d + emojiData.emoji;
      return next.length <= HARD_LIMIT ? next : d;
    });
    composerRef.current?.focus();
  }, []);

  // Close emoji picker on outside click.
  const emojiAnchorRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!showEmoji) return;
    const handler = (e: MouseEvent) => {
      if (
        emojiAnchorRef.current &&
        !emojiAnchorRef.current.contains(e.target as Node)
      ) {
        setShowEmoji(false);
      }
    };
    // Defer so the open-click doesn't immediately close.
    const t = setTimeout(() => document.addEventListener("mousedown", handler), 0);
    return () => {
      clearTimeout(t);
      document.removeEventListener("mousedown", handler);
    };
  }, [showEmoji]);

  // ── derived ────────────────────────────────────────────────────────────
  const draftLen = draft.length;
  const overLimit = draftLen > HARD_LIMIT;
  const counterVisible = draftLen > SOFT_LIMIT;
  const counterColor =
    draftLen > HARD_LIMIT
      ? "text-red-500"
      : draftLen > WARN_LIMIT
        ? "text-amber-500"
        : "text-muted-foreground";

  return (
    <aside className="aletheia-card is-solid h-full flex flex-col overflow-hidden">
      <header className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg grid place-items-center text-white"
            style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
          >
            <SparklesIcon width={14} height={14} />
          </div>
          <div>
            <div className="text-sm font-bold leading-tight">Aletheia</div>
            <div className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              online
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setSearchOpen((v) => !v)}
            title="Search past conversation"
            className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:bg-foreground/5 transition"
            aria-label="Search messages"
          >
            <SearchIcon width={14} height={14} />
          </button>
          {onCollapse && (
            <button
              type="button"
              onClick={onCollapse}
              className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:bg-foreground/5 transition"
            >
              <ChevronDownIcon width={14} height={14} className="rotate-90" />
            </button>
          )}
        </div>
      </header>

      {searchOpen && (
        <div className="border-b border-border px-3 py-2 space-y-2">
          <input
            autoFocus
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              void runSearch(e.target.value)
            }
            onKeyDown={onSearchKeyDown}
            placeholder="Search past conversation…"
            className="w-full bg-transparent outline-none text-sm px-3 py-2 rounded-lg border border-border focus:border-primary/40 transition"
          />
          {searching && (
            <div className="text-[11px] text-muted-foreground px-1">Searching…</div>
          )}
          {!searching && searchQuery && searchResults.length === 0 && (
            <div className="text-[11px] text-muted-foreground px-1">No matches.</div>
          )}
          {searchResults.length > 0 && (
            <div className="max-h-40 overflow-y-auto space-y-1">
              {searchResults.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => void handleJumpTo(r.id)}
                  className="w-full text-left text-xs px-2 py-1.5 rounded hover:bg-foreground/5 transition"
                >
                  <div className="text-muted-foreground text-[10px] font-mono mb-0.5">
                    {new Date(r.created_at).toLocaleDateString()} ·{" "}
                    {r.sender_type === "user" ? "You" : "Aletheia"}
                  </div>
                  <div className="line-clamp-2">{r.body}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5 relative"
      >
        {loadingOlder && (
          <div className="text-center text-[11px] text-muted-foreground py-1">
            Loading…
          </div>
        )}
        {!hasMore && messages.length > 0 && (
          <div className="text-[10px] text-center font-mono text-muted-foreground/60 uppercase tracking-widest py-1">
            Start of conversation
          </div>
        )}

        {loading && (
          <div className="text-center text-sm text-muted-foreground py-8">
            Loading your conversation…
          </div>
        )}

        {!loading && messages.length === 0 && !error && (
          <div className="text-center text-sm text-muted-foreground py-8">
            Say hi to your travel companion <span aria-hidden>👋</span>
          </div>
        )}

        {error && (
          <div className="text-center text-sm text-red-500 py-4 px-3">
            {error}
          </div>
        )}

        {messages.map((m) => {
          const ui = m.sender_type === "agent" ? getUiBlock(m) : null;
          // A choice prompt renders as ONE self-contained card (prompt + chips),
          // so the plain bubble is suppressed to avoid showing the question twice.
          if (ui) {
            const interactive =
              m.id === lastAgentId && !answered.has(m.id) && !pendingReply;
            return (
              <SlotChoices
                key={m.id}
                ui={ui}
                time={formatTime(m.created_at)}
                interactive={interactive}
                answeredLabels={answered.get(m.id) ?? null}
                onSelect={(values, label) => handleSelect(m.id, ui.slot, values, label)}
                onQuickReply={(sendText, label) => handleQuickReply(m.id, sendText, label)}
              />
            );
          }
          return (
            <ChatBubble
              key={m.id}
              msg={m}
              highlight={flashId === m.id}
              registerRef={registerRef}
              onContextMenu={openContextMenu}
            />
          );
        })}

        {/* Streaming reply takes priority; otherwise the paced status line.
            No generic typing dots — only the real intermediary states show
            (Task 37). */}
        {streamingText ? (
          <div className="flex justify-start">
            <div
              className="chat-bubble-interactive max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed text-foreground"
              style={{
                background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
                border: "1px solid var(--border)",
                borderBottomLeftRadius: 6,
              }}
              aria-live="polite"
            >
              <div className="chat-md break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
                      <a {...props} target="_blank" rel="noopener noreferrer" />
                    ),
                  }}
                >
                  {streamingText}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ) : streamStatus ? (
          <div className="flex justify-start">
            <div
              className="flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs text-muted-foreground"
              style={{
                background: "color-mix(in oklab, var(--foreground) 4%, transparent)",
                border: "1px solid var(--border)",
                borderBottomLeftRadius: 6,
              }}
              aria-live="polite"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              <span className="italic">{streamStatus}</span>
            </div>
          </div>
        ) : null}

        <div ref={bottomAnchorRef} />
      </div>

      <footer className="border-t border-border p-3 relative">
        {showEmoji && (
          <div ref={emojiAnchorRef} className="absolute bottom-full left-2 mb-2 z-20">
            <EmojiPicker
              onEmojiClick={onEmojiClick}
              theme={colorScheme}
              width={320}
              height={380}
              searchPlaceholder="Search emoji…"
              skinTonesDisabled
              lazyLoadEmojis
              previewConfig={{ showPreview: false }}
            />
          </div>
        )}

        <div
          className="flex items-end gap-1.5 rounded-2xl pl-2 pr-1.5 py-1.5 border border-border focus-within:border-primary/40 transition"
          style={{ background: "color-mix(in oklab, var(--foreground) 3%, transparent)" }}
        >
          <button
            type="button"
            onClick={() => setShowEmoji((v) => !v)}
            title="Insert emoji"
            aria-label="Insert emoji"
            className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
          >
            <SmileIcon width={16} height={16} />
          </button>

          <TextareaAutosize
            ref={composerRef}
            value={draft}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setDraft(e.target.value)
            }
            onKeyDown={onKeyDown}
            placeholder="Tell me about your day…"
            minRows={1}
            maxRows={6}
            className="flex-1 bg-transparent outline-none text-sm py-1.5 placeholder:text-muted-foreground resize-none"
          />

          <button
            type="button"
            onClick={handleSend}
            disabled={!draft.trim() || pendingReply || overLimit}
            className="w-9 h-9 rounded-xl grid place-items-center text-white transition hover:scale-105 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
            style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
            aria-label="Send message"
          >
            <SendIcon width={14} height={14} />
          </button>
        </div>
        {counterVisible && (
          <div className={`mt-1 text-[10px] font-mono text-right ${counterColor}`}>
            {draftLen} / {HARD_LIMIT}
          </div>
        )}
      </footer>

      {menu && (
        <BubbleContextMenu
          x={menu.x}
          y={menu.y}
          msg={menu.msg}
          selectedText={menu.selectedText}
          copied={copiedId === menu.msg.id}
          onCopy={() =>
            handleCopy(menu.selectedText ?? menu.msg.body, menu.msg.id)
          }
          onResend={() => handleResend(menu.msg)}
        />
      )}
    </aside>
  );
}

/* ── Context menu (right-click on a bubble) ────────────────────────────── */

function BubbleContextMenu({
  x,
  y,
  msg,
  selectedText,
  copied,
  onCopy,
  onResend,
}: {
  x: number;
  y: number;
  msg: ChatMessage;
  selectedText: string | null;
  copied: boolean;
  onCopy: () => void;
  onResend: () => void;
}) {
  const errored = !!(msg.metadata && (msg.metadata as { error?: boolean }).error);
  const copyLabel = copied
    ? "Copied!"
    : selectedText
      ? "Copy selection"
      : "Copy message";

  return (
    <div
      data-chat-menu
      role="menu"
      className="fixed z-50 min-w-[168px] py-1 rounded-lg border border-border shadow-xl text-sm overflow-hidden"
      style={{
        left: x,
        top: y,
        background: "var(--background)",
        boxShadow:
          "0 10px 30px -10px color-mix(in oklab, var(--foreground) 40%, transparent)",
      }}
    >
      {errored && (
        <button
          type="button"
          role="menuitem"
          onClick={onResend}
          className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-foreground/5 transition"
        >
          <RefreshSmallIcon width={14} height={14} />
          <span>Resend</span>
        </button>
      )}
      <button
        type="button"
        role="menuitem"
        onClick={onCopy}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-foreground/5 transition"
      >
        <CopyIcon width={14} height={14} />
        <span>{copyLabel}</span>
      </button>
    </div>
  );
}

/* ── Floating bubble (mobile + "floating" desktop variant) ─────────────── */
export function ChatBubbleFloating({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute bottom-5 right-5 z-40 px-4 h-12 rounded-full text-white font-semibold text-sm flex items-center gap-2 transition hover:scale-105"
      style={{
        background: "linear-gradient(135deg, var(--primary), #9333ea)",
        boxShadow:
          "0 16px 36px -10px color-mix(in oklab, var(--primary) 60%, transparent)",
      }}
    >
      <SparklesIcon width={16} height={16} />
      <span>Ask Aletheia</span>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
    </button>
  );
}

/* ── tiny inline icons (search + smile) — keeps lucide bundle slim ────── */
function SearchIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function SmileIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 14s1.5 2 4 2 4-2 4-2" />
      <circle cx="9" cy="10" r="0.6" fill="currentColor" />
      <circle cx="15" cy="10" r="0.6" fill="currentColor" />
    </svg>
  );
}

function CopyIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}

function RefreshSmallIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}
