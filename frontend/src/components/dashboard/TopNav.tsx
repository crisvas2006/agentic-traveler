"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { TripSummary } from "@/lib/dashboard-data";
import type { UserProfile } from "@/hooks/useUserProfile";
import { StatusChip } from "./DashChips";
import { SparklesIcon, DNAIcon, ChevronDownIcon } from "./DashIcons";
import { BookOpen } from "lucide-react";
import { AvatarButton, ProfileDropdown } from "./ProfileDropdown";

interface TopNavProps {
  summaries: TripSummary[];
  activeId: string | null;
  onTripSelect: (id: string) => void;
  userProfile: UserProfile;
}

export function TopNav({ summaries, activeId, onTripSelect, userProfile }: TopNavProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const active = summaries.find((t) => t.id === activeId) ?? summaries[0];
  const [profileOpen, setProfileOpen] = useState(false);

  // Wraps both the AvatarButton and ProfileDropdown so clicks inside
  // the container are not treated as "outside" by the dismiss handler.
  const profileContainerRef = useRef<HTMLDivElement>(null);

  return (
    <nav
      className="h-14 px-4 flex items-center justify-between border-b border-border aletheia-card"
      style={{ borderRadius: 0 }}
    >
      {/* Logo */}
      <a href="#" className="flex items-center gap-2 group">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110"
          style={{
            background: "linear-gradient(135deg, var(--primary), #9333ea)",
            boxShadow:
              "0 8px 20px -8px color-mix(in oklab, var(--primary) 60%, transparent)",
          }}
        >
          <SparklesIcon width={20} height={20} className="text-white" />
        </div>
        <span className="text-lg font-black tracking-tighter">Aletheia</span>
      </a>

      {/* Trip context chip */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2.5 px-3.5 h-9 rounded-full border border-border hover:border-primary/30 transition"
          style={{ background: "color-mix(in oklab, var(--foreground) 3%, transparent)" }}
        >
          <span className="relative flex w-2 h-2">
            <span className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-60" />
            <span className="relative w-2 h-2 rounded-full bg-emerald-500" />
          </span>
          <span className="text-sm font-bold">{active?.destination ?? "No trips yet"}</span>
          {active && <span className="text-xs text-muted-foreground">· {active.dayLabel}</span>}
          <ChevronDownIcon width={14} height={14} className="text-muted-foreground" />
        </button>

        {open && summaries.length > 0 && (
          <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 w-72 aletheia-card p-2 animate-fade-up z-50">
            {summaries.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => { onTripSelect(t.id); setOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left hover:bg-foreground/5 transition ${
                  t.id === activeId ? "bg-foreground/[0.04]" : ""
                }`}
              >
                <div
                  className="w-8 h-8 rounded-lg flex-shrink-0"
                  style={{
                    background: `linear-gradient(135deg, hsl(${t.cover.hue} 60% 50%), hsl(${(t.cover.hue + 30) % 360} 70% 38%))`,
                  }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold leading-tight">{t.destination}</div>
                  <div className="text-[11px] text-muted-foreground">{t.dayLabel}</div>
                </div>
                <StatusChip status={t.status} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          title="Traveler DNA"
          className="w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
        >
          <DNAIcon width={16} height={16} />
        </button>
        <button
          type="button"
          title="Capability guide"
          aria-label="See everything Aletheia can do"
          onClick={() => router.push("/guide")}
          className="w-9 h-9 rounded-full grid place-items-center text-muted-foreground hover:text-primary hover:bg-foreground/5 transition"
        >
          <BookOpen width={16} height={16} />
        </button>
        <div className="w-px h-5 bg-border mx-1" />

        {/* Profile avatar + dropdown */}
        <div className="relative" ref={profileContainerRef}>
          <AvatarButton
            initials={userProfile.initials}
            open={profileOpen}
            onClick={() => setProfileOpen((v) => !v)}
          />
          {profileOpen && (
            <ProfileDropdown
              userProfile={userProfile}
              onClose={() => setProfileOpen(false)}
              containerRef={profileContainerRef}
            />
          )}
        </div>
      </div>
    </nav>
  );
}
