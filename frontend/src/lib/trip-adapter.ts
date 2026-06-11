// trip-adapter — maps the raw assembled trip from `useTripRealtime`
// (parent JSONB columns + child collections, snake_case DB shape) into the
// view model the dashboard components consume (`Trip` + `TripDay[]`).
//
// Keeping this translation in one place means the existing itinerary layouts
// (accordion / timeline / kanban) keep their well-tested view model untouched
// while the data underneath becomes live. Everything here is defensive: JSONB
// columns can hold anything, so we read with optional chaining and sane
// fallbacks rather than trusting shape.

import type { Trip as RawTrip } from "@/hooks/useTripRealtime";
import type {
  Trip,
  TripDay,
  TripPhase,
  TripStatus,
  TripBooking,
  TripBudget,
  TripLiveState,
  TripScratchpad,
  TripJournal,
  CountryIntelData,
  DayBlock,
  BlockType,
  DayStatus,
  TripCover,
  TripSummary,
} from "@/lib/dashboard-data";

type Json = Record<string, unknown>;

function asObj(v: unknown): Json {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Json) : {};
}
function asArr(v: unknown): Json[] {
  return Array.isArray(v) ? (v as Json[]) : [];
}
function str(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() ? v : undefined;
}
function num(v: unknown): number | undefined {
  return typeof v === "number" && !Number.isNaN(v) ? v : undefined;
}

// ── status / phase ─────────────────────────────────────────────────────────

const KNOWN_PHASES: TripPhase[] = [
  "DREAMING", "SHAPING", "ANCHORING", "PLANNING",
  "READY", "LIVING", "REMEMBERING", "ARCHIVED",
];

/** Canonical UI phase from trips.status (+ saga_state when more specific). */
export function deriveUiPhase(status?: string, sagaState?: string): TripPhase {
  const ss = (sagaState || "").toUpperCase();
  if (ss === "DETAILING") return "PLANNING";
  if (ss === "READY_TO_GO") return "READY";
  if ((KNOWN_PHASES as string[]).includes(ss)) return ss as TripPhase;

  switch ((status || "").toLowerCase()) {
    case "active":   return "LIVING";
    case "ready":    return "READY";
    case "planning": return "PLANNING";
    case "past":     return "REMEMBERING";
    case "archived": return "ARCHIVED";
    case "dreaming":
    default:         return "DREAMING";
  }
}

/** The 4-value chip status the existing StatusChip/STATUS_META understands. */
function toChipStatus(status?: string): TripStatus {
  switch ((status || "").toLowerCase()) {
    case "active":   return "active";
    case "planning":
    case "ready":    return "planning";
    case "past":
    case "archived": return "complete";
    default:         return "exploring";
  }
}

// ── small formatters ─────────────────────────────────────────────────────────

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtShort(iso?: string): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  return `${MONTHS[d.getMonth()]} ${String(d.getDate()).padStart(2, "0")}`;
}

function deriveDateRange(discovery: Json, referenceDate?: string): string {
  const tf = asObj(discovery.timeframe);
  const start = fmtShort(str(tf.start_date) ?? referenceDate);
  const end = fmtShort(str(tf.end_date));
  if (start && end) return `${start} – ${end}`;
  if (start) return start;
  const text = str(tf.text);
  if (text) return text;
  return "Dates TBD";
}

/** "City, Country" → { city, country }. */
function splitPlace(name?: string): { city: string; country: string } {
  if (!name) return { city: "Untitled trip", country: "" };
  const parts = name.split(",").map((p) => p.trim()).filter(Boolean);
  if (parts.length >= 2) return { city: parts[0], country: parts[parts.length - 1] };
  return { city: parts[0] || name, country: "" };
}

function deriveCover(raw: Json, city: string): TripCover {
  const c = asObj(raw.cover);
  const hue = num(c.hue);
  if (hue !== undefined) {
    return {
      hue,
      label: str(c.label) ?? city,
      tone: c.tone === "cool" ? "cool" : "warm",
    };
  }
  // Deterministic hue from the city name so cards stay visually stable.
  let h = 0;
  for (let i = 0; i < city.length; i++) h = (h * 31 + city.charCodeAt(i)) % 360;
  return { hue: h, label: city, tone: h > 120 && h < 280 ? "cool" : "warm" };
}

// ── days + blocks ────────────────────────────────────────────────────────────

const BLOCK_TYPES: BlockType[] = ["culture", "wander", "food", "nature", "rest", "transit"];

function toBlockType(t?: string): BlockType {
  const v = (t || "").toLowerCase();
  return (BLOCK_TYPES as string[]).includes(v) ? (v as BlockType) : "wander";
}

function fmtDuration(min?: number): string {
  if (!min || min <= 0) return "—";
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function dayDate(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const wd = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][d.getDay()];
  return `${wd} · ${MONTHS[d.getMonth()]} ${String(d.getDate()).padStart(2, "0")}`;
}

function dayStatus(n: number, todayN: number): DayStatus {
  if (n < todayN) return "past";
  if (n === todayN) return "today";
  return "future";
}

function mapBlocks(blocks: Json[]): DayBlock[] {
  return blocks
    .slice()
    .sort((a, b) => (num(a.ord) ?? 0) - (num(b.ord) ?? 0))
    .map((b, i): DayBlock => ({
      id: str(b.id) ?? `block-${i}`,
      time: str(b.time_slot) ?? ["Morning", "Afternoon", "Evening"][i] ?? "—",
      title: str(b.title) ?? "Untitled",
      type: toBlockType(str(b.type)),
      duration: fmtDuration(num(b.duration_min)),
      energy: num(b.energy) ?? 2,
      walk: str(b.walk),
      why: str(b.why),
      // The mock map uses an abstract 0–1000 canvas that real lat/lng can't map
      // onto, and the map is replaced wholesale in task 49. Live itinerary
      // blocks carry a neutral pin; the map renders from its placeholder days.
      pin: { x: 0, y: 0 },
    }));
}

export interface AdaptedTrip {
  trip: Trip;
  days: TripDay[];
  todayN: number;
}

/**
 * Map the raw assembled trip into the dashboard view model. Returns null when
 * there is no trip (caller renders the empty-trip onboarding canvas).
 */
export function adaptTrip(raw: RawTrip | null): AdaptedTrip | null {
  if (!raw) return null;

  const discovery = asObj(raw.discovery);
  const live = asObj(raw.live_state) as Json;
  const status = str(raw.status);
  const sagaState = str(raw.saga_state);
  const phase = deriveUiPhase(status, sagaState);

  // Destination + country from child destination rows (fallback: discovery).
  const dests = asArr(raw.destinations);
  const primaryDest =
    dests.find((d) => str(d.status) === "confirmed") ?? dests[0] ?? {};
  const place = splitPlace(str(primaryDest.name));
  const isoCountries = dests
    .map((d) => str(d.iso_country))
    .filter(Boolean) as string[];
  const country =
    place.country ||
    (isoCountries.length ? isoCountries.join(" · ") : "");

  // todayN: explicit live cursor, else derived, else day 1.
  const totalDays = asArr(raw.days).length;
  const todayN = num(live.current_day_n) ?? 1;

  // Day label per phase.
  let dayLabel: string;
  if (phase === "LIVING") {
    dayLabel = totalDays ? `Day ${todayN} of ${totalDays}` : "On trip";
  } else if (phase === "REMEMBERING") {
    dayLabel = "Trip complete";
  } else if (totalDays) {
    dayLabel = `${totalDays}-day plan`;
  } else {
    dayLabel = { DREAMING: "Dreaming", SHAPING: "Taking shape", ANCHORING: "Anchoring", PLANNING: "Planning", READY: "Ready to go", ARCHIVED: "Archived" }[phase] ?? "Planning";
  }

  // Bookings map almost 1:1 (DB row → view model).
  const bookings: TripBooking[] = asArr(raw.bookings).map((b): TripBooking => ({
    id: str(b.id) ?? "",
    trip_id: str(b.trip_id) ?? raw.id,
    kind: (str(b.kind) as TripBooking["kind"]) ?? "other",
    datetime_local: str(b.datetime_local),
    confirmation_code: str(b.confirmation_code),
    payload: asObj(b.payload),
    created_at: str(b.created_at) ?? "",
    updated_at: str(b.updated_at) ?? "",
  }));

  // Days: join trip_days with their blocks (by day_id).
  const blocksByDay = new Map<string, Json[]>();
  for (const blk of asArr(raw.day_blocks)) {
    const dayId = str(blk.day_id);
    if (!dayId) continue;
    (blocksByDay.get(dayId) ?? blocksByDay.set(dayId, []).get(dayId)!).push(blk);
  }
  const days: TripDay[] = asArr(raw.days)
    .slice()
    .sort((a, b) => (num(a.n) ?? 0) - (num(b.n) ?? 0))
    .map((d): TripDay => {
      const n = num(d.n) ?? 0;
      return {
        n,
        date: dayDate(str(d.date)),
        isoDate: str(d.date),
        title: str(d.title) ?? `Day ${n}`,
        status: dayStatus(n, todayN),
        energy: num(d.energy_target) ?? 2,
        weather: str(d.weather_snapshot),
        note: str(d.ai_note),
        blocks: mapBlocks(blocksByDay.get(str(d.id) ?? "") ?? []),
      };
    });

  const lastMood = asObj(live.last_mood);

  const trip: Trip = {
    id: raw.id,
    destination: place.city,
    country,
    dateRange: deriveDateRange(discovery, str(raw.reference_date)),
    status: toChipStatus(status),
    phase,
    dayLabel,
    cover: deriveCover(raw as Json, place.city),
    title: str(raw.title),
    vision: str(raw.vision_summary) ?? str(discovery.vision_summary),
    bookings,
    countryIntel: asArr(raw.country_intel) as CountryIntelData[],
    budget: asObj(raw.budget) as TripBudget,
    liveState: asObj(raw.live_state) as TripLiveState,
    scratchpad: asObj(raw.scratchpad) as TripScratchpad,
    journal: asObj(raw.journal) as TripJournal,
    destinations: dests.map((d) => ({
      id: str(d.id) ?? "",
      name: str(d.name) ?? "",
      status: str(d.status) ?? "considering",
      coords: asObj(d.coords),
    })),
    mood: str(lastMood.label)
      ? { last: str(lastMood.label)!, suggested: "" }
      : undefined,
  };

  return { trip, days, todayN };
}

// ── trip library summaries ───────────────────────────────────────────────────

/** Map a raw `trips` row (with the `trip_destinations` relation embedded, or
 * `discovery.destinations` as fallback) to a library card summary. */
export function adaptSummary(row: Json): TripSummary {
  const discovery = asObj(row.discovery);
  const dests = asArr(row.trip_destinations).length
    ? asArr(row.trip_destinations)
    : asArr(discovery.destinations);
  const place = splitPlace(str((dests[0] ?? {}).name) ?? str(row.title));
  const status = str(row.status);
  const phase = deriveUiPhase(status, str(row.saga_state));
  return {
    id: str(row.id) ?? "",
    destination: place.city,
    country: place.country,
    dateRange: deriveDateRange(discovery, str(row.reference_date)),
    status: toChipStatus(status),
    dayLabel:
      phase === "LIVING" ? "On trip"
      : phase === "REMEMBERING" ? "Trip complete"
      : phase === "DREAMING" ? "Dreaming"
      : "Planning",
    cover: deriveCover(row, place.city),
    updatedAt: str(row.updated_at) ?? "",
  };
}
