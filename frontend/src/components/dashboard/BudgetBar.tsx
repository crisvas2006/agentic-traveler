"use client";

import { useState } from "react";
import type { TripBudget } from "@/lib/dashboard-data";
import { ChevronDownIcon } from "./DashIcons";

/**
 * BudgetBar (Task 40, proposal §6.2 #7) — a compact target/actual bar.
 * Renders ONLY when a target is set (progressive disclosure). Each category is
 * a slice sized by its target; a slice goes amber when its actual exceeds its
 * target. Tapping expands per-category detail.
 */

const CAT_LABELS: Record<string, string> = {
  flights: "Flights",
  lodging: "Lodging",
  food: "Food",
  activities: "Activities",
  transport: "Transport",
  misc: "Misc",
};

function eur(n: number): string {
  return `€${Math.round(n).toLocaleString()}`;
}

export function BudgetBar({ budget }: { budget?: TripBudget }) {
  const [open, setOpen] = useState(false);

  const target = budget?.target_eur ?? 0;
  const byCat = budget?.by_category ?? {};
  const cats = Object.entries(byCat);

  // Only meaningful with a target set.
  if (!target || target <= 0) return null;

  const totalActual = cats.reduce((sum, [, c]) => sum + (c.actual ?? 0), 0);
  const totalCatTarget = cats.reduce((sum, [, c]) => sum + (c.target ?? 0), 0);
  const denom = Math.max(totalCatTarget, target, 1);
  const over = totalActual - target;

  return (
    <section className="rounded-2xl border border-border p-3.5" style={{ background: "color-mix(in oklab, var(--background) 55%, transparent)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 text-left"
      >
        <div className="flex items-baseline gap-2">
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Budget</span>
          <span className="text-sm font-bold tabular-nums">{eur(totalActual)}</span>
          <span className="text-xs text-muted-foreground tabular-nums">/ {eur(target)}</span>
        </div>
        <span className="flex items-center gap-1.5">
          <span className={`text-[11px] font-semibold ${over > 0 ? "text-amber-500" : "text-emerald-500"}`}>
            {over > 0 ? `${eur(over)} over` : "On track"}
          </span>
          <ChevronDownIcon width={14} height={14} className={`transition-transform text-muted-foreground ${open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {/* Stacked bar */}
      <div className="mt-2.5 flex h-2 w-full overflow-hidden rounded-full" style={{ background: "color-mix(in oklab, var(--foreground) 8%, transparent)" }}>
        {cats.map(([key, c]) => {
          const slice = ((c.target ?? 0) / denom) * 100;
          if (slice <= 0) return null;
          const catOver = (c.actual ?? 0) > (c.target ?? 0);
          return (
            <span
              key={key}
              title={`${CAT_LABELS[key] ?? key}: ${eur(c.actual ?? 0)} / ${eur(c.target ?? 0)}`}
              style={{
                width: `${slice}%`,
                background: catOver
                  ? "linear-gradient(90deg, #f59e0b, #f97316)"
                  : "linear-gradient(90deg, var(--primary), #9333ea)",
                opacity: (c.actual ?? 0) > 0 ? 1 : 0.28,
              }}
            />
          );
        })}
      </div>

      {open && (
        <ul className="mt-3 space-y-1.5 animate-fade-up">
          {cats.map(([key, c]) => {
            const catOver = (c.actual ?? 0) > (c.target ?? 0);
            return (
              <li key={key} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{CAT_LABELS[key] ?? key}</span>
                <span className={`tabular-nums font-medium ${catOver ? "text-amber-500" : "text-foreground/80"}`}>
                  {eur(c.actual ?? 0)} <span className="text-muted-foreground font-normal">/ {eur(c.target ?? 0)}</span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
