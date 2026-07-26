# Analysis: Conceptual Overview vs Current Implementation

This document maps every feature described in `CONCEPTUAL_OVERVIEW.md` against what actually exists in `backend/tools/`.

---

## 1. Session (Section 1 of Conceptual Overview)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| Unique UUID container | Yes — each session owns everything | Session ID generated via hash of project_id + sections + time | ✅ Implemented (hash-based) |
| JSONL transcript file | Yes — all messages/tool calls/results | `transcript.py` — JSONL writer with async lock | ✅ Implemented |
| Context window (message chain) | Yes — sent to API each turn | `message_manager.py` — tracks messages, token budget | ✅ Implemented (basic) |
| Set of tools | Defined in `Tool.ts`, registered in `tools.ts` | `registry.py` — `ToolDefinition` + auto-registration via `builtins/__init__.py` | ✅ Implemented |
| Zero or one active agent | Yes | `agent_spawner.py` — can spawn multiple background agents | ⚠️ Partial (multiple supported) |
| State machine (idle → running → idle → requires_action) | Yes — `sessionState.ts` | `session.py` — status: idle/running/complete/error/cancelled | ✅ Implemented |
| QueryGuard (one query at a time) | Yes | Not implemented — no concurrency lock on `query_loop.run()` | ❌ Missing |

---

## 2. Query Loop — Per-turn Preparation (Section 2, steps 1-8)

| Step | Conceptual Description | Current | Status |
|------|----------------------|---------|--------|
| 1. Strip pre-compact messages | Remove messages already compacted | Not implemented | ❌ Missing |
| 2. Release raw tool result payloads | Free memory after processing | Not implemented | ❌ Missing |
| 3. Apply tool result budget | Cap oversized results before sending | Not implemented | ❌ Missing |
| 4. Snip compact | Replace large file contents with stubs when msg count > 30 | `file_read.py` truncates at 100K chars but not as "snip" stubs | ❌ Missing |
| 5. Microcompact | Clear old tool results with placeholder (time-based, ~10min) | Not implemented | ❌ Missing |
| 6. Context collapse | Commit pre-staged collapses of old spans | `message_manager.collapse_context()` — keeps system + last 2 exchanges | ✅ Implemented (aggressive version) |
| 7. Auto-compact | Summarize old conversation (session memory first, fallback to API) | Not implemented | ❌ Missing |
| 8. Build final messages array | system + boundary + summary + recent preserved | `message_manager.format_messages()` — system + messages only | ⚠️ Partial (no boundary/summary) |

---

## 3. Query Loop — Execution (Section 2, steps 9-14)

| Step | Conceptual Description | Current | Status |
|------|----------------------|---------|--------|
| 9. Call API → stream response | Streaming API call | `query_loop.py` — non-streaming with retry/fallback | ⚠️ Partial (non-streaming) |
| 10. Extract tool_use blocks | Parse response for tool calls | `query_loop.py` — extracts `tool_calls` from response | ✅ Implemented |
| 11. Execute tools (parallel/serial) | Safe tools parallel, unsafe serial | `concurrency.py` — `ConcurrencyManager.partition()` + `executor.py` | ✅ Implemented |
| 12. Collect tool_results | Gather all tool results | `query_loop.py` — collects into list | ✅ Implemented |
| 13. Loop if more tool_use | While loop, continues until text-only | `query_loop.run()` — `while turn < max_turns` | ✅ Implemented |
| 14. Turn complete | No more tool calls → done | Returns final text | ✅ Implemented |

---

## 4. Per-turn Side Effects (Section 2, step 15+)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| recordTranscript() → JSONL | Write turn to transcript | `transcript.py` — `write_turn()` / `awrite_turn()` | ✅ Implemented |
| Post-sampling hooks | Plugin extension mechanism | Not implemented | ❌ Missing |
| Session memory (periodic) | Extract/save memory periodically | Not implemented | ❌ Missing |

---

## 5. Tools — Tool Definition (Section 4)

| Field | Conceptual | Current `ToolDefinition` | Status |
|-------|-----------|------------------------|--------|
| name | ✅ | ✅ `tool.name` | ✅ |
| inputSchema (ZodSchema) | ✅ | ✅ `tool.input_schema` (Pydantic) | ✅ |
| outputSchema (ZodSchema) | ✅ | ❌ Not present in schema (no output validation) | ❌ Missing |
| prompt(options) | Dynamic description | ✅ `tool.get_description(context)` | ✅ |
| call(input, context, canUseTool, onProgress) | ✅ | ✅ `tool.execute()` (async where needed) | ✅ |
| isConcurrencySafe | ✅ | ✅ `tool.is_concurrency_safe` | ✅ |
| renderToolUseMessage | UI rendering | ❌ Not implemented (no UI layer) | ❌ Missing |
| renderToolUseProgressMessage | Live progress rendering | ❌ Not implemented | ❌ Missing |
| renderToolResultMessage | Result rendering | ❌ Not implemented | ❌ Missing |
| PreToolUse hooks | Plugins can intercept | ❌ Not implemented | ❌ Missing |
| PostToolUse hooks | Plugins can modify output | ❌ Not implemented | ❌ Missing |
| Permission check | canUseTool → user prompt/auto-allow | ❌ Not implemented (no permission layer) | ❌ Missing |

### Tool Categories — Present & Working

| Tool | Name | is_concurrency_safe | Status |
|------|------|---------------------|--------|
| FileRead | `file_read.py` | ✅ True | ✅ |
| FileWrite | `file_write.py` | ❌ False | ✅ |
| FileEdit | `file_edit.py` | ❌ False | ✅ |
| Bash | `bash.py` | ❌ False | ✅ |
| Glob | `glob.py` | ✅ True | ✅ |
| Search | `search.py` | ✅ True | ✅ |
| TodoWrite | `todo_write.py` | ✅ True | ✅ |
| Skill | `skill.py` | ✅ True | ✅ |
| Agent | `agent.py` | ❌ False | ✅ |
| SendMessage | `send_message.py` | ✅ True | ✅ |
| TaskCreate | `task_create.py` | ❌ False | ✅ |
| TaskUpdate | `task_update.py` | ❌ False | ✅ |
| TaskList | `task_list.py` | ✅ True | ✅ |
| TaskGet | `task_get.py` | ✅ True | ✅ |
| TaskOutput | `task_output.py` | ✅ True | ✅ |
| TaskStop | `task_stop.py` | ❌ False | ✅ |

---

## 6. Agents (Section 5)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| Agent tool call triggers subagent | `Agent` tool → `runAgent()` | ✅ `builtins/agent.py` → `AgentSpawner.spawn()` | ✅ |
| Fork subagent (full context inheritance) | Special fork flag | ❌ Not implemented | ❌ Missing |
| Isolated context (separate AppState) | Own setAppState | ✅ `context_isolation.py` — `AgentContext` + `AgentContextManager` | ✅ |
| Own toolUseContext | ✅ | ✅ Passed to subagent | ✅ |
| Own permission mode | `'bubble'` for parent terminal | ❌ Not implemented | ❌ Missing |
| Own query() loop | Full agentic loop inside | ✅ Creates independent `QueryLoop` | ✅ |
| Can call API/tools/more agents | ✅ | ✅ Subagent has full tool access | ✅ |
| Returns summarized tool_result | Single result to parent | ✅ `AgentResult.to_tool_result_block()` | ✅ |
| Agent abort hierarchy | Parent→child cascade | ✅ `abort_controller.py` — `_AbortHierarchy.register()` + `abort_tree()` | ✅ |
| Inter-agent messaging | Mailbox delivery | ✅ `agent_mailbox.py` — file-based `Mailbox` + `MailboxManager` | ✅ |
| Resource cleanup on exit | `AgentCleaner.cleanup()` | ✅ `agent_cleanup.py` — transcript, abort, messages, tokens | ✅ |

---

## 7. Progress (Section 6)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| Progress types (bash/powershell/mcp/sleep) | `EPHEMERAL_PROGRESS_TYPES` set | ❌ Not implemented | ❌ Missing |
| onProgress() → createProgressMessage | Wraps in `ProgressMessage<P>` | ❌ Not implemented | ❌ Missing |
| StreamingToolExecutor yields progress | Real-time UI updates | ❌ Not implemented | ❌ Missing |
| Progress is transient (not in transcript) | UI-only, discarded after render | N/A (no progress system) | — |
| Only tool_use/tool_result in transcript | Permanent record | ✅ `transcript.py` — writes turns as JSONL | ✅ |

---

## 8. Context Management — Compaction Strategies (Section 3)

| Strategy | Conceptual | Current | Status |
|----------|-----------|---------|--------|
| Snip Compact | Replace large file contents with stubs when msg count > 30 | ❌ Not implemented | ❌ Missing |
| Microcompact (time-based) | Replace old tool results every ~10 min | ❌ Not implemented | ❌ Missing |
| Microcached (cache_edits) | API-side cache edits instead of local modification | ❌ Not implemented | ❌ Missing |
| Context Collapse (marble-origami) | Pre-staged collapses, read-time projection | ⚠️ Basic collapse (keeps system + last 2 exchanges) | ✅ Partial |
| Auto-Compact (emergency) | Token threshold → session memory → API fallback | ❌ Not implemented | ❌ Missing |
| Session Memory Compact | Reuse extracted memory as summary | ❌ Not implemented | ❌ Missing |
| Legacy Compact (API summarization) | Send old messages to API for summarize | ❌ Not implemented | ❌ Missing |
| Circuit breaker | Stop after 3 consecutive auto-compact failures | ❌ Not implemented | ❌ Missing |

---

## 9. Session State & Guard (Section 8)

| Item | Conceptual | Current | Status |
|------|-----------|---------|--------|
| Session state (idle/running/requires_action) | `sessionState.ts` | ✅ `session.py` — status field | ✅ |
| Query guard (concurrency lock) | `QueryGuard.ts` — only one query at a time | ❌ Not implemented | ❌ Missing |
| Tool progress (live output) | `pendingProgress` on TrackedTool | ❌ Not implemented | ❌ Missing |
| Memory extraction state | SessionMemory utils | ❌ Not implemented | ❌ Missing |
| Auto-compact tracking | `state.ts` autoCompactTracking | ❌ Not implemented | ❌ Missing |
| Context collapse state | Transcript snapshot entries | ❌ Not implemented | ❌ Missing |
| Cost/state (tokens, budget) | Telemetry counters per API call | ✅ `token_tracker.py` — `TokenUsageTracker` | ✅ |
| TODO list | Extracted from TodoWrite in transcript | ✅ `todo_write.py` — `_todo_state` dict | ✅ |

---

## 10. System Prompts (Section of SYSTEM_PROMPT_MANAGEMENT.md)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| System prompt as array of blocks | Static prefix + dynamic tail with boundary | ❌ Not implemented — flat string | ❌ Missing |
| Static vs dynamic sections | `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` divider | ❌ Not implemented | ❌ Missing |
| Dynamic registry (cached/uncached sections) | `systemPromptSection()` / `DANGEROUS_uncachedSystemPromptSection()` | ❌ Not implemented | ❌ Missing |
| Prompt caching scopes (global/org/null) | `splitSysPromptPrefix()` with `cache_control` | ❌ Not implemented | ❌ Missing |
| CLAUDE.md user context injection | Synthetic user message before each call | ❌ Not implemented | ❌ Missing |
| Git status system context | Appended to system prompt array | ❌ Not implemented | ❌ Missing |
| Attachments layer | Memory/skills/plans as attachment messages | ❌ Not implemented | ❌ Missing |
| Prompt priority (override > custom > default) | `buildEffectiveSystemPrompt()` | ❌ Not implemented | ❌ Missing |
| Compaction resets system prompt cache | `clearSystemPromptSections()` | ❌ Not implemented | ❌ Missing |

---

## 11. Error Recovery (Error Handling)

| Feature | Conceptual | Current | Status |
|---------|-----------|---------|--------|
| Multi-tiered recovery (retry, fallback, collapse) | `error_recovery.py` | ✅ Partial — `ErrorRecovery` class with model fallback chain | ✅ Partial |
| Tool error feedback to LLM | Structured error result block | ✅ `executor.py` — `format_error()` returns structured dict | ✅ |
| Model fallback chain | Try next model on failure | ✅ `fallback_chain` parameter in `QueryLoop` | ✅ |
| Max retry limit | Configurable retry count | ✅ `DEFAULT_MAX_RETRIES = 10` | ✅ |

---

## Summary Matrix

### Fully Implemented ✅
- Core query loop (model → tools → result → loop)
- Tool registry + 16 built-in tools
- Tool execution with Pydantic validation
- Concurrency partitioning (safe=parallel, unsafe=serial)
- Agent spawning with isolated context
- Agent abort hierarchy (parent→child cascade)
- Inter-agent mailbox messaging
- Agent cleanup on exit
- Transcript JSONL writing
- Token usage tracking
- Task state machine (5 states + TTL eviction)
- Session creation/loading/persistence
- Error recovery (retry + model fallback)

### Partially Implemented ⚠️
- Context collapse (exists but too aggressive — no marble-origami)
- Transcript writing (exists but not atomic)
- System prompt (flat string — no block structure)
- Progress tracking (no live progress at all)
- Streaming API (non-streaming only)

### Missing ❌ (Need Implementation)
| Priority | Feature | Impact |
|----------|---------|--------|
| **P0** | Context compaction (snip + microcompact + auto-compact) | Conversation memory grows unbounded |
| **P0** | Query guard (one query at a time) | Race conditions on concurrent queries |
| **P1** | Session memory extraction + reuse | Auto-compact can't save tokens/money |
| **P1** | Progress tracking (onProgress) | No live feedback to user |
| **P1** | Streaming API integration | Slower response, no character-by-character display |
| **P2** | System prompt block structure | Can't use API-level prompt caching |
| **P2** | Permission checks | Tools execute without authorization |
| **P2** | Pre/Post ToolUse hooks | No plugin extensibility |
| **P2** | Tool result budget capping | Could overflow context window |
| **P3** | Output schema validation | No guarantee on tool output format |
| **P3** | UI rendering (renderToolUseMessage etc.) | Not needed for backend-only use |
| **P3** | Post-sampling hooks | No observability plugin points |
| **P3** | Fork subagent (full context inheritance) | Only one agent context mode |

---

## Recommended Implementation Order

1. **P0**: Add `QueryGuard` to `query_loop.py` — single query lock
2. **P0**: Add context compaction pipeline to `query_loop.py` — snip → microcompact → auto-compact
3. **P1**: Add session memory extraction + reuse to auto-compact
4. **P1**: Add progress tracking via `onProgress` callbacks
5. **P1**: Add streaming API support to query loop
6. **P2**: Restructure system prompt into blocks with caching scopes
7. **P2**: Add permission checking layer to executor
8. **P2**: Add Pre/Post ToolUse hook system to executor
9. **P2**: Add tool result budget capping to preparation pipeline
10. **P3**: Add remaining low-priority features as needed
