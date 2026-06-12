"use client";

import { useState } from "react";
import type { TripLiveState, TripDay } from "@/lib/dashboard-data";
import { SparklesIcon } from "./DashIcons";

/**
 * LiveStateCard (Task 40, proposal §6.2 #9) — shown only while a trip is
 * LIVING. Surfaces today's mood, the day's anchor activity, and any live
 * alerts. The mood selector fires a single chat message (`onMood`) — the
 * app's chat-first model means the assistant records it into
 * `live_state.last_mood` (MoodCheckinSaga, task 41) rather than a fake local
 * write here.
 */

export const MOODS: { label: string; energy: number; emoji: string }[] = [
  { label: "drained", energy: 1, emoji: "🥱" },
  { label: "tired",   energy: 2, emoji: "😌" },
  { label: "steady",  energy: 3, emoji: "🙂" },
  { label: "good",    energy: 4, emoji: "😄" },
  { label: "buzzing", energy: 5, emoji: "🤩" },
];

/** Shared mood-button grid. Used by LiveStateCard and the chat ephemeral picker. */
export function MoodGrid({
  picked,
  onPick,
}: {
  picked?: string | null;
  onPick: (label: string, energy: number) => void;
}) {
  return (
    <div className="flex gap-1.5">
      {MOODS.map((m) => {
        const active = picked === m.label;
        return (
          <button
            key={m.label}
            type="button"
            onClick={() => onPick(m.label, m.energy)}
            title={m.label}
            className="flex-1 flex flex-col items-center gap-1 py-2 rounded-xl border transition-all hover:scale-[1.04]"
            style={
              active
                ? { background: "linear-gradient(135deg, var(--primary), #9333ea)", borderColor: "transparent", color: "#fff" }
                : { borderColor: "var(--border)", background: "color-mix(in oklab, var(--background) 50%, transparent)" }
            }
          >
            <span className="text-lg leading-none">{m.emoji}</span>
            <span className={`text-[9px] font-semibold uppercase tracking-wide ${active ? "text-white/90" : "text-muted-foreground"}`}>
              {m.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function LiveStateCard({
  liveState, today, onMood,
}: {
  liveState?: TripLiveState;
  today?: TripDay;
  onMood?: (label: string, energy: number) => void;
}) {
  const logged = liveState?.last_mood?.label;
  const [picked, setPicked] = useState<string | null>(logged ?? null);

  const anchor = today?.blocks?.[0];
  const alerts = liveState?.live_alerts ?? [];

  const handlePick = (label: string, energy: number) => {
    setPicked(label);
    onMood?.(label, energy);
  };

  return (
    <section
      className="rounded-2xl border p-4"
      style={{
        background: "color-mix(in oklab, #10b981 8%, var(--background))",
        borderColor: "color-mix(in oklab, #10b981 28%, transparent)",
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-emerald-600 dark:text-emerald-400">
          Right now{liveState?.current_location ? ` · ${liveState.current_location}` : ""}
        </h3>
      </div>

      {/* Mood check-in */}
      <div className="mb-3">
        <p className="text-sm font-semibold mb-2">How are you feeling today?</p>
        <MoodGrid picked={picked} onPick={handlePick} />
      </div>

      {/* Today's anchor */}
      {anchor && (
        <div className="rounded-xl p-3 mb-2" style={{ background: "color-mix(in oklab, var(--background) 60%, transparent)" }}>
          <div className="flex items-center gap-1.5 mb-1">
            <SparklesIcon width={12} height={12} className="text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Today&apos;s anchor</span>
          </div>
          <div className="text-sm font-bold leading-tight">{anchor.title}</div>
          {anchor.why && <p className="text-xs text-muted-foreground leading-relaxed mt-1">{anchor.why}</p>}
        </div>
      )}

      {/* Live alerts */}
      {alerts.map((a, i) => (
        <div key={i} className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1.5 mt-1.5">
          <span aria-hidden>⚠</span>
          <span>{a.text}</span>
        </div>
      ))}
    </section>
  );
}
