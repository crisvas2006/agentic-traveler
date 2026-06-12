// capabilities.ts — the single capability registry (Task 50).
//
// One source of truth for everything the product can do, rendered by THREE
// surfaces: the ✨ launcher sheet (CapabilitySheet), the contextual chips
// (CapabilityChips), and the in-app manual page (Task 53, /guide). Capability
// copy, grouping, launch behavior and availability are authored here ONCE and
// never duplicated per surface.
//
// This module is pure data + types — no React, no lucide imports — so it can be
// consumed anywhere (client components today, a Telegram /help generator later).
// Icons are stored as lucide-react export names (PascalCase strings); each
// rendering surface maps the name to its component.

import type { TripPhase } from "@/lib/dashboard-data";

// ── launch kinds ─────────────────────────────────────────────────────────────
// Exhaustively typed (AC-1). A launch is one of:
//   message       — send `text` through the normal chat send path (persists).
//   draft         — pre-fill the composer with `text` without sending; the user
//                   completes and sends manually. Use when sending without
//                   context would be meaningless (e.g. "add a booking" needs
//                   the booking details).
//   intent        — POST /chat/send { body: label, capability: intent }; the
//                   backend maps `intent` directly to its saga (router skip).
//   link          — client-side navigation; no chat message.
//   ephemeral_mood — inject a local-only mood-picker card into the chat so the
//                   user taps a mood rather than typing it. Disappears on refresh.
export type CapabilityLaunch =
  | { kind: "message"; text: string }
  | { kind: "draft"; text: string }
  | { kind: "intent"; intent: string; label: string }
  | { kind: "link"; href: string }
  | { kind: "ephemeral_mood" };

// `plan`   — destination discovery and itinerary planning (no trip needed).
// `trip`   — intel and checks for the currently selected trip.
// `during` — actions taken while physically travelling (trip must be LIVING).
// `after`  — reflection and memory after the trip ends.
// `account`— preferences, channels, credits.
export type CapabilityGroup = "plan" | "trip" | "during" | "after" | "account";

export type CapabilityContext = "empty_chat" | "no_trip";

// State the availability/hide rules read. Everything is optional/loose: rules
// must be evaluable from state the dashboard already holds, and must never
// trigger a fetch (spec §5). Unknown state degrades to "shown" — the flow itself
// handles preconditions conversationally (E2/E6).
export type AvailabilityState = {
  hasTrip: boolean;
  tripPhase?: TripPhase;
  telegramLinked?: boolean;
  // Active trip name for group label display ("For your trip · Kyoto").
  tripName?: string;
};

export type Capability = {
  id: string; // stable, snake_case
  name: string; // "Plan a trip"
  icon: string; // lucide-react export name, e.g. "Compass"
  oneLiner: string; // ≤ 60 chars — launcher row + chip label
  howItWorks: string; // 2–3 sentences — launcher inline expand AND manual card body
  example?: string; // optional illustrative user phrasing — manual page only
  group: CapabilityGroup;
  launch: CapabilityLaunch;
  contexts?: CapabilityContext[]; // which contextual chip surfaces show this entry
  // Disabled-with-reason: return `true` to enable, or a reason string to render
  // the entry shown-but-disabled. Never fetches; reads AvailabilityState only.
  availability?: (s: AvailabilityState) => true | string;
  // Hard hide (rare): return true to remove the entry entirely (e.g. Telegram
  // already linked). Kept separate from `availability` so the disabled-reason
  // contract stays `true | string`.
  hideWhen?: (s: AvailabilityState) => boolean;
};

// ── shared group labels + blurbs ─────────────────────────────────────────────
// Launcher section headers and manual page group headers both read this, so the
// two never disagree. The `trip` and `during` group labels are dynamically
// suffixed with the trip name on each rendering surface.
export const GROUP_META: Record<CapabilityGroup, { label: string; blurb: string }> = {
  plan: { label: "Plan & discover", blurb: "Find a destination and shape the trip." },
  trip: { label: "For your trip", blurb: "Intel and checks for your selected trip." },
  during: { label: "During the trip", blurb: "Keep things moving while you travel." },
  after: { label: "After the trip", blurb: "Hold on to what mattered." },
  account: { label: "Account & setup", blurb: "Preferences, channels, and credits." },
};

// Whether a group label should show the active trip name as a badge.
export const GROUP_SHOWS_TRIP: Record<CapabilityGroup, boolean> = {
  plan: false,
  trip: true,
  during: true,
  after: false,
  account: false,
};

// Fixed render order for groups (both sheet and manual).
export const GROUP_ORDER: CapabilityGroup[] = ["plan", "trip", "during", "after", "account"];

// ── availability rules (shared, pure) ────────────────────────────────────────
const needsTrip = (s: AvailabilityState): true | string =>
  s.hasTrip ? true : "Needs an active trip";

const needsLivingTrip = (s: AvailabilityState): true | string =>
  s.hasTrip && s.tripPhase === "LIVING" ? true : "Available while you're travelling";

const needsPastTrip = (s: AvailabilityState): true | string =>
  s.hasTrip && (s.tripPhase === "REMEMBERING" || s.tripPhase === "ARCHIVED")
    ? true
    : "Available after a trip";

// ── the registry ─────────────────────────────────────────────────────────────
// Note: `what_can_you_do` is intentionally NOT a registry entry — it is a
// chip-only affordance that opens the sheet itself, handled in CapabilityChips
// (it has no message/intent/link launch, so it stays out of the typed union).
export const CAPABILITIES: Capability[] = [
  // ── Plan & discover ──
  {
    id: "find_where_to_go",
    name: "Find where to go",
    icon: "Compass",
    oneLiner: "Not sure of the destination yet",
    howItWorks:
      "Tell me the feeling you're after — a season, a budget, a mood — and I'll suggest places that fit how you travel, not just what's trending. We can compare a few before you commit.",
    example: "somewhere warm in February",
    group: "plan",
    launch: { kind: "message", text: "Help me figure out where to go" },
    contexts: ["empty_chat", "no_trip"],
  },
  {
    id: "plan_a_trip",
    name: "Plan a trip",
    icon: "Map",
    oneLiner: "Build an itinerary day by day",
    howItWorks:
      "I'll ask a few light questions — pace, who's coming, rough budget — then draft a day-by-day plan you can reshape any time. Nothing is locked; it's a starting point we refine together.",
    example: "8 slow days in Kyoto",
    group: "plan",
    launch: { kind: "message", text: "I want to plan a trip" },
    contexts: ["empty_chat", "no_trip"],
  },

  // ── For your trip (trip-specific intel) ──
  {
    id: "country_intel",
    name: "Country intel",
    icon: "ShieldCheck",
    oneLiner: "Visa, safety, money, health",
    howItWorks:
      "I pull together the practical brief for your destination — entry rules, safety, money, health and connectivity — with sources and a 'verify with official sources' note. It's a cached snapshot, never legal advice.",
    example: "is Mexico safe right now?",
    group: "trip",
    launch: { kind: "message", text: "Give me the country intel for my trip" },
    availability: needsTrip,
  },
  {
    id: "check_weather",
    name: "Check the weather",
    icon: "CloudSun",
    oneLiner: "How the forecast looks for your trip",
    howItWorks:
      "I'll check the forecast for your destination and dates and flag anything worth planning around — a rainy day to keep indoors, a cold snap to pack for.",
    example: "what's the weather in Kyoto this week?",
    group: "trip",
    launch: { kind: "message", text: "How's the weather looking for my trip?" },
    availability: needsTrip,
  },
  // ── During the trip ──
  {
    id: "add_booking",
    name: "Add a booking",
    icon: "Ticket",
    oneLiner: "Paste a flight or hotel, I'll file it",
    howItWorks:
      "Paste a confirmation — flight, hotel, train, restaurant — and I'll pull out the details and add it to your trip as a card. You confirm what I parsed before anything is saved.",
    example: "LH716, MUC→KIX, Dec 15, conf ABC123",
    group: "during",
    // draft: pre-fills the composer so the user adds their booking details before sending.
    launch: { kind: "draft", text: "I'd like to add a booking. Here are the details: " },
    availability: needsTrip,
  },
  {
    id: "mood_checkin",
    name: "Mood check-in",
    icon: "Smile",
    oneLiner: "Tell me how today feels",
    howItWorks:
      "While you're travelling, tell me how the day feels and I'll adapt what's ahead — dial the pace down when you're tired, lean in when you've got energy.",
    example: "feeling a bit worn out today",
    group: "during",
    // ephemeral_mood: opens an inline mood-picker card in the chat (local state,
    // gone on refresh) so the user taps a mood rather than typing one.
    launch: { kind: "ephemeral_mood" },
    availability: needsLivingTrip,
  },

  // ── After the trip ──
  {
    id: "journal_trip",
    name: "Journal the trip",
    icon: "BookOpen",
    oneLiner: "Capture what mattered",
    howItWorks:
      "After the trip, I'll offer gentle prompts to capture the highlights, the surprises, and the things you'd do differently — so the trip stays with you and shapes the next one.",
    example: "I want to write about the trip",
    group: "after",
    launch: { kind: "message", text: "I want to journal about my trip" },
    availability: needsPastTrip,
  },

  // ── Account & setup ──
  {
    id: "reply_length",
    name: "Reply length",
    icon: "SlidersHorizontal",
    oneLiner: "Make replies terser or richer",
    howItWorks:
      "Prefer short answers or more detail? Set your reply length in settings and every flow respects it from then on.",
    group: "account",
    launch: { kind: "link", href: "/settings" },
  },
  {
    id: "link_telegram",
    name: "Link Telegram",
    icon: "Send",
    oneLiner: "Chat with me on Telegram too",
    howItWorks:
      "Connect your Telegram account to chat with me there as well — same trip, same memory, on whichever app is closest to hand.",
    group: "account",
    launch: { kind: "link", href: "/settings#telegram" },
    hideWhen: (s) => s.telegramLinked === true,
  },
  {
    id: "redeem_promo",
    name: "Redeem a promo code",
    icon: "Gift",
    oneLiner: "Have a code? Add credits.",
    howItWorks:
      "Got a promo code? Share it with me and I'll apply the credits to your balance.",
    example: "I have a promo code",
    group: "account",
    launch: { kind: "message", text: "I have a promo code" },
  },
];

// ── shared helpers (used by sheet, chips, manual) ────────────────────────────

/** True when the entry should be removed entirely for this state. */
export function isHidden(c: Capability, s: AvailabilityState): boolean {
  return c.hideWhen ? c.hideWhen(s) : false;
}

/** `true` (enabled) or a reason string (shown but disabled). */
export function availabilityOf(c: Capability, s: AvailabilityState): true | string {
  return c.availability ? c.availability(s) : true;
}

/** Registry entries for a group, hidden ones removed, in registry order. */
export function capabilitiesForGroup(
  group: CapabilityGroup,
  s: AvailabilityState,
): Capability[] {
  return CAPABILITIES.filter((c) => c.group === group && !isHidden(c, s));
}

/**
 * Contextual chips for a surface: entries whose `contexts` include the surface,
 * not hidden, and currently available (enabled). Capped at `max` (default 3,
 * per AC-6). Returns [] when none apply so callers can render nothing (AC-10).
 */
export function contextualCapabilities(
  context: CapabilityContext,
  s: AvailabilityState,
  max = 3,
): Capability[] {
  return CAPABILITIES.filter(
    (c) =>
      c.contexts?.includes(context) &&
      !isHidden(c, s) &&
      availabilityOf(c, s) === true,
  ).slice(0, max);
}
