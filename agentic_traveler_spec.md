This section is a spec for an agentic coder. It should be enough to implement and deploy the system as stateless Cloud Run functions using ADK and Python.

### 3.1 Agent system overview

Agents and their roles:

1.  Conversation Orchestrator Agent
    
2.  Profile and Memory Agent
    
3.  Discovery Agent
    
4.  Planner and Companion Agent
    
5.  Safety Filter (as a tool or post processing layer)
    

All agents run inside one Cloud Run service, within an ADK agent graph. Cloud Run remains stateless between requests. All long term and trip state lives in Firestore and, optionally, in a vector store.

### 3.2 Data and tools available to agents

Core tools to define and expose to agents:

1.  **FirestoreUserTool**
    
    *   get\_user\_by\_telegram\_id(telegramUserId)
        
        *   Returns: user document including user\_profile, preferenceSignals, tripRefs.
            
    *   update\_user\_preferences(userId, preferenceDelta)
        
        *   Applies counts to preferenceSignals (for example increment likes.hikes).
            
2.  **FirestoreTripTool**
    
    *   get\_active\_trip(userId)
        
        *   Returns the current trip document or null.
            
    *   create\_trip(userId, tripInput)
        
        *   Creates a new trip with status planned, stores trip constraints.
            
    *   update\_trip(tripId, updateFields)
        
        *   Updates current phase, candidate destinations, chosen destination, itinerary summary, current day, etc.
            
3.  **FirestoreEventTool**
    
    *   log\_event(userId, tripId, eventType, payload)
        
        *   Stores events: suggestion shown, accepted, rejected, feedback text.
            
4.  **WebSearchTool**
    
    *   Generic web search used for:
        
        *   Destination characteristics.
            
        *   Travel patterns.
            
        *   Activity ideas.
            
5.  **WeatherTool**
    
    *   Simple weather forecast query based on location and date range.
        
    *   Used by Discovery Agent (for seasonality) and Planner and Companion Agent (for in trip decisions).
        
6.  **MapsAndPoiTool** (optional for MVP, can be approximated with web search)
    
    *   Search for points of interest by category, location, and radius.
        
7.  **SafetyCheckTool**
    
    *   Given a proposed suggestion (text), returns flags:
        
        *   isIllegal, isObviouslyUnsafe, isUncertain.
            
    *   Implementation can be rule based plus a small LLM safety classifier.
        
8.  **LoggingTool**
    
    *   For internal logging and tracing.
        

All tools are implemented as Python functions or classes and exposed to ADK via its tool interface.

### 3.3 Conversation Orchestrator Agent

Purpose:

*   Entry point for all Telegram messages.
    
*   Understand user intent.
    
*   Route the request to the correct agent or combination of agents.
    
*   Ensure context continuity by loading user and trip state from Firestore.
    

Inputs:

*   telegramUserId, chatId, messageText, timestamp.
    
*   Derived internal userId if mapping exists.
    

Steps on each request:

1.  Use FirestoreUserTool to fetch or create user record based on telegramUserId.
    
2.  If no user\_profile is present:
    
    *   Prompt user to fill the Tally form, and stop.
        
3.  Classify messageText into one of:
    
    *   New trip or trip idea.
        
    *   Refinement or question about current planning.
        
    *   In trip adjustment request.
        
    *   General chat or help.
        
4.  Based on classification:
    
    *   For new trip: call Profile and Memory Agent to extract trip level constraints from the message, then call Discovery Agent.
        
    *   For refinement during planning: call Discovery Agent or Planner as needed.
        
    *   For in trip: call Planner and Companion Agent.
        
5.  Collect response from called agents, run through Safety Filter, return replyText and optional markup.
    

Outputs:

*   A response object with text and optional structured actions, sent back to Make.
    

### 3.4 Profile and Memory Agent

Purpose:

*   Translate user\_profile and free text into a structured internal representation that other agents can use.
    
*   Maintain and update simple learned preferences over time.
    

Inputs:

*   user\_profile from Firestore, which has these main sections reflecting the Tally questionnaire:
    
    *   quickContext
        
    *   lifestyleEnergy
        
    *   travelStyle
        
    *   personalityValues
        
    *   pastTravel
        
    *   practicalConstraints
        
    *   goals
        

Responsibilities:

1.  { "budgetBand": "...", "preferredTripVibes": \["nature", "culture"\], "structurePreference": "loose\_skeleton", "soloComfort": "high", "riskTolerance": 4, "socialPreference": "mixed", "spiritualInterest": "sometimes", "maxTypicalTripLength": "1-2 weeks", "hardAvoidances": \["very\_cold", "heavy\_partying", "long\_flights"\], "motivationsNextTrip": \["rest", "self\_discovery"\]}
    
2.  Maintain preferenceSignals:
    
    *   { "likes": { "hikes": 3, "cafes": 5, "museums": 2 }, "dislikes": { "nightclubs": 4, "long\_guided\_tours": 2 }}
        
    *   Update this whenever the Planner and Companion Agent reports accepted or rejected suggestions by category.
        
3.  Expose a function to other agents:
    
    *   get\_enriched\_profile(userId) → returns merged view of static profile and learned preferences.
        

### 3.5 Discovery Agent

Purpose:

*   Given a user’s enriched profile and a trip request, propose concrete destination candidates.
    

Inputs:

*   Enriched profile from Profile and Memory Agent.
    
*   Trip request:
    
    *   Desired period or month range.
        
    *   Duration band (from Tally or from chat).
        
    *   Vibe words for this specific trip.
        
    *   Budget emphasis and flexibility.
        
    *   Tolerance for discomfort and uncertainty.
        
    *   Hard avoidances and constraints.
        

Behavior:

1.  Use WebSearchTool and general knowledge to identify a pool of destination candidates that:
    
    *   Align with the desired vibe and energy.
        
    *   Fit the budget band and typical spend pattern.
        
    *   Respect hard avoidances (for example avoid very cold locations if user checked that).
        
2.  Use WeatherTool for seasonality checks in the requested period.
    
3.  Use simple heuristic cost bands (for example cheap, medium, expensive relative to budgetBand) from web search or static data.
    
4.  Rank candidates and select three to five.
    
5.  For each candidate produce an explanation that explicitly references:
    
    *   Questionnaire answers, for traceability and user trust.
        
    *   Learned preferences when relevant.
        

Outputs:

*   { "destinations": \[ { "name": "Destination A", "fitReasons": \["matches your nature and culture vibe", "good for moderate risk tolerance"\], "estimatedBudgetBand": "medium", "recommendedWindows": \["2026-05-10 to 2026-05-17"\], "travelEffort": "direct flights from Bucharest in 2-3 hours", "notes": \["verify safety info and visa rules before booking"\] }, ... \]}
    

The Conversation Orchestrator converts this into user facing language and sends it back via Telegram.

### 3.6 Planner and Companion Agent

Purpose:

*   Before the trip: create a flexible, aligned itinerary for a chosen destination.
    
*   During the trip: adapt suggestions to mood, energy, weather, and time.
    

Inputs:

*   Enriched profile.
    
*   Trip document: chosen destination, dates, duration, and constraints.
    
*   In trip context from chat:
    
    *   Current location or assumed destination.
        
    *   Time of day.
        
    *   Weather from WeatherTool.
        
    *   User mood and energy descriptions.
        
    *   Budget for the day if provided.
        

Behavior when planning:

1.  Decide level of structure based on profile:
    
    *   If structurePreference is “plan it all” then produce more detailed day plans.
        
    *   If “loose skeleton”, propose key anchors and suggested free time.
        
    *   If “zero plan”, provide high level suggestions and optional ideas, not a rigid schedule.
        
2.  Use WebSearchTool and MapsAndPoiTool to collect candidate activities:
    
    *   Culture and history, nature and outdoor, spiritual, party, food, etc.
        
    *   Filter out categories that strongly contradict hard avoidances and preferenceSignals.
        
3.  Build a per day plan with alternatives labelled by energy:
    
    *   Example:
        
        *   Day 2 morning:
            
            *   Option A: high energy hike.
                
            *   Option B: easy walking tour with cafes.
                
4.  Store the itinerary summary and key anchor activities in Firestore trips document.
    

Behavior during the trip:

1.  Interpret incoming messages:
    
    *   For example: “I am tired, it is raining, but I want something meaningful to do this afternoon.”
        
2.  Retrieve current day and location from the trip record or from user clarifications.
    
3.  Use WeatherTool to confirm weather.
    
4.  Use WebSearchTool and MapsAndPoiTool to identify two to three options that match:
    
    *   Indoor vs outdoor.
        
    *   Energy level.
        
    *   Social vs introspective mood.
        
    *   Budget emphasis.
        
5.  Call SafetyCheckTool on each suggestion.
    
6.  Log events via FirestoreEventTool:
    
    *   suggestion\_shown.
        
    *   Later, when the user confirms, suggestion\_accepted or suggestion\_rejected.
        
7.  Pass feedback to Profile and Memory Agent to update preferenceSignals.
    

Outputs:

*   User ready suggestions in natural language, and structured event logs for learning.
    

### 3.7 Safety Filter

Purpose:

*   Apply safety and uncertainty policies across all responses before sending to the user.
    

Implementation:

*   Can be a separate tool called at the end of each orchestration, or a small wrapper function.
    

Behavior:

1.  Receive the draft answer text and structured suggestions.
    
2.  For each suggestion:
    
    *   Use SafetyCheckTool to evaluate.
        
    *   Remove or rewrite suggestions that are clearly illegal or obviously unsafe.
        
    *   If isUncertain is true or the domain is safety sensitive, attach a sentence:“Please verify details and safety before booking or acting on this suggestion.”
        
3.  Ensure no authoritative claims about visas, medical or legal issues are made. Replace with “check with official sources” language.
    
4.  Return the cleaned and annotated answer to the Conversation Orchestrator.
    

### 3.8 Deployment plan

Cloud Run:

*   Service name: agentic-traveler-orchestrator.
    
*   Runtime: Python.
    
*   Entrypoint: HTTP handler that:
    
    *   Receives POST at /telegram-webhook.
        
    *   Normalizes payload, initializes ADK agent graph, calls Conversation Orchestrator agent, processes response and safety filter, returns JSON.
        

Environment variables:

*   GCP\_PROJECT\_ID = agentic-traveler-db.
    
*   FIRESTORE\_USERS\_COLLECTION = users.
    
*   FIRESTORE\_TRIPS\_COLLECTION = trips.
    
*   FIRESTORE\_EVENTS\_COLLECTION = events.
    
*   Keys or references for web search, weather, and maps tools.
    
*   Any ADK configuration variables.
    

State:

*   No in memory state is relied upon across requests.
    
*   All persistent data is in Firestore, plus optional vector store for advanced personalization later.
    
*   This ensures horizontal scaling and simple stateless deployment.
    

Testing approach:

*   Unit tests for tools: Firestore read and write, web search wrapper, weather lookup.
    
*   Offline tests for agents with mocked tools, using sample user\_profile and trip inputs consistent with the Tally form.
    
*   Manual tests of Telegram conversation flow using Make and Cloud Run in a staging environment.