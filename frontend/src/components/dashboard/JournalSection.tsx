"use client";

import type { TripJournal } from "@/lib/dashboard-data";

/**
 * JournalSection (Task 40, proposal §6.2 #10) — shown only in REMEMBERING /
 * past trips. Read view of captured entries, highlights and regrets; the
 * prompts that capture them are tappable and open the chat (`onAsk`), where
 * the JournalSaga (task 41) records the reply. Text-only by design (no photos
 * in alpha — cost discipline).
 */

const PROMPTS = [
  "What stuck with you?",
  "What surprised you?",
  "What would you do differently?",
];

import { useState } from "react";
import { ChevronDownIcon } from "./DashIcons";
import { Edit2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

export function JournalSection({
  journal, onAsk,
}: {
  journal?: TripJournal;
  onAsk?: (text: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const entries = journal?.entries ?? [];
  const highlights = journal?.highlights ?? [];
  const regrets = journal?.regrets ?? [];
  const hasContent = entries.length > 0 || highlights.length > 0 || regrets.length > 0;
  // New-entry composer (empty); existing entries are summarised in the header
  // badge. Saving sends the note through chat so the JournalSaga (task 41)
  // captures it — there's no direct journal-write endpoint (chat-first model).
  const [text, setText] = useState("");

  return (
    <div className="rounded-xl border border-border overflow-hidden" style={{ background: isOpen ? "color-mix(in oklab, var(--background) 60%, transparent)" : "transparent" }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-3 text-left hover:bg-foreground/[0.03] transition"
      >
        <div className="flex items-center gap-2">
          <Edit2 width={14} height={14} className="text-muted-foreground" />
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-foreground">Journal</span>
          {hasContent && !isOpen && (
            <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-semibold ml-2">
              {entries.length} entries
            </span>
          )}
        </div>
        <ChevronDownIcon width={16} height={16} className={`transition-transform ${isOpen ? "rotate-180" : ""} text-muted-foreground`} />
      </button>

      {isOpen && (
        <div className="px-3.5 pb-4 space-y-4 animate-fade-up">
          <Textarea 
            value={text} 
            onChange={(e) => setText(e.target.value)} 
            placeholder="Capture the trip while it's fresh..." 
            className="min-h-[120px] text-sm resize-y" 
          />
          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-1.5 flex-1">
              {PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => onAsk?.(p)}
                  className="text-[10px] px-2 py-1 rounded-full font-semibold transition hover:bg-foreground/5 text-muted-foreground border border-dashed border-border"
                >
                  {p}
                </button>
              ))}
            </div>
            <Button size="sm" disabled={!text.trim()} onClick={() => {
              const note = text.trim();
              if (note) { onAsk?.(note); setText(""); }
              setIsOpen(false);
            }}>
              Save Note
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
