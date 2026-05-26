"use client";

import { useRef } from "react";
import { cn } from "@/lib/utils";
import { useInView } from "@/hooks/use-in-view";

/**
 * A thin client island that fades-and-slides its children into view when
 * they enter the viewport.  Keeps parent pages as Server Components so they
 * ship as static HTML — only this tiny wrapper is hydrated on the client.
 */
export function Reveal({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-1000",
        inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10",
        className,
      )}
    >
      {children}
    </div>
  );
}
