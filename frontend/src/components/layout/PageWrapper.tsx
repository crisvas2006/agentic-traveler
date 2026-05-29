"use client";

import * as React from "react";
import { Navbar } from "./Navbar";
import { Footer } from "./Footer";
import { ThemeProvider } from "./ThemeProvider";

interface PageWrapperProps {
  children: React.ReactNode;
}

import { useTheme } from "./ThemeProvider";
import { BeamsBackground } from "@/components/ui/BeamsBackground";

function PageContent({ children }: PageWrapperProps) {
  const { theme } = useTheme();
  // Only mount the canvas-driven background in dark mode. In light mode the
  // opacity:0 trick still left a 60fps rAF loop running into a hidden canvas
  // (and the GPU still compositing the blurred layer). Conditionally mounting
  // means the loop literally doesn't exist in light mode.
  const showBeams = theme === "dark";

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20">
      <Navbar />

      {/* Sleek Design Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        {/* Dynamic Beams — dark mode only */}
        {showBeams && (
          <div className="absolute inset-0">
            <BeamsBackground intensity="medium" />
          </div>
        )}

        {/* Gradient for Light Mode */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-background to-purple-50 dark:hidden" />

        {/* Static accent orbs.
            We dropped the `animate-float` transform — transform animations
            on `blur-[120px]` elements force a full composited repaint of the
            blurred layer every frame. The blur radius is also reduced from
            120px to 70px (~3x cheaper fill rate, visually almost identical). */}
        <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-blue-500/10 dark:bg-blue-600/5 rounded-full blur-[70px]" />
        <div className="absolute bottom-[10%] right-[-5%] w-[35%] h-[35%] bg-purple-500/10 dark:bg-purple-600/5 rounded-full blur-[70px]" />

        {/* Subtle Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-20" />
      </div>

      <main className="relative z-10 pt-16">
        {children}
      </main>

      <Footer />
    </div>
  );
}

export function PageWrapper({ children }: PageWrapperProps) {
  return (
    <ThemeProvider>
      <PageContent>{children}</PageContent>
    </ThemeProvider>
  );
}
