"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface BeamsBackgroundProps {
  className?: string;
  children?: React.ReactNode;
  intensity?: "subtle" | "medium" | "strong";
}

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
  subtle: 15,
  medium: 25,
  strong: 40,
};

export function BeamsBackground({
  className,
  children,
  intensity = "medium",
}: BeamsBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const beamsRef = useRef<Beam[]>([]);
  const animationFrameRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const updateCanvasSize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = "100%";
      canvas.style.height = "100%";
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
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      beamsRef.current.forEach((beam, index) => {
        beam.y -= beam.speed;
        beam.x += Math.tan(beam.angle) * beam.speed;
        beam.pulse += beam.pulseSpeed;

        if (beam.y + beam.length < -100) {
          resetBeam(beam, index, beamsRef.current.length, window.innerWidth, window.innerHeight);
        }

        drawBeam(ctx, beam);
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", updateCanvasSize);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [intensity]);

  return (
    <div className={cn("absolute inset-0 overflow-hidden", className)}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0"
        style={{ filter: "blur(8px)" }}
      />
      {/* Pulse overlay using CSS animation instead of Framer Motion */}
      <div 
        className="absolute inset-0 bg-primary/5 animate-pulse-soft pointer-events-none" 
        style={{ animationDuration: '8s' }}
      />
    </div>
  );
}
