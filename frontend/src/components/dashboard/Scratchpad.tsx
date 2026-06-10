"use client";

import { useState } from "react";
import type { TripScratchpad } from "@/lib/dashboard-data";
import { ChevronDownIcon, CheckIcon, SparklesIcon } from "./DashIcons";

/**
 * Scratchpad (Task 40, proposal §6.2 #8) — saved ideas, packing list, custom
 * notes. Three collapsible groups. Saved-idea chips are tappable: they open
 * the chat with the idea as a question (`onAsk`) — the app is chat-first, so
 * mutations (saving ideas, ticking packing) happen through the assistant
 * rather than fake local writes. The packing group only appears once the trip
 * is close (READY) or underway (LIVING).
 */

function Group({
  title, count, defaultOpen, children,
}: {
  title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-foreground/[0.03] transition"
      >
        <span className="text-xs font-bold flex-1">{title}</span>
        {count !== undefined && count > 0 && (
          <span className="text-[10px] font-semibold text-muted-foreground tabular-nums">{count}</span>
        )}
        <ChevronDownIcon width={14} height={14} className={`text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-3 pb-3 animate-fade-up">{children}</div>}
    </div>
  );
}

export function Scratchpad({
  scratchpad, onAsk,
}: {
  scratchpad?: TripScratchpad;
  onAsk?: (text: string) => void;
}) {
  const ideas = scratchpad?.saved_ideas ?? [];
  const packing = scratchpad?.packing_list ?? [];
  const notes = scratchpad?.custom_notes?.trim();

  // Fully empty -> hide entirely? Or show placeholders?
  // Let's show placeholders for each group to showcase capabilities.

  return (
    <section>
      <div className="flex items-center gap-2 mb-2">
        <SparklesIcon width={14} height={14} className="text-primary" />
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Scratchpad</h3>
      </div>
      <div className="space-y-2">
        {/* Saved ideas */}
        <Group title="Saved ideas" count={ideas.length} defaultOpen={ideas.length > 0}>
          {ideas.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {ideas.map((idea, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onAsk?.(idea.text)}
                  className="text-[11px] px-2.5 py-1 rounded-full font-medium transition hover:scale-[1.03]"
                  style={{
                    background: "color-mix(in oklab, var(--primary) 12%, transparent)",
                    color: "color-mix(in oklab, var(--primary) 85%, var(--foreground))",
                    border: "1px solid color-mix(in oklab, var(--primary) 22%, transparent)",
                  }}
                >
                  {idea.text}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Ask me to <em>save an idea</em> and it lands here.</p>
          )}
        </Group>

        {/* Packing list */}
        <Group title="Packing list" count={packing.length} defaultOpen={packing.length > 0}>
          {packing.length > 0 ? (
            <ul className="space-y-1.5">
              {packing.map((item, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <span
                    className="w-4 h-4 rounded-[5px] grid place-items-center flex-shrink-0"
                    style={
                      item.done
                        ? { background: "linear-gradient(135deg, var(--primary), #9333ea)" }
                        : { border: "1.5px solid color-mix(in oklab, var(--foreground) 25%, transparent)" }
                    }
                  >
                    {item.done && <CheckIcon width={10} height={10} style={{ color: "#fff" }} />}
                  </span>
                  <span className={item.done ? "text-muted-foreground line-through" : ""}>{item.label}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">Tell me what to pack and I&apos;ll build the list.</p>
          )}
        </Group>

        {/* Custom notes */}
        <Group title="Notes" defaultOpen={!!notes}>
          {notes ? (
            <p className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">{notes}</p>
          ) : (
            <p className="text-xs text-muted-foreground">No notes yet — jot one down in chat.</p>
          )}
        </Group>
      </div>
    </section>
  );
}
