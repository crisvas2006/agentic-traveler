"use client";

import { AlertTriangleIcon } from "lucide-react";

interface SafetyWarningBannerProps {
  score: number;
  country: string;
  sources?: string[];
}

export function SafetyWarningBanner({ score, country, sources }: SafetyWarningBannerProps) {
  // Typical default threshold is 7.0
  if (score >= 7.0) return null;

  return (
    <div className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 flex gap-3 text-amber-600 dark:text-amber-400">
      <AlertTriangleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-relaxed opacity-90">
          Travel advisories suggest extra caution for {country}. Verify with official sources before booking.
        </p>
        {sources && sources.length > 0 && (
          <div className="mt-1.5 text-[10px] uppercase tracking-wider opacity-70">
            Sources: {sources.join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}
