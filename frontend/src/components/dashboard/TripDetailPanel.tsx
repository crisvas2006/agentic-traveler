"use client";

import { useState, useRef, useEffect } from "react";
import type { Trip, TripDay, DayBlock, Density, PanelLayout } from "@/lib/dashboard-data";
import { TypeChip, EnergyBar } from "./DashChips";
import {
  SparklesIcon, RainIcon, ChevronDownIcon, ClockIcon, WalkIcon, CheckIcon,
} from "./DashIcons";
import { CountryIntelStrip } from "./CountryIntelStrip";
import { SafetyWarningBanner } from "./SafetyWarningBanner";
import { LogisticsRail } from "./LogisticsRail";
import { BookingFormSheet } from "./BookingFormSheet";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

/* ── Suggestion card ── */
function SuggestionCard({ s }: { s: NonNullable<TripDay["suggestions"]>[number] }) {
  const Icon = s.kind === "weather" ? RainIcon : SparklesIcon;
  return (
    <article
      className="group rounded-2xl border border-primary/20 p-3.5 transition-all hover:border-primary/40 hover:bg-primary/[0.06]"
      style={{ background: "color-mix(in oklab, var(--primary) 4%, transparent)" }}
    >
      <div className="flex gap-2.5">
        <span
          className="mt-0.5 w-7 h-7 rounded-xl grid place-items-center flex-shrink-0"
          style={{ background: "color-mix(in oklab, var(--primary) 14%, transparent)" }}
        >
          <Icon width={14} height={14} className="text-primary" />
        </span>
        <div className="min-w-0">
          <div className="font-semibold text-sm leading-tight">{s.title}</div>
          <div className="text-xs text-muted-foreground leading-relaxed mt-1">{s.body}</div>
          <div className="mt-2.5 flex gap-2">
            <button
              type="button"
              className="text-[11px] font-bold px-3 py-1 rounded-full text-white"
              style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
            >
              Apply
            </button>
            <button
              type="button"
              className="text-[11px] font-semibold px-3 py-1 rounded-full text-muted-foreground hover:bg-foreground/5"
            >
              Tell me more
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

/* ── Block row atom — shared by all layouts ── */
function BlockRow({
  b, density, idx, current, isDone, onToggleDone,
}: {
  b: DayBlock; density: Density; idx: number; current?: boolean;
  isDone?: boolean; onToggleDone?: () => void;
}) {
  const padding =
    density === "compact" ? "p-2.5" : density === "expanded" ? "p-4" : "p-3";
  const titleSize =
    density === "compact" ? "text-sm" : density === "expanded" ? "text-base" : "text-[15px]";
  const showWhy = density !== "compact" && b.why;

  return (
    <div
      className={`relative rounded-xl ${padding} transition ${current ? "" : "hover:bg-foreground/[0.03]"}`}
      style={
        current
          ? {
              background: "color-mix(in oklab, var(--primary) 8%, transparent)",
              border: "1px solid color-mix(in oklab, var(--primary) 25%, transparent)",
            }
          : { border: "1px solid transparent" }
      }
    >
      <div className="flex items-start gap-3">
        {/* Step number */}
        <div className="flex-shrink-0 mt-0.5">
          <div
            className="w-7 h-7 rounded-full grid place-items-center font-bold text-xs"
            style={
              current
                ? { background: "linear-gradient(135deg, var(--primary), #9333ea)", color: "#fff" }
                : {
                    background: "color-mix(in oklab, var(--foreground) 6%, transparent)",
                    color: "color-mix(in oklab, var(--foreground) 60%, transparent)",
                  }
            }
          >
            {idx + 1}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
              {b.time}
            </span>
            <span className="text-[10px] text-muted-foreground inline-flex items-center gap-1">
              <ClockIcon width={10} height={10} /> {b.duration}
            </span>
            {b.walk && (
              <span className="text-[10px] text-muted-foreground inline-flex items-center gap-1">
                <WalkIcon width={10} height={10} /> {b.walk}
              </span>
            )}
          </div>
          <div className={`${titleSize} font-bold leading-tight mt-0.5`}>{b.title}</div>
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            <TypeChip type={b.type} />
            <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
              Energy <EnergyBar level={b.energy} />
            </span>
          </div>
          {showWhy && (
            <div className="mt-2 text-xs text-muted-foreground leading-relaxed">{b.why}</div>
          )}
        </div>

        {/* Done toggle — always visible, ghost checkmark when undone so the
            affordance is clear at a glance without dominating the card */}
        {onToggleDone !== undefined && (
          <button
            type="button"
            onClick={onToggleDone}
            title={isDone ? "Mark undone" : "Mark done"}
            className="flex-shrink-0 mt-0.5 w-6 h-6 rounded-full grid place-items-center transition-all hover:scale-110"
            style={
              isDone
                ? {
                    background: "linear-gradient(135deg, var(--primary), #9333ea)",
                    border: "2px solid transparent",
                  }
                : {
                    background: "transparent",
                    border: "2px solid color-mix(in oklab, var(--foreground) 22%, transparent)",
                  }
            }
          >
            <CheckIcon
              width={11}
              height={11}
              className="transition-opacity"
              style={{
                color: isDone ? "#fff" : "color-mix(in oklab, var(--foreground) 35%, transparent)",
                opacity: isDone ? 1 : 0.7,
              }}
            />
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Accordion layout ── */
function AccordionLayout({
  days, todayN, activeDayN, setActiveDayN, density, bookings = []
}: {
  days: TripDay[]; todayN: number; activeDayN: number;
  setActiveDayN: (n: number | null) => void; density: Density;
  bookings?: TripBooking[];
}) {
  // Block IDs are unique across all days — one flat Set covers everything.
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const toggleDone = (id: string) => {
    setDoneIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-1.5">
      {days.map((d) => {
        const open = d.n === activeDayN;
        const isToday = d.n === todayN;
        const isPast = d.status === "past";
        
        const dayBookings = bookings.filter(b => {
          if (!b.datetime_local) return false;
          const bDate = b.datetime_local.split("T")[0];
          return bDate === d.isoDate;
        });

        // Highlight the block immediately after the highest-indexed done block
        // for this day. If none done → highlight first; if all done → no highlight.
        const maxDoneIdx = d.blocks.reduce((acc, b, i) => (doneIds.has(b.id) ? i : acc), -1);
        const currentIdx = maxDoneIdx + 1 < d.blocks.length ? maxDoneIdx + 1 : -1;

        return (
          <div
            key={d.n}
            className="rounded-xl border border-border overflow-hidden"
            style={{ background: open ? "color-mix(in oklab, var(--background) 60%, transparent)" : "transparent" }}
          >
            <button
              type="button"
              onClick={() => setActiveDayN(open ? null! : d.n)}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 text-left hover:bg-foreground/[0.03] transition"
            >
              <div
                className="w-8 h-8 rounded-lg grid place-items-center font-bold text-xs"
                style={
                  isToday
                    ? { background: "linear-gradient(135deg, var(--primary), #9333ea)", color: "#fff" }
                    : isPast
                    ? {
                        background: "color-mix(in oklab, var(--foreground) 4%, transparent)",
                        color: "color-mix(in oklab, var(--foreground) 35%, transparent)",
                      }
                    : {
                        background: "color-mix(in oklab, var(--foreground) 6%, transparent)",
                        color: "color-mix(in oklab, var(--foreground) 65%, transparent)",
                      }
                }
              >
                {d.n}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  {d.date}
                </div>
                <div className={`text-sm font-bold leading-tight ${isPast ? "text-foreground/50" : ""}`}>
                  {d.title}
                </div>
              </div>
              {isToday && (
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-500 mr-1">
                  Today
                </span>
              )}
              <ChevronDownIcon
                width={16} height={16}
                className={`transition-transform ${open ? "rotate-180" : ""} text-muted-foreground`}
              />
            </button>
            {open && (
              <div className="px-2.5 pb-3 space-y-1.5 animate-fade-up">
                {dayBookings.length > 0 && (
                  <div className="mb-3 px-1">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5 ml-1">
                      Linked Bookings
                    </div>
                    <div className="flex flex-col gap-1.5 border-l-2 border-primary/20 pl-2">
                      {dayBookings.map(b => (
                        <div key={b.id} className="text-xs bg-slate-50 border border-border p-2 rounded-md flex items-center gap-2">
                           <span className="font-semibold">{b.kind === "flight" ? "Flight" : b.kind === "accommodation" ? "Stay" : "Booking"}:</span>
                           <span className="truncate">{b.payload?.airline || b.payload?.name || "Confirmed"}</span>
                           <span className="ml-auto text-muted-foreground">{b.datetime_local?.split("T")[1] || ""}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {d.blocks.map((b, i) => (
                  <BlockRow
                    key={b.id}
                    b={b}
                    idx={i}
                    density={density}
                    current={i === currentIdx}
                    isDone={doneIds.has(b.id)}
                    onToggleDone={() => toggleDone(b.id)}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Timeline layout ── */
function TimelineLayout({
  days, todayN, activeDayN, setActiveDayN, density, note,
}: {
  days: TripDay[]; todayN: number; activeDayN: number;
  setActiveDayN: (n: number) => void; density: Density;
  note?: string;
}) {
  const stripRef = useRef<HTMLDivElement>(null);
  const d = days.find((dd) => dd.n === activeDayN) || days.find((dd) => dd.n === todayN)!;

  // Per-block done state. Block IDs are unique across all days so a flat Set works.
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const toggleDone = (id: string) => {
    setDoneIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // Highlight the block immediately after the highest-indexed done block.
  // If no blocks are done, highlight the first one.
  // If the last block is done (or all done), no highlight.
  const maxDoneIdx = d.blocks.reduce((acc, b, i) => (doneIds.has(b.id) ? i : acc), -1);
  const currentIdx = maxDoneIdx + 1 < d.blocks.length ? maxDoneIdx + 1 : -1;

  // Native non-passive wheel listener so preventDefault reliably stops the panel
  // from scrolling vertically while the cursor is over the day strip.
  // Using scrollBy with behavior:'smooth' avoids the whole-button-width jump.
  useEffect(() => {
    const el = stripRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      el.scrollLeft += e.deltaY + e.deltaX;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return (
    <div>
      {/* Day-picker strip — fixed-width buttons, "Today" badge inline on line 2 */}
      <div
        ref={stripRef}
        className="flex gap-1.5 overflow-x-auto pb-3 mb-4 -mx-2 px-2 scrollbar-primary"
      >
        {days.map((day) => {
          const isActive = day.n === activeDayN;
          const isPast   = day.status === "past";
          return (
            <button
              key={day.n}
              type="button"
              onClick={() => setActiveDayN(day.n)}
              className={`flex-shrink-0 flex-grow-0 w-[88px] px-3 py-2 rounded-xl border transition-all text-left
                ${isActive ? "border-transparent text-white" : "border-border hover:border-primary/30"}
                ${isPast && !isActive ? "opacity-50" : ""}`}
              style={
                isActive
                  ? { background: "linear-gradient(135deg, var(--primary), #9333ea)" }
                  : { background: "color-mix(in oklab, var(--foreground) 4%, transparent)" }
              }
            >
              <div className={`text-[10px] font-mono uppercase tracking-wider ${isActive ? "text-white/70" : "text-muted-foreground"}`}>
                Day {day.n}
              </div>
              <div className={`text-xs font-bold mt-0.5 leading-tight ${isActive ? "text-white" : "text-foreground"}`}>
                {day.date.split(" · ")[0]}
              </div>
            </button>
          );
        })}
      </div>

      {/* AI note — below strip, above blocks */}
      {note && (
        <div
          className="rounded-2xl border border-primary/20 px-3.5 py-2.5 mb-4 text-xs text-foreground/80 leading-relaxed"
          style={{ background: "color-mix(in oklab, var(--primary) 6%, transparent)" }}
        >
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-primary mr-1.5">AI</span>
          {note}
        </div>
      )}

      {/* Block list */}
      <div className="space-y-2.5">
        {d.blocks.map((b, i) => {
          const isDone    = doneIds.has(b.id);
          const isCurrent = i === currentIdx;
          return (
            <BlockRow
              key={b.id}
              b={b}
              idx={i}
              density={density}
              current={isCurrent}
              isDone={isDone}
              onToggleDone={() => toggleDone(b.id)}
            />
          );
        })}
      </div>
    </div>
  );
}

/* ── Kanban layout ── */
function KanbanLayout({
  days, todayN, activeDayN, setActiveDayN, density,
}: {
  days: TripDay[]; todayN: number; activeDayN: number;
  setActiveDayN: (n: number) => void; density: Density;
}) {
  const d = days.find((dd) => dd.n === activeDayN) || days.find((dd) => dd.n === todayN)!;
  const cols = [
    { time: "Morning",   b: d.blocks[0] },
    { time: "Afternoon", b: d.blocks[1] },
    { time: "Evening",   b: d.blocks[2] },
  ];
  return (
    <div>
      <div className="flex gap-1.5 overflow-x-auto pb-3 mb-4 -mx-2 px-2">
        {days.map((day) => {
          const isActive = day.n === activeDayN;
          const isPast = day.status === "past";
          return (
            <button
              key={day.n} type="button" onClick={() => setActiveDayN(day.n)}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full border transition-all text-xs font-bold
                ${isActive ? "border-transparent text-white" : "border-border hover:border-primary/30"}
                ${isPast && !isActive ? "opacity-50" : ""}`}
              style={isActive ? { background: "linear-gradient(135deg, var(--primary), #9333ea)" } : undefined}
            >
              Day {day.n}
            </button>
          );
        })}
      </div>
      <div className="grid grid-cols-3 gap-2.5">
        {cols.map((c, i) => (
          <div
            key={c.time}
            className="rounded-2xl border border-border p-2.5"
            style={{ background: "color-mix(in oklab, var(--background) 50%, transparent)" }}
          >
            <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground mb-2 px-1">
              {c.time}
            </div>
            <BlockRow b={c.b} idx={i} density={density} current={c.b.current} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Panel header ── */
function PanelHeader({ trip, day }: { trip: Trip; day: TripDay }) {
  return (
    <header className="px-5 pt-5 pb-3 border-b border-border">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
              {trip.dateRange.split(" – ")[0]} → {trip.dateRange.split(" – ")[1]}
            </span>
          </div>
          <h2 className="font-extrabold tracking-tight leading-tight">
            <span className="text-2xl">{trip.destination}</span>
            <br />
            <span className="text-lg font-bold text-foreground/50">Day {day.n} of 7</span>
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">{day.title}</p>
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          {trip.weather && (
            <div
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
              style={{
                background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
                color: "color-mix(in oklab, var(--foreground) 75%, transparent)",
              }}
            >
              <RainIcon width={12} height={12} /> {trip.weather.temp} · drizzle
            </div>
          )}
          <button
            type="button"
            className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-primary"
          >
            Expand ↗
          </button>
          {(trip.bookings?.length ?? 0) > 0 && (
            <div className="text-[10px] font-medium text-primary mt-1">
              {trip.bookings?.length} Booking{trip.bookings?.length !== 1 ? 's' : ''} saved
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

/* ── Main export ── */
interface TripDetailPanelProps {
  trip: Trip;
  days: TripDay[];
  todayN: number;
  layout?: PanelLayout;
  density?: Density;
  activeDayN: number;
  setActiveDayN: (n: number) => void;
}

export function TripDetailPanel({
  trip, days, todayN,
  layout = "accordion",
  density = "comfortable",
  activeDayN,
  setActiveDayN,
}: TripDetailPanelProps) {
  const [showLogistics, setShowLogistics] = useState(false);
  const [editingBooking, setEditingBooking] = useState<Partial<TripBooking> | null>(null);

  const day = days.find((d) => d.n === activeDayN) || days.find((d) => d.n === todayN)!;

  const layoutProps = { days, todayN, activeDayN, setActiveDayN: setActiveDayN as (n: number) => void, density, bookings: trip.bookings || [] };
  // Only surface the AI note for today; other days have no note.
  const todayNote = day.n === todayN ? day.note : undefined;

  return (
    <div
      className="aletheia-card flex flex-col h-full overflow-hidden"
      style={{ background: "var(--background)" }}
    >
      <PanelHeader trip={trip} day={day} />

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        
        <div className="flex items-center justify-between mb-2">
          <Button variant="outline" size="sm" onClick={() => setShowLogistics(true)}>
            View Logistics & Bookings
          </Button>
        </div>
        
        {trip.countryIntel?.map((intel, idx) => (
          <SafetyWarningBanner 
            key={`safety-${idx}`}
            score={intel.safety?.score_10 ?? 10} 
            country={intel.iso_country || "the region"}
            sources={intel.sources}
          />
        ))}

        {trip.countryIntel && trip.countryIntel.length > 0 && (
          <CountryIntelStrip tripId={trip.id} countryIntel={trip.countryIntel} />
        )}

        {/* Itinerary — AI note is rendered inside TimelineLayout (below strip),
            and inside the accordion's scroll area for other layouts */}
        {layout === "timeline" ? (
          <TimelineLayout {...layoutProps} note={todayNote} />
        ) : layout === "kanban" ? (
          <KanbanLayout {...layoutProps} />
        ) : (
          <>
            {/* Accordion: show AI note at the top of the scroll area */}
            {todayNote && (
              <div
                className="rounded-2xl border border-primary/20 px-3.5 py-2.5 text-xs text-foreground/80 leading-relaxed"
                style={{ background: "color-mix(in oklab, var(--primary) 6%, transparent)" }}
              >
                <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-primary mr-1.5">AI</span>
                {todayNote}
              </div>
            )}
            <AccordionLayout {...layoutProps} setActiveDayN={setActiveDayN as (n: number | null) => void} />
          </>
        )}

        {/* AI suggestions */}
        {day.n === todayN && day.suggestions && day.suggestions.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-2">
              <SparklesIcon width={14} height={14} className="text-primary" />
              <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                Adapting to your day
              </h3>
            </div>
            <div className="space-y-2">
              {day.suggestions.map((s, i) => (
                <SuggestionCard key={i} s={s} />
              ))}
            </div>
          </section>
        )}
      </div>

      <Sheet open={showLogistics} onOpenChange={setShowLogistics}>
        <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto p-0">
          <LogisticsRail
            bookings={trip.bookings || []}
            onEdit={(b) => setEditingBooking(b)}
            onAdd={(kind) => setEditingBooking({ kind, trip_id: trip.id, payload: {} })}
          />
        </SheetContent>
      </Sheet>

      <BookingFormSheet
        booking={editingBooking}
        onClose={() => setEditingBooking(null)}
        onSave={() => {
          // In a real implementation this would trigger an API call to save the booking
          setEditingBooking(null);
        }}
      />
    </div>
  );
}
