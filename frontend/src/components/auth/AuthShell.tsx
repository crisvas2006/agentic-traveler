"use client";

import { BeamsBackground } from "@/components/ui/BeamsBackground";
import { useTheme } from "@/components/layout/ThemeProvider";
import { Sparkles, Sun, Moon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

interface AuthShellProps {
  children: ReactNode;
  marketingContent: ReactNode;
}

export function AuthShell({ children, marketingContent }: AuthShellProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute inset-0 opacity-0 dark:opacity-100 transition-opacity duration-700">
          <BeamsBackground intensity="strong" />
        </div>
        <div
          className="absolute inset-0 dark:hidden"
          style={{ background: "linear-gradient(135deg, #eff6ff 0%, var(--background) 50%, #faf5ff 100%)" }}
        />
        <div className="absolute -top-[10%] -left-[5%] w-[42%] h-[42%] rounded-full blur-[120px] animate-float bg-blue-500/10 dark:bg-blue-500/[0.08]" />
        <div className="absolute bottom-[6%] -right-[6%] w-[38%] h-[38%] rounded-full blur-[120px] animate-float-reverse bg-purple-500/10 dark:bg-purple-500/[0.08]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-20" />
      </div>

      {/* Theme toggle */}
      <div className="fixed top-5 right-5 z-50">
        <button
          type="button"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
          className="w-10 h-10 rounded-full flex items-center justify-center bg-foreground/5 hover:bg-primary/10 text-muted-foreground hover:text-primary transition-all"
        >
          {theme === "dark"
            ? <Sun className="w-[18px] h-[18px]" />
            : <Moon className="w-[18px] h-[18px]" />}
        </button>
      </div>

      {/* Split layout */}
      <div className="relative z-10 min-h-screen grid lg:grid-cols-[1.05fr_1fr]">
        {/* Marketing rail — hidden on mobile */}
        <div className="hidden lg:block p-6">
          <div className="h-full bg-background/70 backdrop-blur-xl border border-border rounded-[1.75rem] overflow-hidden shadow-[0_30px_60px_-30px_rgba(0,0,0,0.25)]">
            <aside className="h-full p-12 flex flex-col justify-between">
              <Link href="/" className="flex items-center gap-2 group w-fit">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-lg shadow-primary/20 group-hover:scale-110 transition-transform">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <span className="text-2xl font-black tracking-tighter text-foreground">Aletheia Travel</span>
              </Link>

              {marketingContent}

              <p className="text-xs text-muted-foreground">
                © 2026 Aletheia Travel · For the individual, not the average.
              </p>
            </aside>
          </div>
        </div>

        {/* Form column */}
        <div className="grid place-items-center px-5 py-10 sm:px-10">
          <div className="w-full max-w-[420px] animate-fade-up">
            {/* Mobile-only logo */}
            <div className="lg:hidden mb-8 flex justify-center">
              <Link href="/" className="flex items-center gap-2 group">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-lg shadow-primary/20 group-hover:scale-110 transition-transform">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <span className="text-2xl font-black tracking-tighter text-foreground">Aletheia Travel</span>
              </Link>
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
