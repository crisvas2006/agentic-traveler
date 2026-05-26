import { STATUS_META, TYPE_META, type TripStatus, type BlockType } from "@/lib/dashboard-data";

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
