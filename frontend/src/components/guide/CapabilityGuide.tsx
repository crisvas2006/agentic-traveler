"use client";

import { useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import {
  GROUP_ORDER,
  GROUP_META,
  GROUP_SHOWS_TRIP,
  capabilitiesForGroup,
  type AvailabilityState,
} from "@/lib/capabilities";
import { useTripList, useTrip } from "@/hooks/useTrip";
import { GuideCapabilityCard } from "./GuideCapabilityCard";
import { track } from "@/lib/metrics";
import { SparklesIcon } from "@/components/dashboard/DashIcons";

// ── LaunchFromParam ───────────────────────────────────────────────────────────
// Reads ?launch=<id> from the URL on mount. Used when this page is navigated TO
// (unlikely for /guide itself, but here for completeness). The primary consumer
// lives in DashboardShell for the /dashboard?launch=<id> handoff.
// Needs Suspense because useSearchParams suspends in Next.js App Router.
function LaunchParamCleaner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const launched = searchParams.get("launch");
  useEffect(() => {
    if (launched) router.replace("/guide");
  }, [launched, router]);
  return null;
}

// ── Main component ────────────────────────────────────────────────────────────
export function CapabilityGuide() {
  const { defaultActiveId } = useTripList();
  const { trip } = useTrip(defaultActiveId);

  const availability: AvailabilityState = {
    hasTrip: !!trip,
    tripPhase: trip?.phase,
    tripName: trip?.title ?? undefined,
    // telegramLinked not yet in UserProfile; cards render enabled (spec E6)
  };

  useEffect(() => {
    track("capability_guide_viewed");
  }, []);

  return (
    <div
      className="min-h-screen"
      style={{ background: "var(--background)", color: "var(--foreground)" }}
    >
      <Suspense>
        <LaunchParamCleaner />
      </Suspense>

      {/* ── Sticky header ── */}
      <header
        className="sticky top-0 z-20 h-14 px-4 sm:px-6 flex items-center gap-3 border-b border-border"
        style={{
          background:
            "color-mix(in oklab, var(--background) 80%, transparent)",
          backdropFilter: "blur(14px)",
        }}
      >
        <Link
          href="/dashboard"
          className="flex items-center gap-2 group shrink-0"
          aria-label="Back to dashboard"
        >
          <div
            className="w-8 h-8 rounded-xl grid place-items-center transition-transform group-hover:scale-110"
            style={{
              background: "linear-gradient(135deg, var(--primary), #9333ea)",
            }}
          >
            <SparklesIcon width={16} height={16} className="text-white" />
          </div>
          <span className="text-sm font-bold hidden sm:inline">Aletheia</span>
        </Link>

        <span className="text-border select-none hidden sm:inline">·</span>
        <span className="text-sm font-medium text-muted-foreground">
          Capabilities
        </span>

        <div className="flex-1" />

        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to dashboard
        </Link>
      </header>

      {/* ── Main content ── */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        {/* Hero */}
        <div className="mb-14 sm:mb-16 text-center">
          <div
            className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold mb-5 text-primary"
            style={{
              background: "color-mix(in oklab, var(--primary) 10%, var(--muted))",
              border: "1px solid color-mix(in oklab, var(--primary) 20%, transparent)",
            }}
          >
            <SparklesIcon width={11} height={11} />
            What I can do
          </div>

          <h1
            className="text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight"
            style={{
              background:
                "linear-gradient(135deg, var(--foreground) 0%, color-mix(in oklab, var(--primary) 60%, var(--foreground)) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Everything Aletheia can do
          </h1>
          <p className="mt-4 text-base text-muted-foreground max-w-sm mx-auto leading-relaxed">
            Grouped by where you are in the journey — tap anything to start.
          </p>
        </div>

        {/* ── Grouped capability sections ── */}
        <div className="space-y-14 sm:space-y-16">
          {GROUP_ORDER.map((group) => {
            const items = capabilitiesForGroup(group, availability);
            if (items.length === 0) return null;
            const meta = GROUP_META[group];
            const showsTripBadge =
              GROUP_SHOWS_TRIP[group] && !!availability.tripName;

            return (
              <section key={group} aria-labelledby={`group-${group}`}>
                {/* Group header */}
                <div className="mb-6">
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <h2
                      id={`group-${group}`}
                      className="text-lg font-bold tracking-tight"
                    >
                      {meta.label}
                    </h2>
                    {showsTripBadge && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary/80 leading-none">
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-primary/70 shrink-0"
                          aria-hidden
                        />
                        {availability.tripName}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{meta.blurb}</p>

                  {/* Thin rule under group header */}
                  <div
                    className="mt-4 h-px w-12 rounded-full"
                    style={{
                      background:
                        "linear-gradient(90deg, var(--primary), #9333ea)",
                    }}
                  />
                </div>

                {/* Card grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {items.map((c) => (
                    <GuideCapabilityCard
                      key={c.id}
                      capability={c}
                      availability={availability}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>

        {/* Footer */}
        <div className="mt-16 pt-8 border-t border-border text-center">
          <p className="text-sm text-muted-foreground">
            Questions? Just ask in{" "}
            <Link
              href="/dashboard"
              className="text-primary hover:underline underline-offset-2"
            >
              chat
            </Link>
            .
          </p>
        </div>
      </main>
    </div>
  );
}
