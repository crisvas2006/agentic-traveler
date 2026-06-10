// Mock dashboard data — will be replaced by live Supabase queries in a later step.

export type TripStatus = "exploring" | "planning" | "active" | "complete";
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

export interface TripWeather {
  code: string;
  temp: string;
  note: string;
}

export interface Trip {
  id: string;
  destination: string;
  country: string;
  dateRange: string;
  status: TripStatus;
  dayLabel: string;
  cover: TripCover;
  weather?: TripWeather;
  mood?: { last: string; suggested: string };
  countryIntel?: any[];
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

export const TRIPS: Trip[] = [
  {
    id: "kyoto",
    destination: "Kyoto",
    country: "Japan",
    dateRange: "Apr 14 – Apr 21",
    status: "active",
    dayLabel: "Day 3 of 7",
    cover: { hue: 348, label: "京都", tone: "warm" },
    weather: { code: "rain", temp: "15°", note: "light drizzle until noon" },
    mood: { last: "tired", suggested: "low-energy morning, indoor afternoon" },
    countryIntel: [
      {
        iso_country: "JP",
        fetched_at: new Date().toISOString(),
        entry: { visa_rule: "Visa-free up to 90 days for US/EU citizens.", validity: "90 days" },
        safety: { summary: "Very low crime. Earthquakes can occur.", score_10: 9.5 },
        health: { vaccines: ["Routine"], water_safe: true },
        money: { currency: "Japanese Yen (JPY)", card_acceptance: "Widely accepted, but carry some cash for small shops.", tipping: "No tipping." },
        connectivity: { esim_support: true, wifi_availability: "Common in hotels and cafes." },
        climate_by_month: { summary: "April is mild with cherry blossoms. Light rain is possible." }
      }
    ],
  },
  {
    id: "patagonia",
    destination: "Patagonia",
    country: "Chile · Argentina",
    dateRange: "Sep 02 – Sep 14",
    status: "planning",
    dayLabel: "Trip in 14 weeks",
    cover: { hue: 200, label: "Patagonia", tone: "cool" },
  },
  {
    id: "lisbon",
    destination: "Lisbon",
    country: "Portugal",
    dateRange: "Jun 06 – Jun 09",
    status: "exploring",
    dayLabel: "3-day weekend",
    cover: { hue: 38, label: "Lisboa", tone: "warm" },
  },
];

export const KYOTO_DAYS: TripDay[] = [
  {
    n: 1, date: "Mon · Apr 14", title: "Arrival & easing in",
    status: "past", energy: 2,
    blocks: [
      {
        id: "d1-m", time: "Morning", title: "Land at KIX", type: "transit",
        duration: "—", energy: 1, walk: "75 min to Kyoto Station",
        why: "Kansai Airport to Kyoto via Haruka express — no changes needed.",
        pin: { x: 920, y: 760 },
      },
      {
        id: "d1-a", time: "Afternoon", title: "Settle in Higashiyama ryokan", type: "rest",
        duration: "2h", energy: 1,
        why: "Check in early, drop bags, orient yourself before the trip begins.",
        pin: { x: 670, y: 470 },
      },
      {
        id: "d1-e", time: "Evening", title: "Quiet kaiseki at the inn", type: "food",
        duration: "2h", energy: 2,
        why: "In-house dining means no navigating an unfamiliar city while jet-lagged.",
        pin: { x: 670, y: 470 },
      },
    ],
  },
  {
    n: 2, date: "Tue · Apr 15", title: "Higashiyama hills",
    status: "past", energy: 4,
    blocks: [
      {
        id: "d2-m", time: "Morning", title: "Kiyomizu-dera early", type: "culture",
        duration: "2h", energy: 3, walk: "10 min uphill from bus stop",
        why: "Arriving before 9am beats the tour groups by an hour — you get the terrace almost to yourself.",
        pin: { x: 730, y: 480 },
      },
      {
        id: "d2-a", time: "Afternoon", title: "Sannenzaka & Ninenzaka walk", type: "wander",
        duration: "3h", energy: 3, walk: "Gentle hills, mix of paved and stone",
        why: "Stone-paved lanes lined with ceramics, matcha cafés, and craft shops — easy to linger.",
        pin: { x: 700, y: 470 },
      },
      {
        id: "d2-e", time: "Evening", title: "Gion lantern hour", type: "wander",
        duration: "2h", energy: 2, walk: "5 min from Sannenzaka",
        why: "The preserved geisha district feels entirely different after dark — quieter, more atmospheric.",
        pin: { x: 640, y: 430 },
      },
    ],
  },
  {
    n: 3, date: "Wed · Apr 16", title: "Slow temples, rivers, alleys",
    status: "today", energy: 2, weather: "light rain",
    note: "You said you felt tired. Plan is dialled down — indoor temples, no long walks.",
    blocks: [
      {
        id: "d3-m", time: "Morning", title: "Tofuku-ji moss garden", type: "culture",
        duration: "1.5h", energy: 2, walk: "2 min from station",
        why: "Covered approach, indoor garden. Stays calm on a rainy day.",
        pin: { x: 690, y: 670 }, current: true,
      },
      {
        id: "d3-a", time: "Afternoon", title: "Pottery district & tea house", type: "wander",
        duration: "3h", energy: 2, walk: "Café-hop, no hills",
        why: "Low-effort browsing under awnings. Tea breaks built in.",
        pin: { x: 660, y: 510 },
      },
      {
        id: "d3-e", time: "Evening", title: "Pontocho riverside izakaya", type: "food",
        duration: "2h", energy: 2, walk: "12 min stroll",
        why: "Covered alley, short walk from the hotel.",
        pin: { x: 540, y: 460 },
      },
    ],
    suggestions: [
      {
        kind: "swap", title: "Skip the pottery district?",
        body: "Rain is forecast to stay until 3pm. The covered Nishiki Market is 8 min by metro and matches your energy. Want to swap?",
      },
      {
        kind: "weather", title: "Bring an umbrella to dinner",
        body: "Pontocho alley is covered but the river-side approach isn't. Drizzle expected at 18:30.",
      },
    ],
  },
  {
    n: 4, date: "Thu · Apr 17", title: "Arashiyama bamboo grove",
    status: "future", energy: 3,
    blocks: [
      {
        id: "d4-m", time: "Morning", title: "Bamboo grove at sunrise", type: "nature",
        duration: "2h", energy: 3, walk: "8 min walk from Arashiyama Station",
        why: "The grove gets crowded by 9am — arriving at first light is transformative and quiet.",
        pin: { x: 180, y: 380 },
      },
      {
        id: "d4-a", time: "Afternoon", title: "Tenryu-ji & boat ride", type: "culture",
        duration: "3h", energy: 3, walk: "3 min from bamboo grove",
        why: "UNESCO garden backed by forested hills; the boat adds a completely different perspective.",
        pin: { x: 200, y: 420 },
      },
      {
        id: "d4-e", time: "Evening", title: "Return train, light dinner", type: "food",
        duration: "1.5h", energy: 2, walk: "5 min to Saga-Arashiyama Station",
        why: "Arashiyama to central Kyoto is 25 min on the Sagano Line — easy end to a full day.",
        pin: { x: 540, y: 460 },
      },
    ],
  },
  {
    n: 5, date: "Fri · Apr 18", title: "Fushimi Inari at dawn",
    status: "future", energy: 4,
    blocks: [
      {
        id: "d5-m", time: "Morning", title: "Fushimi Inari torii hike", type: "nature",
        duration: "3h", energy: 4, walk: "2 min from Inari Station",
        why: "Thousands of vermilion gates stretch up the mountain — most visitors only reach the first bend.",
        pin: { x: 760, y: 760 },
      },
      {
        id: "d5-a", time: "Afternoon", title: "Nap + onsen", type: "rest",
        duration: "3h", energy: 1,
        why: "Recovery window after an early-morning hike — saves energy for the evening.",
        pin: { x: 670, y: 470 },
      },
      {
        id: "d5-e", time: "Evening", title: "Yakitori in Gion", type: "food",
        duration: "2h", energy: 2, walk: "10 min from hotel",
        why: "Casual counter dining, smoke, skewers — a good contrast to the contemplative day.",
        pin: { x: 640, y: 430 },
      },
    ],
  },
  {
    n: 6, date: "Sat · Apr 19", title: "Nishiki & Nijo",
    status: "future", energy: 3,
    blocks: [
      {
        id: "d6-m", time: "Morning", title: "Nishiki Market crawl", type: "food",
        duration: "2h", energy: 2, walk: "5 min from hotel",
        why: "Kyoto's 'kitchen' — 100+ stalls of pickles, tofu, grilled mochi. Better before lunch crowds.",
        pin: { x: 470, y: 470 },
      },
      {
        id: "d6-a", time: "Afternoon", title: "Nijo Castle", type: "culture",
        duration: "2.5h", energy: 3, walk: "15 min bus from Nishiki",
        why: "The famous nightingale floors squeak underfoot to detect intruders — a remarkable bit of feudal design.",
        pin: { x: 410, y: 380 },
      },
      {
        id: "d6-e", time: "Evening", title: "Sake tasting near hotel", type: "food",
        duration: "2h", energy: 2,
        why: "Wind down the last full evening with local brews — a relaxed, low-effort end to the day.",
        pin: { x: 670, y: 470 },
      },
    ],
  },
  {
    n: 7, date: "Sun · Apr 20", title: "Slow morning, depart",
    status: "future", energy: 1,
    blocks: [
      {
        id: "d7-m", time: "Morning", title: "Kamogawa river walk", type: "wander",
        duration: "1.5h", energy: 2, walk: "2 min from hotel",
        why: "A slow, flat stroll along the river — pairs perfectly with a final coffee before the journey home.",
        pin: { x: 580, y: 470 },
      },
      {
        id: "d7-a", time: "Afternoon", title: "Pack + onward to KIX", type: "transit",
        duration: "3h", energy: 1, walk: "Haruka express from Kyoto Station",
        why: "Leave by 13:00 to catch an 18:00 flight comfortably — no rushing.",
        pin: { x: 920, y: 760 },
      },
      {
        id: "d7-e", time: "Evening", title: "Flight home", type: "transit",
        duration: "—", energy: 1,
        why: "End of trip.",
        pin: { x: 920, y: 760 },
      },
    ],
  },
];

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

export const TODAY_N = 3;
