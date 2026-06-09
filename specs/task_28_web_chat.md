# Task 28: Web Chat — Persistent Messaging on the Dashboard

**Status: ✅ COMPLETED**

> Bring the conversational experience from Telegram to the web dashboard.
> Persist every individual message (web + Telegram) in a new, append-only
> `messages` table. Render a chat surface inside the existing Dashboard
> shell that streams the latest messages, lazy-loads older history on
> scroll, and supports full-text search with jump-to-message.

---

## 1. Task Overview

- **Summary:** Today the user can only chat with the agent via Telegram. The Next.js dashboard has a static `ChatPanel.tsx` rendering mock messages from `CHAT_HISTORY`. This task adds an end-to-end web chat: a new Supabase table (`messages`) that stores every message regardless of channel, a FastAPI endpoint that the web client calls to send messages and receive replies, an updated `OrchestratorAgent` flow that records each message in both `messages` and `conversations`, and a live React chat surface with windowed history loading and message search.
- **Background:**
  - The Python backend already has a working orchestrator (`backend/src/agentic_traveler/orchestrator/agent.py`) that returns `{"text": str, "action": str}` for any user message. Today only `interfaces/routers/telegram.py` exercises it.
  - Conversation context for agents lives in `public.conversations` (one row per user, JSONB `recent_messages` + summary, compacted by `ConversationManager`). This is an internal context window — it intentionally throws away the bulk of history. **It stays as-is. It is NOT the source of truth for the user-facing history.**
  - The web dashboard already has authenticated routes (`/dashboard`), a Supabase session, a `useUserProfile` hook, and `auth.uid()` maps to `public.users` (via `users.auth_id`, soon to be merged per Task 27 — this task must work with the **current** layout: `users.auth_id` indirection).
  - Telegram users with no Supabase Auth account still send messages via Telegram; those messages must appear in the web `messages` table under the same `public.users.id` so that when a Telegram user later signs up on the web with a linked account, they see their Telegram history seamlessly.
- **Primary Owner:** Cristian

---

## 2. Objectives & Success Criteria

- **Goals:**
  - A new `public.messages` table (PK `id bigint identity`, `conversation_id uuid` FK to a new `public.chat_threads` table, `sender_type`, `sender_user_id`, `body text`, `created_at timestamptz`, optional `metadata jsonb`).
  - A new `public.chat_threads` table that groups messages. For now every user has **exactly one** thread of kind `direct_ai`. Schema designed so that future kinds `group` and `direct_user` can be added without table-level migrations.
  - A FastAPI endpoint `POST /chat/send` that: validates a Supabase JWT, resolves it to `public.users.id`, runs the orchestrator, persists the user message + the agent reply in `messages`, returns `{ message_id, reply: { id, body, created_at } }`.
  - A FastAPI endpoint `GET /chat/messages` for paginated history (`?before=<id>&limit=50`) and `GET /chat/search?q=<text>` returning matched message IDs.
  - Telegram flow (`_process_message_bg` in `interfaces/routers/telegram.py`) ALSO writes both messages to `messages` after the orchestrator returns — so the web history stays complete even when the user only uses Telegram.
  - The dashboard ChatPanel renders real data from `messages`, lazy-loads older messages on scroll-up (50 at a time), and exposes a search input that jumps to the matching message and highlights it.
  - On a fresh page load the last 30 messages of the user's `direct_ai` thread are shown.
  - The user can send a message; while the agent is thinking a placeholder bubble is shown; the reply is appended in-place when it arrives.
  - The agent's existing `ConversationManager` rolling context window keeps working unchanged.

- **Non-Goals:**
  - Group chats, user-to-user DMs, or any chat thread with more than one human participant. (Schema must permit it; UI/route must not implement it.)
  - Realtime push to the web client when the user sends a Telegram message in another tab/session. Polling on focus is acceptable; Supabase Realtime is a stretch goal called out in §8.
  - Streaming token-by-token agent reply. The reply lands as a single message when the orchestrator returns.
  - Editing or deleting messages.
  - Migrating the existing `conversations.recent_messages` JSONB into the new `messages` table. Pre-task history is intentionally lost for the web view; nothing depends on it.
  - Touching the Telegram-side rendering (placeholders, edits, Markdown sanitizer) — that stays exactly as it is.
  - **Any non-text input** — image upload, voice notes, file attachments, stickers as media. The `messages.body` column is plain text; `metadata` JSONB is reserved for future use but no UI exposes it.
  - Adopting a full chat-framework library (Stream, CopilotKit, chatscope). See §5.10 for the rationale.

- **Definition of Done:**
  - [ ] `chat_threads` and `messages` tables exist in Supabase with RLS + GRANTs from §5.1.
  - [ ] `POST /chat/send` works end-to-end against a real Supabase JWT: user message persisted, orchestrator called, reply persisted, JSON returned.
  - [ ] `GET /chat/messages?before=<id>&limit=50` returns rows in `created_at DESC` order; cursor-based pagination is stable.
  - [ ] `GET /chat/search?q=<text>` returns matching message IDs + thread_id; backed by a Postgres `tsvector` index for performance.
  - [ ] Sending a message via Telegram results in two new rows in `messages` (one user, one agent) under the same `users.id`.
  - [ ] Dashboard ChatPanel renders live messages, loads more on upward scroll, and search-jumps to a hit with a 1.5s highlight pulse.
  - [ ] Composer supports: emoji picker, multiline (Shift+Enter), auto-grow up to 6 lines, Enter-to-send, "agent is thinking…" indicator, character counter at 3500+ chars.
  - [ ] Agent messages render Markdown (bold, italics, lists, links, inline code) — not raw asterisks. Links open in a new tab with `rel="noopener"`.
  - [ ] Emoji input via picker AND native `:smile:` style shortcodes both produce real Unicode emoji in the persisted body.
  - [ ] Sending a message from the web takes ≤ orchestrator latency + 200ms p95 (no extra network round-trips on the hot path).
  - [ ] Unit tests for the new repository + integration test for `POST /chat/send` with a stub orchestrator pass green.

---

## 3. System Context

- **Repositories / Services Affected:**
  - **Supabase** — new tables, RLS policies, GRANTs, full-text index. Do NOT alter `conversations`, `users`, or any existing table.
  - **Backend (`backend/src/agentic_traveler/`):**
    - `interfaces/dependencies.py` — add `verify_supabase_jwt` dependency.
    - `interfaces/routers/chat.py` — new router, registered in `interfaces/main.py`.
    - `interfaces/schemas.py` — new Pydantic schemas for chat endpoints.
    - `tools/chat_repo.py` — new repository class for `messages` + `chat_threads`.
    - `orchestrator/agent.py` — wrap the orchestrator call site so both Telegram and web persist messages identically. Prefer a small adapter rather than duplicating logic.
    - `interfaces/routers/telegram.py` — after the orchestrator returns, also persist both messages via `ChatRepository`.
  - **Frontend (`frontend/src/`):**
    - `app/api/chat/send/route.ts` — Next.js Route Handler that proxies to the FastAPI backend with the user's Supabase JWT (avoids exposing the backend URL + CORS configuration).
    - `app/api/chat/messages/route.ts` — same pattern for history pagination.
    - `app/api/chat/search/route.ts` — same pattern for search.
    - `hooks/useChat.ts` — new hook: state, pagination cursor, send, search.
    - `components/dashboard/ChatPanel.tsx` — replace mock with live data, add infinite scroll + search.
    - `lib/dashboard-data.ts` — remove `CHAT_HISTORY` constant + `ChatMessage` interface.

- **Architecture flow (web send):**
  ```
  Web ChatPanel
    └─ POST /api/chat/send  (Next.js Route Handler, attaches Supabase access token)
        └─ POST {BACKEND_URL}/chat/send  (FastAPI, verify_supabase_jwt)
            ├─ ChatRepository.append_user_message(user_id, body) → messages row
            ├─ OrchestratorAgent.process_request(user_id, body, ...)
            ├─ ChatRepository.append_agent_message(user_id, reply_body) → messages row
            └─ return { reply: { id, body, created_at } }
  ```

- **Architecture flow (Telegram send — additive):**
  ```
  Telegram webhook (existing)
    └─ _process_message_bg (existing)
        ├─ OrchestratorAgent.process_request(...)  [unchanged]
        ├─ NEW: ChatRepository.append_pair(user_id, user_text, reply_text)
        └─ edit_telegram_message(...)              [unchanged]
  ```
  The `ChatRepository.append_pair` call sits **after** the orchestrator returns but
  **before** the Telegram edit, inside a try/except — a write failure must never
  block the user reply.

- **ID resolution rule:**
  - Web user → JWT `sub` is `auth.users.id`. Resolve to `public.users.id` via `users.auth_id = auth.uid()`. If no row exists (alpha user did not complete Tally), return 403 "Profile not provisioned."
  - Telegram user → `users.id` already resolved by existing `UserRepository.get_user_with_ref`.
  - Both code paths converge on `users.id` before calling `ChatRepository`.

- **Relevant Specs / Docs:**
  - `supabase/schema_public.sql` — existing tables.
  - `supabase/rls_policies.sql` — existing RLS patterns (the `user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())` style).
  - `backend/src/agentic_traveler/orchestrator/agent.py` — orchestrator entry point.
  - `backend/src/agentic_traveler/orchestrator/conversation_manager.py` — context window manager (unchanged by this task).
  - `frontend/src/components/dashboard/ChatPanel.tsx` — UI to replace.

---

## 4. Constraints & Requirements

- **Technical Constraints:**
  - Postgres 15+ (Supabase). Use a generated `tsvector` column + GIN index for search; no third-party search service.
  - Backend: Python 3.13, FastAPI, `supabase-py` via existing `tools/db_client.get_db()` (service role).
  - Frontend: Next.js 16, React 19, `@supabase/ssr` for the access-token retrieval inside Route Handlers.
  - Pagination uses `id` as the cursor (monotonic identity column), not `created_at` (clock skew + duplicate timestamps are real for Telegram bursts).
  - Orchestrator latency p95 today is ≈4–8s; the hot path must add ≤ 200ms.
  - No new external dependencies.

- **Operational Constraints:**
  - Migration runs against the live Supabase project. New tables only — no `ALTER` on existing tables.
  - Backend deploys to Cloud Run; the new endpoint must respect the same cold-start lazy-init pattern used in `interfaces/routers/telegram.py` (`_orchestrator_instance` lazily built per process).
  - Service role key is already wired into the backend `tools/db_client`. No new secrets needed backend-side.
  - Frontend already has `SUPABASE_SERVICE_ROLE_KEY` (used by welcome-grant). The chat Route Handlers do **NOT** need it — they only need the user's JWT to forward to the backend.

- **Security / Compliance:**
  - All `messages` writes happen via service role from the backend. Web users never write directly to the table.
  - RLS allows authenticated users to `SELECT` only their own messages. No INSERT/UPDATE/DELETE policy for users — they MUST go through the backend so that orchestrator/credits/off-topic logic runs.
  - The new FastAPI endpoint must verify the Supabase JWT signature, not just trust the `Authorization` header. Use `PyJWT` with the project's JWT secret (`SUPABASE_JWT_SECRET` env var, already configured for the project).
  - Message bodies may contain PII the user typed. Apply the existing `sanitize_user_input` before persisting on the input side. Do NOT apply `sanitize_telegram_markdown` to web messages — that's Telegram-specific.

---

## 5. Implementation Plan

### 5.1 Database — new tables, RLS, GRANTs

Append to `supabase/schema_public.sql` (or create a numbered migration file under `supabase/migrations/` once that folder is in use):

```sql
-- ---------------------------------------------------------------------------
-- chat_threads
-- Groups messages. Today every user has one thread of kind 'direct_ai'.
-- Schema is forward-compatible with 'group' and 'direct_user' kinds.
-- For 'direct_ai', the owner_user_id IS the participant.
-- For future 'group'/'direct_user', participants are stored in chat_thread_members
-- (NOT created in this task — listed here so future migrations don't surprise anyone).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.chat_threads (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  kind          text        NOT NULL CHECK (kind IN ('direct_ai', 'group', 'direct_user')),
  owner_user_id uuid        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  title         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One direct_ai thread per user. Future thread kinds are not constrained.
CREATE UNIQUE INDEX IF NOT EXISTS chat_threads_owner_direct_ai_uniq
  ON public.chat_threads (owner_user_id)
  WHERE kind = 'direct_ai';


-- ---------------------------------------------------------------------------
-- messages
-- Append-only message log. Source of truth for the user-facing web view.
-- - sender_type='user'  → sender_user_id = the human's users.id, body = their text
-- - sender_type='agent' → sender_user_id = NULL,                  body = orchestrator reply
-- - source              = 'web' | 'telegram'  (audit/debug only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.messages (
  id              bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  thread_id       uuid        NOT NULL REFERENCES public.chat_threads(id) ON DELETE CASCADE,
  sender_type     text        NOT NULL CHECK (sender_type IN ('user', 'agent')),
  sender_user_id  uuid                 REFERENCES public.users(id) ON DELETE SET NULL,
  body            text        NOT NULL,
  source          text        NOT NULL CHECK (source IN ('web', 'telegram')),
  metadata        jsonb       NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),

  -- Generated tsvector for full-text search.
  body_tsv        tsvector    GENERATED ALWAYS AS (to_tsvector('simple', body)) STORED
);

-- Newest-first pagination + cursor seeks on (thread, id).
CREATE INDEX IF NOT EXISTS messages_thread_id_idx
  ON public.messages (thread_id, id DESC);

-- Full-text search.
CREATE INDEX IF NOT EXISTS messages_body_tsv_idx
  ON public.messages USING GIN (body_tsv);


-- ---------------------------------------------------------------------------
-- RLS — authenticated users read only their own thread/messages.
-- All writes go through the service-role backend.
-- ---------------------------------------------------------------------------
ALTER TABLE public.chat_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_threads_self_read" ON public.chat_threads
  FOR SELECT
  USING (
    owner_user_id IN (
      SELECT id FROM public.users WHERE auth_id = auth.uid()
    )
  );

CREATE POLICY "messages_self_read" ON public.messages
  FOR SELECT
  USING (
    thread_id IN (
      SELECT id FROM public.chat_threads
      WHERE owner_user_id IN (
        SELECT id FROM public.users WHERE auth_id = auth.uid()
      )
    )
  );

GRANT SELECT ON public.chat_threads TO authenticated;
GRANT SELECT ON public.messages     TO authenticated;
```

**Note on Task 27:** As of 2026-05-28 Task 27 lands first (`migrations/000_merge_auth_id.sql`). The chat policies use direct equality (`owner_user_id = auth.uid()`) — see `migrations/001_chat_tables.sql` for the actual SQL.

### 5.2 Backend — `tools/chat_repo.py`

New module. Signatures:

```python
class ChatRepository:
    """Append-only persistence for chat threads and messages."""

    def get_or_create_direct_ai_thread(self, user_id: str) -> str:
        """Return the user's direct_ai thread UUID, creating it on first use."""

    def append_user_message(
        self,
        user_id: str,
        body: str,
        source: Literal["web", "telegram"],
        thread_id: Optional[str] = None,
    ) -> dict:
        """Insert a row with sender_type='user'. Returns {id, thread_id, created_at}."""

    def append_agent_message(
        self,
        user_id: str,
        body: str,
        source: Literal["web", "telegram"],
        thread_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Insert a row with sender_type='agent'. Returns {id, thread_id, created_at}."""

    def list_messages(
        self,
        user_id: str,
        before_id: Optional[int] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return messages in id DESC order, up to `limit`. Cursor: id < before_id."""

    def search_messages(
        self,
        user_id: str,
        query: str,
        limit: int = 50,
    ) -> list[dict]:
        """Full-text search inside the user's threads. Uses plainto_tsquery('simple', q)."""
```

Implementation notes:
- All methods use the service-role DB client (`get_db()`), so RLS is bypassed and lookups are direct.
- `get_or_create_direct_ai_thread` is the only path that creates threads. The unique partial index makes it idempotent.
- `metadata` for agent messages may carry `{"action": "...", "latency_ms": ...}` for future debugging — keep this off the hot path (do not block).

### 5.3 Backend — `interfaces/dependencies.py` addition

```python
def verify_supabase_jwt(authorization: str = Header(...)) -> dict:
    """
    Verify a Supabase access token. Returns the decoded payload dict.
    Raises 401 on invalid/expired/malformed tokens.

    Env: SUPABASE_JWT_SECRET (HS256, already used by Supabase Auth).
    """
```

Inside the resolver, after decoding, look up `users.auth_id = payload['sub']` and attach `users.id` to the dependency's return value (use a tiny Pydantic model: `class WebUserCtx(BaseModel): user_id: str; auth_id: str; email: str`). If no `users` row is found, raise 403 with `"Profile not provisioned"`.

### 5.4 Backend — `interfaces/routers/chat.py`

```python
router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/send")
async def chat_send(payload: ChatSendRequest, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """
    1. Sanitize the body (sanitize_user_input).
    2. Resolve/create the user's direct_ai thread.
    3. chat_repo.append_user_message(...).
    4. orchestrator.process_request(user_id=ctx.user_id, message_text=body)
       NOTE: the orchestrator currently takes telegram_user_id and resolves
       users.id internally. Refactor it to also accept a pre-resolved user_doc
       (the cleanest split is a thin wrapper `process_request_by_user_doc`
       used by both telegram.py and chat.py).
    5. chat_repo.append_agent_message(...) with metadata {action, latency_ms}.
    6. Return {reply: {id, body, created_at, metadata}}.
    """

@router.get("/messages")
async def chat_messages(before: int | None = None, limit: int = 50, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """Cursor-paginated history. limit clamped to [1, 100]."""

@router.get("/search")
async def chat_search(q: str, limit: int = 25, ctx: WebUserCtx = Depends(verify_supabase_jwt)):
    """Full-text search. q is trimmed; empty → 400."""
```

Register in `interfaces/main.py`:
```python
from agentic_traveler.interfaces.routers.chat import router as chat_router
app.include_router(chat_router)
```

CORS: the existing app has none. Add `fastapi.middleware.cors.CORSMiddleware` allowing the frontend origin (`FRONTEND_ORIGIN` env). Restrict methods/headers tightly. Telegram + Tally are server-to-server and unaffected.

### 5.5 Backend — orchestrator entry-point refactor

`OrchestratorAgent.process_request` today takes `telegram_user_id: str` and re-does the `get_user_with_ref` lookup. Extract the post-lookup logic into a private method `_process_user_doc(user_doc, user_id, message_text, status_callback)` and have the public method become a thin shim. Add a second public method `process_request_for_user(user_id: str, message_text: str)` used by the web router — it does its own lookup by `users.id` and calls `_process_user_doc`. Both paths share the same downstream logic, ensuring credit deduction, off-topic guard, and conversation-manager save behave identically.

### 5.6 Backend — Telegram router additive persistence

In `_process_message_bg`, after `response = get_orchestrator().process_request(...)` and before editing the placeholder, add:

```python
try:
    chat_repo.append_pair(
        user_id=user_doc["id"],
        user_body=text,
        agent_body=reply,
        source="telegram",
        agent_metadata={"action": response.get("action")},
    )
except Exception:
    logger.exception("chat_repo append failed for telegram user %s", user_id)
```

`append_pair` is a tiny convenience that calls `append_user_message` then `append_agent_message` against the same thread, ensuring both rows share the same `thread_id` lookup once.

### 5.7 Frontend — Next.js Route Handlers

Three files, all server-only, all reading the Supabase session via `@supabase/ssr` `createClient()`:

- `app/api/chat/send/route.ts` — `POST` → forward body + `Authorization: Bearer ${accessToken}` to `${BACKEND_URL}/chat/send`. Return the backend's response verbatim.
- `app/api/chat/messages/route.ts` — `GET` → forward `?before&limit`.
- `app/api/chat/search/route.ts` — `GET` → forward `?q&limit`.

No fancy error mapping — propagate status codes. The frontend never holds the backend URL in client JS.

### 5.8 Frontend — `hooks/useChat.ts`

```ts
type ChatMessage = {
  id: number;
  sender_type: "user" | "agent";
  body: string;
  created_at: string;
};

type UseChatState = {
  messages: ChatMessage[];        // ordered ascending by id
  loading: boolean;
  loadingOlder: boolean;
  hasMore: boolean;
  pendingReply: boolean;          // a placeholder bubble is shown while true
  error: string | null;
};

function useChat(): UseChatState & {
  send: (text: string) => Promise<void>;
  loadOlder: () => Promise<void>;
  search: (q: string) => Promise<ChatMessage[]>;
  jumpTo: (id: number) => Promise<void>;  // loads pages until id is in window
};
```

Internal rules:
- Initial fetch: `GET /api/chat/messages?limit=30`.
- `loadOlder`: `GET /api/chat/messages?before=<oldest.id>&limit=50`.
- `send`: optimistic-append the user message (with a temp negative id), set `pendingReply=true`, POST, replace temp id with server id on response, append the reply.
- `jumpTo`: walks `loadOlder` until the target id is in `messages`, then returns. The component scrolls + pulses the row.

### 5.9 Frontend — `components/dashboard/ChatPanel.tsx`

Replace the mock-driven body. Keep the existing visual styling (gradient bubbles for user, neutral for agent, timestamps). New elements:

- **Search bar** pinned to the top (small, collapsible). Returns a result list; clicking a result triggers `jumpTo(id)`. Empty-state hint: "Search past conversation…".
- **Scroll container** with `onScroll` that calls `loadOlder` when `scrollTop < 80` and `hasMore`. Preserve scroll anchor when new older rows are prepended (compute pre-prepend scrollHeight, restore offset after).
- **Composer** at the bottom:
  - `react-textarea-autosize` (1 to 6 lines), Enter sends, Shift+Enter inserts newline.
  - Inline emoji button (left side) opens an `@emoji-mart/react` picker as a floating panel. Themed against existing CSS vars (`--primary`, `--background`, `--border`). Set `previewPosition="none"`, `skinTonePosition="none"`, `navPosition="bottom"`, `theme="auto"`.
  - Send button (right side) disabled while `pendingReply || !body.trim()`.
  - Character counter appears once `body.length > 3000`; turns amber at 3500, blocks send at 4000.
- **Agent reply rendering**:
  - `react-markdown` + `remark-gfm` for the body. Allow only inline formatting (bold, italics, lists, links, inline code, blockquotes). Custom `a` renderer adds `target="_blank" rel="noopener noreferrer"` and an external-link icon.
  - Auto-linkify bare URLs (handled by `remark-gfm`).
  - Code blocks render with a monospace background but **without** a syntax-highlighter dependency — keeps the bundle small. Travel agent doesn't emit code.
- **User reply rendering**: plain text. Newlines preserved (`white-space: pre-wrap`). No Markdown — what the user typed is what they see.
- **Thinking indicator**: while `pendingReply` is true, show an agent-style bubble with three pulsing dots (`<span className="chat-typing-dots">●●●</span>` with CSS keyframes in `globals.css`).
- **Highlight on jump**: when `jumpTo` lands, scroll the row into view and apply a CSS class `chat-msg-flash` for 1.5s (background fade animation in `globals.css`).
- **Timestamp grouping**: collapse repeated timestamps when consecutive messages are within 60s (Slack-style — show name+time only on the first of a run).
- **Empty state**: if `messages.length === 0`, show a friendly "Say hi to your travel companion 👋" placeholder above the composer.
- Remove the import from `@/lib/dashboard-data` and remove `CHAT_HISTORY` from that file.

### 5.10 Library choices — what we adopt and why we don't adopt a chat framework

**Adopted libraries** (small, themeable, single-purpose):

| Package | Purpose | Why this one |
|---|---|---|
| `@emoji-mart/react` + `@emoji-mart/data` | Emoji picker + `:shortcode:` → emoji conversion | Tree-shakeable, themeable via CSS custom props, no peer-network calls, ~80kB gz. Active maintenance, used by Slack/Linear-style apps. |
| `react-markdown` | Render agent Markdown safely | Pluggable, no `dangerouslySetInnerHTML`, easy to lock down allowed elements. |
| `remark-gfm` | GitHub-flavored Markdown (tables, autolinks, strikethrough) | Pairs with `react-markdown`. The agents already emit GFM-flavored output. |
| `react-textarea-autosize` | Auto-growing composer textarea | Tiny (<3kB), single-purpose, doesn't fight Tailwind. |

**Rejected libraries and rationale:**

- **`stream-chat-react`** — Assumes Stream's hosted backend; would force us to mirror state into their system. Heavy (~250kB), opinionated styling clashes with the existing dashboard aesthetic.
- **`@chatscope/chat-ui-kit-react`** — Decent themeable kit but its component model (MainContainer/ChatContainer/MessageList) replaces our layout primitives. Migrating the existing `ChatPanel` styling to its slot model is more work than building bubbles by hand.
- **`@copilotkit/react-ui`** — Designed around CopilotKit's runtime + their own backend protocol (`copilotRuntime`). We already have a custom orchestrator and persistence; their abstractions would fight us.
- **`assistant-ui`** — Closest fit (headless, themeable, AI-first), and worth re-evaluating if we add streaming. But it currently assumes a streaming protocol (Vercel AI SDK or LangGraph). Our orchestrator returns a single reply — adopting it for v1 buys little and adds a dependency.
- **Vercel AI SDK `useChat`** — A hook, not a UI kit, and tightly bound to its own streaming envelope. We'd be re-implementing send/history/search around it anyway.

**Bottom line:** The chat surface is ~400 lines of focused React. A framework would replace those 400 lines with ~2000 lines of integration glue plus a heavy dependency. The four small libraries above give us the modern feel (emojis, Markdown, auto-grow input) without surrendering layout control.

**Forward door:** When we add streaming (out of scope; §8), re-evaluate `assistant-ui`. Its primitives + our `useChat` hook are structurally compatible — the migration would replace the rendering layer only, not the data layer.

---

## 6. Testing & Validation

- **Unit (backend):**
  - `tests/tools/test_chat_repo.py` — `get_or_create_direct_ai_thread` idempotency, `list_messages` cursor correctness across two pages, `search_messages` returns the row that contains the query token.
  - `tests/interfaces/test_chat_router.py` — `POST /chat/send` with a fake JWT + stubbed orchestrator returns the expected JSON; `GET /chat/messages` honours `before`.
  - `tests/orchestrator/test_agent_entry_points.py` — both `process_request` (telegram path) and `process_request_for_user` (web path) call the same private method with identical args (assert via spy).

- **Integration (manual, smoke):**
  - Sign in on the dashboard with a known account. Send "Hi" — agent reply appears within ~5s. Refresh. Both messages still there.
  - Open Telegram with the same account, send a message. Refresh the dashboard. The Telegram exchange is visible in the web log.
  - Scroll up — older messages load 50 at a time, no duplicates, no flicker.
  - Search for a word from message 200 — the result jumps and pulses.

- **Performance:**
  - `EXPLAIN ANALYZE` on `SELECT … FROM messages WHERE thread_id=$1 AND id<$2 ORDER BY id DESC LIMIT 50` should hit the `messages_thread_id_idx`.
  - Full-text search on a ~10k-message thread returns in <50ms locally.

- **Tooling:** Existing pytest + `uv run pytest`. No new CI jobs needed.

---

## 7. Risk Management

- **Risk (removed):** ~~Web user sends a message but `users` row missing.~~ After
  Task 27, the `on_auth_user_created` trigger guarantees `users`,
  `user_profiles`, and `credits` rows exist for every authenticated user.
  No "profile not provisioned" path remains.

- **Risk:** Two parallel `POST /chat/send` calls from the same user duplicate the user row.
  **Mitigation:** `messages` is append-only; both will be saved. Add a client-side disable-while-pending guard on the send button so this is hard to trigger.

- **Risk:** Telegram `chat_repo.append_pair` fails — Telegram users would lose web history.
  **Mitigation:** This must not be possible under normal operation — the same
  DB connection is already used for reads on the hot path. To survive
  transient hiccups, `chat_repo` wraps each write in a bounded
  exponential-backoff retry (`_retry`, 3 attempts, 0.25s base). Final failure
  is logged at ERROR. The Telegram reply still goes through regardless. If
  this fires in production it indicates a real config or connectivity issue
  that warrants alerting, not silent degradation.

- **Risk:** `to_tsvector('simple', body)` doesn't handle non-English well.
  **Mitigation:** `'simple'` is the conservative choice (no stemming, no stopwords) — good for a multilingual user base (Romanian, English, etc.). If quality is poor we can revisit with a language column later.

- **Risk:** Orchestrator latency now blocks the HTTP response (Telegram works around this with a background task + placeholder edit).
  **Mitigation:** Acceptable for web v1 — the spinner UI is fine for a 5–8s wait. Streaming is explicitly out of scope.

- **Rollback Plan:** Drop the new tables, revert the orchestrator refactor, restore the static `ChatPanel`. No existing flows depend on the new code.

---

## 8. Future Extensions (explicitly out of scope; spec-aware design only)

Captured in `specs/task_41_chat_future_extensions.md`:
- Group / DM threads (chat_thread_members + relaxed RLS).
- Supabase Realtime subscription on messages.
- SSE streaming agent replies.
- Attachments (images/voice/files) via `messages.metadata`.
- **RAG over messages** — embed each row with a small efficient model
  (384-d, ideally 192-d), store as `pgvector`, HNSW index, async embedding
  worker, top-K retrieval in the agent prompt.
- **Multiple-choice prompts with confirm button** — structured agent
  reply rendered as options + submit; client posts the selection back.

---

## 9. Delivery & Handoff

- **Deliverables:**
  - SQL migration file (or appended block in `supabase/schema_public.sql` + `rls_policies.sql`).
  - Backend PR: `chat_repo.py`, `chat.py` router, dependency, orchestrator refactor, telegram persistence hook, tests.
  - Frontend PR: route handlers, `useChat` hook, new `ChatPanel`, removal of mock constants.
- **Review:** Cristian.
- **Post-delivery:** Monitor `chat_repo` errors for 48h. Verify that Telegram-only users start accumulating `messages` rows. If the search query feels slow, revisit `to_tsvector` language config.

---

## 10. Appendix

- **Glossary:**
  - *Thread (`chat_threads`)* — a conversation envelope. Today: 1 per user, kind `direct_ai`.
  - *Message (`messages`)* — a single utterance, `user` or `agent`.
  - *Conversation context (`conversations`)* — the agent's rolling-window memory, untouched by this task.
- **Change Log:**
  - 2026-05-28 — Initial draft.
  - 2026-05-28 — Added §5.10 (library choices), composer details (emoji picker, autosize textarea, Markdown rendering, typing indicator), text-only scope clarification.
  - 2026-05-28 — Implementation pass:
    - Task 27 (`auth_id` merge) landed first; RLS simplified to direct equality.
    - Risk #1 removed (no "profile not provisioned" path anymore).
    - Risk #3 hardened with `_retry` exponential-backoff in `chat_repo`.
    - Swapped `@emoji-mart/react` (no React 19 peer-dep) for `emoji-picker-react`.
    - Future extensions moved to `specs/task_41_chat_future_extensions.md` and
      expanded with RAG + multi-choice UI items.
