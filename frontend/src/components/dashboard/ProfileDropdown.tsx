"use client";

import { useEffect, useState, type RefObject } from "react";
import type { UserProfile } from "@/hooks/useUserProfile";
import {
  SettingsIcon,
  CreditIcon,
  SunIcon,
  MoonIcon,
  HelpIcon,
  LogOutIcon,
} from "./DashIcons";

/* ─────────────────────────────────────────────────────────────
   Theme toggle hook
───────────────────────────────────────────────────────────── */
function useTheme() {
  const [isDark, setIsDark] = useState(
    () =>
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("dark")
  );

  useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() =>
      setIsDark(el.classList.contains("dark"))
    );
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);

  const toggle = (dark: boolean) => {
    const el = document.documentElement;
    if (dark) {
      el.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      el.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  return { isDark, toggle };
}

/* ─────────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────────── */
function Divider() {
  return <div className="my-1.5 h-px bg-border" />;
}

function Row({
  icon,
  label,
  sub,
  destructive = false,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  sub?: string;
  destructive?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors text-left group ${destructive
          ? "hover:bg-rose-500/10 text-rose-500 dark:text-rose-400"
          : "hover:bg-foreground/5 text-foreground"
        }`}
    >
      <span
        className={`flex-shrink-0 ${destructive
            ? "text-rose-500 dark:text-rose-400"
            : "text-muted-foreground group-hover:text-foreground transition-colors"
          }`}
      >
        {icon}
      </span>
      <span className="flex-1 min-w-0">
        <span className="text-sm font-medium leading-tight">{label}</span>
        {sub && (
          <span className="block text-[11px] text-muted-foreground leading-tight mt-0.5">
            {sub}
          </span>
        )}
      </span>
    </button>
  );
}

function CreditsRow({ balance, initialGrant }: { balance: number; initialGrant: number }) {
  // Use initialGrant as the 100% baseline; fall back to balance itself so
  // the bar still renders even if initial_grant hasn't been set yet.
  const baseline = initialGrant > 0 ? initialGrant : balance;
  const pct = baseline > 0 ? Math.min(100, Math.round((balance / baseline) * 100)) : 100;

  const critical = balance < 25;
  const low = !critical && balance < 50;

  const labelColor = critical
    ? "text-rose-500 dark:text-rose-400"
    : low
      ? "text-amber-500 dark:text-amber-400"
      : "text-muted-foreground";

  const barColor = critical
    ? "bg-gradient-to-r from-rose-500 to-red-500"
    : low
      ? "bg-gradient-to-r from-amber-400 to-orange-500"
      : "bg-gradient-to-r from-primary to-purple-500";

  return (
    <div className="px-3 py-2.5 rounded-xl">
      <div className="flex items-center gap-3 mb-2">
        <span className="flex-shrink-0 text-muted-foreground">
          <CreditIcon width={16} height={16} />
        </span>
        <span className="text-sm font-medium text-foreground flex-1">Credits</span>
        <span className={`text-xs font-semibold tabular-nums ${labelColor}`}>
          {balance} remaining
        </span>
      </div>
      {baseline > 0 && (
        <>
          <div className="h-1.5 rounded-full bg-foreground/10 overflow-hidden ml-7">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          {critical && (
            <p className="text-[11px] text-rose-500 dark:text-rose-400 ml-7 mt-1.5">
              Almost out — top up in account settings.
            </p>
          )}
          {low && (
            <p className="text-[11px] text-amber-500 dark:text-amber-400 ml-7 mt-1.5">
              Running low — top up when you can.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ThemeToggleRow() {
  const { isDark, toggle } = useTheme();

  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <span className="flex-shrink-0 text-muted-foreground">
        {isDark ? <MoonIcon width={16} height={16} /> : <SunIcon width={16} height={16} />}
      </span>
      <span className="text-sm font-medium text-foreground flex-1">Theme</span>
      <div
        className="flex rounded-lg border border-border p-0.5 gap-0.5"
        style={{ background: "color-mix(in oklab, var(--foreground) 4%, transparent)" }}
      >
        <button
          type="button"
          onClick={() => toggle(false)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${!isDark ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
        >
          <SunIcon width={12} height={12} />
          Day
        </button>
        <button
          type="button"
          onClick={() => toggle(true)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-all ${isDark ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
            }`}
        >
          <MoonIcon width={12} height={12} />
          Night
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Avatar component (reused in trigger button and panel header)
───────────────────────────────────────────────────────────── */
function Avatar({ initials, size = "sm" }: { initials: string; size?: "sm" | "lg" }) {
  const cls = size === "lg" ? "w-11 h-11 text-base font-bold" : "w-9 h-9 text-sm font-bold";
  return (
    <div
      className={`${cls} rounded-full grid place-items-center text-white flex-shrink-0`}
      style={{ background: "linear-gradient(135deg, #f59e0b, #ec4899)" }}
    >
      {initials}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Avatar trigger button (exported — used by TopNav)
───────────────────────────────────────────────────────────── */
interface AvatarButtonProps {
  initials: string;
  open: boolean;
  onClick: () => void;
}

export function AvatarButton({ initials, open, onClick }: AvatarButtonProps) {
  return (
    <button
      type="button"
      title="Profile"
      onClick={onClick}
      aria-haspopup="true"
      aria-expanded={open}
      className={`
        w-9 h-9 rounded-full grid place-items-center text-white font-bold text-sm
        transition-all duration-150
        hover:scale-110 hover:shadow-lg hover:shadow-pink-500/30
        active:scale-95
        ${open ? "ring-2 ring-primary ring-offset-2 ring-offset-background scale-105" : ""}
      `}
      style={{ background: "linear-gradient(135deg, #f59e0b, #ec4899)" }}
    >
      {initials}
    </button>
  );
}

/* ─────────────────────────────────────────────────────────────
   Dropdown panel
───────────────────────────────────────────────────────────── */
interface ProfileDropdownProps {
  userProfile: UserProfile;
  onClose: () => void;
  containerRef: RefObject<HTMLDivElement | null>;
  /**
   * Optional extra ref whose subtree is treated as "inside" for the
   * outside-click check.  Used on mobile to exclude the avatar button
   * (which lives outside the fixed dropdown wrapper) so the toggle onClick
   * can close the panel without racing against this handler.
   */
  excludeRef?: RefObject<Element | null>;
}

export function ProfileDropdown({
  userProfile,
  onClose,
  containerRef,
  excludeRef,
}: ProfileDropdownProps) {
  /* Close on Escape or click outside the container */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onOutside = (e: MouseEvent) => {
      const inContainer = containerRef.current?.contains(e.target as Node) ?? false;
      const inExcluded = excludeRef?.current?.contains(e.target as Node) ?? false;
      if (!inContainer && !inExcluded) onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onOutside);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onOutside);
    };
  }, [onClose, containerRef, excludeRef]);

  const handleSignOut = async () => {
    // POST to the route handler so the sign-out is server-side and cannot be
    // triggered via CSRF (a GET-based logout can be fired by any <img> tag).
    await fetch("/logout", { method: "POST" });
    window.location.href = "/login";
  };

  const hasDna = userProfile.dnaTags.length > 0;

  return (
    <div
      role="menu"
      className="absolute top-full mt-2 right-0 w-72 border border-border rounded-[1.75rem] animate-fade-up z-50 overflow-hidden"
      style={{
        background: "var(--background)",
        boxShadow:
          "0 4px 6px -1px rgba(0,0,0,.15), 0 20px 40px -10px rgba(0,0,0,.3), 0 1px 0 color-mix(in oklab, var(--foreground) 5%, transparent) inset",
      }}
    >
      <div className="p-2">
        {/* ── Section 1: Identity ── */}
        <div className="px-3 pt-2.5 pb-3">
          <div className="flex items-center gap-3">
            <Avatar initials={userProfile.initials} size="lg" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-foreground leading-tight truncate">
                {userProfile.name || (
                  <span className="text-muted-foreground">Loading…</span>
                )}
              </div>
              <div className="text-xs text-muted-foreground truncate mt-0.5">
                {userProfile.email}
              </div>
            </div>
          </div>

          {/* DNA tags or CTA */}
          <div className="mt-3">
            {hasDna ? (
              <div className="flex flex-wrap gap-1.5">
                {userProfile.dnaTags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold"
                    style={{
                      background: "color-mix(in oklab, var(--primary) 12%, transparent)",
                      color: "var(--primary)",
                      border: "1px solid color-mix(in oklab, var(--primary) 25%, transparent)",
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <button
                type="button"
                onClick={onClose}
                className="text-xs font-semibold text-primary hover:underline"
              >
                Complete your Traveler DNA →
              </button>
            )}
          </div>
        </div>

        <Divider />

        {/* ── Section 2: My account ── */}
        <p className="px-3 pt-1 pb-0.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          My account
        </p>
        <a href="/settings" className="block" onClick={onClose}>
          <Row
            icon={<SettingsIcon width={16} height={16} />}
            label="Account settings"
            sub="Profile, credits, security"
          />
        </a>
        <CreditsRow balance={userProfile.balance} initialGrant={userProfile.initialGrant} />

        <Divider />

        {/* ── Section 3: App ── */}
        <p className="px-3 pt-1 pb-0.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          App
        </p>
        <ThemeToggleRow />
        <Row
          icon={<HelpIcon width={16} height={16} />}
          label="Help & FAQ"
          sub="Guides, shortcuts, contact us"
          onClick={onClose}
        />

        <Divider />

        {/* ── Section 4: Sign out ── */}
        <Row
          icon={<LogOutIcon width={16} height={16} />}
          label="Sign out"
          destructive
          onClick={handleSignOut}
        />
      </div>
    </div>
  );
}
