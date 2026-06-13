"use client";

import { useCallback, useState, useRef, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUserProfile, type UserProfile } from "@/hooks/useUserProfile";
import { useTrip, useTripList } from "@/hooks/useTrip";
import { ChatProvider, useChat } from "@/hooks/useChat";
import type { Trip, TripDay, TripSummary } from "@/lib/dashboard-data";
import { WelcomeGrantModal } from "./WelcomeGrantModal";
import { TopNav } from "./TopNav";
import { TripLibrary } from "./TripLibrary";
import { TripDetailPanel } from "./TripDetailPanel";
import dynamic from "next/dynamic";
import { ChatStripIcons, ChatPanel } from "./ChatPanel";
import { CapabilityChips } from "./CapabilityChips";
import { CAPABILITIES } from "@/lib/capabilities";
import type { AvailabilityState } from "@/lib/capabilities";

const TripMap = dynamic(() => import("./TripMap"), { ssr: false });
import { SparklesIcon, LibraryIcon } from "./DashIcons";
import { AvatarButton, ProfileDropdown } from "./ProfileDropdown";

// ── ?launch=<id> one-shot consumer (Task 53 / spec §7 Step 3) ─────────────────
// Reads the search param, fires the matching capability send, then clears the
// URL with router.replace. A ref guards against double-fire on re-render.
// Must be inside ChatProvider so it can call useChat() for setComposerDraft.
// Wrapped in Suspense because useSearchParams suspends in Next.js App Router.
function LaunchFromParamInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { send, sendCapability, setComposerDraft, injectMoodPicker, openChatPanel } = useChat();
  const fired = useRef(false);

  useEffect(() => {
    const id = searchParams.get("launch");
    if (!id || fired.current) return;
    fired.current = true;

    const cap = CAPABILITIES.find((c) => c.id === id);
    // Always clear the param first — unknown id, link-kind, and all others.
    router.replace("/dashboard");

    if (!cap) return; // spec E5: unknown id → clear param, no send

    if (cap.launch.kind === "link") {
      router.push(cap.launch.href); // spec E8: link-kind navigates directly
      return;
    }

    // Defer one tick: sibling shell useEffect hooks (registerOpenChatPanel,
    // registerComposerSetter) run after LaunchFromParamInner in React's
    // depth-first effect order, so we must yield before calling into them.
    setTimeout(() => {
      if (cap.launch.kind === "message") {
        void send(cap.launch.text);
      } else if (cap.launch.kind === "intent") {
        void sendCapability(cap.id, cap.launch.label);
      } else if (cap.launch.kind === "draft") {
        setComposerDraft(cap.launch.text);
      } else if (cap.launch.kind === "ephemeral_mood") {
        injectMoodPicker();
      }
      openChatPanel();
    }, 0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally runs once on mount only

  return null;
}

function LaunchFromParam() {
  return (
    <Suspense>
      <LaunchFromParamInner />
    </Suspense>
  );
}

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
function EmptyTripCanvas({
  availability,
  onLaunched,
}: {
  availability: AvailabilityState;
  onLaunched?: () => void;
}) {
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
      <div className="mt-7">
        <CapabilityChips context="no_trip" availability={availability} onLaunched={onLaunched} />
      </div>
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
  setActiveTripId: (id: string | null) => void;
  theme: "light" | "dark";
  userProfile: UserProfile;
  sendMessage: (text: string) => void;
  availability: AvailabilityState;
  // Task 52 — trip-focus bridge.
  getFocusedTripId: () => string | null;
  applyFocus: (id: string | null) => void;
  clearFocus: () => void;
}

/* ── Desktop layout ── */
function DesktopShell({
  trip, days, todayN, summaries, activeTripId, setActiveTripId,
  theme, userProfile, sendMessage, availability,
  getFocusedTripId, applyFocus, clearFocus,
}: ShellViewProps) {
  const [activeDayN, setActiveDayN] = useState(todayN);
  const [chatStyle, setChatStyle] = useState<"strip" | "drawer">("strip");
  const [chatExpanded, setChatExpanded] = useState(false);

  const { registerOpenChatPanel, registerFocusBridge } = useChat();
  useEffect(() => {
    registerOpenChatPanel("desktop", () => setChatStyle("drawer"));
  }, [registerOpenChatPanel]);
  useEffect(() => {
    registerFocusBridge(getFocusedTripId, applyFocus);
  }, [registerFocusBridge, getFocusedTripId, applyFocus]);

  // The chip shows the focused trip's primary destination (Task 52 AC-11).
  const focusedTrip = activeTripId
    ? { id: activeTripId, destination: summaries.find((s) => s.id === activeTripId)?.destination ?? "Trip" }
    : null;

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
          <TripMap trip={trip} days={days} activeDayN={activeDayN} theme={theme} userProfile={userProfile} />
          <div
            className="absolute inset-0 pointer-events-none"
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
                      onClose={() => { setActiveTripId(null); clearFocus(); }}
                    />
                  ) : (
                    <EmptyTripCanvas
                      availability={availability}
                      onLaunched={() => setChatStyle("drawer")}
                    />
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
                  availability={availability}
                  focusedTrip={focusedTrip}
                  onOpenTrip={() => setChatExpanded(false)}
                  onClearFocus={clearFocus}
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
                availability={availability}
                focusedTrip={focusedTrip}
                onOpenTrip={() => setChatExpanded(false)}
                onClearFocus={clearFocus}
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
  theme, userProfile, sendMessage, availability,
  getFocusedTripId, applyFocus, clearFocus,
}: ShellViewProps) {
  const [pane, setPane] = useState(1); // 0=library, 1=trip, 2=map
  const [chatOpen, setChatOpen] = useState(false);
  const [activeDayN, setActiveDayN] = useState(todayN);

  const { registerOpenChatPanel, registerFocusBridge } = useChat();
  useEffect(() => {
    registerOpenChatPanel("mobile", () => setChatOpen(true));
  }, [registerOpenChatPanel]);
  useEffect(() => {
    registerFocusBridge(getFocusedTripId, applyFocus);
  }, [registerFocusBridge, getFocusedTripId, applyFocus]);

  const focusedTrip = activeTripId
    ? { id: activeTripId, destination: summaries.find((s) => s.id === activeTripId)?.destination ?? "Trip" }
    : null;
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
                onClose={() => { setActiveTripId(null); clearFocus(); }}
              />
            ) : (
              <EmptyTripCanvas
                availability={availability}
                onLaunched={() => setChatOpen(true)}
              />
            )}
          </div>

          <div className="h-full p-3" style={{ width: "33.3333%" }}>
            <div className="aletheia-card h-full overflow-hidden relative">
              <TripMap trip={trip} days={days} activeDayN={activeDayN} theme={theme} userProfile={userProfile} />
              <div className="absolute top-3 left-3 pointer-events-none">
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
          <ChatPanel
            onCollapse={() => setChatOpen(false)}
            availability={availability}
            focusedTrip={focusedTrip}
            onOpenTrip={() => { setPane(1); setChatOpen(false); }}
            onClearFocus={clearFocus}
          />
        </div>
      )}
    </div>
  );
}

/* ── Root shell ── */
export function DashboardShell() {
  const { summaries, defaultActiveId } = useTripList();
  const [activeTripId, setActiveTripId] = useState<string | null>(null);

  // Adopt the resolved default trip ONCE on first load, without clobbering a
  // later user choice — including an explicit "clear focus" to null (Task 52
  // AC-12). The ref makes the adoption fire exactly once, so closing the panel
  // (setActiveTripId(null)) no longer bounces straight back to the default.
  const [adoptedDefault, setAdoptedDefault] = useState(false);
  if (!adoptedDefault && activeTripId === null && defaultActiveId !== null) {
    setAdoptedDefault(true);
    setActiveTripId(defaultActiveId);
  }

  // Trip-focus bridge plumbing (Task 52). A ref tracks the latest focus so the
  // getter the chat layer rides on every message is never stale; applyFocus is
  // diff-guarded (same id → no state change → no panel remount, AC-10).
  const activeTripIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeTripIdRef.current = activeTripId;
  }, [activeTripId]);
  const getFocusedTripId = useCallback(() => activeTripIdRef.current, []);
  const applyFocus = useCallback((newId: string | null) => {
    setActiveTripId((cur) => (newId && newId !== cur ? newId : cur));
  }, []);
  const clearFocus = useCallback(() => setActiveTripId(null), []);

  const { trip, days, todayN, loading } = useTrip(activeTripId);
  // Capability availability (Task 50): read from already-loaded client state —
  // no extra fetch (spec §5). telegram_linked isn't exposed by the profile yet,
  // so link_telegram stays visible (E6).
  const availability: AvailabilityState = {
    hasTrip: !!trip,
    tripPhase: trip?.phase,
    // Shown in the sheet group labels: "For your trip · Kyoto" (Task 50).
    tripName: trip?.title ?? undefined,
  };

  // Send a message into the chat thread (idea chips, mood, journal prompts,
  // "plan a trip" CTAs). Fire-and-forget: the persisted turn + reply surface
  // in the chat panel via its realtime subscription (task 37).
  const sendMessage = useCallback((text: string) => {
    void fetch("/api/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: text, focused_trip_id: activeTripIdRef.current }),
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
    theme, userProfile, sendMessage, availability,
    getFocusedTripId, applyFocus, clearFocus,
  };

  return (
    <ChatProvider>
      {/* One-shot consumer for /guide → /dashboard?launch=<id> handoff (Task 53). */}
      <LaunchFromParam />

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
    </ChatProvider>
  );
}

// triggered hot reload
