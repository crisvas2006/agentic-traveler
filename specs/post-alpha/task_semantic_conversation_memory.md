# Task Spec: Semantic Conversation Memory & Group Chat Readiness

> **Status:** POST-ALPHA. Re-baselined 2026-06-04 to align with the saga
> architecture from `specs/proposal_trip_model_and_planning_saga.md`
> (see §10.7 of that proposal). This task ships **after** the alpha launch
> (tasks 44–53) — it is NOT a prerequisite for the alpha.

## Goal
Evolve the ephemeral conversation history into a persistent, group-chat-ready semantic memory system. This allows the AI agent to accurately recall specific historical details using vector search, while maintaining a high-level summary for general context.

**Key Decisions Made:**
1. **Model:** Google `gemini-embedding-001` (Matryoshka supported, 768d target).
2. **Strategy:** Hybrid memory (Keep existing summary + add `search_conversation` capability exposed as a **side-effect listener saga** — `MemorySearchSaga` — NOT as a tool dangling off every agent).
3. **Database:** Supabase with `pgvector` (Option B).
4. **Schema Prep:** Design for multi-user group chats (`conversations`, `conversation_members`, `messages`).
5. **Trip-scope tagging:** `messages.trip_id` (nullable FK to `trips.id`) is captured at write time so vector search can scope to a single trip — the dominant retrieval pattern at usage time. Already required by `task_45_trips_data_model.md`-shipped trips; this task formalizes the column and backfills.

---

## Database Architecture (Supabase extensions)

To support this task, the database schema (from Task 17) must be extended to support group chats and vector embeddings.

### 1. Enable Extensions
```sql
-- Required for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Table Definitions

```sql
-- ============================================================
-- CONVERSATIONS (Channels)
-- ============================================================
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT DEFAULT 'direct' CHECK (type IN ('direct', 'group')),
    name            TEXT,                                 -- For group chats e.g., "Bali Trip 2027"
    summary         TEXT DEFAULT '',                      -- High-level context (compaction)
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- CONVERSATION MEMBERS (Join Table for access control)
-- ============================================================
CREATE TABLE conversation_members (
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    role            TEXT DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    joined_at       TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (conversation_id, user_id)
);

-- ============================================================
-- MESSAGES (The core semantic memory log)
-- ============================================================
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id       TEXT NOT NULL,                        -- Could be a user UUID or 'agent'
    sender_type     TEXT NOT NULL CHECK (sender_type IN ('user', 'agent')),
    content         TEXT NOT NULL,
    embedding       VECTOR(768),                          -- Truncated gemini-embedding-001
    is_compacted    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Index for fast semantic search (HNSW using inner product for normalized vectors)
CREATE INDEX ON messages USING hnsw (embedding vector_ip_ops) WITH (m = 16, ef_construction = 64);
-- Index for fetching chronological history
CREATE INDEX idx_messages_conv_created ON messages(conversation_id, created_at ASC);
```

---

## Core Approach & Implementation Steps

### 1. The Embedding Pipeline
When a user sends a message, or the agent replies:
1. The message is immediately saved to the `messages` table (to not block the reply).
2. An asynchronous background task fetches the embedding using `gemini-embedding-001` (truncated to 768 dimensions for cost/speed efficiency).
3. The background task updates the `messages` row with the generated vector.

### 2. Conversation Manager Updates
The `ConversationManager` needs a rewrite to adapt to the new `conversations` and `messages` tables:
- **Load (Working Memory):** Fetch all messages where `is_compacted = FALSE` chronologically from the `messages` table, plus the `summary` from the `conversations` table. This keeps the active prompt very small.
- **Append:** Insert new rows into `messages`. Fire the async embedding task.
- **Compact (The Trigger):** When the count of `is_compacted = FALSE` messages exceeds a small threshold (e.g., 6 messages / 3 exchanges):
  1. Fire an async background task to compact the oldest 4 uncompacted messages.
  2. Send them to the LLM (along with the existing `conversations.summary`) to generate a new combined summary.
  3. Update `conversations.summary` with the new value.
  4. Run `UPDATE messages SET is_compacted = TRUE WHERE id IN (...)` for those 4 messages.

### 3. The `MemorySearchSaga` (replaces the per-agent tool from the original spec)

Per `proposal_trip_model_and_planning_saga.md` §10.7, expose semantic
recall as a **side-effect listener saga** rather than as a tool dangling
off every agent. This keeps the saga model coherent (every cross-cutting
capability is a saga) and gives us one place to add reranking, freshness
boosts, or trip-scope hints later.

```python
# backend/src/agentic_traveler/orchestrator/sagas/memory_search.py
class MemorySearchSaga(BaseSaga):
    name = "MemorySearchSaga"

    def should_activate(self, intent, entities, trip, state):
        # Activate when the user asks "what did we say about X" / "what hotel
        # did I book" / any recall-shaped phrasing OR when the owner saga
        # signals it needs context. Side-effect listener only — never owner.
        if entities.get("recall_question"):
            return True, False
        return False, False

    def run(self, message, user_doc, trip, state, conv, events):
        events.emit("metric", {"name": "memory_search_started"})
        query_vec = embed(message)
        hits = pgvector_search(
            query=query_vec,
            conversation_id=state.get("conversation_id"),
            trip_id=trip and trip["id"],   # trip-scoped retrieval (preferred)
            k=5,
        )
        # Hits go back via state_delta as injected context for the owner.
        return SagaResult(state_delta={"recall_hits": _format_hits(hits)})
```

The orchestrator picks up `recall_hits` from `state_delta` and folds it
into the owner saga's prompt under `<recalled_context>...</recalled_context>`.
**No agent ever holds a `search_conversation` tool.** The saga model owns
retrieval the same way `CountryIntelSaga` owns intel and `BookingInputSaga`
owns booking parsing.

**Trip-scope first.** When the resolved trip is non-null, the retrieval
filters on `messages.trip_id = trip.id` to dramatically improve relevance
(most user recall is *about this trip*, not the user's lifetime history).
A null `trip_id` filter falls back to whole-conversation search.

**Mechanism details:**
1. Embed the `query` using `gemini-embedding-001` (768d truncated).
2. Execute a vector similarity search against the `messages` table,
   filtered by `conversation_id` and optionally `trip_id`.
3. Return the top K (e.g., K=5) matching messages, formatted with
   speaker and date, so the LLM can answer accurately.

### 3a. Schema delta — add `trip_id` to messages

```sql
ALTER TABLE public.messages
  ADD COLUMN IF NOT EXISTS trip_id uuid REFERENCES public.trips(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS messages_trip_id_idx ON public.messages (trip_id) WHERE trip_id IS NOT NULL;
```

The orchestrator (task 36) writes `trip_id` at message-save time using the
resolved trip. Backfill: leave existing rows NULL — `trip_id`-scoped
retrieval simply degrades to whole-conversation retrieval for messages
that pre-date the saga work.

### 4. Group Chat Context Handling
To prepare for group chats, the context block injected into the LLM prompt must carefully attribute messages to specific users:
- Instead of just `User: Hello`, format as `User (John): Hello`.
- The agent must be instructed in its system prompt to respect differing user profiles within a shared conversation.

---

## Migration Strategy (Context Handling)

Since the current setup saves conversation history as a JSON blob inside the user document (Firestore `conversation_history`), a migration step will be required:
1. Create a 1:1 `direct` conversation in the new `conversations` table for each existing user.
2. Link the user to the conversation via `conversation_members`.
3. Migrate the JSON `recent_messages` into the `messages` table.
4. Move the `summary` to `conversations.summary`.
5. Run a backfill job to generate embeddings for all historic messages migrated.

*(Note: This migration logic should be part of the larger Task 29 script).*

---

## Out of Scope
- Building the actual multi-user UI or routing logic for handling simultaneous incoming messages from different users in the exact same millisecond.
- Implementing `@mention` routing in the Orchestrator for group settings (this will be handled when the Group Chat feature is fully activated).
