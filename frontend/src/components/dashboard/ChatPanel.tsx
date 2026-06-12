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
import type { AvailabilityState } from "@/lib/capabilities";
import { track } from "@/lib/metrics";
import { CapabilitySheet } from "./CapabilitySheet";
import { CapabilityChips } from "./CapabilityChips";
import { MoodGrid } from "./LiveStateCard";
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

/* ── Agent prose (bubble-less, full-width) ─────────────────────────────── */

/**
 * Canonical markdown component map for agent prose (Task 46 AC-5).
 * - h1–h6 all render as one visual heading level (h3 styled via chat-md).
 * - table/thead/tbody/tr/td/th → plain text lines (E1).
 * - img → null (no images in the markdown profile).
 * - code/pre → plain span (E1 variant).
 * - blockquote and links/strong/em are fully supported.
 */
const PROSE_COMPONENTS = {
  // Normalize all heading depths to the single visual level.
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  h4: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  h5: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  h6: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => <h3 {...props}>{children}</h3>,
  // Tables: flatten to plain text lines — never render <table>.
  table: ({ children }: { children?: React.ReactNode }) => <div className="break-words">{children}</div>,
  thead: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  tbody: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  tr: ({ children }: { children?: React.ReactNode }) => <div className="text-sm">{children}</div>,
  th: ({ children }: { children?: React.ReactNode }) => <span className="font-semibold mr-2">{children}</span>,
  td: ({ children }: { children?: React.ReactNode }) => <span className="mr-2">{children}</span>,
  // Images: suppressed per markdown profile.
  img: () => null,
  // Code/pre: rendered as plain inline text.
  code: ({ children }: { children?: React.ReactNode }) => <span>{children}</span>,
  pre: ({ children }: { children?: React.ReactNode }) => <div className="break-words">{children}</div>,
  // Links: open in new tab.
  a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a {...props} target="_blank" rel="noopener noreferrer" />
  ),
};

function AgentProse({
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
      className={`w-full ${highlight ? "chat-msg-flash" : ""}`}
    >
      {/* Attribution row: 6px gradient dot + muted timestamp (spec §7.2) */}
      <div className="chat-prose-attr" aria-hidden="true">
        <span className="chat-prose-attr__dot" />
        <span>{time}</span>
      </div>
      <div
        onContextMenu={(e) => onContextMenu(e, msg)}
        className="chat-md break-words w-full text-sm text-foreground"
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={PROSE_COMPONENTS}
        >
          {msg.body}
        </ReactMarkdown>
      </div>
    </div>
  );
}

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

  // Agent messages now use AgentProse (called from the message list below).
  // ChatBubble only handles user messages.
  return (
    <div
      ref={(el) => registerRef(msg.id, el)}
      className={`flex justify-end ${
        highlight ? "chat-msg-flash" : ""
      }`}
    >
      <div
        onContextMenu={(e) => onContextMenu(e, msg)}
        className="chat-bubble-interactive max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed text-white"
        style={{
          background: errored
            ? "linear-gradient(135deg, #b91c1c, #7f1d1d)"
            : "linear-gradient(135deg, var(--primary), #9333ea)",
          borderBottomRightRadius: 6,
        }}
      >
        <div className="whitespace-pre-wrap break-words">{msg.body}</div>
        <div
          className="text-[10px] mt-1 font-mono select-none text-white/60"
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
  if (ui.kind !== "multi_choice" && ui.kind !== "quick_reply" && ui.kind !== "proposal") return null;
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
      // Proposal (task 45): "Set X" writes the proposed value deterministically
      // (validated server-side against the pending proposal); "Another time" /
      // "Skip" send a plain message that re-engages the advisor / skip path.
      if (ui.kind === "proposal") {
        if (opt.id === "confirm" && opt.value) {
          onSelect([opt.value], opt.label);
        } else {
          onQuickReply(opt.send ?? opt.label, opt.label);
        }
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

export function ChatPanel({
  onCollapse,
  onExpand,
  expandedMode,
  availability = { hasTrip: false },
}: {
  onCollapse?: () => void;
  /** lg+ only: expand the chat over the full dashboard. Not shown on mobile. */
  onExpand?: () => void;
  /** When true the panel is already in expanded mode; toggle becomes a collapse. */
  expandedMode?: boolean;
  /** Capability availability (trip presence/phase, telegram) for the ✨ launcher
   *  and the empty-state chips (Task 50). */
  availability?: AvailabilityState;
}) {
  const {
    messages,
    loading,
    loadingOlder,
    hasMore,
    loadingNewer,
    hasMoreNewer,
    pendingReply,
    error,
    streamStatus,
    streamingText,
    send,
    sendSelection,
    retry,
    loadOlder,
    loadNewer,
    search,
    jumpTo,
    jumpToPresent,
    ephemeralPicker,
    dismissEphemeral,
    registerComposerSetter,
  } = useChat();

  const [isScrolledUp, setIsScrolledUp] = useState(false);

  // ✨ capability launcher (Task 50).
  const [sheetOpen, setSheetOpen] = useState(false);
  const openSheet = useCallback(() => {
    track("capability_sheet_opened", { surface: "composer" });
    setSheetOpen(true);
  }, []);

  const [draft, setDraft] = useState("");

  // Register setDraft with the chat context so useCapabilityLaunch can
  // pre-fill the composer for `draft`-kind capabilities (Task 50).
  useEffect(() => {
    registerComposerSetter(setDraft);
  }, [registerComposerSetter]);
  // Slot prompts the user has answered this session (id → chosen label), so the
  // tapped chips immediately render as answered before the next reply lands.
  const [answered, setAnswered] = useState<Map<number, string>>(() => new Map());
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const hasMoreNewerRef = useRef(hasMoreNewer);
  useEffect(() => {
    hasMoreNewerRef.current = hasMoreNewer;
  }, [hasMoreNewer]);
  const [searchResults, setSearchResults] = useState<ChatMessage[]>([]);
  const [searching, setSearching] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [flashId, setFlashId] = useState<number | null>(null);
  // The id we want to scroll to once its row lands in the DOM. The scroll is
  // driven from a layout effect (not imperatively after `await`) so it rides
  // React's own commit cycle and retries across renders until the row exists.
  const [pendingJumpId, setPendingJumpId] = useState<number | null>(null);
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
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  // True while a jump-to-message navigation is settling: blocks the infinite-
  // scroll loader and the streaming/auto-bottom effects from hijacking it.
  const isJumpingRef = useRef(false);
  // Holds the timer that releases isJumpingRef after a jump scroll. Kept in a
  // ref (not an effect cleanup) so nulling pendingJumpId — which re-runs the
  // scroll effect — can't cancel the release before it fires.
  const jumpReleaseTimerRef = useRef<number | null>(null);

  // Detect system theme to skin the emoji picker.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setTimeout(() => setColorScheme(mq.matches ? "dark" : "light"), 0);
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
      !isJumpingRef.current &&
      prevScrollHeightRef.current > 0 &&
      container.scrollHeight > prevScrollHeightRef.current &&
      container.scrollTop < 120;

    if (prependLikely) {
      const delta = container.scrollHeight - prevScrollHeightRef.current;
      container.scrollTop = container.scrollTop + delta;
    } else if (grew && !hasMoreNewerRef.current && !isJumpingRef.current) {
      // Newest message arrived — stick to bottom if we were near it.
      // Guard: never override an in-flight jump-to-message navigation.
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
  const initialScrollDoneRef = useRef(false);
  useEffect(() => {
    if (!loading && messages.length > 0 && !initialScrollDoneRef.current) {
      initialScrollDoneRef.current = true;
      bottomAnchorRef.current?.scrollIntoView({ behavior: "auto" });
    }
  }, [loading, messages.length]);

  // Keep the streaming reply / status line in view as it grows (only when the
  // user is already near the bottom, so we never yank them up while scrolling).
  // Guard: never override an in-flight jump-to-message navigation.
  useEffect(() => {
    if (!streamingText && !streamStatus) return;
    if (isJumpingRef.current) return;
    const c = scrollRef.current;
    if (!c) return;
    const nearBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 240;
    if (nearBottom) bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamingText, streamStatus]);

  // ── jump-to-message scroll (search result tap) ──────────────────────────
  // Centers the target row in the scroll viewport once it lands in the DOM.
  // Runs after every messages commit; if the row isn't mounted yet (jumpTo's
  // new window is still being fetched/committed) it no-ops and retries on the
  // next commit. getBoundingClientRect math is used instead of
  // Element.scrollIntoView so only THIS scroll container moves — scrollIntoView
  // walks every scrollable ancestor and behaves unpredictably in the nested
  // flex layout.
  useLayoutEffect(() => {
    if (pendingJumpId == null) return;
    const container = scrollRef.current;
    const el = messageRefs.current.get(pendingJumpId);
    if (!container || !el) return; // not mounted yet — wait for the next commit

    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const delta =
      elRect.top - containerRect.top - (container.clientHeight - el.clientHeight) / 2;
    container.scrollTop += delta;

    setFlashId(pendingJumpId);
    setPendingJumpId(null);
    // Release the scroll-load guard once the programmatic scroll settles, so
    // the scroll event it triggers doesn't kick off a loadOlder/loadNewer.
    // Timer lives in a ref so the re-run from nulling pendingJumpId (and its
    // effect cleanup) can't cancel it.
    if (jumpReleaseTimerRef.current) window.clearTimeout(jumpReleaseTimerRef.current);
    jumpReleaseTimerRef.current = window.setTimeout(() => {
      isJumpingRef.current = false;
      jumpReleaseTimerRef.current = null;
    }, 300);
  }, [pendingJumpId, messages]);

  // Clear the jump-release timer on unmount.
  useEffect(() => {
    return () => {
      if (jumpReleaseTimerRef.current) window.clearTimeout(jumpReleaseTimerRef.current);
    };
  }, []);

  // Flash highlight auto-clear (decoupled from the scroll effect so re-renders
  // of pendingJumpId never cut the highlight short).
  useEffect(() => {
    if (flashId == null) return;
    const t = window.setTimeout(() => setFlashId(null), 1600);
    return () => window.clearTimeout(t);
  }, [flashId]);

  // Safety net: if the target never materializes (deleted row, empty window),
  // don't leave the panel stuck in jumping state.
  useEffect(() => {
    if (pendingJumpId == null) return;
    const t = window.setTimeout(() => {
      setPendingJumpId(null);
      isJumpingRef.current = false;
    }, 2500);
    return () => window.clearTimeout(t);
  }, [pendingJumpId]);

  // Infinite scroll up and down
  const onScroll = useCallback(() => {
    if (isJumpingRef.current) return;

    const c = scrollRef.current;
    if (!c) return;
    
    // Near top: load older
    if (c.scrollTop < 200 && hasMore && !loadingOlder) {
      void loadOlder();
    }
    
    // Near bottom: load newer
    const distFromBottom = c.scrollHeight - c.scrollTop - c.clientHeight;
    if (distFromBottom < 200 && hasMoreNewer && !loadingNewer) {
      void loadNewer();
    }

    // Show jump-to-present if far up
    setIsScrolledUp(distFromBottom > 800);
  }, [hasMore, loadingOlder, loadOlder, hasMoreNewer, loadingNewer, loadNewer]);

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
      if (q.trim().length < 3) {
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

  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchResults([]);
  }, []);

  const onSearchKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") closeSearch();
    },
    [closeSearch],
  );

  const handleJumpTo = useCallback(
    async (id: number) => {
      isJumpingRef.current = true;
      // Close search first so the overlay doesn't cover the target row.
      closeSearch();
      // Ensure the window containing `id` is loaded, then hand off to the
      // layout effect, which scrolls once the row is actually in the DOM.
      await jumpTo(id);
      setPendingJumpId(id);
    },
    [jumpTo, closeSearch],
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
    const scrollContainer = scrollRef.current;
    scrollContainer?.addEventListener("scroll", closeContextMenu);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", closeContextMenu);
      scrollContainer?.removeEventListener("scroll", closeContextMenu);
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

  // Focus search input without browser-native scroll.
  // Using autoFocus causes browsers to restore the pre-focus scroll position
  // when the input unmounts, which snaps the chat back to the bottom.
  useEffect(() => {
    if (searchOpen && searchInputRef.current) {
      searchInputRef.current.focus({ preventScroll: true });
    }
  }, [searchOpen]);

  // Close search on outside click (the search button's second-press is the
  // primary dismiss; this catches clicks on messages / header / footer).
  useEffect(() => {
    if (!searchOpen) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null;
      if (t?.closest("[data-search-panel]") || t?.closest("[data-search-btn]")) return;
      closeSearch();
    };
    const tid = setTimeout(() => document.addEventListener("mousedown", handler), 0);
    return () => {
      clearTimeout(tid);
      document.removeEventListener("mousedown", handler);
    };
  }, [searchOpen, closeSearch]);

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
            data-search-btn
            type="button"
            onClick={() => {
              if (searchOpen) closeSearch();
              else setSearchOpen(true);
            }}
            title="Search past conversation"
            className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:bg-foreground/5 transition"
            aria-label="Search messages"
          >
            <SearchIcon width={14} height={14} />
          </button>
          {/* Expand / collapse toggle — desktop only (AC-9: no affordance on mobile) */}
          {onExpand && (
            <button
              type="button"
              onClick={onExpand}
              title={expandedMode ? "Collapse to pane" : "Expand to full width"}
              aria-label={expandedMode ? "Collapse chat" : "Expand chat"}
              className="hidden lg:grid w-8 h-8 rounded-lg place-items-center text-muted-foreground hover:bg-foreground/5 transition"
            >
              <ExpandToggleIcon expanded={!!expandedMode} />
            </button>
          )}
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

      {/* Scrollable area + overlays — relative wrapper owns positioning */}
      <div className="relative flex-1 min-h-0 flex flex-col">

        {/* Glassmorphic search overlay — floats on top of messages */}
        {searchOpen && (
          <div
            data-search-panel
            className="absolute inset-x-0 top-0 z-30"
            style={{
              background: "color-mix(in oklab, var(--background) 92%, var(--primary) 8%)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              borderBottom: "1.5px solid color-mix(in oklab, var(--primary) 30%, var(--border))",
              boxShadow: "0 6px 24px -4px color-mix(in oklab, var(--foreground) 14%, transparent)",
            }}
          >
            <div className="px-3 py-2.5 space-y-2">
              <input
                ref={searchInputRef}
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  void runSearch(e.target.value)
                }
                onKeyDown={onSearchKeyDown}
                placeholder="Search past conversation… (min 3 chars)"
                className="w-full bg-transparent outline-none text-sm px-3 py-2 rounded-lg border border-border focus:border-primary/40 transition"
              />
              {searching && (
                <div className="text-[11px] text-muted-foreground px-1">Searching…</div>
              )}
              {!searching && searchQuery.trim().length >= 3 && searchResults.length === 0 && (
                <div className="text-[11px] text-muted-foreground px-1">No matches.</div>
              )}
              {searchResults.length > 0 && (
                <div className="max-h-48 overflow-y-auto space-y-1">
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
          </div>
        )}

        {/* Jump-to-present — anchored to the bottom of the content area */}
        {(hasMoreNewer || isScrolledUp) && (
          <div className="absolute inset-x-0 bottom-3 flex justify-center z-20 pointer-events-none">
            <button
              type="button"
              onClick={() => {
                if (hasMoreNewer) void jumpToPresent();
                else bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
              }}
              className="pointer-events-auto flex items-center gap-2 px-4 py-2 rounded-full text-white font-bold text-xs shadow-[0_8px_32px_rgba(147,51,234,0.3)] transition hover:scale-[1.03] active:scale-95"
              style={{
                background: "linear-gradient(135deg, color-mix(in oklab, var(--primary) 85%, transparent), color-mix(in oklab, #9333ea 85%, transparent))",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                animation: "fade-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both",
              }}
            >
              <ChevronDownIcon width={14} height={14} />
              Jump to Present
            </button>
          </div>
        )}

        {/* Messages */}
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5"
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
          <div className="py-8 space-y-4">
            <div className="text-center text-sm text-muted-foreground">
              Say hi to your travel companion <span aria-hidden>👋</span>
            </div>
            <CapabilityChips
              context="empty_chat"
              availability={availability}
              onOpenSheet={openSheet}
            />
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
              // Wrapper registers the ref so handleJumpTo can scroll to this message.
              <div key={m.id} ref={(el) => registerRef(m.id, el)}>
                <SlotChoices
                  ui={ui}
                  time={formatTime(m.created_at)}
                  interactive={interactive}
                  answeredLabels={answered.get(m.id) ?? null}
                  onSelect={(values, label) => handleSelect(m.id, ui.slot, values, label)}
                  onQuickReply={(sendText, label) => handleQuickReply(m.id, sendText, label)}
                />
              </div>
            );
          }
          // Agent messages render as bubble-less prose; user messages keep bubbles.
          if (m.sender_type === "agent") {
            return (
              <AgentProse
                key={m.id}
                msg={m}
                highlight={flashId === m.id}
                registerRef={registerRef}
                onContextMenu={openContextMenu}
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
          <div className="w-full" aria-live="polite">
            {/* Attribution row for streaming agent prose */}
            <div className="chat-prose-attr" aria-hidden="true">
              <span className="chat-prose-attr__dot" />
              <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            </div>
            <div className="chat-md break-words w-full text-sm text-foreground">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={PROSE_COMPONENTS}
              >
                {streamingText}
              </ReactMarkdown>
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

        {/* Ephemeral mood picker (Task 50). Local-only; dismissed on selection or
            when the sheet is re-opened. Disappears on page refresh by design. */}
        {ephemeralPicker === "mood" && (
          <MoodPickerCard
            onPick={(label, energy) => {
              void send(`Mood check-in: feeling ${label} today (energy ${energy}/5).`);
              dismissEphemeral();
            }}
            onDismiss={dismissEphemeral}
          />
        )}

        <div ref={bottomAnchorRef} />
        </div>{/* end scroll area */}
      </div>{/* end relative wrapper */}

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
            onClick={openSheet}
            disabled={pendingReply}
            title="What can I help with?"
            aria-label="What can I help with?"
            className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <SparklesIcon width={16} height={16} />
          </button>

          <button
            type="button"
            onClick={() => setShowEmoji((v) => !v)}
            title="Insert emoji"
            aria-label="Insert emoji"
            className="hidden lg:grid w-8 h-8 rounded-lg place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
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

      <CapabilitySheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        availability={availability}
      />
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

// ── Ephemeral mood picker (Task 50) ──────────────────────────────────────────
// Reuses MoodGrid from LiveStateCard so both surfaces look identical.
function MoodPickerCard({
  onPick,
  onDismiss,
}: {
  onPick: (label: string, energy: number) => void;
  onDismiss: () => void;
}) {
  return (
    <div
      className="mx-auto mb-3 w-full max-w-sm rounded-2xl border border-border p-4"
      style={{ background: "color-mix(in oklab, var(--foreground) 3%, transparent)" }}
      role="group"
      aria-label="Mood check-in"
    >
      <p className="mb-2 text-sm font-semibold">How are you feeling today?</p>
      <MoodGrid onPick={onPick} />
      <button
        type="button"
        onClick={onDismiss}
        className="mt-2 block w-full text-center text-[11px] text-muted-foreground hover:text-foreground transition"
      >
        Dismiss
      </button>
    </div>
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

/** Expand ⤢ / collapse ⤡ toggle icon for the chat panel header (AC-9). */
function ExpandToggleIcon({ expanded, ...props }: { expanded: boolean } & React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" width={14} height={14} {...props}>
      {expanded ? (
        <>
          <path d="M8 3v3a2 2 0 0 1-2 2H3" />
          <path d="M21 8h-3a2 2 0 0 1-2-2V3" />
          <path d="M3 16h3a2 2 0 0 1 2 2v3" />
          <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
        </>
      ) : (
        <>
          <path d="M15 3h6v6" />
          <path d="M9 21H3v-6" />
          <path d="M21 3l-7 7" />
          <path d="M3 21l7-7" />
        </>
      )}
    </svg>
  );
}
