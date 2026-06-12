// CapabilitySheet — the ✨ launcher (Task 50).
//
// One grouped panel with every available capability visible. Groups are headers;
// capabilities are rows beneath. A chevron expands the row's "how it works"
// inline (one open at a time). Unavailable rows render disabled with reason.
// A "See everything →" footer links to /guide.
//
// Layout (both viewports): floating card anchored bottom-right over the chat,
//   with margin so the chat behind stays recognisable.

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { ChevronDown, ArrowRight, Lock } from "lucide-react";

import {
  GROUP_ORDER,
  GROUP_META,
  GROUP_SHOWS_TRIP,
  capabilitiesForGroup,
  availabilityOf,
  type AvailabilityState,
  type Capability,
} from "@/lib/capabilities";
import { capabilityIcon } from "./capabilityIcons";
import { useCapabilityLaunch } from "./useCapabilityLaunch";

export function CapabilitySheet({
  open,
  onOpenChange,
  availability,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  availability: AvailabilityState;
}) {
  const launch = useCapabilityLaunch();
  const router = useRouter();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  function handleLaunch(c: Capability) {
    launch(c, "sheet");
    if (c.launch.kind === "link") return;
    onOpenChange(false);
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        {/* Backdrop — very light scrim */}
        <DialogPrimitive.Backdrop className="fixed inset-0 z-50 transition-opacity duration-200 data-starting-style:opacity-0 data-ending-style:opacity-0 bg-black/10 supports-backdrop-filter:backdrop-blur-[1px] lg:bg-black/[0.04] lg:backdrop-blur-none" />

        {/* Panel — compact anchored card on all viewports */}
        <DialogPrimitive.Popup
          aria-label="What can I help with?"
          className={[
            // base
            "fixed z-50 flex flex-col overflow-hidden",
            "bg-popover text-sm text-popover-foreground",
            "rounded-2xl border border-border shadow-lg shadow-black/[0.08]",
            "outline-none",
            // animation
            "transition duration-200 ease-out",
            "data-starting-style:opacity-0 data-ending-style:opacity-0",
            "data-starting-style:translate-y-2 data-ending-style:translate-y-2",
            // ── mobile: side margins, above bottom bar, max-h uses dvh so browser
            //    chrome doesn't push the top edge off-screen ──────────────────────
            "inset-x-3 bottom-3 max-h-[82dvh]",
            // ── desktop: anchored bottom-right, compact width ─────────────────────
            "lg:inset-x-auto lg:right-4 lg:bottom-[4.5rem] lg:w-[360px] lg:max-h-[74vh]",
          ].join(" ")}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 pt-3.5 pb-2 shrink-0 border-b border-border/50">
            <h2 className="text-[13px] font-semibold tracking-tight">
              What can I help with?
            </h2>
            <DialogPrimitive.Close
              className="grid h-6 w-6 place-items-center rounded-md text-muted-foreground hover:bg-foreground/8 hover:text-foreground transition"
              aria-label="Close"
            >
              <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </DialogPrimitive.Close>
          </div>

          {/* Scrollable list */}
          <div className="flex-1 overflow-y-auto min-h-0 px-2.5 py-2.5 space-y-3 overscroll-contain">
            {GROUP_ORDER.map((group) => {
              const items = capabilitiesForGroup(group, availability);
              if (items.length === 0) return null;
              const meta = GROUP_META[group];
              const showsTripBadge =
                GROUP_SHOWS_TRIP[group] && !!availability.tripName;
              return (
                <section key={group}>
                  {/* Group header */}
                  <div className="flex items-center gap-1.5 px-1 mb-1">
                    <h3 className="text-[9px] font-bold uppercase tracking-[0.12em] text-muted-foreground/70">
                      {meta.label}
                    </h3>
                    {showsTripBadge && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold text-primary/80 leading-none">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary/70 shrink-0" aria-hidden />
                        {availability.tripName}
                      </span>
                    )}
                  </div>

                  <ul className="space-y-1">
                    {items.map((c) => {
                      const avail = availabilityOf(c, availability);
                      const disabled = avail !== true;
                      const Icon = capabilityIcon(c.icon);
                      const expanded = expandedId === c.id;
                      return (
                        <li
                          key={c.id}
                          className={[
                            "rounded-lg border transition-colors",
                            disabled
                              ? "border-border/40 opacity-50"
                              : "border-border/60 hover:border-primary/25 hover:bg-foreground/[0.015]",
                          ].join(" ")}
                        >
                          <div className="flex items-center gap-2.5 px-2.5 py-2">
                            <button
                              type="button"
                              disabled={disabled}
                              onClick={() => handleLaunch(c)}
                              className="flex flex-1 items-center gap-2.5 text-left disabled:cursor-not-allowed min-w-0"
                            >
                              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-muted/50 text-muted-foreground">
                                <Icon className="h-3.5 w-3.5" aria-hidden />
                              </span>
                              <span className="min-w-0">
                                <span className="block truncate text-[13px] font-medium leading-tight">
                                  {c.name}
                                </span>
                                <span className="block truncate text-[11px] text-muted-foreground mt-0.5 leading-none">
                                  {c.oneLiner}
                                </span>
                              </span>
                            </button>

                            {disabled ? (
                              <span className="flex shrink-0 items-center gap-1 ml-0.5 text-[10px] text-muted-foreground/60">
                                <Lock className="h-3 w-3 shrink-0" aria-hidden />
                                <span className="hidden sm:inline max-w-[80px] truncate">
                                  {avail}
                                </span>
                              </span>
                            ) : (
                              <button
                                type="button"
                                aria-label={expanded ? "Hide details" : "Show details"}
                                aria-expanded={expanded}
                                onClick={() => setExpandedId(expanded ? null : c.id)}
                                className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-muted-foreground transition hover:bg-foreground/8 hover:text-primary"
                              >
                                <ChevronDown
                                  className={`h-3.5 w-3.5 transition-transform duration-200 ${
                                    expanded ? "rotate-180" : ""
                                  }`}
                                />
                              </button>
                            )}
                          </div>

                          {expanded && !disabled && (
                            <p className="px-2.5 pb-2.5 pl-[3.25rem] text-[11px] leading-relaxed text-muted-foreground">
                              {c.howItWorks}
                            </p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              );
            })}
          </div>

          {/* Footer */}
          <div className="border-t border-border/50 px-3 py-2 shrink-0 text-center">
            <button
              type="button"
              onClick={() => {
                onOpenChange(false);
                router.push("/guide");
              }}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-primary hover:underline underline-offset-2"
            >
              See everything
              <ArrowRight className="h-3 w-3" />
            </button>
          </div>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
