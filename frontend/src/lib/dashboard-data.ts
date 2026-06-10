// Dashboard view-model types + presentation metadata.
//
// Task 40: runtime trip data now comes from live Supabase queries
// (`useTrip` → `adaptTrip`). The Kyoto mock that used to live here moved to
// `dashboard-fixtures.ts` (tests + the map placeholder pending task 49). This
// file keeps the shared TYPES and presentation maps only.

export type TripStatus = "exploring" | "planning" | "active" | "complete";

// Canonical lifecycle phase, derived from trips.status + trips.saga_state.
// Drives progressive disclosure of TripDetailPanel sections (proposal §6.2).
export type TripPhase =
  | "DREAMING"
  | "SHAPING"
  | "ANCHORING"
  | "PLANNING"
  | "READY"
  | "LIVING"
  | "REMEMBERING"
  | "ARCHIVED";
export type BlockType = "culture" | "wander" | "food" | "nature" | "rest" | "transit";
export type DayStatus = "past" | "today" | "future";
export type PanelLayout = "accordion" | "timeline" | "kanban";
export type ChatStyle = "strip" | "drawer" | "floating";
export type Density = "compact" | "comfortable" | "expanded";

export interface TripCover {
  hue: number;
  label: string;
  tone: "warm" | "cool";
}

export interface TripChecklistItem {
  id: string;
  text: string;
  status: "done" | "todo" | "idea";
}

export interface TripBookingPayload {
  kind?: "flight" | "accommodation" | "ground" | "restaurant" | "activity";
  airline?: string;
  number?: string;
  from_?: string;
  to?: string;
  depart_local?: string;
  arrive_local?: string;
  name?: string;
  address?: string;
  check_in?: string;
  check_out?: string;
  datetime_local?: string;
  reservation_status?: string;
  confirmation_code?: string;
  notes?: string;
  [key: string]: unknown;
}

export interface TripBooking {
  id: string;
  trip_id: string;
  kind: "flight" | "accommodation" | "ground" | "restaurant" | "activity" | "other";
  datetime_local?: string;
  confirmation_code?: string;
  payload: TripBookingPayload;
  created_at: string;
  updated_at: string;
}

export interface TripWeather {
  code: string;
  temp: string;
  note: string;
}

export interface CountryIntelData {
  safety?: { score_10?: number; summary?: string; [key: string]: unknown };
  iso_country?: string;
  sources?: string[];
  [key: string]: unknown;
}

// ── Budget (trips.budget JSONB) ──────────────────────────────────────────
export interface BudgetCategory {
  target?: number;
  actual?: number;
}
export interface TripBudget {
  target_eur?: number;
  by_category?: Record<string, BudgetCategory>;
}

// ── Live state (trips.live_state JSONB, meaningful only when active) ──────
export interface TripLiveState {
  current_day_n?: number;
  current_location?: string;
  last_mood?: { label?: string; energy?: number; logged_at?: string };
  live_alerts?: { text: string }[];
}

// ── Scratchpad (trips.scratchpad JSONB) ──────────────────────────────────
export interface SavedIdea {
  text: string;
  saved_at?: string;
}
export interface PackingItem {
  label: string;
  done?: boolean;
}
export interface TripScratchpad {
  saved_ideas?: SavedIdea[];
  packing_list?: PackingItem[];
  custom_notes?: string;
}

// ── Journal (trips.journal JSONB, post-trip) ─────────────────────────────
export interface JournalEntry {
  day_n?: number;
  text: string;
}
export interface TripJournal {
  entries?: JournalEntry[];
  highlights?: string[];
  regrets?: string[];
  tags_learned?: string[];
}

export interface Trip {
  id: string;
  destination: string;
  country: string;
  dateRange: string;
  status: TripStatus;
  phase: TripPhase;
  dayLabel: string;
  cover: TripCover;
  title?: string;
  vision?: string;
  weather?: TripWeather;
  bookings?: TripBooking[];
  mood?: { last: string; suggested: string };
  countryIntel?: CountryIntelData[];
  budget?: TripBudget;
  liveState?: TripLiveState;
  scratchpad?: TripScratchpad;
  journal?: TripJournal;
}

// Lightweight row for the trip library list (one card per trip).
export interface TripSummary {
  id: string;
  destination: string;
  country: string;
  dateRange: string;
  status: TripStatus;
  dayLabel: string;
  cover: TripCover;
  updatedAt: string;
}

export interface BlockPin {
  x: number;
  y: number;
}

export interface DayBlock {
  id: string;
  time: string;
  title: string;
  type: BlockType;
  duration: string;
  energy: number;
  pin: BlockPin;
  walk?: string;
  why?: string;
  current?: boolean;
}

export interface DaySuggestion {
  kind: "swap" | "weather";
  title: string;
  body: string;
}

export interface TripDay {
  n: number;
  date: string;
  isoDate?: string;
  title: string;
  status: DayStatus;
  energy: number;
  weather?: string;
  note?: string;
  blocks: DayBlock[];
  suggestions?: DaySuggestion[];
}

// ChatMessage was moved to `@/hooks/useChat` and is now sourced from the
// `messages` Supabase table. The old static `CHAT_HISTORY` constant has been
// removed — ChatPanel renders live data via the `useChat` hook.

export const DNA_TAGS = ["Slow traveler", "Culture-curious", "Energy-aware"];

export const TYPE_META: Record<string, { glyph: string; label: string }> = {
  culture: { glyph: "⛩", label: "Culture" },
  wander:  { glyph: "✦", label: "Wander"  },
  food:    { glyph: "◐", label: "Food"    },
  nature:  { glyph: "▲", label: "Nature"  },
  rest:    { glyph: "○", label: "Rest"    },
  transit: { glyph: "→", label: "Transit" },
};

export const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  exploring: { label: "Exploring", color: "#60a5fa", bg: "rgba(96,165,250,.12)"  },
  planning:  { label: "Planning",  color: "#a78bfa", bg: "rgba(167,139,250,.12)" },
  active:    { label: "Active",    color: "#34d399", bg: "rgba(52,211,153,.14)"  },
  complete:  { label: "Complete",  color: "#f59e0b", bg: "rgba(245,158,11,.12)"  },
};

