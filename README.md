# Agentic Traveler

An agentic travel planner powered by Google Gen AI.

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

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Setup**:
    - Create a `.env` file in the root directory.
    - Add your Google API key:
      ```
      GOOGLE_API_KEY=your_api_key_here
      ```

## Usage

Run the agent via the CLI:

```bash
python src/agentic_traveler/main.py --budget "Medium" --climate "Tropical" --activity "Relaxation" --duration "1 week"
```

Or simply run it interactively:

```bash
python src/agentic_traveler/main.py
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Google Cloud.
