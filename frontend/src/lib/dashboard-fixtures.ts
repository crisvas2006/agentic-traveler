// Demo / test fixtures — NOT runtime data.
//
// Task 40 moved the hand-coded Kyoto trip out of the runtime path
// (`dashboard-data.ts`) into here. Two consumers remain:
//   1. component/unit tests that need a fully-populated trip + days, and
//   2. the dashboard map placeholder (KyotoMap) until task 49 replaces it
//      with a real MapLibre map fed by geocoded trip coordinates.
// Nothing in the live data flow imports this file.

import type { Trip, TripDay } from "./dashboard-data";

export const TRIPS: Trip[] = [
  {
    id: "kyoto",
    destination: "Kyoto",
    country: "Japan",
    dateRange: "Apr 14 – Apr 21",
    status: "active",
    phase: "LIVING",
    dayLabel: "Day 3 of 7",
    cover: { hue: 348, label: "京都", tone: "warm" },
    weather: { code: "rain", temp: "15°", note: "light drizzle until noon" },
    mood: { last: "tired", suggested: "low-energy morning, indoor afternoon" },
    vision: "A slow spring escape — temples in the rain, quiet meals, walks by the river.",
    budget: {
      target_eur: 5000,
      by_category: {
        flights: { target: 2000, actual: 1960 },
        lodging: { target: 1500, actual: 1540 },
        food: { target: 600, actual: 220 },
        activities: { target: 400, actual: 80 },
      },
    },
    liveState: {
      current_day_n: 3,
      current_location: "Higashiyama",
      last_mood: { label: "tired", energy: 2 },
    },
    scratchpad: {
      saved_ideas: [{ text: "Day trip to Nara?" }],
      packing_list: [
        { label: "Travel adapter", done: true },
        { label: "Light rain jacket", done: false },
      ],
      custom_notes: "Try to bike along the Kamogawa one morning.",
    },
    countryIntel: [
      {
        iso_country: "JP",
        fetched_at: new Date().toISOString(),
        entry: { visa_rule: "Visa-free up to 90 days for US/EU citizens.", validity: "90 days" },
        safety: { summary: "Very low crime. Earthquakes can occur.", score_10: 9.5 },
        health: { vaccines: ["Routine"], water_safe: true },
        money: { currency: "Japanese Yen (JPY)", card_acceptance: "Widely accepted, but carry some cash for small shops.", tipping: "No tipping." },
        connectivity: { esim_support: true, wifi_availability: "Common in hotels and cafes." },
        climate_by_month: { summary: "April is mild with cherry blossoms. Light rain is possible." },
      },
    ],
  },
  {
    id: "patagonia",
    destination: "Patagonia",
    country: "Chile · Argentina",
    dateRange: "Sep 02 – Sep 14",
    status: "planning",
    phase: "PLANNING",
    dayLabel: "Trip in 14 weeks",
    cover: { hue: 200, label: "Patagonia", tone: "cool" },
  },
  {
    id: "lisbon",
    destination: "Lisbon",
    country: "Portugal",
    dateRange: "Jun 06 – Jun 09",
    status: "exploring",
    phase: "DREAMING",
    dayLabel: "3-day weekend",
    cover: { hue: 38, label: "Lisboa", tone: "warm" },
    vision: "A sun-warmed long weekend — miradouros, pastéis, and no fixed plan.",
  },
];

export const KYOTO_DAYS: TripDay[] = [
  {
    n: 1, date: "Mon · Apr 14", isoDate: "2026-04-14", title: "Arrival & easing in",
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
    n: 2, date: "Tue · Apr 15", isoDate: "2026-04-15", title: "Higashiyama hills",
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
    n: 3, date: "Wed · Apr 16", isoDate: "2026-04-16", title: "Slow temples, rivers, alleys",
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
    n: 4, date: "Thu · Apr 17", isoDate: "2026-04-17", title: "Arashiyama bamboo grove",
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
    n: 5, date: "Fri · Apr 18", isoDate: "2026-04-18", title: "Fushimi Inari at dawn",
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

export const TODAY_N = 3;
