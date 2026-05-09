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
  
  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20">
      <Navbar />
      
      {/* Sleek Design Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        {/* Dynamic Beams for Dark Mode */}
        <div className="absolute inset-0 opacity-0 dark:opacity-100 transition-opacity duration-1000">
          <BeamsBackground intensity="strong" />
        </div>

        {/* Gradient for Light Mode */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-background to-purple-50 dark:hidden" />
        
        {/* Animated Accent Orbs */}
        <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-blue-500/10 dark:bg-blue-600/5 rounded-full blur-[120px] animate-float" />
        <div className="absolute bottom-[10%] right-[-5%] w-[35%] h-[35%] bg-purple-500/10 dark:bg-purple-600/5 rounded-full blur-[120px] animate-float [animation-direction:reverse] [animation-duration:25s]" />
        
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
