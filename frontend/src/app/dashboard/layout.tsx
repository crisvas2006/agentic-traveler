import type { ReactNode } from "react";
import { ThemeProvider } from "@/components/layout/ThemeProvider";

export const metadata = {
  title: "Dashboard — Aletheia Travel",
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      {/* Full-viewport shell with no scroll at the root level */}
      <div className="h-screen w-full overflow-hidden">
        {children}
      </div>
    </ThemeProvider>
  );
}
