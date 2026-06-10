"use client";

import { DNA_TAGS, type TripSummary } from "@/lib/dashboard-data";
import { StatusChip } from "./DashChips";
import { LibraryIcon, PlusIcon, DNAIcon, ChevronRightIcon } from "./DashIcons";

function TripCard({ trip, active, onClick }: { trip: TripSummary; active: boolean; onClick: () => void }) {
  const { cover } = trip;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group w-full text-left rounded-2xl border transition-all overflow-hidden ${
        active
          ? "border-transparent shadow-lg"
          : "border-border hover:border-primary/30 hover:bg-foreground/[0.02]"
      }`}
      style={
        active
          ? {
              background: "color-mix(in oklab, var(--primary) 10%, var(--background))",
              boxShadow: "0 8px 24px -12px color-mix(in oklab, var(--primary) 50%, transparent)",
            }
          : { background: "color-mix(in oklab, var(--background) 70%, transparent)" }
      }
    >
      {/* Cover tile */}
      <div
        className="relative h-20 overflow-hidden"
        style={{
          background: `linear-gradient(135deg, hsl(${cover.hue} 60% ${cover.tone === "warm" ? 52 : 48}%) 0%, hsl(${(cover.hue + 30) % 360} 70% ${cover.tone === "warm" ? 38 : 36}%) 100%)`,
        }}
      >
        <span className="absolute -bottom-1 -right-1 text-[42px] font-black tracking-tight leading-none text-white/30 select-none whitespace-nowrap">
          {cover.label}
        </span>
        <div className="absolute top-2 left-2.5">
          <StatusChip status={trip.status} />
        </div>
      </div>

      <div className="p-3.5">
        <div className="flex items-baseline justify-between gap-2">
          <div className="font-bold text-foreground leading-tight">{trip.destination}</div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground whitespace-nowrap">
            {trip.country.split(" · ")[0]}
          </div>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">{trip.dateRange}</div>
        <div className="mt-2 text-[11px] font-medium text-foreground/70">{trip.dayLabel}</div>
      </div>
    </button>
  );
}

function DNATeaser() {
  return (
    <a
      href="#"
      className="group block rounded-2xl border border-border p-3.5 bg-foreground/[0.02] hover:bg-foreground/[0.04] transition"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] font-bold text-muted-foreground">
          <DNAIcon width={12} height={12} /> Traveler DNA
        </div>
        <ChevronRightIcon
          width={14} height={14}
          className="text-muted-foreground group-hover:text-primary transition"
        />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {DNA_TAGS.map((tag) => (
          <span
            key={tag}
            className="text-[11px] px-2 py-0.5 rounded-full font-medium"
            style={{
              background: "color-mix(in oklab, var(--primary) 12%, transparent)",
              color: "color-mix(in oklab, var(--primary) 80%, var(--foreground))",
            }}
          >
            {tag}
          </span>
        ))}
      </div>
    </a>
  );
}

interface TripLibraryProps {
  summaries: TripSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew?: () => void;
}

export function TripLibrary({ summaries, activeId, onSelect, onNew }: TripLibraryProps) {
  return (
    <aside className="aletheia-card flex flex-col h-full overflow-hidden">
      <header className="px-4 pt-4 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LibraryIcon width={16} height={16} className="text-muted-foreground" />
          <span className="text-sm font-bold tracking-tight">Journeys</span>
        </div>
        <button
          type="button"
          onClick={onNew}
          className="inline-flex items-center gap-1 text-xs font-semibold rounded-full px-2.5 py-1 bg-foreground/5 hover:bg-primary/10 text-foreground/80 hover:text-primary transition"
        >
          <PlusIcon width={12} height={12} /> New
        </button>
      </header>

      <div className="flex-1 px-3 pb-3 space-y-2.5 overflow-y-auto">
        {summaries.length > 0 ? (
          summaries.map((t) => (
            <TripCard
              key={t.id}
              trip={t}
              active={t.id === activeId}
              onClick={() => onSelect(t.id)}
            />
          ))
        ) : (
          <p className="px-2 py-6 text-xs text-muted-foreground text-center leading-relaxed">
            No journeys yet.<br />Start one in chat.
          </p>
        )}
      </div>

      <div className="px-3 pb-3">
        <DNATeaser />
      </div>
    </aside>
  );
}
