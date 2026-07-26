# What's Missing in ArchTech V5 (vs CCB Reference)

## A. Agent Spawn & Lifecycle Management

| Feature | CCB | ArchTech V5 Gap |
|---|---|---|
| AsyncLocalStorage context isolation | `agentContext.ts` + `teammateContext.ts` — isolates agent context across async chains | Missing entirely. All state is shared module-level dicts. Two concurrent agents would corrupt each other's state. |
| Abort controller hierarchy | Child agents linked to parent AbortController — killing parent kills children | Missing. `AgentSpawner._spawn_sync` has no AbortController. No way to cancel a running subagent. |
| Comprehensive cleanup | 10+ cleanup steps in `runAgent` finally block: MCP cleanup, session hooks, file state cache clear, fork context release, todos cleanup, shell task kill, monitor task kill | Missing. AgentSpawner has no finally cleanup. Leaked tasks, caches, and state accumulate forever. |
| Context state cloning | Forked agents get cloned `fileReadingState` + `contentReplacementState` caches | Missing. Subagents share the same module-level state as the parent. No isolation of file reads/writes. |
| Task state machine | 5 states (pending/running/completed/failed/killed) with transitions in `Task.ts` | Partial. ArchTech only has launched/completed/failed/error. No pending/killed states, no state transitions. |
| Task eviction & grace periods | `evictTerminalTask()` with PANEL_GRACE_MS (30s) retention, retain flag, STOPPED_DISPLAY_MS for killed tasks | Missing. Tasks in `_task_store` are never evicted. Memory leaks on long sessions. |
| Disk-backed output | `diskOutput.ts` — symlinks to transcript files, incremental delta reads via outputOffset | Missing. Results are only in-memory. No way to recover after process crash or view partial output. |
| Sidechain transcript persistence | JSONL files at `subagents/{agentId}.jsonl` + `.meta.json` for each agent | Missing. Subagent conversation history is never persisted to disk. |
| Resume via SendMessage | CCB can resume evicted agents from their JSONL transcript, restoring messages from disk | Missing. `send_message()` in ArchTech is a stub that just echoes the message back. |

## B. Message & Communication

| Feature | CCB | ArchTech V5 Gap |
|---|---|---|
| File-based mailbox system | `teammateMailbox.ts` — JSON mailbox per agent with locking, size limits (4MB), message compaction, 14 message types | Missing. No inter-agent messaging. `send_message()` is a no-op stub. |
| Agent name registry | `agentNameRegistry: Map<string, AgentId>` for routing SendMessage by human-readable name | Missing. Only numeric `agent-{N}` IDs exist. No name-to-ID mapping. |
| Broadcast messaging | `"*"` broadcasts to all teammates via mailbox | Missing. |
| Pending message queue | `pendingMessages[]` array in task state, `queuePendingMessage()`/`drainPendingMessages()` | Missing. |
| Structured message types | Shutdown requests/responses, plan approvals, permission requests | Missing. |
| Token-based message budget | `MessageManager` with `max_tokens: 128_000` and `available_tokens` tracking | Partial. ArchTech's `MessageManager` exists but isn't wired into the query loop or used anywhere. |

## C. Tool Execution & Results

| Feature | CCB | ArchTech V5 Gap |
|---|---|---|
| Structured AgentToolResult | Full schema: usage (input/output tokens, cache reads, server tool use), totalToolUseCount, totalDurationMs, content | Partial. `AgentResult` has basic fields but no token usage tracking, no cache metrics. |
| Streaming tool results | Results yielded incrementally via generator pattern (`yield message`), written to sidechain after each message | Missing. Results are batch-only. No streaming or incremental delivery. |
| Progress tracking | `ProgressTracker` with `updateProgressFromMessage()` — extracts todo/completion signals | Missing. No progress feedback from subagents to parent. |
| Context updates from tools | `context_updates` dict in ToolExecutionResult for state changes | Partial. Field exists in dataclass but is never populated or consumed by any tool. |
| Tool permission system | Permission mode, denial tracking, permission requests routed to parent | Missing. No permission system at all. |
| Concurrent batch optimization | `ConcurrencyManager` groups safe tools into parallel batches | Partial. `ConcurrencyManager` exists but is never used by QueryLoop — tools execute serially. |

## D. Memory & Knowledge Management

| Feature | CCB | ArchTech V5 Gap |
|---|---|---|
| Persistent agent memory (scoped) | 3 scopes: user/project/local (`~/.claude/agent-memory/`) with MEMORY.md index | Missing. ArchTech has its own MEMORY.md via MemoryManagementAgent but no scoped persistent memory for agents. |
| Session memory (auto-extracted) | SessionMemory background forked subagent extracts key conversation notes to `.claude/session-memory.md` | Missing. No auto-extraction of session-level summaries. |
| Prompt cache break detection | `cleanupAgentTracking()` / PROMPT_CACHE_BREAK_DETECTION feature flag | Missing. |
| Analytics/tracing | `logEvent` calls, `endTrace(subTrace)` for Langfuse, `unregisterPerfettoAgent()` | Partial. Logging exists but no structured analytics or distributed tracing. |
| Error recovery with context collapse | `ErrorRecovery.collapse_context()` + `recover_from_output_limit()` with injected recovery messages | Partial. `ErrorRecovery` exists but `collapse_context` keeps only 2 pairs (too aggressive vs CCB's configurable approach). |

## E. Architecture-Level Gaps

| Area | CCB | ArchTech V5 Gap |
|---|---|---|
| Immutable state updates | `DeepImmutable<AppState>` with functional updates (`setAppState(prev => {...})`) | Missing. Direct mutation of module-level dicts. No undo/rollback capability. |
| SDK event queue | `enqueueSdkEvent()` for task lifecycle events, `enqueuePendingNotification()` for push updates | Missing. No event-driven architecture. |
| Worktree isolation | Agents can spawn in isolated git worktrees | Missing. |
| MCP server per agent | Each agent can have its own MCP servers, cleaned up in finally block | Missing. |
| Skill invocation tracking | `clearInvokedSkillsForAgent()` per agent, SKILL.md loading | Partial. Skills exist but no per-agent tracking/cleanup. |

## Summary: Highest Priority Gaps

| # | Gap | Severity |
|---|---|---|
| 1 | No context isolation — concurrent agents corrupt shared state | Critical |
| 2 | No cleanup/eviction — memory leaks on long sessions | High |
| 3 | No abort/cancellation — can't kill a running subagent | High |
| 4 | No persistence — all memory lost on crash | High |
| 5 | No inter-agent messaging — `send_message()` is a stub | High |
| 6 | MessageManager not wired in — exists but unused by the query loop | Medium |
| 7 | ConcurrencyManager not wired in — exists but tools run serially | Medium |
