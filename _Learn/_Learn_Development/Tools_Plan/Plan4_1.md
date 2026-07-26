# Development Plan: Bridge Missing Features in backend/tools/

## Context

The conceptual overview in `CONCEPTUAL_OVERVIEW.md` and `SYSTEM_PROMPT_MANAGEMENT.md` describes a production-grade agent orchestration system with 8 layers of context management, streaming API integration, progress tracking, permissions, session memory, and block-structured system prompts.

The current Python `backend/tools/` implementation covers the **core engine** (query loop, tool registry, concurrency partitioning, agent lifecycle, transcript, token tracking, error recovery) but is **missing critical infrastructure** that prevents it from operating at scale.

This plan bridges every gap as a dependency graph — each layer builds on prior layers, all with exact file paths.

---

## Dependency Graph

```
Layer 0 (foundation — no deps)
  ├── query_guard.py          ← single-query concurrency lock
  ├── progress_types.py       ← progress event types + buffer (no MCP — only bash/powershell/sleep)
  └── session_manager.py      ← session lifecycle (PID file, resume, clear, discover)

Layer 1 (builds on Layer 0)
  ├── executor.py (mod)       ← add Pre/Post hooks + permission check
  └── permission.py           ← permission rules for tools

Layer 2 (builds on Layer 0, 1)
  ├── compaction.py           ← snip + microcompact + auto-compact pipeline
  └── session_memory.py       ← session memory extraction + caching + reuse

Layer 3 (builds on Layer 0-2)
  └── streaming_api.py        ← streaming API + progress injection

Layer 4 (builds on Layer 0-3)
  └── system_prompt.py        ← block-structured system prompt with caching

Layer 5 (integrates all layers)
  ├── query_loop.py (mod)     ← wire guard, compaction, streaming, memory, prompt
  ├── transcript.py (mod)     ← enhance JSONL with entry types, recovery, batch queue
  ├── session.py (mod)        ← add session management per CCB spec
  └── __init__.py (mod)       ← export all new modules

Layer 6 (verification)
  └── tests + manual integration
```

---

## Layer 0: Foundation — No Dependencies

### 0a. `query_guard.py` (NEW)

**Problem:** No concurrency control — multiple queries corrupt session state simultaneously.

**What to create:**
- `QueryGuard` class with `tryStart(session_id) -> bool` / `end(session_id)` / `reserve(session_id)`
- State machine: `idle -> dispatching -> running -> idle` and `-> requires_action (tool waiting)`
- `tryStart()`: returns `True` if transitioned to `running`, `False` if already `running` (locks out concurrent queries)
- `reserve()`: returns `True` if transitioned to `dispatching` (used for user input)
- `end()`: transitions `running -> idle`, releases lock
- Thread-safe via `asyncio.Lock`

**File:** `backend/tools/query_guard.py`

### 0b. `progress_types.py` (NEW)

**Problem:** No progress event system — users see nothing until tools finish.

**What to create:**
1. `ProgressType` enum: `BASH_PROGRESS`, `POWERSHELL_PROGRESS`, `SLEEP_PROGRESS`, `TOOL_START`, `TOOL_PROGRESS`, `TOOL_COMPLETE` (no MCP)
2. `ProgressMessage` dataclass: `type: ProgressType`, `content: str`, `is_complete: bool`, `tool_call_id: str | None`, `timestamp: float`
3. `ProgressBuffer` class — thread-safe FIFO per session:
   - `push(msg: ProgressMessage)`, `pop_all() -> list[ProgressMessage]`
   - `get_everyp(type) -> list[ProgressMessage]`
   - Clear on turn completion (progress is ephemeral)

**File:** `backend/tools/progress_types.py`

### 0c. `session_manager.py` (NEW)

**Problem:** Session management (PID file, resume, clear, discover) described in CCB spec is not implemented. Current `session.py` is limited to stage progress.

**What to create:**
1. `SessionLifecycle` class:
   - `create(session_id, project_path, entrypoint="cli") -> SessionRecord`
   - Creates `.archtech/sessions/<PID>.json` with pid, sessionId, cwd, startedAt, kind, entrypoint
   - Creates transcript at `.archtech/projects/<sanitized-project-path>/<sessionId>.jsonl`

2. `SessionRecord` dataclass:
   - `session_id`, `pid`, `cwd`, `started_at`, `kind`, `entrypoint`
   - `transcript_path`, `status`, `parent_session_id` (for /clear)

3. `SessionResume`:
   - `load_latest(project_path) -> SessionRecord | None` — finds latest non-terminal session
   - `switch(session_id) -> bool` — moves from old transcript to new session (for /clear)

4. `SessionDiscovery`:
   - `list_active() -> list[SessionRecord]` — reads PID files
   - `list_history(project_path) -> list[SessionRecord]` — reads project transcript directories

**File:** `backend/tools/session_manager.py`

---

## Layer 1: Core Execution Augmentation

### 1a. Modify `executor.py` — Add Hook System + Permission

**Problem:** No extensibility (no plugin hooks), no authorization (tools execute without permission).

**Changes:**
1. **PreToolUse hooks:** Add `self._pre_hooks: list[Callable]` to `__init__`. Before `tool.execute()`, run each: `result = hook(tool.name, input)`. If hook returns `None`, abort tool call with `"Blocked by pre-hook"` error.
2. **PostToolUse hooks:** Add `self._post_hooks: list[Callable]`. After `tool.execute()`, run each: `result = hook(tool.name, result, is_error)`.
3. **Permission check:** Add `self._permission_checker: PermissionChecker | None`. Before each tool: `if checker and not checker.can_use(tool.name): return ToolExecutionResult(is_error=True, content="Permission denied for tool: {tool_name}")`.
4. **Module-level registration:** `register_pre_hook(fn)`, `register_post_hook(fn)` — appends to module-level lists that new executors inherit.

**File:** `backend/tools/executor.py` (modify `__init__`, `execute`, add hook storage)

### 1b. `permission.py` (NEW)

**Problem:** Tools execute without authorization — Bash can write anywhere, FileEdit can delete entire files.

**What to create:**
- `PermissionMode` enum: `FULL_AUTO` (no prompts), `REQUIRE_PROMPT` (confirm each), `SKIP` (deny all)
- `PermissionChecker` class:
  - `auto_allow = {"FileRead", "FileWrite", "FileEdit", "Glob", "Search", "TaskList", "TaskGet", "TaskOutput", "Skill", "SendMessage"}`
  - `require_prompt = {"Bash", "TaskCreate", "TaskUpdate", "TaskStop", "Agent", "TodoWrite"}`
  - `can_use(tool_name) -> bool`: checks `auto_allow`, returns `True` for auto, `False` for require_prompt mode
  - `check(tool_name, mode) -> bool`: returns `True` if allowed, `False` if denied
  - `get_denied_tools(mode) -> list[str]`: lists tools denied in given mode

**File:** `backend/tools/permission.py`

---

## Layer 2: Context Compaction + Session Memory

### 2a. `compaction.py` (NEW)

**Problem:** Conversation grows without bound — tokens exceed context window, API fails or costs too much.

**What to create (single file, 4 classes):**

1. **`SnipCompact`**:
   - `run(messages, message_threshold=30) -> list[dict]`
   - Scans messages for file content references in tool_result blocks
   - Replaces large file content (>500 chars) with `[File: /path/to/file, N lines]`
   - Only applies to messages with `role == "tool"` (result blocks)
   - Returns modified messages with stubbed content

2. **`MicroCompact`**:
   - `run(messages, turn_threshold=5) -> list[dict]`
   - Scans from front (oldest), replaces tool_result content with `'[Old tool result content cleared]'`
   - Only applies to compactable tools: FileRead, Glob, Search, TodoWrite, Skill
   - Preserves last 2 tool results and all assistant text
   - Returns modified messages

3. **`AutoCompact`**:
   - `run(messages, token_budget, summarize_fn) -> tuple[list[dict], str | None]`
   - When tokens exceed budget: splits into `old` (before boundary) + `recent` (tail ~40% of messages)
   - Calls `summarize_fn(old)` which comes from session_memory.py (session memory first) or is None (legacy)
   - Returns `(boundary_message + summary + recent, summary_text)`
   - Circuit breaker: tracks `consecutive_fails`, stops after 3

4. **`CompactPipeline`**:
   - `run(messages, state) -> list[dict]`
   - Step 1: `SnipCompact.run(messages)`
   - Step 2: `MicroCompact.run(messages)`
   - Step 3: if tokens exceeded budget -> `AutoCompact.run(messages)`
   - Tracks state: `message_count`, `token_count`, `consecutive_fails`

**File:** `backend/tools/compaction.py`

### 2b. `session_memory.py` (NEW)

**Problem:** Auto-compact has no summary — can't reuse extracted memory, makes wasteful API calls.

**What to create:**
1. **`SessionMemoryExtractor`**:
   - `extract(messages, session_id) -> dict`
   - Scans last turn's messages for: file paths, function signatures, class names, key decisions, TODO items
   - Returns `{files: [{path, lines}], decisions: [...], code_changes: [...], todos: [...]}`
   - Called after each turn (incremental, not full transcript)

2. **`SessionMemoryCache`**:
   - `save(session_id, memory: dict) -> None` — writes to `.archtech/sessions/<session_id>/memory.json`
   - `load(session_id) -> dict | None` — reads memory for this session
   - `clear(session_id) -> None` — called on /clear or compaction reset
   - `update(session_id, delta: dict) -> dict` — merges new memory with existing

3. **`SessionMemoryCompactAdapter`**:
   - `get_summary(session_id) -> str | None` — returns formatted memory as compact summary
   - If no memory exists, returns `None` (triggers legacy fallback in compaction)

**File:** `backend/tools/session_memory.py`

---

## Layer 3: Streaming API + Progress Integration

### 3a. `streaming_api.py` (NEW)

**Problem:** Query loop uses non-streaming API — slow response, no character-by-character display, no per-token progress.

**What to create:**
1. **`StreamingLLMClient`**:
   - Wraps existing `StreamingLLMHandler` from `backend/llm_api_handler.py`
   - `stream(messages, tools, system_prompt, on_progress) -> AsyncGenerator[str, None]`
   - Yields token chunks as they arrive
   - Calls `on_progress(chunk, "bash_progress")` for each text chunk
   - Handles tool_use blocks: accumulates tokens until complete block, yields `{"type": "tool_use", ...}`

2. **`ProgressInjector`**:
   - `inject_progress(stream_response, tool_call_id, tool_name) -> AsyncGenerator[ProgressMessage, None]`
   - Converts raw stream into typed `ProgressMessage` objects
   - Pushes to `ProgressBuffer` for UI consumption

3. **Integration with query_loop**:
   - `_stream_call_with_fallback()` replaces `_call_with_fallback()`
   - Yields progress events during execution
   - Falls back to non-streaming if streaming API unavailable

**File:** `backend/tools/streaming_api.py`

---

## Layer 4: Block-Structured System Prompt

### 4a. `system_prompt.py` (NEW)

**Problem:** System prompt is a flat string — no caching scopes, no dynamic sections, no CLAUDE.md injection, no git status context.

**What to create:**
1. **`SystemPromptBlock`** dataclass:
   - `content: str`, `cache_scope: str | None` (`"global"`, `"org"`, `None`)
   - `is_cached: bool` (tracks cache hit status per session)

2. **`StaticBlockBuilder`**:
   - `build(tools: list, model: str) -> list[SystemPromptBlock]`
   - Builds: attribution header, CLI prefix, identity, rules, actions, tone, tool descriptions
   - All blocks get `cache_scope="global"`
   - Inserts `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` sentinel

3. **`DynamicBlockBuilder`**:
   - `build(session_memory: dict, git_status: str, mcp_instructions: str) -> list[SystemPromptBlock]`
   - Builds: session_guidance, memory, env_info, MCP instructions, scratchpad, token_budget
   - All blocks get `cache_scope=None` (session-scoped)

4. **`UserContextBuilder`**:
   - `build(claude_md: str, current_date: str) -> dict`
   - Returns `{"role": "user", "content": "Here are your project instructions..." + claude_md + date}`
   - Injected as synthetic user message before each API call

5. **`SystemContextBuilder`**:
   - `build(git_status: str) -> SystemPromptBlock`
   - Appended to system prompt array

6. **`SystemPromptManager`**:
   - `build(tools, session_id, memory, git_status) -> list[SystemPromptBlock]`
   - Assembles static prefix + dynamic tail
   - `clear_cache()` — called on `/clear` or `/compact`
   - `get_blocks_for_api() -> list[dict]` — returns blocks with `cache_control` annotations

**File:** `backend/tools/system_prompt.py`

---

## Layer 5: Integration — Wire Everything Together

### 5a. Modify `query_loop.py` — Full Integration

**Changes to `run()` method — complete replacement of the loop body:**

```
# PREP (before API call):
# 0. Guard check
if not self._query_guard.try_start():
    return "Query already running"

# 1. Strip pre-compact messages
full_messages = self._strip_pre_compact(full_messages)

# 2. Release raw tool result payloads (free memory)
self._release_tool_payloads(full_messages)

# 3-7. Run compaction pipeline
full_messages, summary_text = self._compaction_pipeline.run(full_messages, state)

# 8. Build system prompt blocks + user context
system_blocks = self._system_prompt_manager.build(tools=tools, session_id=self._session_id)
user_context = self._user_context_builder.build()
messages = system_blocks + [user_context] + full_messages

# EXECUTE:
# 9. Call API (streaming or non-streaming)
if self._streaming_enabled:
    async for progress_msg in self._streaming_client.stream(messages, ...):
        yield progress_msg
else:
    response = await self._call_with_fallback(...)

# 10. Extract tool_use blocks
# 11. Execute tools with progress + hooks + permission
tool_results = await self._execute_tools_with_progress(tool_calls)

# 12. Collect tool_results into messages
# 13. Loop back if more tool_use

# SIDE EFFECTS (end of turn):
# Session memory extraction (periodic)
await self._memory_extractor.extract(full_messages, self._session_id)

# Write transcript
self._transcript_writer.write_turn(role="assistant", content=...)

# End query guard
self._query_guard.end()
```

**Files modified:** `backend/tools/query_loop.py`

### 5b. Modify `transcript.py` — Enhanced JSONL with Entry Types

**Problem:** Transcript currently only has `role`-based entries. CCB spec requires typed entries (user, assistant, attachment, tool_use, tool_result, compact_summary).

**Changes:**
1. Add `TranscriptEntry` dataclass: `type` (user|assistant|attachment|tool_use|tool_result|compact_summary), `content`, `tool_call_id`, `timestamp`
2. `write_entry(entry: TranscriptEntry)` — writes typed entry
3. `write_turn_with_entries(messages) -> None` — groups assistant + tool_use + tool_result into one atomic write
4. **Corruption recovery**: `recover() -> bool` — reads entire file, filters bad JSON lines, rewrites
5. **Large file handling**: if transcript > 50MB, skip recovery (OOM safety)
6. **Batch queue**: 100ms batch write queue for high-frequency writes

**File:** `backend/tools/transcript.py` (modify `TranscriptWriter`)

### 5c. Modify `session.py` — Add Session Management per CCB Spec

**Problem:** Current `session.py` is limited to stage progress. Missing session lifecycle (create, resume, clear, discover, PID file).

**Changes:**
1. Add `SessionLifecycle` class (delegates to `session_manager.py`):
   - `create(project_id, target_sections) -> SessionInfo` — calls `SessionLifecycle.create()`
   - `resume(project_id) -> SessionInfo | None` — calls `SessionLifecycle.load_latest()`
   - `clear(session_id) -> bool` — calls `switch()`, sets `parent_session_id`
   - `discover_active() -> list[SessionInfo]` — calls `SessionDiscovery.list_active()`
   - `discover_history(project_id) -> list[SessionInfo]` — calls `SessionDiscovery.list_history()`

2. Enhance `SessionInfo`:
   - Add `parent_session_id: str | None` (for /clear)
   - Add `entrypoint: str` (cli, vscode, etc.)
   - Add `transcript_path: str`
   - Add `pid: int`

**File:** `backend/tools/session.py` (modify SessionInfo, add lifecycle methods)

### 5d. Modify `__init__.py` — Export All New Modules

**Changes:**
```python
from .query_guard import QueryGuard
from .progress_types import ProgressType, ProgressMessage, ProgressBuffer
from .session_manager import SessionLifecycle, SessionRecord, SessionDiscovery
from .compaction import CompactPipeline, SnipCompact, MicroCompact, AutoCompact
from .session_memory import SessionMemoryExtractor, SessionMemoryCache
from .streaming_api import StreamingLLMClient, ProgressInjector
from .permission import PermissionChecker, PermissionMode
from .system_prompt import (
    SystemPromptManager, StaticBlockBuilder, DynamicBlockBuilder,
    UserContextBuilder, SystemContextBuilder,
)

__all__ = [..., "QueryGuard", "ProgressType", "ProgressBuffer",
           "SessionLifecycle", "SessionDiscovery", "CompactPipeline",
           "SessionMemoryExtractor", "StreamingLLMClient",
           "PermissionChecker", "SystemPromptManager"]
```

**File:** `backend/tools/__init__.py`

---

## Layer 6: Verification — All Features Wired End-to-End

### 6a. Run existing tests
```bash
cd backend/tools && python test_tools.py
```

### 6b. Full integration test — single end-to-end flow
Instead of isolated unit tests, write ONE comprehensive test that wires every feature together in a single agentic turn:

1. **Session creation** → `SessionLifecycle.create()` writes `.archtech/sessions/<PID>.json`
2. **Query guard** → `QueryGuard.tryStart()` succeeds, second concurrent call rejected
3. **System prompt** → `SystemPromptManager.build()` creates blocks with `global` cache scope for static, `None` for dynamic
4. **User context** → CLAUDE.md + date injected as synthetic user message
5. **Context management** → SnipCompact replaces large file content with stubs (>500 chars)
6. **MicroCompact** → After 5 turns, oldest tool results replaced with placeholder
7. **Auto-Compact** → When tokens exceed budget, SessionMemory provides summary (saves API call)
8. **Streaming API** → `StreamingLLMClient.stream()` yields `ProgressMessage` objects during call
9. **Permission check** → FileRead auto-allowed, Bash blocked in `FULL_AUTO` mode
10. **Tool execution** → Pre/Post hooks fire around `tool.execute()`, tool result written to transcript
11. **Progress buffer** → `ProgressBuffer.push()` during streaming, `pop_all()` consumed by UI layer
12. **Transcript** → Typed entries (tool_use, tool_result, compact_summary) written atomically
13. **Session memory** → `SessionMemoryExtractor.extract()` after turn, cached for future auto-compact
14. **Query guard end** → `QueryGuard.end()` releases lock, session returns to `idle`

### 6c. Negative test scenarios
1. **Corrupted transcript** → `TranscriptWriter.recover()` repairs bad JSON, files >50MB skip recovery
2. **Session conflict** → Two processes claim same PID file — second detects alive process via `/proc`
3. **Auto-compact cascade failure** → Circuit breaker stops after 3 consecutive failures
4. **Permission denied cascade** → All tools blocked → AI returns error message to user

---

## Summary of All Files

| Action | File | What |
|--------|------|------|
| NEW | `query_guard.py` | Single-query concurrency lock (P0) |
| NEW | `progress_types.py` | Progress event types + buffer (P1) |
| NEW | `session_manager.py` | Session lifecycle per CCB spec (P0) |
| NEW | `permission.py` | Permission checker with rules (P2) |
| NEW | `compaction.py` | Snip + microcompact + auto-compact pipeline (P0) |
| NEW | `session_memory.py` | Memory extraction + caching + reuse (P1) |
| NEW | `streaming_api.py` | Streaming API + progress injection (P1) |
| NEW | `system_prompt.py` | Block-structured system prompt (P2) |
| MOD | `executor.py` | Pre/Post hooks + permission check (P2) |
| MOD | `query_loop.py` | Wire guard, compaction, streaming, memory, prompt (all) |
| MOD | `transcript.py` | Typed entries, recovery, batch queue (P2) |
| MOD | `session.py` | Add lifecycle methods per CCB spec (P0) |
| MOD | `__init__.py` | Export all new modules |

---

## Risk Map

| Risk | Impact | Mitigation |
|------|--------|------------|
| Streaming API changes response format | Tool_use blocks may be fragmented | Token-assembler buffers until complete block |
| Compaction changes API contract | API may not understand stubs | Only apply snip to tool_result blocks (never assistant/system) |
| Session memory extraction is expensive | High CPU per turn | Extract only from last turn (incremental), not full transcript |
| Permission system blocks legitimate auto-runs | User friction | Make `PermissionMode` configurable per-session, default `REQUIRE_PROMPT` |
| Transcript recovery on large files | OOM on >50MB | Skip recovery for files >50MB |
| PID file conflict across processes | Session collision | Use `/proc/<PID>/stat` to verify process alive before claiming session |
