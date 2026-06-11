"use client";

import { useCallback, useState, useRef, useEffect } from "react";
import { useUserProfile, type UserProfile } from "@/hooks/useUserProfile";
import { useTrip, useTripList } from "@/hooks/useTrip";
import type { Trip, TripDay, TripSummary } from "@/lib/dashboard-data";
// Map placeholder data — the dashboard map is a NON-GOAL of task 40 and is
// replaced wholesale by a real MapLibre map in task 49. Until then it renders
// from these demo days so the canvas stays visually coherent, decoupled from
// live trip data (live itinerary blocks carry no abstract-canvas pins).
import { KYOTO_DAYS, TODAY_N as MAP_TODAY_N } from "@/lib/dashboard-fixtures";
import { WelcomeGrantModal } from "./WelcomeGrantModal";
import { TopNav } from "./TopNav";
import { TripLibrary } from "./TripLibrary";
import { TripDetailPanel } from "./TripDetailPanel";
import { KyotoMap } from "./KyotoMap";
import { ChatStripIcons, ChatPanel } from "./ChatPanel";
import { SparklesIcon, LibraryIcon } from "./DashIcons";
import { AvatarButton, ProfileDropdown } from "./ProfileDropdown";

/* ── Map legend ── */
function MapLegend() {
  return (
    <div className="aletheia-card p-2.5 flex items-center gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span
          className="w-3 h-3 rounded-full"
          style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
        />
        Today
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full bg-foreground/30" />
        Past
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full border-2 border-dashed border-foreground/30" />
        Future
      </span>
    </div>
  );
}

/* ── Empty-trip onboarding canvas (frontend_dashboard_design.md §7) ── */
function EmptyTripCanvas({ onStart }: { onStart: () => void }) {
  const cards = [
    { title: "Discover", body: "Find where to go from your travel DNA." },
    { title: "Plan", body: "Shape a day-by-day trip, your pace." },
    { title: "Live", body: "Adapt on the ground, day by day." },
  ];
  return (
    <div className="aletheia-card h-full overflow-y-auto flex flex-col items-center justify-center text-center px-6 py-10" style={{ background: "var(--background)" }}>
      <div
        className="w-14 h-14 rounded-2xl grid place-items-center mb-5"
        style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
      >
        <SparklesIcon width={26} height={26} className="text-white" />
      </div>
      <h2 className="text-2xl font-extrabold tracking-tight">Your journey starts here.</h2>
      <p className="text-sm text-muted-foreground mt-2 max-w-xs">
        Tell me what you&apos;re dreaming of, and I&apos;ll help it take shape.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mt-7 w-full max-w-md">
        {cards.map((c) => (
          <div key={c.title} className="rounded-2xl border border-border p-3.5 text-left" style={{ background: "color-mix(in oklab, var(--background) 55%, transparent)" }}>
            <div className="text-sm font-bold">{c.title}</div>
            <div className="text-xs text-muted-foreground leading-relaxed mt-1">{c.body}</div>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={onStart}
        className="mt-7 px-5 py-2.5 rounded-full text-white font-bold text-sm transition hover:scale-[1.03]"
        style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)" }}
      >
        Plan your first trip →
      </button>
    </div>
  );
}

/* ── Ambient backdrop ── */
function Backdrop({ theme }: { theme: "light" | "dark" }) {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div
        className="absolute inset-0"
        style={{
          background:
            theme === "dark"
              ? "linear-gradient(135deg, #0a0f1f 0%, var(--background) 60%, #0d1326 100%)"
              // Warm ivory ground — accents mixed INTO the paper so the frosted
              // glass cards sample a warm tint, not cold pastel (matches the
              // auth/marketing shells).
              : "linear-gradient(135deg, color-mix(in oklab, var(--primary) 7%, var(--background)) 0%, var(--background) 50%, color-mix(in oklab, #9333ea 7%, var(--background)) 100%)",
        }}
      />
      <div className="absolute inset-0 grid-bg" />
    </div>
  );
}

interface ShellViewProps {
  trip: Trip | null;
  days: TripDay[];
  todayN: number;
  loading: boolean;
  summaries: TripSummary[];
  activeTripId: string | null;
  setActiveTripId: (id: string) => void;
  theme: "light" | "dark";
  userProfile: UserProfile;
  sendMessage: (text: string) => void;
}

/* ── Desktop layout ── */
function DesktopShell({
  trip, days, todayN, summaries, activeTripId, setActiveTripId,
  theme, userProfile, sendMessage,
}: ShellViewProps) {
  const [activeDayN, setActiveDayN] = useState(todayN);
  const [chatStyle, setChatStyle] = useState<"strip" | "drawer">("strip");
  const [chatExpanded, setChatExpanded] = useState(false);

  // Reset to the focused trip's "today" when the trip changes. React's
  // adjust-state-during-render pattern (no effect): converges immediately.
  const [seenTrip, setSeenTrip] = useState(activeTripId);
  if (seenTrip !== activeTripId) {
    setSeenTrip(activeTripId);
    setActiveDayN(todayN);
  }

  // Esc key collapses expand mode (AC-9 / E10).
  useEffect(() => {
    if (!chatExpanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChatExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [chatExpanded]);

  const chatColWidth = chatStyle === "drawer" ? "360px" : "56px";

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden">
      <TopNav summaries={summaries} activeId={activeTripId} onTripSelect={setActiveTripId} userProfile={userProfile} />

      <div className="flex-1 relative overflow-hidden">
        {/* Map — full bleed canvas (placeholder pending task 49) */}
        <div className={`absolute inset-0 ${chatExpanded ? "hidden" : ""}`}>
          <KyotoMap days={KYOTO_DAYS} todayN={MAP_TODAY_N} activeDayN={MAP_TODAY_N} theme={theme} weather="rain" />
          <div
            className="absolute inset-0"
            style={{
              background:
                theme === "dark"
                  ? "radial-gradient(circle at 30% 50%, transparent 0%, rgba(10,18,36,.4) 80%)"
                  : "radial-gradient(circle at 30% 50%, transparent 0%, rgba(247,245,240,.5) 90%)",
            }}
          />
        </div>

        {/* Normal pane layout (hidden when expanded) */}
        {!chatExpanded && (
          <div
            className="absolute inset-0 grid p-4 gap-4 pointer-events-none"
            style={{ gridTemplateColumns: `280px 1fr ${chatColWidth}` }}
          >
            <div className="pointer-events-auto min-h-0">
              <TripLibrary
                summaries={summaries}
                activeId={activeTripId}
                onSelect={setActiveTripId}
                onNew={() => sendMessage("I'd like to plan a new trip.")}
              />
            </div>

            <div className="relative pointer-events-none">
              <div className="absolute top-0 right-0 w-[460px] max-w-full max-h-full pointer-events-auto">
                <div className="h-[calc(100vh-56px-32px)] max-h-full">
                  {trip ? (
                    <TripDetailPanel
                      trip={trip}
                      days={days}
                      todayN={todayN}
                      layout="timeline"
                      density="comfortable"
                      activeDayN={activeDayN}
                      setActiveDayN={setActiveDayN}
                      onSendMessage={sendMessage}
                    />
                  ) : (
                    <EmptyTripCanvas onStart={() => sendMessage("I'd like to plan a trip.")} />
                  )}
                </div>
              </div>

              <div className="absolute bottom-2 left-2 pointer-events-auto">
                <MapLegend />
              </div>
            </div>

            {chatStyle === "strip" ? (
              <div className="pointer-events-auto">
                <ChatStripIcons onExpand={() => setChatStyle("drawer")} />
              </div>
            ) : (
              <div className="pointer-events-auto min-h-0">
                {/* Expand toggle renders in the header via ChatPanel's onExpand prop */}
                <ChatPanel
                  onCollapse={() => setChatStyle("strip")}
                  onExpand={() => setChatExpanded(true)}
                />
              </div>
            )}
          </div>
        )}

        {/* Expand overlay (lg+ only, AC-9). Uses is-solid card — no backdrop-filter
            cost over the map background (spec §5 performance constraint). */}
        {chatExpanded && (
          <div className="absolute inset-0 aletheia-card is-solid flex flex-col overflow-hidden chat-expand-overlay">
            <div className="flex-1 flex flex-col max-w-[720px] w-full mx-auto min-h-0">
              <ChatPanel
                onCollapse={() => setChatExpanded(false)}
                onExpand={() => setChatExpanded(false)}
                expandedMode
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Mobile layout (3-pane swipe) ── */
function MobileShell({
  trip, days, todayN, summaries, activeTripId, setActiveTripId,
  theme, userProfile, sendMessage,
}: ShellViewProps) {
  const [pane, setPane] = useState(1); // 0=library, 1=trip, 2=map
  const [chatOpen, setChatOpen] = useState(false);
  const [activeDayN, setActiveDayN] = useState(todayN);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileDropdownRef = useRef<HTMLDivElement>(null);
  const avatarBtnRef = useRef<HTMLDivElement>(null);

  // Reset to the focused trip's "today" when the trip changes (no effect).
  const [seenTrip, setSeenTrip] = useState(activeTripId);
  if (seenTrip !== activeTripId) {
    setSeenTrip(activeTripId);
    setActiveDayN(todayN);
  }

  const active = summaries.find((t) => t.id === activeTripId) ?? summaries[0];

  const touchStartX = useRef<number | null>(null);
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) < 40) return;
    if (dx < 0 && pane < 2) setPane((p) => p + 1);
    if (dx > 0 && pane > 0) setPane((p) => p - 1);
    touchStartX.current = null;
  };

  const panes = [
    { id: "lib", label: "Library" },
    { id: "trip", label: "Trip" },
    { id: "map", label: "Map" },
  ];

  return (
    <div className="relative w-full h-full overflow-hidden flex flex-col">
      <header
        className="h-14 px-4 flex items-center justify-between border-b border-border flex-shrink-0"
        style={{ background: "color-mix(in oklab, var(--background) 70%, transparent)", backdropFilter: "blur(20px)" }}
      >
        <button type="button" className="w-9 h-9 rounded-full grid place-items-center text-muted-foreground" onClick={() => setPane(0)}>
          <LibraryIcon width={16} height={16} />
        </button>
        <div className="flex flex-col items-center">
          <span className="text-sm font-bold leading-tight">{active?.destination ?? "Aletheia"}</span>
          {active && (
            <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {active.dayLabel}
            </span>
          )}
        </div>
        <div ref={avatarBtnRef}>
          <AvatarButton initials={userProfile.initials} open={profileOpen} onClick={() => setProfileOpen((v) => !v)} />
        </div>
      </header>

      {profileOpen && (
        <div ref={profileDropdownRef} className="fixed top-14 right-3 z-[60]">
          <ProfileDropdown userProfile={userProfile} onClose={() => setProfileOpen(false)} containerRef={profileDropdownRef} excludeRef={avatarBtnRef} />
        </div>
      )}

      <div className="flex-1 relative overflow-hidden" onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
        <div className="absolute inset-0 flex transition-transform duration-500 ease-out" style={{ transform: `translateX(-${pane * (100 / 3)}%)`, width: "300%" }}>
          <div className="h-full p-3 overflow-y-auto" style={{ width: "33.3333%" }}>
            <TripLibrary
              summaries={summaries}
              activeId={activeTripId}
              onSelect={(id) => { setActiveTripId(id); setPane(1); }}
              onNew={() => { sendMessage("I'd like to plan a new trip."); setChatOpen(true); }}
            />
          </div>

          <div className="h-full p-3 overflow-hidden" style={{ width: "33.3333%" }}>
            {trip ? (
              <TripDetailPanel
                trip={trip}
                days={days}
                todayN={todayN}
                layout="accordion"
                density="comfortable"
                activeDayN={activeDayN}
                setActiveDayN={setActiveDayN}
                onSendMessage={sendMessage}
              />
            ) : (
              <EmptyTripCanvas onStart={() => { sendMessage("I'd like to plan a trip."); setChatOpen(true); }} />
            )}
          </div>

          <div className="h-full p-3" style={{ width: "33.3333%" }}>
            <div className="aletheia-card h-full overflow-hidden relative">
              <KyotoMap days={KYOTO_DAYS} todayN={MAP_TODAY_N} activeDayN={MAP_TODAY_N} theme={theme} weather="rain" />
              <div className="absolute top-3 left-3">
                <MapLegend />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        className="flex-shrink-0 flex items-center justify-center gap-1.5 py-3"
        style={{ background: "color-mix(in oklab, var(--background) 70%, transparent)", backdropFilter: "blur(20px)", borderTop: "1px solid var(--border)" }}
      >
        {panes.map((p, i) => (
          <button
            key={p.id} type="button" onClick={() => setPane(i)} aria-label={p.label}
            className="transition-all rounded-full"
            style={{
              width: i === pane ? "24px" : "8px", height: "8px",
              background: i === pane ? "linear-gradient(90deg, var(--primary), #9333ea)" : "color-mix(in oklab, var(--foreground) 14%, transparent)",
            }}
          />
        ))}
      </div>

      {!chatOpen && (
        <button
          type="button" onClick={() => setChatOpen(true)}
          className="absolute bottom-16 right-4 z-40 w-14 h-14 rounded-full text-white grid place-items-center"
          style={{ background: "linear-gradient(135deg, var(--primary), #9333ea)", boxShadow: "0 16px 40px -10px color-mix(in oklab, var(--primary) 70%, transparent)" }}
        >
          <SparklesIcon width={22} height={22} />
        </button>
      )}

      {chatOpen && (
        <div className="absolute inset-0 z-50 flex flex-col animate-fade-up" style={{ background: "var(--background)" }}>
          <ChatPanel onCollapse={() => setChatOpen(false)} />
        </div>
      )}
    </div>
  );
}

/* ── Root shell ── */
export function DashboardShell() {
  const { summaries, defaultActiveId } = useTripList();
  const [activeTripId, setActiveTripId] = useState<string | null>(null);

  // Adopt the resolved default trip once it loads, without clobbering a user
  // choice. Adjust-state-during-render (no effect): the guard makes it
  // converge after the first non-null default.
  if (activeTripId === null && defaultActiveId !== null) {
    setActiveTripId(defaultActiveId);
  }

  const { trip, days, todayN, loading } = useTrip(activeTripId);

  // Send a message into the chat thread (idea chips, mood, journal prompts,
  // "plan a trip" CTAs). Fire-and-forget: the persisted turn + reply surface
  // in the chat panel via its realtime subscription (task 37).
  const sendMessage = useCallback((text: string) => {
    void fetch("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: text }),
    }).catch(() => {});
  }, []);

  const userProfileRaw = useUserProfile();

  useEffect(() => {
    if (!userProfileRaw.loading && !userProfileRaw.fetchError) {
      if (!userProfileRaw.hasCompletedForm) {
        fetch("/api/chat/init-welcome", { method: "POST" })
          .catch((err) => console.error("Failed to initialize welcome message:", err));
      }
    }
  }, [userProfileRaw.loading, userProfileRaw.fetchError, userProfileRaw.hasCompletedForm]);

  const [profileOverride, setProfileOverride] = useState<Partial<typeof userProfileRaw>>({});
  const userProfile = { ...userProfileRaw, ...profileOverride };

  const [modalDismissed, setModalDismissed] = useState(false);

  const handleGranted = (balance: number) => {
    if (balance >= 0) {
      setProfileOverride({ balance, initialGrant: balance, welcomeClaimedAt: new Date().toISOString() });
    } else {
      setProfileOverride({ welcomeClaimedAt: new Date().toISOString() });
    }
  };

  const handleDismiss = async () => {
    setModalDismissed(true);
    try {
      const res = await fetch("/api/credits/welcome-grant", { method: "POST" });
      let body: { status?: "granted" | "already_claimed"; balance?: number; error?: string };
      try {
        body = await res.json();
      } catch {
        body = {};
      }
      if (res.ok && body.status === "granted" && typeof body.balance === "number") {
        setProfileOverride({ balance: body.balance, initialGrant: body.balance, welcomeClaimedAt: new Date().toISOString() });
      } else {
        setProfileOverride({ welcomeClaimedAt: new Date().toISOString() });
      }
    } catch (err) {
      console.error("Failed to silently claim welcome credits on dismiss:", err);
      setProfileOverride({ welcomeClaimedAt: new Date().toISOString() });
    }
  };

  const showWelcomeModal =
    !userProfile.loading &&
    !userProfile.fetchError &&
    userProfile.welcomeClaimedAt === null &&
    !modalDismissed;

  const [theme, setTheme] = useState<"light" | "dark">("dark");
  useEffect(() => {
    const update = () => setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const viewProps: ShellViewProps = {
    trip, days, todayN, loading, summaries, activeTripId, setActiveTripId,
    theme, userProfile, sendMessage,
  };

  return (
    <>
      <Backdrop theme={theme} />

      <div className="relative z-10 hidden lg:block h-full">
        <DesktopShell {...viewProps} />
      </div>

      <div className="relative z-10 flex lg:hidden h-full">
        <MobileShell {...viewProps} />
      </div>

      {showWelcomeModal && (
        <WelcomeGrantModal onGranted={handleGranted} onDismiss={handleDismiss} />
      )}
    </>
  );
}

// triggered hot reload
