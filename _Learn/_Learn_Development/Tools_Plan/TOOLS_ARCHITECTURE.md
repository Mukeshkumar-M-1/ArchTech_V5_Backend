# Tools Package — Complete File-by-File Architecture

**Package**: `backend/tools/`
**Purpose**: A tool orchestration layer enabling an LLM to autonomously perform software engineering tasks across multiple turns.

---

## `__init__.py` — Package Entry Point

| Line | What | Why | How Wired |
|------|------|-----|-----------|
| `from . import builtins` | Triggers auto-registration of all 17 built-in tools | Without this, no tools are registered at import time | Side effect import — just importing `tools` registers everything |
| `from .registry import ...` | Exports `ToolRegistry`, `ToolDefinition`, `register`, `registry` | Core registry system used by every other module | Re-exported for external consumers |
| `from .executor import ...` | Exports `ToolExecutor`, `ToolExecutionResult`, hooks | Tool execution pipeline | Used by `QueryLoop` to execute tool calls |
| `from .concurrency import ConcurrencyManager` | Parallel execution partitioning | Speed up turns with read-only parallel tools | Ready for use in `QueryLoop._execute_tools()` |
| `from .query_loop import QueryLoop` | Main agentic loop | The entry point for agent execution | Called by outer application layer |
| `from .error_recovery import ErrorRecovery` | Multi-tiered error handling | Handles API failures automatically | Used in `QueryLoop._call_with_fallback()` |
| `from .agent_spawner import AgentSpawner, AgentResult` | Subagent process creation | Spawn parallel subagents | Called by `Agent` built-in tool |
| `from .message_manager import MessageManager` | Context budget management | Keep messages within API token limits | Optional dependency in QueryLoop |
| `from .models import FileReadInput, FileWriteInput, ...` | All 16 Pydantic input models | Type validation for tool arguments | Used by `ToolExecutor` and `ToolDefinition` schemas |
| `from .query_guard import QueryGuard, ...` | Concurrency guard (single query per session) | Prevent race conditions on same session | Passed to `QueryLoop` |
| `from .progress_types import ProgressType, ...` | Live UI progress events | Show real-time execution to users | Used by streaming API layer |
| `from .session_manager import SessionLifecycle, SessionRecord` | Session lifecycle management | Persist sessions across restarts | Called when initializing agent sessions |
| `from .permission import PermissionChecker, ...` | Tool permission system | Require user approval for risky tools | Passed to `QueryLoop` and `ToolExecutor` |
| `from .compaction import CompactPipeline, ...` | Conversation compression | Keep conversation within token budget | Used at start of every `QueryLoop` turn |
| `from .session_memory import SessionMemoryExtractor, ...` | Conversation fact extraction | Preserve context across compaction | Extracted every 5 turns in `QueryLoop` |
| `from .streaming_api import StreamingLLMClient, ...` | Real-time LLM streaming | Show LLM output as it generates | Used by `QueryLoop._stream_call()` |
| `from .system_prompt import SystemPromptManager, ...` | Block-structured system prompts | Prompt caching + dynamic session content | Built each turn in `QueryLoop` |

---

## `models.py` — Pydantic Input Schemas

| Class | Fields | Why | How Wired |
|-------|--------|-----|-----------|
| `FileReadInput` | `file_path: str` | Validate file read arguments | `ToolExecutor` validates tool args against this |
| `FileWriteInput` | `file_path: str`, `content: str` | Validate file write arguments | Same as above |
| `FileEditInput` | `file_path`, `target_file`, `range`, `insert_content` | Validate edit arguments with range | Same |
| `BashInput` | `command: str`, `timeout: int=30` | Validate command + enforce timeout | Same |
| `AgentInput` | `agent_type`, `prompt`, `description`, `run_in_background` | Validate subagent spawn args | Same |
| `GlobInput` | `pattern`, `path: Optional` | Validate glob search args | Same |
| `GrepInput` | `pattern`, `path`, `glob`, `output_mode` | Validate search args with output mode | Same |
| `TodoWriteInput` | `todos: list[dict]` | Validate todo list structure | Same |
| `SkillInput` | `skill`, `args: Optional` | Validate skill invocation args | Same |
| `TaskCreateInput` | `subject`, `description`, `activeForm`, `metadata` | Validate task creation args | Same |
| `TaskUpdateInput` | `taskId`, optional subject/desc/status/owner/metadata/addBlocks/addBlockedBy | Validate task update args | Same |
| `TaskListInput` | *(empty)* | No args needed for listing | Same |
| `TaskGetInput` | `taskId: str` | Validate task retrieval | Same |
| `TaskOutputInput` | `task_id`, `block: bool`, `timeout: int` | Validate output retrieval with blocking | Same |
| `TaskStopInput` | `task_id: Optional` | Validate task stopping | Same |
| `SendMessageInput` | `to`, `message`, `message_type` | Validate inter-agent messages | Same |

---

## `registry.py` — Tool Registry & Discovery

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `ToolDefinition` (dataclass) | 24-45 | Holds all info about a single tool: `name`, `description`, `input_schema`, `execute`, `is_concurrency_safe`, `prompt_fn`, `metadata` | Single object representing one available tool | Created by each built-in tool file (e.g., `FileRead = ToolDefinition(...)` in file_read.py) |
| `ToolDefinition.get_description()` | 36-40 | Returns description, using `prompt_fn` if available for dynamic descriptions | Tools can change their description based on context | Called by `build_tool_definitions()` when building API function definitions |
| `ToolDefinition.is_write_tool` (property) | 42-45 | Returns `not is_concurrency_safe` | Quick check if tool modifies files/commands | Used by `ConcurrencyManager` to classify tools |
| `ToolRegistry` | 48-97 | Central store: `self._tools = dict[str, ToolDefinition]` | Single source of truth for all available tools | Global singleton `registry` (line 100) |
| `ToolRegistry.register()` | 54-57 | Adds tool to internal dict | Register new tools | Called by builtins/__init__.py auto-registration loop |
| `ToolRegistry.get()` | 59-61 | Retrieve tool by name | Look up tool definition | Used by `ToolExecutor` and `QueryLoop._execute_tools()` |
| `ToolRegistry.get_all()` | 63-65 | Return all tool definitions | Get full tool list | Used by `Agent` tool to pass tools to subagents |
| `ToolRegistry.get_tool_names()` | 67-69 | Return list of tool name strings | List available tools | Used for debugging/inspection |
| `ToolRegistry.build_tool_definitions()` | 71-88 | Convert all tools to LLM API format: `[{type:"function", function:{name, description, parameters}}]` | The LLM needs to know what tools exist and their schemas | Called by `SystemPromptManager` when building system prompt |
| `ToolRegistry.register_builtins()` | 90-96 | Auto-discover ToolDefinition objects from builtins module | Don't manually register each tool | Called by builtins/__init__.py via loop |
| `registry` (singleton) | 100 | Module-level `ToolRegistry()` instance | Global access point | `from .registry import registry` everywhere |
| `register()` decorator | 103-106 | `@register` on a ToolDefinition to auto-register it | Quick one-line registration | Used implicitly — builtins/__init__.py loops and calls it |
| `build_tool_defs()` | 109-111 | Helper: calls `registry.build_tool_definitions()` | Convenience function | Used by outer application layer |

---

## `executor.py` — Tool Execution Pipeline

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `ToolExecutionResult` (dataclass) | 18-25 | Holds: `tool_call_id`, `tool_name`, `content`, `is_error`, `execution_time_ms`, `context_updates` | Structured result from every tool call | Returned to `QueryLoop` which feeds it back into conversation |
| `[X] _pre_tool_use_hooks` | 29 | Module-level list of pre-execution hook functions | Allow interception before tool runs | `register_pre_hook(fn)` appends to this list |
| `[X] _post_tool_use_hooks` | 30 | Module-level list of post-execution hook functions | Allow modification of results after tool runs | `register_post_hook(fn)` appends to this list |
| `[X] register_pre_hook(fn)` | 33-35 | Add function to pre-hook list | Register pre-execution interceptor | Called by outer layers for logging, validation, etc. |
| `[X] register_post_hook(fn)` | 38-40 | Add function to post-hook list | Register post-execution modifier | Same as above |
| `ToolExecutor.__init__()` | 46-47 | Initialize with optional `permission_checker` | Configure executor | Passed from `QueryLoop._execute_tools()` |
| `ToolExecutor.execute()` | 49-126 | **Main pipeline**: validate → permission → pre-hooks → execute → post-hooks → return result | Every tool call goes through this pipeline | Called by `QueryLoop._execute_tools()` for each tool_use from LLM |
| `ToolExecutor._get_pydantic_model()` | 159-168 | Map tool name to Pydantic model class | Validate tool arguments | Called at line 56 of `execute()` |
| `ToolExecutor._default_model_map()` | 133-157 | Returns dict mapping 16 tool names to their Pydantic models | Default validation schema mapping | Used if custom `model_map` not provided |
| `ToolExecutor.format_error()` | 170-178 | Format exception as `{error_type}: {message}` truncated to 10k chars | LLM-readable error messages | Called at line 123 when tool raises exception |
| `ToolExecutor.format_zod_error()` | 180-196 | Format Pydantic validation errors with field paths (e.g., `"The required parameter 'file_path' field required"`) | LLM can fix its own argument mistakes | Called at line 64 when validation fails |
| `execute_tool()` | 199-204 | Convenience: creates `ToolExecutor` and calls `execute()` | One-liner for external callers | Used by `ErrorRecovery.handle_tool_error()` |

---

## `query_loop.py` — Main Agentic Loop

### Constants

| Name | Value | Purpose |
|------|-------|---------|
| `DEFAULT_MAX_TURNS` | 30 | Prevents infinite loops |
| `DEFAULT_TIMEOUT` | 300 | 5-minute query timeout |
| `DEFAULT_MODEL_OPUS` | "opus46" | Default LLM model |
| `DEFAULT_TOKENS` | 4096 | Max output tokens per call |
| `DEFAULT_TEMP` | 0.1 | Low temperature for deterministic behavior |
| `DEFAULT_TOOL_CONCURRENCY` | 1 | Default max concurrent tools |
| `DEFAULT_MAX_RETRIES` | 10 | Max API retry attempts |
| `DEFAULT_RETRY_SLEEP_TIME` | 10 | Base sleep between retries |
| `DEFAULT_COMPACT_TOKEN_BUDGET` | 100_000 | Token budget before compaction triggers |
| `DEFAULT_SESSION_ID` | "default" | Default session identifier |

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `QueryLoop.__init__()` | 46-99 | Configures: max_turns, timeout, fallback_chain, abort_controller, message_manager, transcript_writer, token_tracker, query_guard, compact_token_budget, permission_checker, streaming_enabled. Also initializes `_compaction` (CompactPipeline), `_memory_extractor` (SessionMemoryExtractor), `_memory_cache` (SessionMemoryCache), `_memory_adapter` (CompactSummary), `_system_prompt_manager` (SystemPromptManager). Wires memory into compaction via `set_summarize_fn()`. | All dependencies injected here; compaction + memory + system prompt all created and wired | Created by outer application layer; passed to `QueryLoop.run()` |
| `QueryLoop.run()` | 101-245 | **Main entry point**. Per turn: guard check → release payloads → compaction → build system prompt → API call → extract tool_calls → permission check → execute tools → feed results back → session memory extraction (every 5 turns) → transcript write → loop. Returns final text. | The entire agentic loop — LLM calls tools, gets results, iterates until no more tool calls | Called by outer application layer with user messages |
| `QueryLoop._call_api()` | 247-265 | Routes to streaming or non-streaming path based on `self._streaming_enabled` | Unified API call interface | Called at line 160 of `run()` |
| `QueryLoop._stream_call()` | 267-291 | Uses `StreamingLLMClient.stream()` → yields text chunks → joins into final response | Real-time streaming with progress events | Called by `_call_api()` when streaming is enabled |
| `QueryLoop._call_with_fallback()` | 293-337 | Non-streaming: retries up to 10 times with exponential backoff. Falls back to different model from `fallback_chain` on first failure. Uses `backend.llm_api_handler.LLMHandler`. | Automatic recovery from API failures | Called by `_call_api()` when streaming is disabled |
| `QueryLoop._execute_tools()` | 341-382 | Builds tool definition map (from passed tools + registry). Creates `ToolExecutor`. Iterates through tool calls, resolves args (handles string JSON and Pydantic models), calls `executor.execute()`, collects results. | Execute all tool_use blocks from LLM response | Called at line 198 of `run()` |
| `QueryLoop._strip_pre_compact()` | 384-386 | Placeholder for stripping already-compacted messages | Future optimization | Called at line 135 of `run()` (currently no-op) |
| `QueryLoop._release_tool_payloads()` | 388-390 | Release raw tool result payloads to free memory | Placeholder for memory optimization | Called at line 137 of `run()` (currently no-op) |
| `QueryLoop._execute_single()` | 392-407 | Execute a single tool call with registry fallback | Legacy method preserved from original implementation | Not used in current code path |
| `QueryLoop._extract_tool_calls()` | 409-432 | Extract `tool_use` blocks from API response. Handles: list of dicts with `type == "tool_use"`, `response["tool_calls"]` array, text parse fallback. | Parse LLM response to find tool calls | Called at line 174 of `run()` |

---

## `query_guard.py` — Concurrency Control

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `QueryState` (enum) | 24 | `IDLE`, `DISPATCHING`, `RUNNING`, `REQUIRES_ACTION` | Define valid states for a session's query lifecycle | Used throughout guard for state transitions |
| `QueryGuardError` | 27-30 | Exception for guard violations | Propagate guard errors to caller | Caught by outer layers |
| `QueryGuard.__init__()` | 32-42 | Creates per-session state dict (`{session_id: (state, lock)}`) and per-session `asyncio.Lock` objects | One lock per session prevents race conditions | Initialized on first `QueryGuard()` creation |
| `QueryGuard.reserve()` | 60-66 | Transitions `IDLE → DISPATCHING`. Acquires per-session lock. Returns `True` on success, `False` if session is already in use. | Reserve session for user input (e.g., during permission dialog) | Called by outer app layer before permission prompts |
| `QueryGuard.try_start()` | 70-78 | Transitions `DISPATCHING → RUNNING` or `IDLE → RUNNING`. Returns `True` on success. | Begin query execution | Called at line 123 of `QueryLoop.run()` |
| `QueryGuard.set_requires_action()` | 83-88 | Transitions `RUNNING → REQUIRES_ACTION`. | Signal that tools are executing and next input is needed | Called between turns when waiting for user input |
| `QueryGuard.end()` | 89-110 | Returns to `IDLE` from any state (`RUNNING`, `REQUIRES_ACTION`, `DISPATCHING`). Releases lock. | Release session for next query | Called at line 243 of `QueryLoop.run()` |
| `get_query_guard()` | 116-120 | Returns singleton `QueryGuard` instance | Global access point | Called by outer app layer for guard operations |

---

## `progress_types.py` — Live UI Progress

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `ProgressType` (enum) | 31 | `BASH_PROGRESS`, `POWERSHELL_PROGRESS`, `SLEEP_PROGRESS`, `TOOL_START`, `TOOL_PROGRESS`, `TOOL_COMPLETE` | Define all transient progress event types | Used by `ProgressInjector` and UI layer |
| `ProgressMessage` (dataclass) | 40-47 | `type`, `content`, `is_complete`, `tool_call_id`, `timestamp` | Single object representing a progress event | Created by `ProgressInjector`, consumed by `ProgressBuffer` |
| `ProgressBuffer` (class) | 50-97 | Thread-safe async FIFO: `push()`, `pop_all()`, `clear()`, `get_by_type()`, `get_unseen()` | Hold transient progress events for UI consumption | `ProgressInjector` pushes, UI layer pops |
| `ProgressBuffer._lock` | 56 | `asyncio.Lock` for thread safety | Prevent concurrent buffer corruption | Used by all buffer methods |

---

## `session_manager.py` — Session Lifecycle

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_dir_cache` | 36 | `dict[str, tuple[Path, Path]]` — cached `(sessions_dir, projects_dir)` per project_id | Avoid repeated path resolution | Populated by `_get_dir_cache()` on first access per project |
| `_get_dir_cache()` | 39-44 | Returns `(sessions_dir, projects_dir)` for project_id, cached | Directory path caching | Called by all `SessionLifecycle` methods |
| `SessionRecord` (dataclass) | 47-85 | `session_id`, `pid`, `cwd`, `started_at`, `kind`, `entrypoint`, `transcript_path`, `status`, `parent_session_id`. Methods: `to_dict()`, `from_dict()`. | Represent a session with all metadata | Used by `SessionLifecycle` for create/resume/clear/discover |
| `SessionLifecycle.create()` | 91-135 | Create new session: generate UUID, write PID file, create transcript dir, touch empty transcript | Start a new agent session with persistence | Called when initializing a new conversation |
| `SessionLifecycle.resume()` | 137-175 | Find latest non-terminal session by scanning `.jsonl` files + PID files. Returns `SessionRecord`. | Resume an existing conversation | Called when user wants to continue a past session |
| `SessionLifecycle.clear()` | 177-227 | Find old session, create new one with `parent_session_id` set to old session_id, update PID file | Clear current session but keep history | Called when user requests /clear |
| `SessionLifecycle.discover_active()` | 229-273 | Read PID files, check `os.kill(pid, 0)` for alive processes, return alive sessions | Show users their active sessions | Called by outer app layer for session list UI |
| `SessionLifecycle.discover_history()` | 275-298 | Scan project transcript directory for `.jsonl` files, sorted by mtime | Show users their past sessions | Called by outer app layer for session history UI |

---

## `permission.py` — Tool Permission System

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `PermissionMode` (enum) | 27 | `FULL_AUTO`, `REQUIRE_PROMPT`, `SKIP` | Three permission modes | Passed to `PermissionChecker` constructor |
| `AUTO_ALLOW` | 37 | Set of auto-allowed tool names | Read-only/low-risk tools never need confirmation | Used as default for `_auto_allow` |
| `REQUIRE_PROMPT` | 43 | Set of require-prompt tool names | Bash, task creation, agent spawning need confirmation | Used as default for `_require_prompt` |
| `PermissionChecker.__init__()` | 50-55 | Initialize with mode + custom allow/deny sets | Configure permission behavior | Passed to `QueryLoop` and `ToolExecutor` |
| `PermissionChecker.can_use()` | 58-78 | Check if tool is allowed: `SKIP` mode → always False; `REQUIRE_PROMPT` mode → check set; `FULL_AUTO` → True; unknown tools → False | Gate tool execution | Called by `QueryLoop.run()` (line 184) and `ToolExecutor.execute()` (line 70) |
| `PermissionChecker.get_required_prompt_for()` | 91-94 | Return `"Allow running tool: {tool_name}?"` for require-prompt tools | Human-readable permission prompt | Used when permission is denied to inform the LLM |

---

## `compaction.py` — Conversation Compression Pipeline

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_SNIP_THRESHOLD` | 23 | 500 chars — threshold for snipping large tool results | Don't snip small outputs | Used by `SnipCompact.run()` |
| `_COMPACTABLE_TOOLS` | 25 | Set of tool names eligible for compaction | Only safe-to-lose tools get compacted | Checked by `SnipCompact` and `MicroCompact` |
| `CompactState` (dataclass) | 28-35 | `message_count`, `token_count`, `consecutive_fails` (circuit breaker), `last_microcompact_turn` | Track compaction state across turns | Passed through compaction pipeline methods |
| `SnipCompact.run()` | 44-63 | Scan tool_result messages. If content > 500 chars, replace with `[File: /path, N lines]` stub | Reduce token usage from large file reads | Called first in `CompactPipeline.run()` |
| `SnipCompact._extract_path()` | 65-76 | Try to find a file path in first 5 lines of content (absolute paths, or paths ending in `.py`, `.ts`, etc.) | Create meaningful stubs instead of generic truncation messages | Called by `SnipCompact.run()` |
| `MicroCompact.run()` | 86-117 | Every 5 turns, clear old tool results (keep last 2). Resets `last_microcompact_turn` counter. | Rolling cleanup of old tool outputs | Called second in `CompactPipeline.run()` |
| `AutoCompact.run()` | 128-187 | Estimate tokens (chars/4). If over budget: split 60/40, try session memory summary, circuit breaker after 3 fails. Add boundary message. | Emergency compression when conversation is too large | Called third in `CompactPipeline.run()` |
| `CompactPipeline.__init__()` | 193-196 | Create `CompactState`, set `token_budget` | Initialize pipeline | Created in `QueryLoop.__init__()` |
| `CompactPipeline.set_summarize_fn()` | 198-200 | Set the summary function for auto-compact | Wire session memory into compaction | Called in `QueryLoop.__init__()` with `CompactSummary.get_summary()` |
| `CompactPipeline.run()` | 202-217 | Execute: Snip → Micro → Auto in sequence. Returns `(compact_messages, summary_text)`. | Orchestrate all compaction strategies | Called at start of every turn in `QueryLoop.run()` |
| `CompactPipeline.reset_fails()` | 219-221 | Reset `consecutive_fails` counter | Reset circuit breaker on successful completion | Called at line 235 of `QueryLoop.run()` |

---

## `session_memory.py` — Conversation Context Extraction

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `MEMORY_BASE` | 21 | `.archtech/sessions` — directory for session memory files | Persistent storage location | Used by `SessionMemoryCache` |
| `SessionMemoryExtractor.FILE_PATH_PATTERN` | 32 | Regex: `[\"']?(/[^\\s'\"]+|\\.\\/[^\\s'\"]+)[\"']?` | Match absolute and relative file paths | Used by `extract()` |
| `SessionMemoryExtractor.FUNCTION_PATTERN` | 33 | Regex: `def\\s+(\\w+)` | Match function definitions | Not actively used in current `extract()` |
| `SessionMemoryExtractor.CLASS_PATTERN` | 34 | Regex: `class\\s+(\\w+)` | Match class definitions | Not actively used in current `extract()` |
| `SessionMemoryExtractor.DECISION_PATTERN` | 35 | Regex: `(?:decided\|choose\|selected\|use\|should use\|go with)` | Match decision-making sentences | Used by `extract()` to find key decisions |
| `SessionMemoryExtractor.extract()` | 37-77 | Scan last 10 messages. Extract unique file paths (from user/assistant messages), decisions (from assistant sentences with decision keywords), code changes (diff lines + function/class defs from tool results). Return `{"files": [], "decisions": [], "code_changes": []}`. | Extract reusable facts from conversation for reuse during compaction | Called every 5 turns in `QueryLoop.run()` (line 216) |
| `SessionMemoryExtractor._extract_changes()` | 79-89 | Extract diff lines (`+`, `-`, `@@`) and function/class definitions from tool result content | Identify what code changed during the session | Called by `extract()` |
| `SessionMemoryCache.__init__()` | 98-100 | Set base directory, create it if needed | Prepare for file-based caching | Created in `QueryLoop.__init__()` |
| `SessionMemoryCache.save()` | 102-106 | Write memory to `.archtech/sessions/<session_id>.json` | Persist extracted facts | Called by `update()` |
| `SessionMemoryCache.load()` | 108-117 | Read and parse JSON memory file | Load cached facts | Called by `CompactSummary.get_summary()` and `QueryLoop.run()` |
| `SessionMemoryCache.clear()` | 119-122 | Delete memory file | Remove cached memory | Called when session is cleared |
| `SessionMemoryCache.update()` | 124-133 | Merge new delta into existing memory (deduplicates), save, return merged result | Incremental memory building | Called at line 219 of `QueryLoop.run()` |
| `CompactSummary.__init__()` | 143-144 | Hold reference to `SessionMemoryCache` | Access cached memory | Created in `QueryLoop.__init__()` |
| `CompactSummary.get_summary()` | 146-182 | First try: load cached memory, format as structured text (files, decisions, code changes). Second: fall back to `legacy_fn`. Return `None` if neither works. | Produce compact summary for auto-compact without API call | Wired to `CompactPipeline.set_summarize_fn()` |

---

## `streaming_api.py` — Real-Time LLM Streaming

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `HAS_STREAMING_HANDLER` | 29 | Boolean — True if `StreamingLLMHandler` import succeeds | Detect streaming availability | Checked by `StreamingLLMClient.__init__()` |
| `StreamingLLMClient.__init__()` | 42-49 | Try to create `StreamingLLMHandler(model)`. If import fails, handler stays None. | Initialize streaming handler | Called by `QueryLoop._stream_call()` |
| `StreamingLLMClient.stream()` | 51-96 | Async generator. Prepends system message to messages. Delegates to `_handler.stream()`. Yields: `{"type":"text","content":"chunk"}`, `{"type":"done"}`, `{"type":"error","message":"..."}`. | Stream LLM output as typed events | Called by `QueryLoop._stream_call()` |
| `ProgressInjector.__init__()` | 106-108 | Initialize `_tool_buffer` (tool_call_id → accumulated content) and `_current_tool` | Track progress per tool | Used by streaming layer |
| `ProgressInjector.token_to_progress()` | 110-117 | Convert token chunk to progress message dict | Bridge streaming tokens to progress system | Called by streaming layer during `stream()` |
| `ProgressInjector.complete_progress()` | 119-126 | Create completion progress message | Signal tool completion to UI | Called when tool_use block finishes |

---

## `system_prompt.py` — Block-Structured System Prompts

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `DYNAMIC_BOUNDARY` | 23 | `"__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"` sentinel | Marks where static blocks end and dynamic blocks begin | Appended by `StaticBlockBuilder.build()` |
| `SystemPromptBlock` (dataclass) | 26-32 | `content`, `cache_scope` (None/"global"/"org"), `is_cached` | Single block of system prompt with caching info | All system prompt content is split into these blocks |
| `StaticBlockBuilder.build()` | 41-196 | Creates blocks with `cache_scope="global"`: attribution header, CLI prefix, identity, core behavior rules, system sections, doing tasks, actions/agent types, tone/style, output efficiency, DYNAMIC_BOUNDARY | Build the unchanging part of the system prompt (cacheable across all sessions) | Called by `SystemPromptManager.build()` |
| `DynamicBlockBuilder.build()` | 206-256 | Creates blocks with `cache_scope=None`: session memory (files, decisions), git status, MCP instructions, env info, language preference | Build session-specific dynamic content | Called by `SystemPromptManager.build()` |
| `UserContextBuilder.build()` | 266-275 | Creates synthetic user message: "Here are your project instructions:\n\n{CLAUDE.md}\n\n{current_date}" | Inject CLAUDE.md as if the user typed it | Called by `SystemPromptManager.get_user_context()` |
| `SystemContextBuilder.build()` | 284-290 | Creates system block with git status | Append git status to system prompt | Called by `SystemPromptManager.get_system_context()` |
| `SystemPromptManager.__init__()` | 299-304 | Create sub-builders + cache dict | Initialize prompt assembly | Created in `QueryLoop.__init__()` |
| `SystemPromptManager.build()` | 306-336 | Priority: override > custom > default. If override: single block. If custom: single block. Else: static blocks + dynamic blocks. | Assemble full system prompt | Called at line 146 of `QueryLoop.run()` |
| `SystemPromptManager.get_user_context()` | 338-340 | Return synthetic user message with CLAUDE.md + date | Get user context for API call | Called at line 152 of `QueryLoop.run()` |
| `SystemPromptManager.get_system_context()` | 342-344 | Return system context block with git status | Get system context for API call | Called when building messages |
| `SystemPromptManager.clear_cache()` | 346-352 | Clear cached blocks (per-session or all) | Reset prompt cache on /clear or /compact | Called by outer app layer |

---

## `error_recovery.py` — Multi-Tiered Error Handling

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `MAX_CONTEXT_COLLAPSE_MSGS` | 24 | 10 — max messages to collapse | Prevent removing too much context | Used by `collapse_context()` |
| `OUTPUT_LIMIT_RECOVERY_MESSAGE` | 25-29 | Text injected after truncated LLM response: "Output token limit hit. Resume directly..." | Tell LLM to continue without apology/recap | Used by `recover_from_output_limit()` |
| `ErrorRecovery.__init__()` | 35-46 | Set `fallback_chain` and `max_context_collapse` | Configure recovery behavior | Created by `QueryLoop` (currently not instantiated — logic inline in `_call_with_fallback`) |
| `ErrorRecovery.handle_api_error()` | 48-75 | Classify error → retry (by caller) → try fallback model → return None if all exhausted | Main entry point for API error recovery | Used by `_call_with_fallback()` in QueryLoop |
| `ErrorRecovery.recover_from_output_limit()` | 77-109 | Find last assistant message, insert recovery message after it. If no assistant message found, append to end. | Recover from truncated LLM output | Called when LLM hits output token limit |
| `ErrorRecovery.collapse_context()` | 111-149 | Remove oldest user messages (keep system prompt), return removed text as summary. Respects `max_context_collapse` limit. | Reduce context size by removing old messages | Called when context exceeds token budget |
| `ErrorRecovery.handle_tool_error()` | 151-177 | Create `ToolExecutor`, format error, return structured tool_result dict with `is_error=True` | Format tool errors for LLM consumption | Called when tool execution fails |
| `ErrorRecovery._classify_error()` | 181-196 | Categorize: RateLimit/429 → "rate_limit", Timeout/408 → "timeout", API/5xx → "server_error", overloaded → "overloaded", else → "unknown" | Select correct recovery strategy | Called by `handle_api_error()` |
| `ErrorRecovery._try_fallback_model()` | 198-262 | Determine fallback order based on error type (overloaded → cheaper models, rate_limit → same model, unknown → fallback chain). Try each with `_get_client()` and `_resolve_model_name()`. | Switch to a different model when primary fails | Called by `handle_api_error()` |

---

## `concurrency.py` — Parallel Tool Execution

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `Batch` (dataclass) | 21-26 | `is_concurrent: bool`, `blocks: list[dict]` (tool calls to execute together) | Represent a batch of parallel or serial tool calls | Return value of `partition()` |
| `MAX_CONCURRENCY` | 29 | 10 — max parallel tool calls | Prevent resource exhaustion | Used as default in `ConcurrencyManager.__init__()` |
| `ConcurrencyManager.__init__()` | 35-36 | Set `max_concurrency` | Configure parallelism limit | Created by outer layers |
| `ConcurrencyManager.partition()` | 38-68 | Iterate tool calls in order. Consecutive `is_concurrency_safe` tools go into one batch. Any `is_concurrency_safe=False` tool gets its own serial batch. | Partition tool calls into parallel + serial groups | Called by `execute_batches()` |
| `ConcurrencyManager.execute_batches()` | 70-112 | For each batch: if concurrent with >1 block → `asyncio.gather()`. If serial → `_execute_single()` for each. Return results in original order. | Actually execute the partitioned batches | Designed for use in `QueryLoop._execute_tools()` |
| `ConcurrencyManager._execute_single()` | 114-137 | Look up tool, call executor_fn, wrap result in standard format. Handle tool-not-found case. | Execute individual tool call within batch | Called by `execute_batches()` |
| `ConcurrencyManager._exception_result()` | 139-147 | Create error result dict for failed parallel tool calls | Standardize error format from parallel failures | Called by `execute_batches()` when `asyncio.gather()` returns exception |

---

## `transcript.py` — JSONL Transcript Storage

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `TranscriptEntry` (dataclass) | 31-50 | `entry_type`, `content`, `tool_call_id`, `tool_name`, `timestamp`. Method: `to_dict()` | Typed transcript entry for JSONL serialization | Used by transcript writer for typed entries |
| `get_transcript_dir()` | 53-55 | Get transcript directory via system config | Resolve storage path | Called by `get_transcript_path()` |
| `recover()` | 58-99 | Read file line by line, filter bad JSON, rewrite with only valid lines. Skip files >50MB. Return True if corruption was found/fixed. | Repair corrupted JSONL files | Called by `TranscriptWriter.recover()` |
| `get_transcript_path()` | 102-104 | Build `{agent_id}.jsonl` path from project_id and agent_id | Get transcript file path | Used by outer layers |
| `TranscriptWriter.__init__()` | 122-129 | Create transcript dir, set `transcript.jsonl` path, `asyncio.Lock`, `_offset`, `_batch_buffer`, `_batch_flush_task` | Prepare writer | Created by outer layers, passed to QueryLoop |
| `TranscriptWriter.write_turn()` | 131-160 | Sync append: `{"timestamp", "role", "content", "tool_calls", "tool_results", "tokens_in", "tokens_out"}` + newline | Write a complete turn to JSONL | Called by `QueryLoop.run()` after each turn |
| `TranscriptWriter.awrite_turn()` | 162-173 | Async version: acquires lock then calls `write_turn()` | Safe async write | Used when in async context |
| `TranscriptWriter.write_entry()` | 175-189 | Write typed entry: `{"type", "content", "timestamp", "tool_call_id"}` | Write individual entry types | Used for user/assistant/tool messages |
| `TranscriptWriter.write_turn_with_entries()` | 191-198 | Group multiple messages into one atomic write | Batch related messages together | Used when writing assistant+tool_use+tool_result together |
| `TranscriptWriter.recover()` | 200-243 | Same as standalone `recover()` but on writer's own path | Repair corrupted transcript | Called by `read_all()` and `read_offset()` |
| `TranscriptWriter.read_all()` | 245-260 | Auto-recover, read all lines, parse JSON, skip corrupted | Load full transcript | Used by outer layers for session resume |
| `TranscriptWriter.read_offset()` | 262-276 | Seek to byte offset, read new lines, parse JSON | Incremental reads without reloading | Used for streaming new lines |
| `TranscriptWriter.close()` | 278-280 | Log close event with offset | Clean shutdown | Called when writer is destroyed |
| `TranscriptWriter.get_size()` | 282-286 | Return current file size in bytes | Monitor transcript growth | Used for debugging/monitoring |

---

## `message_manager.py` — Context Budget Management

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `MessageManager` (dataclass) | 13-14 | `max_tokens: int=128000`, `max_messages: int=100`, `system_prompt: str`, `messages: list[dict]`, `current_size: int` | Manage conversation message buffer | Optional in `QueryLoop.__init__()` |
| `normalize()` | 26-31 | Ensure each message has `role` and `content` fields | Handle malformed messages | Used when constructing message lists |
| `add_message()` | 33-36 | Append message and increment `current_size` | Add to conversation buffer | Used by MessageManager internally |
| `add_system_prompt()` | 38-40 | Set/replace system prompt | Update system prompt | Called when system prompt changes |
| `get_system_prompt()` | 42-44 | Return `{"role": "system", "content": prompt}` | Get API-ready system prompt dict | Used by `format_messages()` |
| `format_messages()` | 46-48 | Return `[system_prompt_dict] + messages` | Get full message list for API call | Used when building API request |
| `clear_context()` | 50-53 | Clear all messages and reset size counter | Reset conversation | Called when session is cleared |
| `get_message_count()` | 55-57 | Return `len(messages)` | Get message count | Used for monitoring |
| `collapse_context()` | 61-72 | Keep system message + last 4 messages (2 exchanges), discard rest | Emergency context reduction | Called when context exceeds budget |
| `trim()` | 74-90 | Shallow copy, if total content > budget, truncate largest content to `max_tokens//2` with "... [truncated]" | Soft context reduction | Called when context exceeds budget |
| `available_tokens` (property) | 92-95 | `max(0, max_tokens - current_size)` | Monitor remaining capacity | Used for budget monitoring |

---

## `token_tracker.py` — Token Usage Tracking

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_TurnRecord` (dataclass) | 20-25 | `turn_number`, `tokens_in`, `tokens_out` | Single turn's token data | Internal storage |
| `TokenUsageTracker.__init__()` | 30-34 | `threading.Lock`, empty turns list, total_in=0, total_out=0 | Initialize thread-safe tracker | Created by outer layers |
| `record_turn()` | 36-41 | Append `_TurnRecord`, accumulate totals | Record one LLM turn's usage | Called by `QueryLoop._call_with_fallback()` |
| `get_total()` | 43-54 | Return `{"input": N, "output": N, "total": N}` | Get aggregate token counts | Used by outer layers for cost display |
| `get_per_turn()` | 56-62 | Return `[{turn: N, in: N, out: N}, ...]` | Get per-turn breakdown | Used by outer layers |
| `get_current_turn_input()` | 64-69 | Return `tokens_in` from last turn, or 0 | Get last turn's input tokens | Used for monitoring |
| `get_current_turn_output()` | 71-76 | Return `tokens_out` from last turn, or 0 | Get last turn's output tokens | Same |
| `snapshot()` | 78-90 | Full snapshot: `total_input`, `total_output`, `total_tokens`, `turn_count`, `per_turn` | Complete usage report | Used by outer layers for dashboard |

---

## `chat_sessions.py` — Chat Session Persistence

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `ChatSession` (dataclass) | 97 | `session_id`, `project_id`, `created_at`, `messages`, `status` | Represent a chat session with all messages | Stored in `ChatSessionManager` |
| `ChatSessionManager.__init__()` | 108-113 | Set base_dir, create directory, init `_cache: dict[session_id, ChatSession]` | Prepare session store | Called by `get_chat_session_manager()` |
| `ChatSessionManager.get_or_create()` | 126-143 | Return existing session or create new one with UUID, persist to disk | Get or start a session | Called by outer app layer |
| `ChatSessionManager.add_message()` | 148-161 | Append message to session, persist to disk | Add to conversation | Called by outer app layer |
| `ChatSessionManager.get_messages()` | 166-173 | Return all messages for session | Read conversation history | Called by outer app layer |
| `ChatSessionManager.set_messages()` | 179-187 | Replace all messages | Reset conversation | Called by outer app layer |
| `ChatSessionManager.clear_session()` | 193-201 | Remove from memory and disk | Delete session | Called on /clear |
| `ChatSessionManager.list_sessions()` | 209-221 | List all active sessions with metadata | Show session list UI | Called by outer app layer |
| `get_chat_session_manager()` | 244-248 | Return singleton `ChatSessionManager` | Global access | Called by outer app layer |

---

## `chat_events.py` — SSE Event Serialization

### Classes

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `ChatEventType` (enum) | 15 | `SESSION_CREATED`, `TURN_START`, `TEXT_DELTA`, `TOOL_USE_START`, `TOOL_USE_COMPLETE`, `TOOL_ERROR`, `TURN_COMPLETE`, `DONE`, `ERROR` | All possible chat event types | Used throughout streaming layer |
| `serialize_event()` | 27-33 | Format as SSE: `data: {json}\n\n` | Convert event to SSE format | Called by streaming layer |
| `yield_event()` | 39-52 | Async wrapper that yields serialized event | Use in async generators | Called by SSE endpoints |

---

## `session.py` — Generation Run Sessions

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| *(session storage)* | *(varies)* | Tracks stage progress, tool call logs, token usage at `output/sessions/{project_id}/{session_id}.json`. Atomic writes, progress summary endpoints. | Separate from chat sessions — for generation/run tracking | Used by generation layer |

---

## `agent_spawner.py` — Subagent Process Creation

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `AgentSpawner.spawn()` | *(varies)* | Create subprocess with agent_type, prompt, description, tools, model, max_turns. Supports foreground (blocking) and background (async). | Spawn parallel subagents | Called by `Agent` tool |
| `AgentResult` | *(varies)* | `content`, `total_tool_uses`, `total_duration_ms`, `status` | Result from spawned agent | Returned by `spawn()` |

---

## `context_isolation.py` — Per-Agent State Isolation

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `AgentContext` (dataclass) | 29 | `agent_id`, `task_store`, `message_manager`, `abort_controller`, `transcript_writer`, `token_tracker` | Isolated state per agent | Created by `AgentSpawner` |
| `AgentContextManager` (context manager) | 47-70 | Sets contextvars on enter, clears on exit via `contextvars.ContextVar` | Async-context isolation | `async with AgentContextManager(context):` |
| `get_context()` | 75-78 | Return current `AgentContext` or `None` | Read isolated state | Called by `get_store()` in tasks.py |
| `get_agent_id()` | 85-87 | Return current agent ID or `None` | Read agent identity | Used by SendMessage tool |
| `get_abort_signal()` | 91-93 | Return current abort signal or `None` | Read abort state | Used by agent execution |
| `clear_all_contexts()` | 97-99 | Emergency reset of all contextvars | Safety cleanup | Called on agent failure |

---

## `abort_controller.py` — Query Cancellation

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `AbortController.abort()` | *(varies)* | Set cancellation flag | Signal agent to stop | Called by outer app layer |
| `AbortController.is_aborted()` | *(varies)* | Check if abort was requested | Check cancellation status | Checked by `QueryLoop` between turns |

---

## `agent_mailbox.py` — Inter-Agent Messaging

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `get_mailbox()` | *(varies)* | Return mailbox manager for agent_id | Get recipient's mailbox | Called by SendMessage tool |
| `mailbox.send()` | *(varies)* | Queue message to recipient's mailbox | Deliver message | Called by SendMessage tool |

---

## `agent_cleanup.py` — Agent Process Cleanup

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| Cleanup functions | *(varies)* | Terminate spawned processes, clean up files and state | Prevent resource leaks | Called on agent completion/failure/session end |

---

## `task_state.py` — Task State Machine

| Class/Function | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `TaskStatus` (enum) | *(varies)* | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `KILLED` | Define valid task states | Used by all task tools |
| `_VALID_TRANSITIONS` | *(varies)* | Dict mapping `from_status → [allowed to_statuses]` | Define valid state transitions | Used by `can_transition()` |
| `can_transition()` | *(varies)* | Check if `from_status → to_status` is valid | Enforce state machine | Called by TaskUpdate tool |
| `TaskState` (class) | *(varies)* | Wraps task with `task_id`, `status`, `description`, `created_at`, `ttl_seconds`, `retain_flag`. Methods: `transition()` | Per-task lifecycle state | Created by TaskStore |
| `TaskStore.__init__()` | *(varies)* | `self._store: dict[task_id, TaskState]` | Task storage | Shared by all task tools |
| `TaskStore.create_task()` | *(varies)* | Create new `TaskState` with PENDING status | Initialize new task | Called by TaskCreate tool |
| `TaskStore.get_task()` | *(varies)* | Return `TaskState` for task_id | Get task lifecycle state | Called by TaskUpdate, TaskStop |
| `TaskStore.transition()` | *(varies)* | Validate transition via `can_transition()`, update status | Change task state | Called by TaskUpdate, TaskStop |
| `TaskStore.__getitem__` / `__setitem__` / `get` / `values` | *(varies)* | Dict-like interface for backward compatibility | Support dict-based task tools | Used by all task-builtins |

---

## `builtins/__init__.py` — Auto-Registration

| Line | What | Why | How Wired |
|------|------|-----|-----------|
| 50-52 | Loop through all 17 tool objects, call `registry.register(_tool)` | Auto-register all builtins without manual registration | Runs at import time |

---

## `builtins/file_read.py` — FileRead Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 19-39 | Read file, truncate at 100k chars, handle permission errors and binary files | Core file read logic | Set as `execute` in `FileRead` definition |
| `FileRead` (ToolDefinition) | 42-69 | `name="FileRead"`, description, `input_schema=FileReadInput.model_json_schema()`, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered via builtins/__init__.py |

---

## `builtins/file_write.py` — FileWrite Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_validate_path()` | 21-32 | Check path is within allowed directory (prevents path traversal) | Security: prevent writing outside project | Called before every write |
| `_execute()` | 35-58 | Validate path, create parent dirs, write to temp file, `os.replace()` (atomic), cleanup temp on failure | Atomic file writes prevent corruption | Set as `execute` in `FileWrite` definition |
| `FileWrite` (ToolDefinition) | 60-76 | `name="FileWrite"`, description, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/file_edit.py` — FileEdit Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 23-61 | Read file, replace lines[start-1:end], write back. Requires `end_line` to prevent destructive defaults. | Surgical file editing | Set as `execute` in `FileEdit` definition |
| `FileEdit` (ToolDefinition) | 63-84 | `name="FileEdit"`, description, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/bash.py` — Bash Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` (async) | 19-49 | `asyncio.create_subprocess_shell()`, capture stdout/stderr, timeout (default 30s), kill on timeout, return exit code + output (truncated at 5000 chars) | Execute arbitrary shell commands | Set as `execute` in `Bash` definition |
| `Bash` (ToolDefinition) | 52-94 | `name="Bash"`, description, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/agent.py` — Agent Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` (async) | 23-66 | Get all tools from registry, create `AgentSpawner`, spawn with `run_in_background` flag, register background task in running tasks store, return content + usage stats | Spawn subagent with full tool access | Set as `execute` in `Agent` definition |
| `Agent` (ToolDefinition) | 69-118 | `name="Agent"`, description with agent types, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/glob.py` — Glob Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 17-33 | `Path.rglob(pattern)`, sort by mtime, return up to 100 results, truncate note if more | File pattern matching | Set as `execute` in `Glob` definition |
| `Glob` (ToolDefinition) | 36-49 | `name="Glob"`, schema, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/search.py` — Search Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 18-72 | Compile regex once, search all files (or glob-filtered), three output modes: `files_with_matches`, `content` (show lines), `count` (show counts) | Regex content search | Set as `execute` in `Search` definition |
| `Search` (ToolDefinition) | 75-96 | `name="Search"`, schema, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/todo_write.py` — TodoWrite Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_todo_state` | 16 | `dict[str, list[dict]]` — session-scoped todo state | Persist todo lists per session | Module-level state |
| `_todo_lock` | 17 | `asyncio.Lock` | Thread-safe state updates | Used by `_update_state()` |
| `_execute()` | 20-57 | Validate todos (content, status, activeForm), enforce exactly one in_progress, update `_todo_state` under lock, build response with status icons | Manage structured task lists | Set as `execute` in `TodoWrite` definition |
| `TodoWrite` (ToolDefinition) | 60-154 | `name="TodoWrite"`, extensive description with usage examples, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/skill.py` — Skill Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_invoked_skills` | 17 | `list[str]` — session-scoped tracking of invoked skills | Prevent duplicate skill invocations | Module-level state |
| `_execute()` | 20-45 | Sanitize skill name (no path traversal), search `.claude/skills/<skill>/SKILL.md` and `src/skills/bundled/<skill>/SKILL.md`, read and return content | Load skill directives | Set as `execute` in `Skill` definition |
| `Skill` (ToolDefinition) | 48-75 | `name="Skill"`, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/send_message.py` — SendMessage Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 16-32 | Get `from_agent` via `get_agent_id()`, if `to="*"` log broadcast attempt, else get recipient mailbox via `get_mailbox(to)`, call `mailbox.send()` | Send message to another agent | Set as `execute` in `SendMessage` definition |
| `SendMessage` (ToolDefinition) | 35-56 | `name="SendMessage"`, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/task_create.py` — TaskCreate Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 19-43 | Get `TaskStore`, generate next ID, create task via `store.create_task()`, build task dict, store in `store[task_id]` | Create new task with lifecycle management | Set as `execute` in `TaskCreate` definition |
| `TaskCreate` (ToolDefinition) | 46-103 | `name="TaskCreate"`, description with usage rules, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/task_update.py` — TaskUpdate Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_STATUS_MAP` | 19-24 | Map string statuses to `TaskStatus` enum values | Convert user input to enum | Used by `_execute()` |
| `_execute()` | 27-87 | Get task from store, if not found return error. Enforce valid status transitions via `can_transition()`. Update subject/description/activeForm/status/owner/metadata/blocks/blockedBy. Return updated fields list. | Update task with state machine enforcement | Set as `execute` in `TaskUpdate` definition |
| `TaskUpdate` (ToolDefinition) | 90-134 | `name="TaskUpdate"`, description with status workflow, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/task_list.py` — TaskList Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 16-50 | Get store, handle both dict and TaskState objects, sort by ID, format as `Task {id}: [{status}] {subject} (owner: {owner}, blockedBy: {blockedBy})` | List all tasks with summary info | Set as `execute` in `TaskList` definition |
| `TaskList` (ToolDefinition) | 53-75 | `name="TaskList"`, description, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/task_get.py` — TaskGet Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 16-59 | Get task from store, handle both dict and TaskState objects, return full details: id, subject, description, status, blocks, blockedBy, owner, activeForm | Get single task details | Set as `execute` in `TaskGet` definition |
| `TaskGet` (ToolDefinition) | 62-84 | `name="TaskGet"`, description, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/task_output.py` — TaskOutput Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` (async) | 17-80 | Check store for completed tasks. Check running_tasks for async tasks. If blocking, wait with timeout. Return status + content or timeout message. | Get output from running/completed task | Set as `execute` in `TaskOutput` definition |
| `TaskOutput` (ToolDefinition) | 83-102 | `name="TaskOutput"`, description, schema, `execute=_execute`, `is_concurrency_safe=True` | Register the tool | Auto-registered |

---

## `builtins/task_stop.py` — TaskStop Tool

| Function/Class | Lines | Purpose | Why | How Wired |
|---------------|-------|---------|-----|-----------|
| `_execute()` | 20-63 | Transition task state to KILLED via `store.get_task().transition()`. If running in async tasks, call `task.cancel()`, handle CancelledError/InvalidStateError, remove from running_tasks dict. | Stop running task | Set as `execute` in `TaskStop` definition |
| `TaskStop` (ToolDefinition) | 66-77 | `name="TaskStop"`, description, schema, `execute=_execute`, `is_concurrency_safe=False` | Register the tool | Auto-registered |

---

## `builtins/tasks.py` — Shared Task Storage

| Function | Lines | Purpose | Why | How Wired |
|----------|-------|---------|-----|-----------|
| `_task_store` | 13 | `TaskStore()` instance — module-level shared task store | Central task storage | Used by all task-builtins |
| `_next_id` | 14 | Auto-increment counter for task IDs | Generate unique task IDs | Used by `get_next_id()` |
| `_running_tasks` | 15 | `dict[str, asyncio.Task]` — tracks running async subagent tasks | Discover running tasks via TaskOutput/TaskStop | Updated by `register_task()` |
| `_task_counter` | 16 | Counter for running task keys | Generate unique keys for running tasks | Used by `register_task()` |
| `get_store()` | 19-25 | Resolve from `AgentContext` (contextvars) if isolated, else return module-level `_task_store` | Per-agent task store isolation | Called by all task-builtins |
| `get_next_id()` | 28-32 | Generate `task_XXX` format IDs | Auto-incrementing task IDs | Called by TaskCreate |
| `get_running_tasks()` | 35-36 | Return `_running_tasks` dict | Expose running tasks | Called by TaskOutput, TaskStop |
| `register_task()` | 39-44 | Generate `running_XXX` key, add task to `_running_tasks` | Register async task for discovery | Called by Agent tool for background tasks |
| `remove_task()` | 47-48 | Remove task by running key | Clean up completed tasks | Called by TaskOutput on task completion |
| `get_terminal_task_count()` | 51-59 | Count tasks in COMPLETED/FAILED/KILLED state | Monitor terminal task count | Used for debugging/monitoring |

---

## Data Flow — How It All Connects

```
Outer App calls: QueryLoop.run(user_messages, tools, system_prompt)
    │
    ├── QueryGuard.try_start(session_id) ──→ one query per session
    │
    ├── for turn in range(30):
    │   │
    │   ├── CompactionPipeline.run(messages)
    │   │   ├── SnipCompact → replace large tool results with stubs
    │   │   ├── MicroCompact → clear old tool results every 5 turns
    │   │   └── AutoCompact → emergency summary when over budget
    │   │
    │   ├── SystemPromptManager.build(tools, session_memory)
    │   │   ├── StaticBlockBuilder → identity, rules, tone (cache_scope="global")
    │   │   └── DynamicBlockBuilder → session memory, git status (cache_scope=None)
    │   │
    │   ├── LLM API Call
    │   │   ├── StreamingLLMClient.stream() → if streaming enabled
    │   │   └── LLMHandler.chat() + fallback chain → if not streaming
    │   │
    │   ├── Extract tool_use blocks from response
    │   │
    │   ├── if no tool_calls → BREAK
    │   │
    │   ├── PermissionChecker.can_use(tool_name) → auto-approve or deny
    │   │
    │   ├── ToolExecutor.execute(tool_def, tool_id, args)
    │   │   ├── Validate (Pydantic from models.py)
    │   │   ├── Permission check
    │   │   ├── Pre-hooks
    │   │   ├── Execute (calls the tool's execute function)
    │   │   └── Post-hooks
    │   │
    │   ├── Feed tool results back into messages
    │   │
    │   ├── if turn % 5 == 0: SessionMemoryExtractor.extract()
    │   │   └── SessionMemoryCache.update() → persist to .archtech/sessions/
    │   │
    │   └── TranscriptWriter.write_turn(role, content, tool_calls, tool_results)
    │       └── append to JSONL file
    │
    └── QueryGuard.end(session_id) ──→ release session lock
```
