# Task Spec: Semantic Conversation Memory & Group Chat Readiness

## Goal
Evolve the ephemeral conversation history into a persistent, group-chat-ready semantic memory system. This allows the AI agent to accurately recall specific historical details using vector search, while maintaining a high-level summary for general context.

**Key Decisions Made:**
1. **Model:** Google `gemini-embedding-001` (Matryoshka supported, 768d target).
2. **Strategy:** Hybrid memory (Keep existing summary + add `search_conversation` sub-agent tool).
3. **Database:** Supabase with `pgvector` (Option B).
4. **Schema Prep:** Design for multi-user group chats (`conversations`, `conversation_members`, `messages`).

---

## Database Architecture (Supabase extensions)

To support this task, the database schema (from Task 29) must be extended to support group chats and vector embeddings.

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

### 3. The `search_conversation` Agent Tool
Equip the `CompanionAgent` (and potentially the `Orchestrator`) with a new function-calling tool:
```python
def search_conversation(self, query: str, conversation_id: str) -> str:
    """
    Search past conversation history for specific details.
    Call this when the user asks about something mentioned previously 
    that is not in the immediate context.
    """
```
**Mechanism:**
1. Embed the `query`.
2. Execute a vector similarity search against the `messages` table, filtered by `conversation_id`.
3. Return the top K (e.g., K=5) matching messages, formatted with speaker and date, so the LLM can answer the user's question accurately.

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
