# Agentic Traveler

An agentic travel planner and companion powered by Google Gen AI.

## High level description

### Problem Statement

When I want to travel, I usually have fuzzy desires and constraints but no clear destination. I bounce between flight sites, booking platforms, blogs, and maps, trying to answer three questions at once:

*   Where should I go that genuinely fits my budget, personality, energy, and constraints
    
*   What concrete itinerary and activities would make this trip feel meaningful, not generic
    
*   How do I adapt plans when reality changes, for example bad weather, low energy, or a different mood than expected
    

Even after hours of research, I can still end up with:

*   Destinations chosen for price or hype, not personal fit
    
*   Overcrowded or under planned itineraries
    
*   Frustration during the trip when plans do not match energy, weather, or local reality
    

Existing tools are either deal engines or rigid planners. They barely model who you are as a traveler: lifestyle, energy, risk tolerance, deeper motivations like self discovery or connection. They also do not behave like a companion that adapts day by day.

I focus the MVP on the solo traveler (who may sometimes bring a partner or friend) who wants trips that align with their personality and current life phase, not just “cheap and popular”.

### Why agents?

The problem is not a single query but an ongoing process:

*   Build a rich, structured profile of the traveler
    
*   Interpret vague requests like “5–7 days in late spring, I’m tired, want nature and some culture, from Bucharest”
    
*   Discover plausible destinations, filter by constraints, and justify why they fit
    
*   Turn a chosen destination into a flexible itinerary
    
*   During the trip, adapt suggestions to mood, weather, and what actually happened
    

This requires:

*   Long term memory (profile and learned preferences)
    
*   Session state per interaction
    
*   Tool use (datastore, search, weather, maps)
    
*   Safety and uncertainty handling
    

Agents fit well because they allow:

*   Small, specialized components (discovery, planning, memory, safety) instead of one giant prompt
    
*   Tight control over what context each agent sees, which improves cost and reduces hallucinations
    
*   A planning-before-acting pattern with explicit tool calls and checks
    
*   Clear separation between runtime (stateless Cloud Run) and state (Firestore + logs)
    

The user does not need “one big model answer” but a persistent, evolving travel companion. Agentic design matches that need.

### What I created

High level, the system has three layers.

#### 1\. Personalization intake

A Tally form, “Know Thy Damn Self (for Travel),” collects a deep but structured profile:

*   Context: age band, home base, budget style
    
*   Lifestyle & energy: daily rhythm, physical activity, typical tempo
    
*   Travel style: preferred trip vibes (nature, culture, spiritual, party, etc), structure preference, solo comfort
    
*   Personality & values: spontaneous vs reflective, social vs independent, motivations to travel, risk tolerance, spiritual interest
    
*   Past travel: what worked, what did not, solo challenges
    
*   Practical constraints: vacation days, diet/lifestyle, climate/logistics avoidances
    
*   Goals & dreams: what they want from their next trip, dream trip style, open notes
    

This form sends data to a GCP HTTP Cloud Function, which writes into Firestore:

*   Project: agentic-traveler-db
    
*   Collection: users
    
*   Each document includes:
    
    *   user\_profile with nested sections reflecting the questionnaire
        
    *   Identification fields: name, email, createdDate
        
    *   Later fields: telegramUserId, preferenceSignals, links to trips
        

The user\_profile field is the main personalization source for the agents.

#### 2\. Automation and messaging

*   Telegram is the main interface.
    
*   A Make scenario connects Telegram to the backend:
    
    *   Receives Telegram webhook updates
        
    *   Extracts telegramUserId, chatId, messageText, timestamp
        
    *   Sends this payload via HTTP POST to Cloud Run (/telegram-webhook)
        
    *   Receives replyText and sends it back to the user
        

This keeps the backend focused on agent logic and state, while Make handles channel plumbing and basic logging.

#### 3\. Agentic backend on Cloud Run

*   Service: agentic-traveler-orchestrator (Python + Google ADK)
    
*   Data: Firestore as source of truth
    
    *   users: long term profile and preferenceSignals
        
    *   trips: constraints, candidates, chosen destination, itinerary summary, status
        
    *   events: suggestion and feedback logs for lightweight learning
        

Core agents:

1.  **Conversation Orchestrator Agent**
    
    *   Entry point for every Telegram request
        
    *   Loads user from Firestore (by telegramUserId)
        
    *   If no user\_profile, asks user to complete the Tally form
        
    *   Classifies message: new trip, planning refinement, in-trip adjustment, or help
        
    *   Routes to Discovery or Planner/Companion as needed
        
    *   Assembles the final answer and calls the Safety Filter
        
2.  **Profile & Memory Agent**
    
    *   Translates user\_profile into an enriched profile object:
        
        *   Budget band, key vibes, structure preference, solo comfort, risk tolerance, hard avoidances, current trip goals
            
    *   Manages preferenceSignals:
        
        *   Simple counters of liked/disliked categories (for example hikes, nightlife, long tours, spiritual events)
            
    *   Exposes get\_enriched\_profile(userId) to other agents
        
3.  **Discovery Agent**
    
    *   Input: enriched profile + trip constraints from chat
        
    *   Uses web search and weather tools to:
        
        *   Identify candidate destinations that match vibes and constraints
            
        *   Check rough seasonality and cost bands in the requested period
            
    *   Produces 3–5 destinations with:
        
        *   Why they fit the person (explicitly tying to profile answers)
            
        *   Estimated budget band and travel effort
            
        *   Recommended windows within the chosen dates
            
4.  **Planner & Companion Agent**
    
    *   Before trip:
        
        *   Uses structure preference to decide how detailed the plan should be
            
        *   Uses search/maps to propose day level activity sets, with options for different energy levels
            
        *   Stores itinerary summary in trips
            
    *   During trip:
        
        *   Uses current mood, energy, time, weather, and destination to suggest 2–3 options
            
        *   Logs suggestion events and, when the user reacts, accepted/rejected categories
            
        *   Passes preference updates to Profile & Memory Agent
            
5.  **Safety Filter**
    
    *   Runs on all responses before sending to user
        
    *   Uses a safety tool / rules to:
        
        *   Remove or rewrite clearly illegal or obviously unsafe suggestions
            
        *   Add “Please verify details and safety before booking or acting on this suggestion” for safety sensitive or uncertain cases
            

The backend is stateless: each request reconstructs context from Firestore and tools, then responds via Make to Telegram.

### The Build

Tools and technologies:

*   **GCP**
    
    *   Firestore for long term state (users, trips, events)
        
    *   Cloud Functions for Tally profile ingestion
        
    *   Cloud Run for the stateless agent service
        
*   **Backend & agents**
    
    *   Python with Google ADK to define the agent graph
        
    *   Small, specialized agents:
        
        *   Orchestrator, Profile & Memory, Discovery, Planner/Companion, Safety Filter
            
    *   Planning before acting:
        
        *   For complex tasks (discovery, itinerary), agents first sketch a plan (steps + tools) then execute tool calls
            
    *   Lightweight learning:
        
        *   Events are aggregated into preferenceSignals instead of loading full histories into the LLM
            
*   **Automation and chat**
    
    *   Tally form for user personalization
        
    *   Cloud Function mapping Tally data into user\_profile in Firestore
        
    *   Telegram bot as interface
        
    *   Make as integration layer between Telegram and Cloud Run
        
*   **Safety and monitoring**
    
    *   Safety Filter for output sanitization and risk wording
        
    *   Logging of:
        
        *   Incoming message metadata
            
        *   Tool calls and outcomes
            
        *   Errors and basic latencies
            
    *   Versioned prompts and tools, so changes can be tracked and rolled back
        

The build emphasizes clear responsibilities per agent, stateless runtime with externalized state, and a realistic but contained scope that still demonstrates agentic behavior, memory, and robustness.

### If I had more time, this is what I’d do

If I had more time, I would extend in these directions:

1.  **Richer behavior modeling**
    
    *   Add a vector store for user embeddings and trip summaries
        
    *   Use similarity search to adapt plans based on past successful trips
        
    *   Move beyond simple counters toward richer “travel archetypes” for each user
        
2.  **Group and relationship aware travel**
    
    *   Support multiple traveler profiles and a group plan
        
    *   Add an agent that mediates between different budgets, vibes, and avoidances
        
    *   Support group chats where the agent helps converge on “good enough for everyone” plans
        
3.  **Deeper travel integrations**
    
    *   Integrate a real flight or accommodation API for realistic price ranges and routes
        
    *   Generate prefilled links or filters for popular booking sites
        
4.  **Proactive companion mode**
    
    *   Optional daily check ins during trips, based on weather and preferences
        
    *   Simple triggers to propose alternatives when key activities fall through
        
5.  **Evaluation and observability**
    
    *   Build a small eval set of scenarios and expected behaviors
        
    *   Use it to test changes in prompts, tools, and logic before deployment
        
    *   Improve tracing to quickly understand “bad” suggestions and fix root causes
        
6.  **User experience surfaces**
    
    *   Add a minimal web UI for visualizing trips and editing profiles
        
    *   Expose the system as an API that other products or agencies could integrate
        

These steps would deepen the technical sophistication and make the project an even stronger showcase of agentic AI, architecture, and product thinking.

## Technical Design Documentation

### 1.1 Problem and product description

Solo travelers with vague desires and constraints spend a lot of time jumping between sites to decide where to go, when to go, and what to do. The process of choosing a destination, creating an itinerary, and adapting on the fly is mentally heavy and fragmented across tools. Existing platforms are either generic deal aggregators or rigid planners, they do not understand the traveler as a person and do not adapt during the trip.

This project is an AI agentic travel companion that:

*   Builds a deep but structured profile of the traveler, including personality, energy, risk tolerance, travel style, and constraints.
    
*   Proposes destinations and itineraries that match this profile and the current life and emotional context.
    
*   Acts as a live companion during trips: answering questions, adapting plans to weather and energy, and learning from behavior over time.
    

The main interaction channel is Telegram chat. There is no custom web frontend in the MVP.

### 1.2 Personalization and data intake

User personalization is collected through a Tally form (https://tally.so/r/9qN6p4):

*   Form: “Know Thy Damn Self (for Travel)”
    
*   Fields cover:
    
    *   Quick context: age band, base city, budget style.
        
    *   Lifestyle and energy: daily rhythm, physical activity.
        
    *   Travel style: desired trip vibe, structure preference, solo comfort.
        
    *   Personality and values: spontaneity, social vs independent, motivation to travel, spiritual interest, risk tolerance.
        
    *   Past travel: best trip, bad trip patterns, solo travel experience and pain points.
        
    *   Practical constraints: vacation days, budget approach, dietary and lifestyle preferences, hard avoidances.
        
    *   Goals and dreams: what they want from next trip, dream trip style, extra notes.
        

Technical intake:

*   Tally form → HTTP triggered Cloud Function on GCP.
    
*   Function writes to Firestore in project agentic-traveler-db, collection users.
    
*   Each document in users has:
    
    *   user\_profile: all structured and free text answers from the questionnaire, organized in logical sections.
        
    *   Identification fields: name, email, createdDate.
        
    *   Later fields: telegramUserId, defaultHomeBase, etc.
        

This user\_profile is the main personalization source for the agents.

### 1.3 MVP capabilities

Must have features for the first version:

1.  **Destination discovery**
    
    *   Input: user profile from Firestore, trip constraints from Telegram chat (rough dates or time window, duration, budget band, desired vibe, energy, willingness for discomfort).
        
    *   Output:
        
        *   A short list of three to five destination candidates.
            
        *   For each destination:
            
            *   Why it matches the user\_profile (vibe words, personality, risk tolerance, energy, budget style, avoidances).
                
            *   Rough budget band.
                
            *   Best periods within the requested window, based on seasonality and cost.
                
            *   Short notes on travel effort (distance, estimated travel time, complexity).
                
2.  **Trip planning**
    
    *   Input: chosen destination, user\_profile, trip window and duration.
        
    *   Output:
        
        *   A rough day level itinerary:
            
            *   Day structure that reflects structure preference (highly planned, loose skeleton, or free form).
                
            *   Activity sets per day, with alternatives for different energy levels.
                
            *   Hints on what to book later: example neighborhoods to stay in, typical local transport patterns, key bookings to secure early.
                
        *   No direct bookings; suggestions are grounded in real world information and current knowledge but the user executes bookings on their usual platforms.
            
3.  **Live companion during the trip**
    
    *   Input: user messages from Telegram:
        
        *   Current mood and energy: tired, social, introspective, bored, restless.
            
        *   Constraints: weather, time of day, physical limitation, budget for the day.
            
    *   Output:
        
        *   Two to three actionable suggestions for what to do next, linked to:
            
            *   Current mood and energy.
                
            *   Current location and time.
                
            *   Known preferences and avoidances.
                
        *   The agent logs what types of suggestions were accepted or rejected and biases future suggestions.
            
4.  **Personalization and learning**
    
    *   The system uses:
        
        *   user\_profile from Firestore as long term personalization.
            
        *   An event log per user and trip (suggestion offered, accepted, rejected), which is used for lightweight preference learning.
            
    *   Behavioral learning is lightweight:
        
        *   Track counts of accepted or rejected categories (for example: hikes, nightlife, long structured tours, spiritual events).
            
        *   Adjust the probability of suggesting these categories in future trips.
            
5.  **Safety and uncertainty handling**
    
    *   The system avoids suggesting illegal or obviously unsafe activities.
        
    *   For any recommendation that touches safety, local laws, or where the system is not confident, it always adds a note such as:“Please verify details and safety before booking or acting on this suggestion.”
        

### 1.4 Not in scope for MVP

*   Automatic group negotiation and group chat.
    
*   Rich web or mobile frontend. Telegram is the primary interface.
    
*   Direct booking flows or payment handling.
    
*   Heavy behavior modeling or complex life phase models.
    
*   Direct integration with specific travel APIs such as Skyscanner or Amadeus in the first version. Use general web search and basic tools instead.
    

### 1.5 Key user stories

Profile and setup:

*   As a solo traveler, I want to fill a single, deep profile form once so that the system can understand my energy, style, constraints, and motivations without asking every time.
    

Destination discovery:

*   As a user, I want to say things like “five to seven days in May or June, I want nature and some culture, medium budget, leaving from Bucharest” and get a small set of destinations that clearly match my travel personality and constraints.
    

Trip planning:

*   As a user who picked a destination, I want a structured but flexible itinerary, with a few alternatives and clear explanations, so I feel guided but not constrained.
    

Live companion:

*   As a user during the trip, I want to tell the agent my mood, energy, and weather situation and get two or three adapted suggestions, so I can salvage bad days and improve good ones without replanning from scratch.
    

Learning:

*   As a repeat user, I want the system to quietly learn that I avoid certain activities and love others, so later trips feel more tailored with less configuration.
    

### 1.6 High level system architecture

Main components:

*   **Tally form**
    
    *   Collects user personalization data.
        
    *   Sends responses to a GCP HTTP Cloud Function.
        
*   **Profile ingestion function (Cloud Function)**
    
    *   Receives HTTP payload from Tally.
        
    *   Maps questionnaire fields into a structured user\_profile object with sections that reflect the form sections.
        
    *   Writes or updates document in Firestore:
        
        *   Project: agentic-traveler-db
            
        *   Collection: users
            
        *   Document id: derived from email or Tally id, plus later mapped to Telegram id.
            
        *   Fields: user\_profile, name, email, createdDate, other metadata.
            
*   **Firestore**
    
    *   users collection:
        
        *   user\_profile with nested sections: quickContext, lifestyleEnergy, travelStyle, personalityValues, pastTravel, practicalConstraints, goals.
            
        *   Identification and mapping fields.
            
        *   Optionally preferenceSignals for lightweight counts and learned preferences.
            
    *   trips collection:
        
        *   Trip constraints, candidate destinations, chosen destination, itinerary summary, current trip status.
            
    *   events collection:
        
        *   Per user and trip, logs of suggestions and user feedback.
            
*   **Telegram Bot**
    
    *   Used by the traveler as main interface.
        
    *   Forwards user messages to an HTTP endpoint in Cloud Run.
        
*   **Make scenario (automation layer)**
    
    *   Routes Telegram webhooks to the Cloud Run service and routes responses back.
        
    *   Handles simple retry and logging.
        
*   **Cloud Run service “agentic-traveler-orchestrator”**
    
    *   Stateless HTTP service in Python.
        
    *   Hosts an ADK based multi agent system.
        
    *   Entry point endpoint: /telegram-webhook receives normalized requests from Make.
        
    *   Uses Firestore as the source of truth for profiles, trips, and events.
        
    *   Uses external tools such as web search, weather, and maps as needed.
        
    *   Applies a safety filter before sending the response back.


##
### Common workflow to eliminate 80% of stylistic mistakes in python code:
black .
ruff check .
mypy .
pytest
isort .

## Features

- **AI Travel Agent**: Generates unique travel ideas based on your budget, climate, activity preferences, and duration.
- **Interactive CLI**: Chat with the agent locally, impersonating an existing Firestore user.

## Setup

### 1. Create and activate the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### 2. Install dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/application_default_credentials.json
```

- **`GOOGLE_API_KEY`** — required for all Gemini LLM calls (agents, classifier, safety filter).
- **`GOOGLE_PROJECT_ID`** — your GCP project ID (used by the Firestore client).
- **`GOOGLE_APPLICATION_CREDENTIALS`** — path to the Application Default Credentials JSON file.
  To generate it, run `gcloud auth application-default login` and copy the path it prints.

> **Note (Microsoft Store Python):** If you use the Microsoft Store version of Python,
> `gcloud` saves credentials under a sandboxed `AppData` path. You **must** set
> `GOOGLE_APPLICATION_CREDENTIALS` explicitly — see the path printed by the gcloud command.

## Usage

### Interactive CLI

Chat with the orchestrator locally by impersonating an existing Firestore user:

```powershell
.\.venv\Scripts\python -m agentic_traveler.cli
```

This lists all users in Firestore, lets you pick one, then opens an interactive chat loop. You can also pass a Telegram ID directly:

```powershell
.\.venv\Scripts\python -m agentic_traveler.cli --telegram-id 12345
```

## Testing

### Unit tests

Unit tests use mocked Firestore and LLM — no credentials needed:

```powershell
.\.venv\Scripts\python -m pytest tests/ --ignore=tests/integration -v
```

### Integration tests

Integration tests use the **real Gemini API** and **real Firestore** database. They require:
- `GOOGLE_API_KEY` set in `.env`
- `GOOGLE_APPLICATION_CREDENTIALS` set in `.env`
- A working GCP project with Firestore enabled

Test data is created with a `_test: True` marker and automatically cleaned up after each test.

```powershell
$env:_INTEGRATION_TESTS="1"; .\.venv\Scripts\python -m pytest -m integration -v
```

> The `_INTEGRATION_TESTS=1` env var tells the test framework to use the real
> Firestore library instead of the mock used by unit tests.

### Run all tests together

```powershell
$env:_INTEGRATION_TESTS="1"; .\.venv\Scripts\python -m pytest -v
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Google Cloud.

