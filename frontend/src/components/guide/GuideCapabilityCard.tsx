"use client";

import { useMemo } from "react";
import { Lock, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { type Capability, availabilityOf, type AvailabilityState } from "@/lib/capabilities";
import { capabilityIcon } from "@/components/dashboard/capabilityIcons";
import { track } from "@/lib/metrics";

interface Props {
  capability: Capability;
  availability: AvailabilityState;
}

export function GuideCapabilityCard({ capability: c, availability }: Props) {
  const router = useRouter();
  const avail = availabilityOf(c, availability);
  const disabled = avail !== true;
  // eslint-disable-next-line react-hooks/static-components
  const Icon = useMemo(() => capabilityIcon(c.icon), [c.icon]);

  function handleLaunch() {
    if (disabled) return;
    track("capability_launched", { id: c.id, kind: c.launch.kind, surface: "guide" });

    if (c.launch.kind === "link") {
      router.push(c.launch.href);
      return;
    }
    // message / intent / draft / ephemeral_mood — hand off to the dashboard
    // via ?launch=<id>; the consumer there fires the actual send/pick (AC-4/spec §7 Step 3).
    router.push(`/dashboard?launch=${encodeURIComponent(c.id)}`);
  }

  return (
    <div
      aria-disabled={disabled}
      className={[
        "aletheia-card flex flex-col gap-3 p-5 transition-all duration-200",
        disabled
          ? "opacity-50 cursor-default"
          : "hover:border-primary/30 hover:-translate-y-0.5 hover:shadow-lg",
      ].join(" ")}
    >
      {/* Icon + name */}
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-xl grid place-items-center shrink-0"
          style={{
            background: "color-mix(in oklab, var(--primary) 12%, var(--muted))",
          }}
        >
          <Icon className="h-[18px] w-[18px] text-primary" aria-hidden />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-[14px] leading-tight">{c.name}</div>
          <div className="text-[12px] text-muted-foreground mt-0.5">{c.oneLiner}</div>
        </div>
      </div>

      {/* How it works */}
      <p className="text-[13px] text-muted-foreground leading-relaxed flex-1">
        {c.howItWorks}
      </p>

      {/* Example chip */}
      {c.example && (
        <div
          className="self-start rounded-md px-2 py-1 text-[11px] font-mono text-muted-foreground/80 leading-none"
          style={{
            background: "color-mix(in oklab, var(--foreground) 5%, transparent)",
            border: "1px solid var(--border)",
          }}
        >
          &ldquo;{c.example}&rdquo;
        </div>
      )}

      {/* Action */}
      <div className="mt-auto pt-1">
        {disabled ? (
          <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <Lock className="h-3 w-3 shrink-0" aria-hidden />
            <span aria-label={`Unavailable: ${avail}`}>{avail}</span>
          </div>
        ) : (
          <button
            type="button"
            onClick={handleLaunch}
            className="inline-flex items-center gap-1.5 text-[12px] font-semibold px-3 py-1.5 rounded-lg text-white transition-all hover:opacity-90 active:scale-95"
            style={{
              background: "linear-gradient(135deg, var(--primary), #9333ea)",
              boxShadow:
                "0 4px 14px -4px color-mix(in oklab, var(--primary) 55%, transparent)",
            }}
          >
            {c.launch.kind === "link" ? (
              <>
                Open settings
                <ArrowRight className="h-3 w-3" aria-hidden />
              </>
            ) : (
              "Start"
            )}
          </button>
        )}
      </div>
    </div>
  );
}
