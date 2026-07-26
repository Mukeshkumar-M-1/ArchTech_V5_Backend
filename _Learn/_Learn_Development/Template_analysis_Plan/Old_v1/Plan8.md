# Plan: Add Missing CCB Features to ArchTech V5 Backend

## Context
ArchTech V5 (`/home/devusr/Mukesh/ArchTech_V5/Backend/backend/`) is a Python agentic system inspired by Claude Code (CCB). It has a working foundation: QueryLoop, AgentSpawner, MemoryManagementAgent, TemplateAnalysisAgent, tool registry, executor, concurrency manager, message manager, error recovery — but several critical CCB-parity features are missing or disconnected. This plan implements 10 missing features in 9 phases, ordered by dependency.

---

## Phase 1: Task State Machine & Eviction (Foundation)

**Goal:** Replace bare module-level dicts with a proper 5-state lifecycle (pending → running → completed/failed/killed) with TTL-based eviction.

**New file:** `tools/task_state.py`
- `TaskStatus` enum (PENDING/RUNNING/COMPLETED/FAILED/KILLED)
- `TaskState` dataclass: `id, status, created_at, updated_at, result, parent_agent_id, retain_flag, ttl_seconds`
- `TaskStateMachine`: enforces valid transitions (e.g., terminal states are absorbing)
- `TaskStore(dict)`: wraps module-level `_task_store`, adds `create_task()`, `transition()`, `evict_terminal_tasks()`, `mark_retained()`. Inherits `dict` to preserve existing callers.

**Modified files:**
- `tools/builtins/tasks.py` — `_task_store` → `TaskStore()` instance. `get_store()` delegates to it.
- `tools/builtins/task_create.py` — calls `TaskStore.create_task()` on create.
- `tools/builtins/task_update.py` — calls `TaskStore.transition()` on status change.
- `tools/builtins/task_stop.py` — transitions to KILLED instead of just cancelling.
- `tools/builtins/task_list.py` / `task_get.py` — read from TaskStore state objects.

**Scope:** ~350 lines new, 5 files modified.

---

## Phase 2: Abort Controller Hierarchy

**Goal:** Parent→child abort chain so killing a parent agent cancels all subagents.

**New file:** `tools/abort_controller.py`
- `AbortSignal`: `is_aborted`, `abort()`, `on_abort(callback)`, `reason`
- `AbortController`: `signal`, `abort(reason)`, `child()` creates linked child controller
- `AbortControllerHierarchy` singleton: `register()`, `abort_tree()`, `cleanup()`

**Modified files:**
- `tools/agent_spawner.py` — `spawn()` accepts optional `abort_controller`. Pass parent's `child()` to subagent.
- `tools/query_loop.py` — `run()` checks `_abort.signal.is_aborted` at top of each loop iteration.

**Scope:** ~200 lines new, 2 files modified.

---

## Phase 3: Agent Context Isolation (contextvars)

**Goal:** Python `contextvars` equivalent of CCB's AsyncLocalStorage — isolates per-agent state across concurrent agents.

**New file:** `tools/context_isolation.py`
- `AgentContext` dataclass: `agent_id, task_store, message_manager, abort_controller, transcript_writer, token_tracker`
- `AgentContextManager` async context manager: `async with enter/exit`
- `get_context()`, `is_isolated()` helpers

**Modified files:**
- `tools/agent_spawner.py` — wrap `_spawn_sync` body in `async with AgentContextManager(...)`.
- `tools/builtins/tasks.py` — `get_store()` checks `get_context().task_store` first, falls back to module-level.
- `tools/query_loop.py` — optionally uses `AgentContext.message_manager`.

**Scope:** ~150 lines new, 3 files modified.

---

## Phase 4: Comprehensive Agent Cleanup

**Goal:** Finally blocks that clean up caches, tasks, state, and leaks on every agent exit path.

**New file:** `tools/agent_cleanup.py`
- `AgentCleaner.cleanup(agent_id, context)`: cancel asyncio tasks, abort controller, close transcript, clear messages, remove from hierarchy registry
- `AgentCleaner.cleanup_background_tasks(spawner)`: iterate `_background_tasks`, await/cancel, remove from set

**Modified files:**
- `tools/agent_spawner.py` — wrap `_spawn_sync` in try/finally → call `AgentCleaner.cleanup()`. Background task wraps in try/finally.
- `tools/query_loop.py` — try/finally cleanup of local state.

**Scope:** ~120 lines new, 2 files modified.

---

## Phase 5: Disk-Backed Transcript Output

**Goal:** JSONL file per agent for persistent, incremental transcript reads.

**New file:** `tools/transcript.py`
- `TranscriptWriter`: `write_turn(turn, role, content, tool_calls, tool_results, tokens_in, tokens_out)` — JSONL append with asyncio.Lock
- `TranscriptReader`: `read_all()`, `read_offset()`, `last_offset()` for incremental reads
- `get_transcript_dir(project_id, agent_id)` helper

**Modified files:**
- `tools/context_isolation.py` — `AgentContext` gains optional `transcript_writer`.
- `tools/agent_spawner.py` — create `TranscriptWriter` per agent, pass into context.
- `tools/query_loop.py` — `run()` accepts optional `transcript_writer`, writes each turn.
- `tools/agent_cleanup.py` — call `transcript_writer.close()` in cleanup.

**Scope:** ~180 lines new, 4 files modified.

---

## Phase 6: Inter-Agent Messaging (SendMessage)

**Goal:** File-based mailbox with locking for agents to send messages to each other.

**New file:** `tools/agent_mailbox.py`
- `Mailbox`: `send(to_agent, from_agent, message)` with atomic file writes + lockfile, `recv(agent, since_offset)` for reading

**Modified files:**
- `tools/builtins/agent.py` — wire `send_message()` to mailbox.
- `tools/agent_spawner.py` — `send_message()` delegates to `get_mailbox().send()`.
- `tools/models.py` — add `SendMessageInput` Pydantic model.
- `tools/builtins/__init__.py` — register `SendMessage` tool.

**Scope:** ~100 lines new, 4 files modified.

---

## Phase 7: Wire Up MessageManager (Context Budget)

**Goal:** Integrate the existing `MessageManager` into `QueryLoop` for context budget management.

**Modified files:**
- `tools/query_loop.py` — accept optional `message_manager`. If not provided, create one. Call `trim()` before each LLM call if budget exceeded, `collapse_context()` if still over.
- `tools/error_recovery.py` — delegate `collapse_context` to `MessageManager.collapse_context()` instead of own implementation.

**Scope:** ~50 lines added, 2 files modified. Reuses existing `MessageManager` entirely.

---

## Phase 8: Wire Up ConcurrencyManager (Parallel Tools)

**Goal:** Integrate the existing `ConcurrencyManager` into `QueryLoop` for parallel tool execution.

**Modified files:**
- `tools/query_loop.py` — replace sequential tool loop with `ConcurrencyManager.execute_batches()`. Build `tool_defs_dict` once. Default `max_concurrency=1` (sequential) for safe rollout.

**Scope:** ~30 lines added, 1 file modified. Reuses existing `ConcurrencyManager` entirely.

---

## Phase 9: Structured Token Usage Tracking

**Goal:** Track input/output tokens per turn from LLM API responses, surface in `AgentResult`.

**New file:** `tools/token_tracker.py`
- `TokenUsage` dataclass: `input_tokens, output_tokens, total_tokens, turn_number`
- `TokenUsageTracker`: `record_turn()`, `get_total()`, `get_per_turn()`, `snapshot()`. Thread-safe via `threading.Lock`.

**Modified files:**
- `tools/context_isolation.py` — `AgentContext` gains `token_tracker`.
- `tools/query_loop.py` — extract `response.usage` after each `_call_with_fallback()`, pass to tracker.
- `tools/agent_spawner.py` — create `TokenUsageTracker` per agent. Populate `AgentResult.input_tokens`, `output_tokens` from tracker at end of `_spawn_sync`.
- `tools/agent_cleanup.py` — log token usage summary on cleanup.

**Scope:** ~80 lines new, 4 files modified.

---

## Phase Dependency Graph

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
                                    │        │
                           ┌────────┘        │
                           ▼                 ▼
                    Phase 5 ◄──┐       Phase 7
                    Phase 6 ◄──┤       Phase 8
                    Phase 9 ◄──┘
```

- **Phase 1** is independent (foundation)
- **Phase 2** depends on Phase 1 (uses TaskState for KILLED)
- **Phase 3** depends on Phases 1 & 2 (wraps their components)
- **Phase 4** depends on Phase 3 (cleans up context)
- **Phases 5–9** depend on Phase 3 (use context), but can be developed in parallel

---

## Critical Files (sorted by modification frequency)

| File | Phases that modify it |
|------|----------------------|
| `tools/query_loop.py` | 2, 3, 5, 7, 8, 9 |
| `tools/agent_spawner.py` | 2, 3, 4, 5, 6, 9 |
| `tools/context_isolation.py` | 3, 5, 9 |
| `tools/builtins/tasks.py` | 1, 3 |
| `tools/agent_cleanup.py` | 4, 5, 9 |
| `tools/transcript.py` | 5 |
| `tools/abort_controller.py` | 2 |
| `tools/agent_mailbox.py` | 6 |
| `tools/token_tracker.py` | 9 |
| `tools/task_state.py` | 1 |
| `tools/builtins/agent.py` | 6 |
| `tools/builtins/task_create.py` | 1 |
| `tools/builtins/task_update.py` | 1 |
| `tools/builtins/task_stop.py` | 1 |
| `tools/builtins/__init__.py` | 6 |
| `tools/models.py` | 6 |
| `tools/error_recovery.py` | 7 |

---

## Verification Plan

1. **Unit tests for TaskStateMachine** — valid/invalid transitions, eviction with TTL
2. **Unit tests for AbortController** — parent abort propagates to children, child abort doesn't affect parent
3. **Integration test: concurrent agents** — spawn 3 agents concurrently, verify isolated state via contextvars
4. **Integration test: agent cleanup** — spawn agent that fails, verify no leaked tasks/asyncio references
5. **Integration test: transcript** — spawn agent with tools, verify JSONL file has all turns
6. **Integration test: SendMessage** — spawn two agents, send message between them via mailbox
7. **Integration test: context budget** — run agent that generates many messages, verify trimming/collapse works
8. **Integration test: concurrent tools** — run agent with multiple safe tools (FileRead, Glob), verify parallel execution
9. **Integration test: token tracking** — run agent, verify `AgentResult` has accurate input/output token counts
10. **Full pipeline test** — run MemoryManagementAgent → TemplateAnalysisAgent → ContentKnowledgeAgent end-to-end, verify all new features work together

Run existing tests: `python -m pytest backend/` before and after each phase.

---

## Risks & Mitigations

1. **TaskStore dict subclass** — Making `TaskStore(dict)` ensures existing callers (task_list, task_get, task_output) that do `store.get()`, `store[task_id]`, `not store` continue working.
2. **contextvars with nested event loops** — Tools check `get_context()` first, fall back to module-level state if `None`. No breaking changes for non-isolated callers.
3. **ConcurrencyManager changes tool semantics** — Default `max_concurrency=1` keeps sequential behavior. Enable parallel batches only when explicitly configured.
4. **File-based mailbox durability** — Atomic writes (`temp file` + `os.replace`). Lockfile for concurrent safety. Skip corrupted JSON lines on read.
5. **Token usage missing from API** — `TokenUsageTracker.record_turn()` tolerates missing usage (records zeros). Logs warning when expected but missing.
