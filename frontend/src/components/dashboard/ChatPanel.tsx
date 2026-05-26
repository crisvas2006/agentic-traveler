"use client";

import { useState } from "react";
import { CHAT_HISTORY } from "@/lib/dashboard-data";
import { SparklesIcon, ChatIcon, MapIcon, LibraryIcon, DNAIcon, RefreshIcon, ChevronDownIcon, SendIcon } from "./DashIcons";

/* ── Single chat bubble ── */
function ChatBubble({ msg }: { msg: typeof CHAT_HISTORY[number] }) {
  const isMe = msg.from === "me";
  return (
    <div className={`flex ${isMe ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isMe ? "text-white" : "text-foreground"
        }`}
        style={
          isMe
            ? {
                background: "linear-gradient(135deg, var(--primary), #9333ea)",
                borderBottomRightRadius: 6,
              }
            : {
                background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
                border: "1px solid var(--border)",
                borderBottomLeftRadius: 6,
              }
        }
      >
        {msg.text}
        <div className={`text-[10px] mt-1 font-mono ${isMe ? "text-white/60" : "text-muted-foreground"}`}>
          {msg.t}
        </div>
      </div>
    </div>
  );
}

/* ── Collapsed strip (icon column) ── */
export function ChatStripIcons({ onExpand }: { onExpand: () => void }) {
  const items = [
    { Icon: MapIcon,     label: "Map"     },
    { Icon: LibraryIcon, label: "Library" },
    { Icon: DNAIcon,     label: "DNA"     },
    { Icon: RefreshIcon, label: "Sync"    },
  ];

  return (
    <aside className="aletheia-card h-full w-14 flex flex-col items-center py-4 gap-2">
      {/* Expand button */}
      <button
        type="button"
        onClick={onExpand}
        className="w-10 h-10 rounded-xl grid place-items-center text-white relative transition hover:scale-105"
        style={{
          background: "linear-gradient(135deg, var(--primary), #9333ea)",
          boxShadow: "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)",
        }}
      >
        <ChatIcon width={18} height={18} />
        <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-[9px] font-bold grid place-items-center bg-emerald-500 text-white">
          2
        </span>
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

/* ── Full chat panel (drawer + mobile full-screen) ── */
export function ChatPanel({ onCollapse }: { onCollapse?: () => void }) {
  const [draft, setDraft] = useState("");

  return (
    <aside className="aletheia-card h-full flex flex-col overflow-hidden">
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
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="w-8 h-8 rounded-lg grid place-items-center text-muted-foreground hover:bg-foreground/5 transition"
          >
            <ChevronDownIcon width={14} height={14} className="rotate-90" />
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2.5">
        <div className="text-[10px] text-center font-mono text-muted-foreground/70 uppercase tracking-widest py-1">
          Today · Wed Apr 16
        </div>
        {CHAT_HISTORY.map((m, i) => (
          <ChatBubble key={i} msg={m} />
        ))}
        {/* Typing indicator */}
        <div className="flex justify-start">
          <div
            className="px-3.5 py-2.5 rounded-2xl text-[11px] text-muted-foreground"
            style={{
              background: "color-mix(in oklab, var(--foreground) 4%, transparent)",
              borderBottomLeftRadius: 6,
            }}
          >
            <span className="inline-flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "120ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "240ms" }} />
            </span>
          </div>
        </div>
      </div>

      <footer className="border-t border-border p-3">
        <div
          className="flex items-end gap-2 rounded-2xl pl-3.5 pr-1.5 py-1.5 border border-border focus-within:border-primary/40 transition"
          style={{ background: "color-mix(in oklab, var(--foreground) 3%, transparent)" }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Tell me about your day…"
            className="flex-1 bg-transparent outline-none text-sm py-2 placeholder:text-muted-foreground"
          />
          <button
            type="button"
            className="w-9 h-9 rounded-xl grid place-items-center text-white transition hover:scale-105"
            style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
          >
            <SendIcon width={14} height={14} />
          </button>
        </div>
      </footer>
    </aside>
  );
}

/* ── Floating bubble (mobile + "floating" desktop variant) ── */
export function ChatBubbleFloating({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute bottom-5 right-5 z-40 px-4 h-12 rounded-full text-white font-semibold text-sm flex items-center gap-2 transition hover:scale-105"
      style={{
        background: "linear-gradient(135deg, var(--primary), #9333ea)",
        boxShadow: "0 16px 36px -10px color-mix(in oklab, var(--primary) 60%, transparent)",
      }}
    >
      <SparklesIcon width={16} height={16} />
      <span>Ask Aletheia</span>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
    </button>
  );
}
