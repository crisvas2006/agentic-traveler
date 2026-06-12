// CapabilityChips — contextual suggestion chips (Task 50).
//
// Renders ≤3 registry entries whose `contexts` include this surface, availability-
// filtered. Used in exactly two moments: the empty chat state and the no-trip
// dashboard. When `onOpenSheet` is given (empty chat, where the launcher sheet
// exists), an extra "What can I do?" chip opens the full sheet. Renders nothing
// when there is nothing to show (AC-10).

"use client";

import { Sparkles } from "lucide-react";

import {
  contextualCapabilities,
  type AvailabilityState,
  type Capability,
  type CapabilityContext,
} from "@/lib/capabilities";
import { capabilityIcon } from "./capabilityIcons";
import { useCapabilityLaunch, type LaunchSurface } from "./useCapabilityLaunch";

const CHIP_CLASS =
  "inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium transition hover:border-primary/40 hover:text-primary";
const CHIP_BG = { background: "color-mix(in oklab, var(--foreground) 3%, transparent)" } as const;

export function CapabilityChips({
  context,
  availability,
  onOpenSheet,
  onLaunched,
}: {
  context: CapabilityContext;
  availability: AvailabilityState;
  /** When provided, adds a "What can I do?" chip that opens the launcher sheet. */
  onOpenSheet?: () => void;
  /** Called after a launch (e.g. open the chat panel on mobile). */
  onLaunched?: () => void;
}) {
  const launch = useCapabilityLaunch();
  const items = contextualCapabilities(context, availability, 3);

  // AC-10: nothing to show and no sheet affordance → render nothing (no husk).
  if (items.length === 0 && !onOpenSheet) return null;

  const surface: LaunchSurface = context === "empty_chat" ? "empty_chat" : "no_trip";

  function handle(c: Capability) {
    launch(c, surface);
    onLaunched?.();
  }

  return (
    <div className="flex flex-wrap justify-center gap-2 px-3">
      {items.map((c) => {
        const Icon = capabilityIcon(c.icon);
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => handle(c)}
            className={`${CHIP_CLASS} text-foreground`}
            style={CHIP_BG}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {c.name}
          </button>
        );
      })}
      {onOpenSheet && (
        <button
          type="button"
          onClick={onOpenSheet}
          className={`${CHIP_CLASS} text-muted-foreground`}
          style={CHIP_BG}
        >
          <Sparkles className="h-3.5 w-3.5" aria-hidden />
          What can I do?
        </button>
      )}
    </div>
  );
}
