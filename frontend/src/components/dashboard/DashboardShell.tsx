"use client";

import { useState, useRef, useEffect } from "react";
import { TRIPS, KYOTO_DAYS, TODAY_N, type Trip } from "@/lib/dashboard-data";
import { useUserProfile, type UserProfile } from "@/hooks/useUserProfile";
import { WelcomeGrantModal } from "./WelcomeGrantModal";
import { TopNav } from "./TopNav";
import { TripLibrary } from "./TripLibrary";
import { TripDetailPanel } from "./TripDetailPanel";
import { KyotoMap } from "./KyotoMap";
import { ChatStripIcons, ChatPanel, ChatBubbleFloating } from "./ChatPanel";
import { SparklesIcon, LibraryIcon } from "./DashIcons";
import { AvatarButton, ProfileDropdown } from "./ProfileDropdown";
import { BeamsBackground } from "@/components/ui/BeamsBackground";

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

/* ── Ambient backdrop ── */
function Backdrop({ theme }: { theme: "light" | "dark" }) {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div className={`absolute inset-0 transition-opacity duration-700 ${theme === "dark" ? "opacity-100" : "opacity-0"}`}>
        {theme === "dark" && <BeamsBackground intensity="medium" />}
      </div>
      <div
        className={`absolute inset-0 transition-opacity duration-700 ${theme === "dark" ? "opacity-0" : "opacity-100"}`}
        style={{ background: "linear-gradient(135deg, #eef4ff 0%, var(--background) 50%, #f5f0ff 100%)" }}
      />
      <div
        className="absolute -top-[10%] -left-[5%] w-[35%] h-[35%] rounded-full blur-[120px] animate-float"
        style={{ background: theme === "dark" ? "rgba(59,130,246,.08)" : "rgba(37,99,235,.16)" }}
      />
      <div
        className="absolute bottom-[6%] -right-[6%] w-[30%] h-[30%] rounded-full blur-[120px] animate-float-reverse"
        style={{ background: theme === "dark" ? "rgba(147,51,234,.08)" : "rgba(147,51,234,.14)" }}
      />
      <div className="absolute inset-0 grid-bg" />
    </div>
  );
}

/* ── Desktop layout ── */
function DesktopShell({
  trip, activeTripId, setActiveTripId, theme, userProfile,
}: {
  trip: Trip; activeTripId: string; setActiveTripId: (id: string) => void; theme: "light" | "dark"; userProfile: UserProfile;
}) {
  const [activeDayN, setActiveDayN] = useState(TODAY_N);
  const [chatStyle, setChatStyle] = useState<"strip" | "drawer">("strip");

  const chatColWidth = chatStyle === "drawer" ? "360px" : "56px";

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden">
      <TopNav trip={trip} onTripSelect={setActiveTripId} userProfile={userProfile} />

      <div className="flex-1 relative overflow-hidden">
        {/* Map — full bleed canvas */}
        <div className="absolute inset-0">
          <KyotoMap
            days={KYOTO_DAYS}
            todayN={TODAY_N}
            activeDayN={activeDayN}
            theme={theme}
            weather="rain"
          />
          {/* Vignette overlay to give panels contrast */}
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

        {/* Three-column floor layout */}
        <div
          className="absolute inset-0 grid p-4 gap-4 pointer-events-none"
          style={{ gridTemplateColumns: `280px 1fr ${chatColWidth}` }}
        >
          {/* Trip library (col 1) */}
          <div className="pointer-events-auto min-h-0">
            <TripLibrary activeId={activeTripId} onSelect={setActiveTripId} />
          </div>

          {/* Center: floating trip detail panel on the right side of the map */}
          <div className="relative pointer-events-none">
            <div className="absolute top-0 right-0 w-[460px] max-w-full max-h-full pointer-events-auto">
              <div className="h-[calc(100vh-56px-32px)] max-h-full">
                <TripDetailPanel
                  trip={trip}
                  days={KYOTO_DAYS}
                  todayN={TODAY_N}
                  layout="timeline"
                  density="comfortable"
                  activeDayN={activeDayN}
                  setActiveDayN={setActiveDayN}
                />
              </div>
            </div>

            {/* Map legend — bottom-left of center column */}
            <div className="absolute bottom-2 left-2 pointer-events-auto">
              <MapLegend />
            </div>
          </div>

          {/* Chat (col 3) */}
          {chatStyle === "strip" ? (
            <div className="pointer-events-auto">
              <ChatStripIcons onExpand={() => setChatStyle("drawer")} />
            </div>
          ) : (
            <div className="pointer-events-auto min-h-0">
              <ChatPanel onCollapse={() => setChatStyle("strip")} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Mobile layout (3-pane swipe) ── */
function MobileShell({
  trip, activeTripId, setActiveTripId, theme, userProfile,
}: {
  trip: Trip; activeTripId: string; setActiveTripId: (id: string) => void; theme: "light" | "dark"; userProfile: UserProfile;
}) {
  const [pane, setPane] = useState(1); // 0=library, 1=trip, 2=map
  const [chatOpen, setChatOpen] = useState(false);
  const [activeDayN, setActiveDayN] = useState(TODAY_N);
  const [profileOpen, setProfileOpen] = useState(false);
  // The dropdown renders as a fixed overlay outside the header to avoid the
  // backdropFilter stacking context making the panel appear transparent.
  // profileDropdownRef → the panel (treated as "inside" by the outside-click check)
  // avatarBtnRef       → the trigger button (excluded so the toggle onClick wins)
  const profileDropdownRef = useRef<HTMLDivElement>(null);
  const avatarBtnRef = useRef<HTMLDivElement>(null);

  // Touch swipe detection
  const touchStartX = useRef<number | null>(null);
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) < 40) return;
    if (dx < 0 && pane < 2) setPane((p) => p + 1); // swipe left → next
    if (dx > 0 && pane > 0) setPane((p) => p - 1); // swipe right → prev
    touchStartX.current = null;
  };

  const panes = [
    { id: "lib",  label: "Library" },
    { id: "trip", label: "Trip"    },
    { id: "map",  label: "Map"     },
  ];

  return (
    <div className="relative w-full h-full overflow-hidden flex flex-col">
      {/* Mobile top bar */}
      <header
        className="h-14 px-4 flex items-center justify-between border-b border-border flex-shrink-0"
        style={{
          background: "color-mix(in oklab, var(--background) 70%, transparent)",
          backdropFilter: "blur(20px)",
        }}
      >
        <button
          type="button"
          className="w-9 h-9 rounded-full grid place-items-center text-muted-foreground"
          onClick={() => setPane(0)}
        >
          <LibraryIcon width={16} height={16} />
        </button>
        <div className="flex flex-col items-center">
          <span className="text-sm font-bold leading-tight">{trip.destination}</span>
          <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-wider flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            {trip.dayLabel}
          </span>
        </div>
        {/* avatarBtnRef is passed as excludeRef to ProfileDropdown so that
            clicking the button when the dropdown is open is treated as "inside"
            — the outside-click handler stays silent and the toggle onClick closes */}
        <div ref={avatarBtnRef}>
          <AvatarButton
            initials={userProfile.initials}
            open={profileOpen}
            onClick={() => setProfileOpen((v) => !v)}
          />
        </div>
      </header>

      {/* Profile dropdown — rendered as a fixed overlay so the header's
          backdropFilter stacking context does not affect the panel background */}
      {profileOpen && (
        <div
          ref={profileDropdownRef}
          className="fixed top-14 right-3 z-[60]"
        >
          <ProfileDropdown
            userProfile={userProfile}
            onClose={() => setProfileOpen(false)}
            containerRef={profileDropdownRef}
            excludeRef={avatarBtnRef}
          />
        </div>
      )}

      {/* Pane container */}
      <div
        className="flex-1 relative overflow-hidden"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div
          className="absolute inset-0 flex transition-transform duration-500 ease-out"
          style={{ transform: `translateX(-${pane * (100 / 3)}%)`, width: "300%" }}
        >
          {/* Pane 0: Library */}
          <div className="h-full p-3 overflow-y-auto" style={{ width: "33.3333%" }}>
            <TripLibrary
              activeId={activeTripId}
              onSelect={(id) => { setActiveTripId(id); setPane(1); }}
            />
          </div>

          {/* Pane 1: Trip detail */}
          <div className="h-full p-3 overflow-hidden" style={{ width: "33.3333%" }}>
            <TripDetailPanel
              trip={trip}
              days={KYOTO_DAYS}
              todayN={TODAY_N}
              layout="accordion"
              density="comfortable"
              activeDayN={activeDayN}
              setActiveDayN={setActiveDayN}
            />
          </div>

          {/* Pane 2: Map */}
          <div className="h-full p-3" style={{ width: "33.3333%" }}>
            <div className="aletheia-card h-full overflow-hidden relative">
              <KyotoMap
                days={KYOTO_DAYS}
                todayN={TODAY_N}
                activeDayN={activeDayN}
                theme={theme}
                weather="rain"
              />
              <div className="absolute top-3 left-3">
                <MapLegend />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Pane indicator dots */}
      <div
        className="flex-shrink-0 flex items-center justify-center gap-1.5 py-3"
        style={{
          background: "color-mix(in oklab, var(--background) 70%, transparent)",
          backdropFilter: "blur(20px)",
          borderTop: "1px solid var(--border)",
        }}
      >
        {panes.map((p, i) => (
          <button
            key={p.id}
            type="button"
            onClick={() => setPane(i)}
            aria-label={p.label}
            className="transition-all rounded-full"
            style={{
              width: i === pane ? "24px" : "8px",
              height: "8px",
              background:
                i === pane
                  ? "linear-gradient(90deg, var(--primary), #9333ea)"
                  : "color-mix(in oklab, var(--foreground) 14%, transparent)",
            }}
          />
        ))}
      </div>

      {/* Floating chat bubble */}
      {!chatOpen && (
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          className="absolute bottom-16 right-4 z-40 w-14 h-14 rounded-full text-white grid place-items-center"
          style={{
            background: "linear-gradient(135deg, var(--primary), #9333ea)",
            boxShadow: "0 16px 40px -10px color-mix(in oklab, var(--primary) 70%, transparent)",
          }}
        >
          <SparklesIcon width={22} height={22} />
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 text-[10px] font-bold grid place-items-center">
            2
          </span>
        </button>
      )}

      {/* Full-screen chat sheet */}
      {chatOpen && (
        <div className="absolute inset-0 z-50 flex flex-col animate-fade-up" style={{ background: "var(--background)" }}>
          <ChatPanel onCollapse={() => setChatOpen(false)} />
        </div>
      )}
    </div>
  );
}

/* ── Root shell — picks desktop vs mobile via CSS visibility ── */
export function DashboardShell() {
  const [activeTripId, setActiveTripId] = useState("kyoto");

  // Live user data: fetched once here, passed down as props
  const userProfileRaw = useUserProfile();

  // Allow the WelcomeGrantModal to optimistically update the balance in state
  // without requiring a full re-fetch after a successful claim.
  const [profileOverride, setProfileOverride] = useState<Partial<typeof userProfileRaw>>({});
  const userProfile = { ...userProfileRaw, ...profileOverride };

  // Session-level dismiss — X button hides modal until next login;
  // if the grant is still unclaimed, the modal will reappear on the next session.
  const [modalDismissed, setModalDismissed] = useState(false);

  const handleGranted = (balance: number) => {
    if (balance >= 0) {
      // Mark claimed and update balance immediately
      setProfileOverride({
        balance,
        initialGrant: balance,
        welcomeClaimedAt: new Date().toISOString(),
      });
    } else {
      // balance=-1 means "already_claimed" — just hide the modal
      setProfileOverride({ welcomeClaimedAt: new Date().toISOString() });
    }
  };

  const handleDismiss = () => setModalDismissed(true);

  // Show modal only when:
  //   • profile has fully loaded (not loading)
  //   • the fetch didn't error (welcomeClaimedAt !== undefined)
  //   • the grant is genuinely unclaimed (welcomeClaimedAt === null)
  //   • user hasn't dismissed it this session
  const showWelcomeModal =
    !userProfile.loading &&
    !userProfile.fetchError &&
    userProfile.welcomeClaimedAt === null &&
    !modalDismissed;

  // Read theme from <html> class (set by ThemeProvider)
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  useEffect(() => {
    const update = () =>
      setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const trip = TRIPS.find((t) => t.id === activeTripId) || TRIPS[0];

  return (
    <>
      <Backdrop theme={theme} />

      {/* Desktop — shown on lg+ screens */}
      <div className="relative z-10 hidden lg:block h-full">
        <DesktopShell
          trip={trip}
          activeTripId={activeTripId}
          setActiveTripId={setActiveTripId}
          theme={theme}
          userProfile={userProfile}
        />
      </div>

      {/* Mobile — shown below lg */}
      <div className="relative z-10 flex lg:hidden h-full">
        <MobileShell
          trip={trip}
          activeTripId={activeTripId}
          setActiveTripId={setActiveTripId}
          theme={theme}
          userProfile={userProfile}
        />
      </div>

      {/* Welcome credits modal — shown once, until claimed */}
      {showWelcomeModal && (
        <WelcomeGrantModal onGranted={handleGranted} onDismiss={handleDismiss} />
      )}
    </>
  );
}
