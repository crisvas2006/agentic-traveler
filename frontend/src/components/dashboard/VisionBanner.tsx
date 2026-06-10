"use client";

/**
 * VisionBanner (Task 40, proposal §6.2 #1) — the trip's "north star" rendered
 * as a single serif-italic line. de Botton: anticipation is itself the trip.
 * It IS the identity, so there's no "Vision" label around it. Self-hides when
 * the trip has no vision yet (the panel also gates it to pre-departure phases).
 */
export function VisionBanner({ vision }: { vision?: string }) {
  if (!vision?.trim()) return null;
  return (
    <section className="px-1">
      <p
        className="font-serif italic text-[15px] sm:text-base leading-relaxed text-foreground/80"
        style={{ textWrap: "balance" }}
      >
        <span
          className="mr-1 text-lg align-[-0.1em] bg-clip-text text-transparent"
          style={{ backgroundImage: "linear-gradient(135deg, var(--primary), #9333ea)" }}
          aria-hidden
        >
          “
        </span>
        {vision}
      </p>
    </section>
  );
}
