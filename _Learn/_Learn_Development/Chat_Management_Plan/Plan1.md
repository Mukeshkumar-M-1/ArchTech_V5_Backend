# Interactive Chat Backend Integration

## Context
The `ChatPanel.jsx` frontend is a simple chat UI with no backend connection. The `backend/tools/` module has a fully functional agentic execution engine (QueryLoop, streaming API, tool registry, session management) but is not wired into the FastAPI server. The goal is to connect them so user messages trigger the agentic loop and streaming responses (text, tool use, tool results) are pushed back to the frontend in real-time.

## Approach: SSE (Server-Sent Events)
SSE is the right choice — request→stream→response is one-directional server→client. FastAPI's `StreamingResponse` with `text/event-stream` works out of the box.

---

## Step 1: Create `backend/tools/chat_events.py`

**Event types:** `TEXT_DELTA`, `TOOL_USE_START`, `TOOL_USE_COMPLETE`, `TOOL_ERROR`, `TURN_START`, `TURN_COMPLETE`, `DONE`, `ERROR`, `SESSION_CREATED`

**Functions:**
- `serialize_event(type, **kwargs)` → returns `"data: {json}\n\n"` string for SSE
- `emit(type, **kwargs)` → async generator that yields serialized SSE event strings

**Reuse:** No dependencies on other new files.

---

## Step 2: Create `backend/tools/chat_sessions.py`

```python
class ChatSessionManager:
    _sessions: dict[str, {session_id, messages, project_id, created_at}]
    _lock: asyncio.Lock()

    async def get_or_create(session_id | None, project_id) -> str
    async def add_message(session_id, role, content)
    async def get_messages(session_id) -> list[dict]
    async def clear_session(session_id) -> bool
    async def list_sessions() -> list[dict]
```

**Reuse:** `SessionLifecycle` from `session_manager.py` for transcript paths.

---

## Step 3: Create `backend/Routes/chat_routes.py`

**Routes on `APIRouter()`:**

### `POST /chat/send` — Main streaming endpoint
- **Request:** `{ session_id?, message, project_id? }`
- **Flow:**
  1. Resolve/create session via `ChatSessionManager.get_or_create()`
  2. Add user message: `chat_sessions.add_message(session_id, "user", message)`
  3. Build tool definitions: `registry.build_tool_definitions()`
  4. Build system prompt: `SystemPromptManager.build(tools=..., session_id=...)`
  5. Run agentic loop using `StreamingLLMClient.stream()` + `ToolExecutor` directly (event-by-event control, not `QueryLoop.run()`)
  6. Yield SSE events: `SESSION_CREATED` → `TURN_START` → `TEXT_DELTA` × N → optional `TOOL_USE_START`/`TOOL_USE_COMPLETE` → `DONE`
- **Response:** `StreamingResponse(generator(), media_type="text/event-stream")`

### `GET /chat/messages/{session_id}` — Fetch history
- Returns `chat_sessions.get_messages(session_id)` as list of `{role, content}`

### `GET /chat/sessions` — List sessions
- Returns `chat_sessions.list_sessions()`

---

## Step 4: Wire into `backend/main.py`

Add two lines:
```python
from Routes.chat_routes import router as chat_router
app.include_router(chat_router, prefix="")
```

---

## Step 5: Frontend SSE Integration

**File: `/home/devusr/Mukesh/ArchTech_V5/Frontend/src/views/SoftwareWorkspace.jsx`**

Replace the `handleChatSend` stub with:
1. `fetch(getApiUrl('/chat/send'), { method: 'POST', body: JSON.stringify({ message, session_id }) })`
2. Read response body with `getReader()` + `TextDecoder`, parse `data:` lines (same SSE pattern used in `handleGenerateDoc`)
3. For each event:
   - `text_delta`: accumulate in buffer, append to last bot message
   - `tool_use_start`/`tool_use_complete`: show tool badge in chat bubble
   - `done`: finalize accumulated buffer as new bot message, set `isStreaming = false`
   - `error`: set `isStreaming = false`, add error message
   - `session_created`: save new session_id
4. Add `currentSessionId` state to the component

**No changes to `ChatPanel.jsx`** — it already accepts the correct props (`messages`, `input`, `onSend`, `isStreaming`, `onClose`).

---

## Step 6: Create Frontend API Helper

**File: `/home/devusr/Mukesh/ArchTech_V5/Frontend/src/api/chatApi.js`**

```javascript
import { getApiUrl } from '../utils/apiConfig';

export async function fetchChatMessages(sessionId) { ... }
export async function fetchChatSessions() { ... }
```

Follows the same pattern as `templateApi.js`.

---

## Critical Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/tools/chat_events.py` | **New** | Event types + SSE serialization |
| `backend/tools/chat_sessions.py` | **New** | In-memory chat session store |
| `backend/Routes/chat_routes.py` | **New** | FastAPI routes: `/chat/send`, `/chat/messages/{id}`, `/chat/sessions` |
| `backend/main.py` | **Modify** | Import + register `chat_router` |
| `SoftwareWorkspace.jsx` | **Modify** | Replace `handleChatSend` with SSE fetch |
| `Frontend/src/api/chatApi.js` | **New** | Frontend API helpers |

## SSE Event Format

```json
{"type": "text_delta", "content": "partial text chunk"}
{"type": "tool_use_start", "tool_call_id": "toolu_...", "name": "FileRead"}
{"type": "tool_use_complete", "tool_call_id": "toolu_...", "output": "file contents"}
{"type": "tool_error", "tool_call_id": "toolu_...", "name": "Bash", "error": "exit code 1"}
{"type": "turn_start", "turn": 3}
{"type": "done", "content": "final response text"}
{"type": "error", "message": "description"}
{"type": "session_created", "session_id": "abc123"}
```

## Verification

1. Run backend: `cd Backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8015`
2. Open frontend and toggle Chat panel
3. Send a message → should stream bot response in real-time
4. Check browser network tab → SSE stream should show `text/event-stream` content-type
5. Run `py_venv/bin/python3 ./backend/tools/test_integration.py` to ensure existing tests still pass
