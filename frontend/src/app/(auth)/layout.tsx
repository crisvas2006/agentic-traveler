import { ThemeProvider } from "@/components/layout/ThemeProvider";
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <div className="min-h-screen w-full theme-ivory">
        {children}
      </div>
    </ThemeProvider>
  );
}
