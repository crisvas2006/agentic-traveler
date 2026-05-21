# Dashboard Design Spec — Aletheia Travel

> Reference document for designing and implementing the authenticated user dashboard.
> Feed this directly into Claude Design or any design tool alongside the existing auth page visual identity.

---

## 1. Product Context

Aletheia is an AI travel companion. Its core loop is: **Discover → Plan → Live**. The web dashboard is the *visual layer* on top of an AI agent that already runs conversationally via Telegram. The dashboard makes trips spatial and tangible — you can see, touch, and navigate your journey rather than just chat about it.

The AI chat is the engine. The dashboard is the cockpit.

---

## 2. User States & Default Views

The dashboard must be **phase-aware** — the default view adapts to where the user is in the travel lifecycle:

| User state | Default view |
|---|---|
| **New user, no trips** | Onboarding canvas — visual capability showcase with a strong "Plan your first trip" CTA. Disappears once first trip is created. |
| **Has trip(s), none active today** | Most recently updated trip in focus, in planning/refining mode. |
| **Active trip (today's date falls within trip dates)** | Live companion view — today's itinerary block highlighted, mood check-in prompt from AI, map centered on current location. |
| **All trips complete** | Trip library with a "Start a new journey" nudge. |

The user can always navigate away from the default view.

---

## 3. Core Panels & Information Architecture

### 3.1 The Five Layers

The dashboard is built on **five overlapping layers** rather than flat pages. On desktop, multiple layers are visible simultaneously. On mobile, one layer occupies the full screen at a time.

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5 (top)    Chat overlay / full-screen on mobile      │
│  Layer 4          Trip detail panel (itinerary, budget...)   │
│  Layer 3          Trip library sidebar                       │
│  Layer 2          Map canvas (always present)                │
│  Layer 1 (base)   App shell (nav bar, theme, ambient bg)     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Trip Library (left sidebar / swipe-right pane on mobile)

- Compact trip cards, sorted by: active first → upcoming → most recently updated
- Each card shows: destination name, date range, status chip (Exploring / Planning / Active / Complete), cover image or map thumbnail
- "New trip" button always pinned at top
- At the very bottom: **Traveler DNA** compact card — a teaser of the user's profile (2–3 personality tags) with a link to the full profile page
- On mobile: this is the **right swipe** pane (swiping right from center brings the library into view)

### 3.3 Map Canvas (center-background / swipe-left pane on mobile)

The map is the **always-present backdrop** of the dashboard on desktop — dimmed when a trip panel overlays it, brought to focus when the user explicitly enters map mode or clicks on a day's activities.

Map behavior adapts to trip phase:
- **Discovery phase**: World/regional map with candidate destination pins. Clicking a pin shows a destination card overlay.
- **Planning phase**: Zoomed-in map of the chosen destination. POIs from the itinerary as numbered pins. Day route shown as a connected path.
- **Active trip (live)**: Same as planning but with a live location dot for the user. Today's route highlighted. Past days dimmed.

On mobile: the map is the **left swipe** pane (swiping left from center brings the map into view).

### 3.4 Trip Detail Panel (center / default pane on mobile)

The primary workspace. Adapts content to phase:

**Discovery sub-view:**
- AI-generated destination shortlist (3–5 cards)
- Each card: destination name, why-it-fits blurb (tied to Traveler DNA), budget band, best travel window, effort level
- "Choose this destination" CTA on each card

**Planning sub-view (after destination chosen):**
- Day-by-day itinerary accordion
  - Each day: morning / afternoon / evening blocks
  - Selecting a day highlights its POIs on the map and draws the route
  - Each block: activity name, type chip, energy level indicator, duration estimate
- Budget overview (collapsible): categories with rough cost ranges
- Key bookings checklist (collapsible): flights, accommodation, activities to book

**Live trip sub-view (active trip):**
- Today's block is expanded and highlighted by default
- Mood check-in widget at the top (quick emoji or slider) — feeds the AI for real-time suggestions
- AI suggestion cards below today's plan ("Based on your energy today…")
- Tomorrow's plan collapsed below

### 3.5 AI Chat (floating bubble → overlay)

**Mobile:**
- Persistent floating bubble (bottom-right corner)
- Tapping expands to a full-screen overlay that slides up from the bottom
- Chat history + input field; close button collapses it back to bubble

**Desktop:**
- Default: right sidebar panel, ~360px wide, always open
- Collapsible to an icon strip on the right edge (like a drawer)
- Shows conversation history and an input field
- When the user asks about a destination → the map responds (pan, pin drop); when they ask for an itinerary change → the trip panel updates in real time

The chat is the primary way to trigger changes. The panels reflect the results.

---

## 4. Layout Schematics

### 4.1 Desktop (≥1024px)

```
┌────────────────────────────────────────────────────────────────────────┐
│ NAV BAR                                                                │
│ [Logo]         [Trip selector ▼ "Kyoto · Day 3 of 7"]    [DNA] [👤]   │
├──────────┬─────────────────────────────────────┬───────────────────────┤
│  TRIP    │                                     │   CHAT SIDEBAR        │
│  LIBRARY │       MAP CANVAS                    │                       │
│          │  (always visible, dims when         │  [conversation]       │
│  [card]  │   trip panel overlaps)              │                       │
│  [card]  │                                     │  [message]            │
│  [card]  │  ┌─────────────────────────────┐   │  [message]            │
│  + New   │  │  TRIP DETAIL PANEL          │   │                       │
│  ──────  │  │  (floats over map)          │   │  ──────────────────   │
│  [DNA ↗] │  │  Day 3 · Kyoto              │   │  [input field]        │
│          │  │  ▶ Morning …                │   │                       │
│          │  │    Afternoon …              │   │  [Collapse →]         │
│          │  │    Evening …                │   │                       │
│          │  └─────────────────────────────┘   │                       │
└──────────┴─────────────────────────────────────┴───────────────────────┘
```

- Left sidebar: ~260px, collapsible
- Map canvas: flex-grows to fill center
- Trip detail panel: floats over the map, ~480px wide, scrollable, can be expanded to ~680px (focus mode covers most of the map)
- Chat sidebar: ~360px, collapsible to ~48px icon strip

### 4.2 Mobile (< 768px) — Three-pane Horizontal Swipe

```
◀ swipe right          DEFAULT              swipe left ▶
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│              │   │              │   │              │
│  TRIP        │   │  TRIP        │   │  MAP         │
│  LIBRARY     │   │  DETAIL      │   │  CANVAS      │
│              │   │  (or         │   │              │
│  [card]      │   │  onboarding) │   │  [pins]      │
│  [card]      │   │              │   │  [route]     │
│  [card]      │   │              │   │              │
│  + New       │   │              │   │              │
│              │   │              │   │              │
└──────────────┘   └──────────────┘   └──────────────┘
                       ● ○ ○              (dot nav)

                   [💬 Chat bubble] ← always visible on all panes
```

- Pane indicator: 3 dots at bottom, current pane filled
- Swipe gesture handles navigation; tab bar hidden (swipe is the nav)
- Bottom of screen (safe area): floating chat bubble, bottom-right
- Chat expands as a full-screen sheet sliding up (dismissible with swipe down)

---

## 5. Navigation & Global Chrome

### Top Navigation Bar
| Element | Notes |
|---|---|
| Logo / wordmark (left) | Taps to home / default state |
| Trip context chip (center) | Shows active or most recent trip name + status. Dropdown to switch trips. |
| Traveler DNA icon | Opens DNA profile page/sheet |
| Notifications bell | AI-triggered nudges (weather alert, booking reminder) |
| Profile / avatar | Settings, logout |

### No bottom tab bar on mobile
Navigation is gesture-driven (swipe). This gives maximum vertical screen real estate for content and keeps the UI feeling like a spatial environment rather than a traditional app.

---

## 6. Trip Lifecycle UI States

```
[Exploring]  →  [Destination chosen]  →  [Itinerary built]  →  [Active]  →  [Complete]
   World map        Destination map         Day route map       Live map      Memory view
   Candidate        Blank itinerary         Full itinerary      Today HL'd    Read-only
   cards            scaffolding             + budget            + mood CTA    + journal
```

Status chips use color:
- Exploring → muted blue
- Planning → primary blue/purple (brand gradient)
- Active → emerald green (live indicator dot)
- Complete → warm amber / sepia

---

## 7. Onboarding Canvas (new users)

Shown before the first trip is created. Disappears permanently once the user creates their first trip.

Layout: full-width centered content (no sidebars)
- Headline: "Your journey starts here."
- 3 capability cards in a horizontal row (or vertical on mobile):
  1. **Discover** — "Tell me where you want to go. I'll find destinations that fit who you are."
  2. **Plan** — "Choose a destination. I'll build a day-by-day itinerary around your energy and style."
  3. **Live** — "On the ground? Tell me your mood. I'll adapt the plan to right now."
- Primary CTA: "Plan your first trip →" (opens chat or a trip creation wizard)
- Secondary: "See how it works" (short inline demo / animation)

---

## 8. Visual Identity Extension

Extend the existing auth page identity (blue→purple gradient, glassmorphic cards, Geist font, dark/light theming) in a bolder, more spatial direction:

| Element | Auth pages | Dashboard |
|---|---|---|
| Background | BeamsBackground (dark) / gradient (light) | Map canvas replaces static background |
| Cards | `bg-background/70 backdrop-blur-xl border border-border` | Same, but with a subtle parallax depth for panels floating over the map |
| Primary CTA | Blue→purple gradient pill button | Same |
| Typography | Geist, extrabold headlines | Same, but larger display type for trip names |
| Status indicators | N/A | Colored chips + animated live dot (emerald, pulsing) for active trips |
| Imagery | None (pure UI) | Destination photography as card backgrounds (low-opacity or as map context) |
| Motion | `animate-fade-up`, gradient-x | Map pan/zoom transitions, panel slide-in, day expand/collapse accordion |

The map tile style should match the theme: dark mode → dark map tiles (Mapbox Dark); light mode → muted/desaturated map tiles.

---

## 9. Key Interactions to Design

1. **Selecting a day in the itinerary** → map pans and zooms to show that day's POIs + route
2. **Clicking a candidate destination pin on world map** → destination detail card slides in over the map
3. **Mood check-in** (active trip) → AI responds in chat with adapted suggestion, trip panel updates
4. **Chat triggers itinerary change** → trip detail panel animates the updated block
5. **Collapsing chat sidebar** (desktop) → map and trip panel expand to fill the space
6. **New trip flow** → full-screen wizard or chat-first (AI asks questions, dashboard populates)
7. **Trip card expand** → panel expands from compact card to full detail (accordion animation)

---

## 10. Out of Scope for This Design Phase

- Social / sharing features (future)
- Group trip negotiation
- In-app booking / payments
- Notification settings page
- Real-time flight/hotel pricing widgets

---

## 11. Questions for Next Design Session

- New trip creation: wizard (guided form) vs chat-first (AI asks questions)? Or a hybrid where chat IS the wizard?
- Traveler DNA full profile page: what does it look like? Dimension scores, tags, radar chart?
- Trip "memory" view (completed trips): photo journal? summary card? or just read-only itinerary?
- Map provider: Mapbox (most flexible) vs Google Maps (familiar) vs Leaflet + OSM (free)?

---

## Change Log
- 2026-05-21 — Initial spec from brainstorming session
