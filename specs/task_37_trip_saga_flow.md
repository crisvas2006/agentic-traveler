# Task Spec: Trip Saga Flow & Builder UI

## Goal
Transform the trip planning experience from an ephemeral conversation into a structured, personalizable **Trip Builder**. 
The goal is to enable an AI agent to act as the core engine that extracts decisions from a natural language chat and populates a heavily structured data model.
Simultaneously, a companion web application will be developed using this spec as a blueprint to render the trip data visually. We will rely on progressive disclosure: only populated fields are rendered in the UI.

## Database Architecture
Trips will **not** be stored inside the user document. Instead, they will be stored in a top-level **`trips` Firestore collection**. 
Each trip document will contain a `user_id` field linking it to the owner, allowing for independent queries, indexing, and sorting (especially using the `timeframe.reference_date`).

## Core Approach & Trip Data Schema
The trip structure operates as a maximal JSON document. The AI (using tools) and the user (via the web UI) write to this shared state.

### 1. Trip Document Schema
```json
{
  "id": "trip_abc123",
  "user_id": "telegram_user_id",
  "metadata": {
    "status": "ideation" 
    // Enum: ["ideation", "planning", "booked", "active", "past"]
  },
  "state": {
    "current_location": "string | null",
    "active_activity": "string | null",
    "last_updated": "2026-04-16T15:00:00Z" // ISO format
    // Purpose: Keeps the Companion agent grounded with the active trip state
  },
  "discovery": {
    "vision_summary": "A relaxing winter escape to the mountains.",
    "destinations": [
       {"name": "Aspen, USA", "status": "confirmed"} 
       // Status Enum: ["considering", "confirmed"]
    ],
    "timeframe": {
       "type": "flexible", 
       // Enum: ["exact", "flexible"]
       "start_date": null, // ISO formatting like "2026-12-15"
       "end_date": null, 
       "text": "Beginning of 2027",
       "reference_date": "2027-01-01T00:00:00Z" 
       // Used EXCLUSIVELY for ordering/indexing trips in the database. 
       // E.g., "beginning of 2027" -> 2027-01-01. "Before I turn 30" -> defaults to the current day.
    },
    "travelers": {
       "count": 2, 
       "composition": "Couple" 
       // Enum: ["Solo", "Couple", "Family", "Friends", "Group"]
    },
    "preferences": {
       "budget_tier": "$$$", 
       // Enum: ["$", "$$", "$$$", "$$$$"]
       "pace": "slow", 
       // Enum: ["slow", "medium", "fast"]
       "themes": ["nature", "culinary", "relaxation"] 
       // String array
    }
  },
  "logistics": {
     // Expected to hold arrays of transport, accommodations, and entry requirements
  },
  "itinerary": {
     // Expected to hold day-by-day blocks with explicit date indices
  },
  "scratchpad": {
     "saved_ideas": [],
     "packing_list": [],
     "custom_notes": ""
  }
}
```

### 2. AI as the Engine
Agents will use function-calling tools (`update_trip_discovery`, `add_itinerary_item`) to map vague user statements ("I want to go somewhere slow-paced with my wife") into precise enum updates in the structure (`pace: "slow", composition: "Couple"`).
When updates occur, the AI will proactively summarize the action in the chat (*"Got it, I've locked in a slow pace for your couple's trip"*).

### 3. Context Management & Trip Retrieval
To prevent token exhaustion and high unneeded costs, the full JSON structures of all a user's trips will **not** be passed into every LLM request. Instead, we use a summary-to-fetch pattern:
1. **Trip Summaries:** The Orchestrator's system prompt is injected with a lightweight summary of the user's trips (containing only `id`, `vision_summary`, `metadata.status`, and `timeframe.reference_date`).
2. **Dynamic Querying Tools:** The AI is equipped with tools like `get_trip_details(trip_id)` or `query_trips(filter)`. If the user asks for specific details ("What hotel did I stay at in Aspen?"), the AI looks at the summary list, uses the tool to query the database, and loads only that specific trip's full JSON structure into context.
3. **Active Trip Hydration:** As an exception, if a trip is marked `metadata.status == "active"` (the user is currently traveling), the Companion Agent will automatically have the full trip JSON hydrated directly into its context so it can provide immediate live assistance without needing a tool call.

---

## Web Frontend: UI Handling Suggestions
This specification serves as the development blueprint for the web-based Trip Builder UI.

### Component Mapping
- **The Header Banner:** Use `discovery.vision_summary` as a beautifully styled, italicized quote at the top of the interface representing the trip "Vibe."
- **The Timeframe Card:** 
  - If `timeframe.type == "exact"`: Render a clean calendar widget displaying `start_date` and `end_date`.
  - If `timeframe.type == "flexible"`: Render an abstract calendar icon displaying the fuzzy `timeframe.text` string. (Hide the `reference_date` entirely from the UI, as it is only for backend sorting).
- **Destinations Component:** Loop over `discovery.destinations`. 
  - Render `status == "confirmed"` items as solid, highly visible location pins. 
  - Render `status == "considering"` items as outlined or dashed pills (indicating they are pending decisions).
- **Tags & Badges:** Map `budget_tier`, `pace`, and `themes` to a row of colorful UI badges. 

### Progressive Disclosure Rules
- Avoid rendering empty states with massive "N/A" text. If a property is empty/null, suppress the block.
- **Example:** If `discovery.themes` is an empty array `[]`, do not render the Themes badge container. If `logistics.flights` is empty, render a tiny "+ Add Flights" ghost button rather than a giant empty table.
- Since the AI handles data entry via chat, the UI must gracefully accept real-time inbound updates when the Firestore listener detects document changes. Ensure frontend state reacts to backend database mutations without overwriting user manual forms.

## Out of Scope
- Actually building the frontend Web Application logic is outside the scope of the AI's backend tasks.
- Execution of real-world bookings.
