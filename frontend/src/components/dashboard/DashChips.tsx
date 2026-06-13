import { STATUS_META, TYPE_META, type TripStatus, type BlockType } from "@/lib/dashboard-data";
import { MapPinIcon, XIcon } from "./DashIcons";

export function StatusChip({ status }: { status: TripStatus }) {
  const meta = STATUS_META[status];
  if (!meta) return null;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] px-2 py-1 rounded-full"
      style={{ background: meta.bg, color: meta.color }}
    >
      {status === "active" && (
        <span className="relative flex w-1.5 h-1.5">
          <span
            className="absolute inset-0 rounded-full animate-ping"
            style={{ background: meta.color, opacity: 0.6 }}
          />
          <span className="relative w-1.5 h-1.5 rounded-full" style={{ background: meta.color }} />
        </span>
      )}
      {meta.label}
    </span>
  );
}

/**
 * FocusedTripChip (Task 52) — a subtle, clickable indicator in the chat header
 * teaching the user that the open trip drives the conversation's context. The
 * pill body opens/scrolls the TripPanel; the trailing X clears focus AND closes
 * the panel (the next message then carries focused_trip_id=null). Shown only when
 * a trip is focused; renders nothing when focus is null.
 */
export function FocusedTripChip({
  destination,
  onOpen,
  onClear,
}: {
  destination: string;
  onOpen?: () => void;
  onClear?: () => void;
}) {
  if (!destination) return null;
  return (
    <span
      className="inline-flex items-center gap-0.5 rounded-full pl-1.5 pr-0.5 py-0.5 max-w-[150px]"
      style={{
        background: "color-mix(in oklab, var(--primary) 12%, transparent)",
        color: "var(--primary)",
      }}
    >
      <button
        type="button"
        onClick={onOpen}
        className="inline-flex items-center gap-1 min-w-0 cursor-pointer hover:opacity-80 transition text-[11px] font-semibold"
        title={`Focused on ${destination} — tap to open the trip`}
        aria-label={`Focused trip: ${destination}. Open the trip panel.`}
      >
        <MapPinIcon width={11} height={11} className="flex-shrink-0" />
        <span className="truncate">{destination}</span>
      </button>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="w-4 h-4 rounded-full grid place-items-center hover:bg-foreground/15 transition flex-shrink-0"
          title="Clear focus & close the trip panel"
          aria-label="Clear trip focus and close the panel"
        >
          <XIcon width={9} height={9} />
        </button>
      )}
    </span>
  );
}

export function TypeChip({ type }: { type: BlockType }) {
  const meta = TYPE_META[type];
  if (!meta) return null;
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-md"
      style={{
        background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
        color: "color-mix(in oklab, var(--foreground) 65%, transparent)",
      }}
    >
      <span className="text-[11px] leading-none">{meta.glyph}</span>
      {meta.label}
    </span>
  );
}

export function EnergyBar({ level }: { level: number }) {
  return (
    <span className="inline-flex items-center gap-[3px]" title={`Energy ${level}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className="w-[3px] rounded-full"
          style={{
            height: `${4 + i * 1.5}px`,
            background:
              i <= level
                ? "var(--primary)"
                : "color-mix(in oklab, var(--foreground) 12%, transparent)",
          }}
        />
      ))}
    </span>
  );
}
