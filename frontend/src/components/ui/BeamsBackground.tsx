"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface BeamsBackgroundProps {
  className?: string;
  children?: React.ReactNode;
  intensity?: "subtle" | "medium" | "strong";
}

// Cap device-pixel-ratio for a soft decorative background — going past 1.5x
// quadruples fill-rate cost for visually negligible gain (the gradients are
// already soft and the layer is downscaled by the browser anyway).
const MAX_DPR = 1.5;

interface Beam {
  x: number;
  y: number;
  width: number;
  length: number;
  angle: number;
  speed: number;
  opacity: number;
  hue: number;
  pulse: number;
  pulseSpeed: number;
}

function createBeam(width: number, height: number): Beam {
  const angle = -35 + Math.random() * 10;
  return {
    x: Math.random() * width * 1.5 - width * 0.25,
    y: height + 100,
    width: 2 + Math.random() * 4,
    length: 150 + Math.random() * 300,
    angle: (angle * Math.PI) / 180,
    speed: 0.5 + Math.random() * 1.5,
    opacity: 0.2 + Math.random() * 0.6,
    hue: 230 + Math.random() * 50, // More punchy blue/purple
    pulse: Math.random() * Math.PI * 2,
    pulseSpeed: 0.02 + Math.random() * 0.03,
  };
}

function drawBeam(ctx: CanvasRenderingContext2D, beam: Beam) {
  ctx.save();
  ctx.translate(beam.x, beam.y);
  ctx.rotate(beam.angle);

  const gradient = ctx.createLinearGradient(0, 0, 0, -beam.length);
  const opacity = beam.opacity * (0.5 + Math.sin(beam.pulse) * 0.5);

  gradient.addColorStop(0, `hsla(${beam.hue}, 80%, 60%, 0)`);
  gradient.addColorStop(0.5, `hsla(${beam.hue}, 80%, 60%, ${opacity})`);
  gradient.addColorStop(1, `hsla(${beam.hue}, 80%, 60%, 0)`);

  ctx.fillStyle = gradient;
  ctx.fillRect(-beam.width / 2, 0, beam.width, -beam.length);
  ctx.restore();
}

function resetBeam(beam: Beam, index: number, totalBeams: number, width: number, height: number) {
  const newBeam = createBeam(width, height);
  Object.assign(beam, newBeam);
  beam.y = height + 100 + (index / totalBeams) * height;
}

const INTENSITY_MAP = {
  subtle: 10,
  medium: 18,
  strong: 28,  // was 40 — visually near-identical, ~30% less fill cost
};

export function BeamsBackground({
  className,
  children: _children,
  intensity = "medium",
}: BeamsBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const beamsRef = useRef<Beam[]>([]);
  const animationFrameRef = useRef<number>(0);
  const runningRef = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Respect the user's OS motion preference.
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const updateCanvasSize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = "100%";
      canvas.style.height = "100%";
      // Reset transform before re-scaling — otherwise ctx.scale stacks on
      // every resize and the canvas resolution explodes.
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);

      const totalBeams = INTENSITY_MAP[intensity];
      beamsRef.current = Array.from({ length: totalBeams }, (_, i) => {
        const beam = createBeam(window.innerWidth, window.innerHeight);
        beam.y = Math.random() * (window.innerHeight + 1000);
        return beam;
      });
    };

    updateCanvasSize();
    window.addEventListener("resize", updateCanvasSize);

    const animate = () => {
      if (!runningRef.current) return;
      const w = window.innerWidth;
      const h = window.innerHeight;

      ctx.clearRect(0, 0, w, h);

      const beams = beamsRef.current;
      for (let i = 0; i < beams.length; i++) {
        const beam = beams[i];
        beam.y -= beam.speed;
        beam.x += Math.tan(beam.angle) * beam.speed;
        beam.pulse += beam.pulseSpeed;

        if (beam.y + beam.length < -100) {
          resetBeam(beam, i, beams.length, w, h);
        }

        drawBeam(ctx, beam);
      }

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    const start = () => {
      if (runningRef.current) return;
      runningRef.current = true;
      animate();
    };
    const stop = () => {
      runningRef.current = false;
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = 0;
      }
    };

    // Pause when the tab is hidden — browsers throttle rAF in background tabs
    // already, but explicit stop is cheaper and avoids the occasional 1Hz tick.
    const onVisibility = () => {
      if (document.visibilityState === "hidden") stop();
      else start();
    };
    document.addEventListener("visibilitychange", onVisibility);

    // Pause when the canvas is scrolled out of view.
    let observer: IntersectionObserver | null = null;
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) start();
        else stop();
      }, { threshold: 0 });
      observer.observe(canvas);
    } else {
      start();
    }

    return () => {
      stop();
      window.removeEventListener("resize", updateCanvasSize);
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, [intensity]);

  return (
    <div className={cn("absolute inset-0 overflow-hidden", className)}>
      {/*
        Canvas: the soft blur is now baked into each beam's gradient stops
        (alpha fades to 0 at both ends), so the GPU-expensive
        `filter: blur(8px)` on the full viewport canvas is no longer needed.
        That single change is the largest perf win in this component.
      */}
      <canvas ref={canvasRef} className="absolute inset-0" />
      <div
        className="absolute inset-0 bg-primary/5 animate-pulse-soft pointer-events-none"
        style={{ animationDuration: "8s" }}
      />
    </div>
  );
}
