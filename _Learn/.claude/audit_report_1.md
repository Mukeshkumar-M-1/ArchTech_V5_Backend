# AgentCore Deep Architecture Gap & Coding-Agent Readiness Audit

## Executive Summary

AgentCore is a **document-generation-specific orchestration system** with an **active LLM agent loop** inside a sea of **M2/M3 scaffolding**. The system can generate technical documents section-by-section via an HTTP route, but most of the 130 files are **never executed** in the production path. The cognitive engines (reflection, repair, verification), action planner/executor, reasoning engine, and knowledge graph are all **stubs** — they exist in the codebase but are **zero-wired** into the actual execution flow. The active runtime is: routes.py -> MissionOrchestrator -> RuntimeAdapter -> GenerationAgentKernel -> ExecutionEngine -> QueryLoop.

---

## 1. Actual Entry Point

```
HTTP POST /generate-document-stream
    |
    v
agents/routes.py:generate_document_stream()
    |
    |-- Creates SSEEventQueue (main stream) + SSEToolQueue (tool events)
    |
    |-- set_tool_event_queue(tool_events_queue._queue)  -- global SSE hook
    |
    |-- Spawns _document_agent_worker() background task
    |       |
    |       v
    |       MissionOrchestrator(project_id, num_workers=3)
    |           |
    |           v
    |       await boot_cluster()       -- registers 3 dummy workers
    |           |
    |           v
    |       MissionParser().parse()    -- reads templates, knowledge, memory
    |           |
    |           v
    |       TaskPlanner().plan()       -- creates one TaskContract per section
    |           |
    |           v
    |       TaskGraphBuilder().build_graph()  -- DAG with section dependencies
    |           |
    |           v
    |       MissionStateManager.initialize_from_graph()  -- counts total tasks
    |           |
    |           v
    |       ReadyTaskSelector() + TaskQueue
    |
    |   while completed < total:
    |       |-- is_paused(project_id)?
    |       |-- Inject traceability_data into ready tasks
    |       |-- build_ready_tasknode()
    |       |-- scheduler.run_scheduling_cycle(task_queue)
    |           |
    |           v
    |       RuntimeAdapter.execute(task)
    |           |
    |           v
    |       GenerationAgentKernel.run_task(task_id, task_contract, tools, max_turns=20)
    |           |
    |           v
    |       ExecutionEngine.execute_task(task_id, task_contract, tools, max_turns=20)
    |           |
    |           |-- For each turn (up to 20):
    |           |   |-- Build LLM messages (developer + user context)
    |           |   |-- QueryLoop._LLM_chatcomplete_call()  -- real LLM API
    |           |   |-- QueryLoop._parse_response()  -- text + tool calls
    |           |   |-- If text only: return final_answer
    |           |   |-- If tool calls: ToolExecutor.execute() for each
    |           |   |-- Append tool results to conversation history
    |           |   |-- Sliding window: keep only last 5 turns
    |           |
    |           v
    |       Return generated markdown section
    |
    |   Save section to JSON with version tracking
    |   Stream section_chunk SSE events (500-char chunks)
    |
    v
SSEEventQueue.stream() -> StreamingResponse (text/event-stream)
```

**Data passed at each transition:**
- `routes.py -> MissionOrchestrator`: project_id, template_type, goal string
- `MissionOrchestrator -> MissionParser`: goal, project_id, template_type
- `MissionParser -> TaskPlanner`: MissionSpecification (with template_context, knowledge_content)
- `TaskPlanner -> TaskGraphBuilder`: list of planned task dicts
- `TaskGraphBuilder -> TaskQueue`: TaskContract objects
- `TaskQueue -> RuntimeAdapter -> GenerationAgentKernel -> ExecutionEngine`: TaskContract with goal + execution_context dict
- `ExecutionEngine -> QueryLoop`: messages list (developer + user context), tool definitions, model=opus46, max_tokens=32768, temp=0.1
- `QueryLoop -> LLM API`: OpenAI-compatible chat.completions.create() call
- `LLM -> QueryLoop`: ChatCompletion object with choices
- `QueryLoop -> ToolExecutor`: ToolDefinition + args dict
- `ToolExecutor -> Builtins (Bash/FileRead/Search/etc.)`: validated args
- `Builtins -> QueryLoop -> ExecutionEngine`: result strings
- `ExecutionEngine -> routes.py -> SSEEventQueue`: section markdown text

---

## 2. Actual End-to-End Execution Flow

The complete chain is a **single-pass, section-by-section generation** flow:

```
User Request
    -> FastAPI Route (routes.py)
    -> MissionOrchestrator (orchestration/orchestrator.py)
    -> MissionParser.parse() (orchestration/mission_layer.py)
    -> TaskPlanner.plan() (orchestration/mission_layer.py)
    -> TaskGraphBuilder.build_graph() (orchestration/mission_layer.py)
    -> ReadyTaskSelector.build_ready_tasknode() (orchestration/mission_layer.py)
    -> SchedulerManager.run_scheduling_cycle() (orchestration/scheduling_manager.py)
    -> Dispatcher.dispatch() (orchestration/lease_manager.py)
    -> RuntimeAdapter.execute() (orchestration/runtime_adapter.py)
    -> GenerationAgentKernel.run_task() (observability/agent_kernel.py)
    -> ExecutionEngine.execute_task() (core/execution_engine.py)
    -> QueryLoop._LLM_chatcomplete_call() (execution/query_loop.py)
    -> [OpenAI-compatible LLM API]
    -> QueryLoop._parse_response()
    -> ToolExecutor.execute() (execution/tool_executor.py)
    -> Builtins (file_read.py, file_write.py, file_edit.py, bash.py, glob.py, search.py)
    -> QueryLoop (sliding window, next turn)
    -> [loop back 1-8 times typically]
    -> QueryLoop returns final text
    -> ExecutionEngine.execute_task returns section markdown
    -> GenerationAgentKernel returns result
    -> RuntimeAdapter returns RuntimeResult
    -> MissionOrchestrator processes result, writes to JSON
    -> MissionOrchestrator yields section_chunk SSE events
    -> SSEEventQueue -> StreamingResponse -> User
```

---

## 3. Actual Agent Loop

The agent loop is implemented by **ExecutionEngine.execute_task()** in `core/execution_engine.py`, which internally uses **QueryLoop** from `execution/query_loop.py` for the LLM call.

**Who owns the loop:** ExecutionEngine.execute_task() (core/execution_engine.py:50)

**Who starts the loop:** RuntimeAdapter.execute() (orchestration/runtime_adapter.py:50) calls GenerationAgentKernel.run_task() calls ExecutionEngine.execute_task()

**Who decides continuation:** ExecutionEngine (via the for loop on agent_turn in range(1, max_turns+1))

**Who interprets model output:** QueryLoop._parse_response() (execution/query_loop.py:560)

**Who handles tool calls:** ExecutionEngine.execute_task() (line 306-427) + QueryLoop._execute_tools() (line 656)

**Who inserts tool results back into context:** ExecutionEngine.execute_task() appends tool messages to store (line 411-417)

**Who detects final completion:** ExecutionEngine (line 292-303): `if not result_tool_calls and agent_response_context is not None: return`

**Who handles malformed model output:** QueryLoop._parse_response() returns empty text + empty tool_calls

**Who handles LLM failure:** QueryLoop._LLM_chatcomplete_call() has retry/backoff via llm_api_handler, then fallback chain, then returns "Error: API call failed"

**Who handles tool failure:** ToolExecutor.execute() catches exceptions and returns ToolExecutionResult with is_error=True

**Who handles context overflow:** Sliding window in QueryLoop (line 307-310): keeps only last 5 turns. Also ContextCompactPipeline (unused in active path).

**Who handles cancellation:** AbortController (execution/abort_controller.py) — check at start of each loop iteration

**Who records the turn:** ExecutionEngine.appends to ExecutionStore (line 417)

**Who emits events:** AsyncEventBus (ExecutionEngine line 263, 294, 328, 369, 428)

**Who terminates the task:** ExecutionEngine (max turns hit, text-only response, or error)

---

## 4. PTaO Necessity Analysis

**Verdict: SKELETON — Not Necessary**

The PTaO (Planning-Thinking-Action-Observation) pattern appears in:
- `reasoning/reason_engine.py` — Always returns hardcoded SEARCH/COMPLETE decision
- `action/action_planner.py` — Stubs that convert SEARCH to SEARCH_REPO+SEARCH_FILES
- `action/action_executor.py` — Internal actions like THINK/REFLECT just return strings
- `orchestration/dependency_graph.py` — Only used for document section dependencies, not task dependencies

**None of these are wired into the execution path.** The actual execution path is:
```
MissionOrchestrator -> RuntimeAdapter -> GenerationAgentKernel -> ExecutionEngine -> QueryLoop
```

The `reason_engine.py` and `action_executor.py` are **never called** by any active component. They are M2/M3 scaffolding from a previous planning phase.

**Verdict: F — Legacy system + H — Partially implemented + DUPLICATE of QueryLoop's loop logic**

---

## 5. Core vs Execution Responsibility Matrix

| Component | Status | Active? | Notes |
|-----------|--------|---------|-------|
| `core/execution_engine.py` | **CORE_RUNTIME** | YES | Actual active execution engine |
| `core/agent_state.py` | **SUPPORTING** | YES | AgentStateStore used by ExecutionEngine |
| `core/agent_session_manager.py` | **LEGACY** | NO | Not used in active path |
| `core/execution_history.py` | **PARTIALLY WIRED** | YES | ExecutionStore + ContextManager used by ExecutionEngine |
| `execution/query_loop.py` | **CORE_RUNTIME** | YES | Active LLM loop with tool execution |
| `execution/tool_registry.py` | **INFRASTRUCTURE** | YES | Active global registry |
| `execution/tool_executor.py` | **INFRASTRUCTURE** | YES | Active tool execution with validation |
| `execution/permission_manager.py` | **SKELETON** | PARTIALLY | PermissionMode exists but all tools auto-allowed |
| `execution/context_compaction.py` | **WRAPPER** | PARTIALLY | Token budget exists but sliding window is primary mechanism |
| `execution/session_manager.py` | **CORE_RUNTIME** | YES | Active session progress tracking |
| `execution/agent_spawner.py` | **SKELETON** | NO | Never used — workers are hardcoded in boot_cluster() |
| `execution/agent_mailbox.py` | **UNUSED** | NO | Inter-agent messaging never used |
| `execution/builtins/` | **INFRASTRUCTURE** | YES | All 10 builtins active |

---

## 6. Action vs Orchestration vs Execution

| Component | Responsibility | Active? |
|-----------|---------------|---------|
| `action/action_planner.py` | Expand reasoning decisions to execution plans | NO |
| `action/action_executor.py` | Route actions to tools or internal handlers | NO |
| `action/tool_router.py` | Map action types to tool names | NO |
| `orchestration/orchestrator.py` | Mission flow control (section loop) | YES |
| `orchestration/mission_layer.py` | Task parsing/planning/graph building | YES |
| `orchestration/lease_manager.py` | Task queue + dispatcher | YES |
| `orchestration/runtime_adapter.py` | Worker execution boundary | YES |
| `orchestration/scheduling_manager.py` | Capability-based task assignment | PARTIALLY (only uses LeastBusyPolicy) |
| `orchestration/worker_management.py` | Worker registry + heartbeats | PARTIALLY (dummy workers only) |
| `execution/query_loop.py` | LLM interaction loop | YES |
| `execution/tool_executor.py` | Tool invocation | YES |
| `core/execution_engine.py` | Turn management | YES |

**RESPONSIBILITY OVERLAP:**
- `orchestration/task_planner.py` and `orchestration/mission_layer.py:TaskPlanner` — Two planners. Only mission_layer.TaskPlanner is used.
- `orchestration/planner_engine.py` — Unused, never imported by active path.
- `action/action_planner.py` — Stubs, never used.
- `orchestration/dependency_graph.py` — Only used for section-level MD dependencies, not task execution.

---

## 7. Tool System Audit

### Tool Discovery
**AVAILABLE** — Global singleton registry, auto-registered via `execution/builtins/__init__.py`

### Tool Schemas
**AVAILABLE BUT WEAK** — Pydantic models (shared/types.py) provide validation. ToolExecutor validates arguments before execution. However, schemas are simple strings — no deep constraint checking.

### Tool Routing
**Single path** — ToolExecutor looks up ToolDefinition by name, calls execute(). No separate routing layer is needed.

### Permission
**SKELETON** — PermissionManager has modes (FULL_AUTO, REQUIRE_PROMPT, SKIP) but all tools are in AUTO_ALLOW. REQUIRE_PROMPT set is **empty**. No policy enforcement.

### Timeout
**AVAILABLE** — Bash tool has timeout parameter. LLM call has retry/backoff. No tool-level timeout in ToolExecutor.

### Cancellation
**PARTIALLY WIRED** — AbortController exists. QueryLoop checks abort signal at turn start. ExecutionEngine doesn't check it.

### Output Limits
**AVAILABLE** — Error truncation (DEFAULT_ERROR_TRUNCATE=10000). Bash output truncated to 5000 chars. SSE tool output truncated to 200 chars.

### Errors
**AVAILABLE** — Tool errors returned as structured content to LLM. Validation errors formatted as human-readable strings.

### Traceability
**PARTIALLY** — SessionManager logs tool calls and stage completions. No full turn-level trace.

### Built-in Tools Inventory:
| Tool | Available | Active? | Notes |
|------|-----------|---------|-------|
| FileRead | YES | YES | |
| FileWrite | YES | YES | |
| FileEdit | YES | YES | Range-based replacement |
| Bash | YES | YES | Async, with timeout |
| Glob | YES | YES | |
| Search | YES | YES | |
| Agent | YES | YES | Sub-agent spawning (stub) |
| SendMessage | YES | YES | Inter-agent messaging (stub) |
| RequestUserInput | YES | YES | |
| ProposeContentEdit | YES | YES | |

---

## 8. Coding-Agent Tool Completeness

| Capability | Status | Notes |
|------------|--------|-------|
| READ | AVAILABLE | FileRead tool |
| SEARCH | AVAILABLE | Search tool |
| GLOB | AVAILABLE | Glob tool |
| EDIT | AVAILABLE | FileEdit (range-based) |
| WRITE | AVAILABLE | FileWrite |
| DELETE | **MISSING** | No Delete tool |
| MOVE/RENAME | **MISSING** | No Move tool |
| BASH | AVAILABLE | With timeout |
| GIT | **MISSING** | Can only use via Bash |
| TEST | **MISSING** | Can only use via Bash |
| BUILD | **MISSING** | Can only use via Bash |
| ASK USER | AVAILABLE | RequestUserInput |
| SPAWN AGENT | AVAILABLE BUT WEAK | Agent tool is a stub, never actually spawns |

---

## 9. Repository Intelligence

| Query Type | Status | Notes |
|------------|--------|-------|
| Symbol lookup | KEYWORD-ONLY | repo_query_engine.find_symbol() works but limited |
| Find callers | STUB | Returns empty list |
| File imports | AVAILABLE | find_file_imports() |
| Requirement lookup | AVAILABLE | Document-specific |
| Related requirements | AVAILABLE | Via cross-references |
| Symbol-aware search | NO | No AST-level reference resolution |
| Dependency-aware | PARTIAL | imports tracking exists but callers is stub |

**Highest impact gap:** No symbol-aware cross-reference resolution. find_callers() is a stub.

---

## 10. Context Architecture

### Three Context Builders — Only One Active:

| Builder | File | Active? | Purpose |
|---------|------|---------|---------|
| `context/context_builder.py` | M2/M3 architecture | NO | Stub — builds ExecutionContext |
| `orchestration/context_builder.py` | M5 | YES | Builds turn context for MissionParser |
| `platform/llm/builder.py` | LLM prompt builder | PARTIALLY | Platform-level LLM context |

### Context Pipeline (Actual):
```
MissionParser parses -> TaskPlanner plans -> TaskGraph builds ->
RuntimeAdapter executes -> ExecutionEngine builds messages ->
  - developer message (section-specific instructions)
  - user message (goal + template content + knowledge)
-> QueryLoop appends _message_history (sliding window, last 5 turns)
-> LLM API
```

### Context Architecture Issues:
- **context/ folder is dead code** — never imported by active path
- `execution/context_compaction.py` exists but QueryLoop uses **sliding window** (not compaction) as its primary mechanism
- `execution/session_memory.py` — Memory extraction for compaction, partially wired
- `execution/system_prompt.py` — System prompt builder, actively used
- `prompt/prompt_manager.py`, `prompt/prompt_registry.py`, `prompt/prompt_template.py` — Unused scaffolding

---

## 11. Context Compaction Quality

**Primary mechanism: Sliding window** (QueryLoop line 307-310, keeps last 5 turns)

**Secondary mechanism: ContextCompactPipeline** (execution/context_compaction.py) — has TokenBudgetEnforcer, ContextSummarizer, etc. but is **not used** in the active path.

**When compaction occurs:** Never in the active path. Sliding window handles context size.

**What is preserved:** Last 5 turns of conversation (messages + tool results)

**What is discarded:** Older turns beyond 5

**Whether task state survives:** No — only conversation history. Task execution context (section_number, template, etc.) is in the base messages.

**Long-running tasks:** Supported via sliding window (last 5 turns) + base messages. For a 20-turn generation with tool calls, this may lose context.

---

## 12. File Editing System

### Actual implementation: FileEdit tool (execution/builtins/file_edit.py)

**Operation:** Read file -> replace lines[start-1:end] with insert_content

**What's missing vs ideal:**
- No patch/diff generation
- No stale-file detection
- No concurrent modification protection
- No atomic writes (uses simple write_text)
- No syntax validation
- No rollback on failure
- No edit history tracking
- No failed patch recovery

**ProposeContentEdit** exists but is a stub tool.

**DiffEngine** (platform/artifacts/diff_engine.py) exists but is **never used** in the active path.

---

## 13. Verification/Repair Loop

### Verdict: **ALL STUBS — NOT WIRED**

| Engine | File | Status | Active? |
|--------|------|--------|---------|
| ReflectionEngine | cognitive/reflection_engine.py | STUB | NO — always returns simulated decisions |
| VerifierEngine | cognitive/verifier_engine.py | STUB | NO — always returns passed=True |
| RepairEngine | cognitive/repair_engine.py | STUB | NO — returns simulated RepairPlan |

### Execution path:
```
QueryLoop -> LLM returns text only -> ExecutionEngine returns result -> DONE
```

There is **no verification step**, **no repair loop**, **no failure classification**. The LLM just produces text and it's returned. If the LLM produces bad content, the system has no mechanism to detect or repair it.

---

## 14. State Architecture

### Every State Model:

| Name | Owner | Created by | Modified by | Persisted? | Lifecycle |
|------|-------|-----------|-------------|------------|-----------|
| `AgentStateStore` (core/agent_state.py) | ExecutionEngine | auto | execute_task() | NO | Per-task, in-memory |
| `TaskState` (execution/task_state.py) | Stub | - | - | - | Unused |
| `ReasoningState` (domain/reasoning_state.py) | ReasoningEngine stub | - | - | - | Unused |
| `RuntimeState` (runtime/state_machine.py) | RuntimeAdapter | __init__ | transition() | NO | Per-RuntimeAdapter, in-memory |
| `SessionRecord` (execution/session_manager.py) | GenerationSessionManager | create() | _save() | YES (JSON files) | Per-session, file-based |

### Duplicate state concepts:
- `AgentStateStore` and `RuntimeState` — Two parallel state tracking mechanisms. RuntimeState is per-worker (RuntimeAdapter) but only tracks CREATED->READY->RUNNING->COMPLETED/FAILED. AgentStateStore tracks loop_count, version_data per turn.
- `MissionStateManager` and `SessionRecord.progress` — MissionStateManager tracks completed_tasks count. SessionRecord tracks progress percentage. Both updated in MissionOrchestrator.

---

## 15. Session/Memory Architecture

### Session Lifecycle:
```
GenerationSessionManager.create() -> writes JSON to .ArchTech/{project_id}/sessions/
    -> MissionOrchestrator executes sections
    -> GenerationSessionManager.update_progress() on each section
    -> GenerationSessionManager.log_stage_complete() after each section
    -> On cancel: GenerationSessionManager.cancel()
    -> On progress query: GenerationSessionManager.get_progress() -> reads latest session JSON
```

### Memory Systems:

| System | File | Active? | Purpose |
|--------|------|---------|---------|
| StoreManager + 3 stores | memory/ | NO | M2/M3 architecture — never used |
| SessionMemoryExtractor | execution/session_memory.py | PARTIALLY | Compaction summary extraction |
| SessionRecord | execution/session_manager.py | YES | Progress tracking, tool call logs |

### Gaps:
- No persistent state between mission runs
- No checkpoint/resume within a session
- Working memory and scratchpad stores are dead code

---

## 16. Observation/Knowledge

### Event Bus Architecture:

| Bus | File | Type | Active? | Used By |
|-----|------|------|---------|---------|
| ObservationBus | event_bus.py (typed) | Sync, EventType enum | YES | ChatAgentKernel lifecycle |
| AsyncEventBus | event_bus.py | Async, string-based | YES | ExecutionEngine, GenerationAgentKernel |
| InfraEventBus | event_bus.py | Sync, minimal | YES | RuntimeAdapter (state machine) |
| ObservationBus (knowledge/) | knowledge/observation_bus.py | Sync, ObservationManager | NO | Dead code |

### Data Flow (Actual):
```
Tool Result -> ExecutionEngine -> AsyncEventBus.emit("ToolFinished"/"TurnCompleted")
    -> GenerationAgentKernel._on_tool_finished (logs only)
```

### Evidence/Knowledge:
The knowledge/ folder contains ObservationManager, ObservationEngine, ObservationParser, EvidenceManager — all **unused scaffolding** from M2/M3. The actual "knowledge" is just a text block injected into the LLM prompt by MissionParser.

---

## 17. Runtime/Recovery

### Checkpoint/Recovery:
- `runtime/checkpoint_manager.py` — Exists but **never used** in the active path
- `runtime/replay_engine.py` — Exists but **unused**
- `runtime/cancellation_manager.py` — Used by RuntimeAdapter
- `runtime/failure_classifier.py` — Used by RetryManager (in lease_manager.py), but RetryManager is **never called**

### Survival analysis:
| Failure Type | Survival | Notes |
|-------------|----------|-------|
| LLM failure | YES | Retry + fallback chain |
| Tool failure | YES | Returns error to LLM |
| Network failure | YES | Via retry mechanism |
| Timeout | PARTIAL | Bash has timeout, LLM has retry but no hard timeout |
| Process interruption | NO | No checkpoint persistence |
| Cancellation | YES | AbortController + session cancel |
| Context overflow | PARTIAL | Sliding window, no hard limit |
| Worker failure | PARTIAL | Single-worker fallback |

---

## 18. Pause/Resume/Cancel

### Pause:
- `execution/pause_manager.py:is_paused()` checked in MissionOrchestrator loop
- `execution/pause_manager.py:set_paused()` called from routes.py
- **Gap:** Only checked at section boundary, not during LLM call or tool execution

### Cancel:
- `execution/abort_controller.py:abort_tree()` — aborts tasks and hierarchies
- `agents/routes.py:cancel_document_generation()` — finds session, calls abort
- **Gap:** No propagation to LLM API call, no cleanup of background tasks

### State Machine Transitions:
RuntimeState has: CREATED->READY->RUNNING->COMPLETED/FAILED/CANCELLED/Paused/WAITING_TOOL/WAITING_USER/REFLECTING/VERIFYING/REPAIRING/CHECKPOINTING
**But only** CREATED->READY->RUNNING->COMPLETED/FAILED are ever used.

---

## 19. Multi-Agent System

### Verdict: **STUB / NOT FUNCTIONAL**

| Component | File | Status |
|-----------|------|--------|
| AgentSpawner | execution/agent_spawner.py | Stub |
| AgentMailbox | execution/agent_mailbox.py | Never wired |
| AgentSpawn/Builtins | execution/builtins/agent.py | Stub |
| SendMessage | execution/builtins/send_message.py | Stub |
| Tasks | execution/builtins/tasks.py | Internal helpers |
| WorkerManagement | orchestration/worker_management.py | Dummy workers only |
| ContextIsolation | execution/context_isolation.py | Exists but never used |

### What actually happens:
- `boot_cluster()` registers 3 workers with ID "worker_001", "worker_002", "worker_003"
- Workers have capability `["bash", "python"]` — hardcoded, generic
- HeartbeatMonitor runs in background — collects empty heartbeats
- Tasks are dispatched one at a time (0.1s timeout on asyncio.wait)
- All 3 workers are essentially dummy placeholders — tasks go to a single worker

---

## 20. Permission/Safety

### Verdict: **SKELETON — NOT ENFORCED**

| Check | Status | Notes |
|-------|--------|-------|
| Tool permission | NO | All tools auto-allowed, REQUIRE_PROMPT is empty |
| Shell safety | PARTIAL | Timeout, empty command check |
| Filesystem safety | NO | No sandbox, no restricted paths |
| Git safety | NO | Git via Bash with no special handling |
| Network safety | NO | No network restrictions |
| Process safety | NO | Can kill system processes |
| Sub-agent safety | NO | Never functional |

---

## 21. Observability/Agent Trace

### Verdict: **INCOMPLETE**

| Capability | Status |
|-----------|--------|
| User request logged | YES |
| Agent decision logged | PARTIAL — tool calls logged via SessionManager |
| LLM request logged | YES — log messages |
| LLM response logged | PARTIAL — only length, not content |
| Tool call logged | YES — SessionManager.log_tool_call() |
| Tool result logged | PARTIAL — truncated (200 chars) in SSE |
| State change logged | YES — RuntimeState transitions |
| File change logged | NO |
| Verification logged | N/A — no verification |
| Failure logged | YES — error logging |
| Repair logged | N/A — no repair |
| Final result logged | YES |

### Missing: Full agent trace — no single system reconstructs the complete decision flow.

---

## 22. Streaming/UX Architecture

### What user receives:
| Event | SSE Type | Notes |
|-------|----------|-------|
| Mission started | `mission_started` | Total task count |
| Generation start | `gen_start` | Section count, version |
| Section start | `section_start` | Section number, heading |
| Progress | `progress` | Percentage, phase |
| Section chunk | `section_chunk` | 500-char markdown chunks |
| Section complete | `section_complete` | Headings, tools used |
| Task failed | `task_failed` | Error message |
| Gen complete | `gen_complete` | Total sections |

### Missing:
- Thinking/planning events
- Reading file events
- Searching events
- Editing file events (only in tool_events_queue)
- Test result events
- Waiting for approval events
- Repairing failure events
- Events are **not structured** with correlation IDs

---

## 23. Agent Kernel Audit

| Kernel | File | Purpose | Active? |
|--------|------|---------|---------|
| ChatAgentKernel | observability/agent_kernel.py | Lifecycle, budget, events | YES — exists but GenerationAgentKernel is the active one |
| GenerationAgentKernel | observability/agent_kernel.py | Task execution | YES — actively used |

### Two Kernels — Only One Used:
- **ChatAgentKernel**: Full lifecycle (start/cancel/pause/resume/cleanup), budget management, blackboard. Used by external APIs.
- **GenerationAgentKernel**: Task executor. Wires EventBus + AgentStateStore + AgentSessionManager + ExecutionEngine. **This is the active one.**

### Relationship:
They don't duplicate each other. ChatAgentKernel is for chat sessions. GenerationAgentKernel is for document generation tasks. They share ExecutionEngine.

---

## 24. Budget/Resource Governance

| Limit | Declared | Enforced | Observable |
|-------|----------|----------|------------|
| Max turns | YES (max_turns=20 per task) | YES | PARTIAL (logs) |
| Max tokens | YES (32768) | NO | NO |
| Max execution time | PARTIAL (timeout=300) | NO | NO |
| Max tool calls | NO | NO | NO |
| Max sub-agents | NO | NO | NO |
| Max command duration | YES (30s default) | YES | PARTIAL |
| Max cost | NO (BudgetManager exists but unused) | NO | NO |

### BudgetManager (observability/budget_manager.py):
Exists with start_timer(), validate(), BudgetStatus. But **never wired** into the execution path.

---

## 25. Legacy/Duplication Audit

### Component Pairs:

| Component A | Component B | Relationship | Recommendation |
|-------------|-------------|-------------|----------------|
| `context/context_builder.py` | `orchestration/context_builder.py` | DUPLICATE | Keep orchestration/, deprecate context/ |
| `context/execution_context.py` | `orchestration/contracts.py:TaskContract` | DUPLICATE | Merge |
| `context/context_selector.py` | UNUSED | UNUSED | Deprecate |
| `core/agent_state.py` | `runtime/state_machine.py` | SPECIALIZED | Keep both (different concerns) |
| `core/agent_session_manager.py` | `execution/session_manager.py` | DUPLICATE | Keep execution/, deprecate core/ |
| `core/execution_history.py` | `execution/context_compaction.py` | WRAPPER | Keep execution_history/ as it's actually used |
| `knowledge/observation_bus.py` | `event_bus.py:ObservationBus` | DUPLICATE | Keep event_bus/, deprecate knowledge/ |
| `knowledge/observation_manager.py` | UNUSED | UNUSED | Deprecate |
| `knowledge/observation_engine.py` | UNUSED | UNUSED | Deprecate |
| `knowledge/observation_parser.py` | UNUSED | UNUSED | Deprecate |
| `knowledge/evidence_manager.py` | UNUSED | UNUSED | Deprecate |
| `knowledge/knowledge_manager.py` | UNUSED | UNUSED | Deprecate |
| `memory/store_manager.py` | `execution/session_memory.py` | DUPLICATE | Keep execution/ |
| `memory/mission_store.py` | UNUSED | UNUSED | Deprecate |
| `memory/working_store.py` | UNUSED | UNUSED | Deprecate |
| `memory/scratchpad_store.py` | UNUSED | UNUSED | Deprecate |
| `reasoning/reason_engine.py` | `execution/query_loop.py` | DUPLICATE | Keep query_loop/ |
| `reasoning/turn_manager.py` | UNUSED | UNUSED | Deprecate |
| `cognitive/reflection_engine.py` | UNUSED | UNUSED | Deprecate |
| `cognitive/repair_engine.py` | UNUSED | UNUSED | Deprecate |
| `cognitive/verifier_engine.py` | UNUSED | UNUSED | Deprecate |
| `action/action_planner.py` | UNUSED | UNUSED | Deprecate |
| `action/action_executor.py` | UNUSED | UNUSED | Deprecate |
| `action/tool_router.py` | UNUSED | UNUSED | Deprecate |
| `prompt/prompt_manager.py` | `execution/system_prompt.py` | DUPLICATE | Keep system_prompt/ |
| `prompt/prompt_registry.py` | UNUSED | UNUSED | Deprecate |
| `prompt/prompt_template.py` | UNUSED | UNUSED | Deprecate |
| `orchestration/planner_engine.py` | UNUSED | UNUSED | Deprecate |
| `orchestration/task_planner.py` | UNUSED | UNUSED | Deprecate |
| `orchestration/workflow.py` | UNUSED | UNUSED | Deprecate |
| `observability/agent_kernel.py:ChatAgentKernel` | `observability/blackboard.py` | WRAPPER | Blackboard unused |
| `platform/artifacts/diff_engine.py` | UNUSED | UNUSED | Deprecate |
| `platform/artifacts/artifact_manager.py` | UNUSED | UNUSED | Deprecate |
| `platform/execution/sandbox_manager.py` | UNUSED | UNUSED | Deprecate |
| `platform/llm/*` | UNUSED | UNUSED | Deprecate |
| `execution/builtins/tasks.py` | INTERNAL | YES | Internal task helpers |
| `execution/agent_spawner.py` | `execution/builtins/agent.py` | DUPLICATE | Deprecate both |
| `execution/agent_mailbox.py` | `execution/builtins/send_message.py` | DUPLICATE | Deprecate both |
| `infrastructure/policy_manager.py` | UNUSED | UNUSED | Deprecate |
| `infrastructure/telemetry_manager.py` | UNUSED | UNUSED | Deprecate |
| `journal/execution_journal.py` | UNUSED | UNUSED | Deprecate |
| `observability/budget_manager.py` | UNUSED | UNUSED | Deprecate |
| `observability/agent_kernel.py` (unused imports) | `__init__.py` | WRAPPER | ChatAgentKernel exported but not used by active path |
| `domain/*` models | UNUSED | UNUSED | All domain models are dead code |
| `runtime/dispatch_manager.py` | UNUSED | UNUSED | Deprecate |
| `runtime/interrupt_manager.py` | UNUSED | UNUSED | Deprecate |
| `orchestration/traceability_builder.py` | YES | ACTIVE | Used for traceability injection |
| `orchestration/section_registry.py` | YES | ACTIVE | Section parsing |
| `orchestration/contracts.py` | YES | ACTIVE | Used by RuntimeAdapter |
| `orchestration/dependency_graph.py` | YES | ACTIVE | Section dependencies |
| `orchestration/scheduling_manager.py` | YES | ACTIVE | Task dispatch |
| `orchestration/result_layer.py` | YES | ACTIVE | Result processing |
| `repository/*` | YES | ACTIVE | Repo index/query used |
| `platform/llm/*` | UNUSED | UNUSED | Deprecate |

---

## 26. Dependency Violations

### Upward dependencies (lower layers calling higher layers):
| Violation | Direction | Severity |
|-----------|-----------|----------|
| `platform/llm/builder.py` depends on `system_config` | infra -> platform | MEDIUM |
| `execution/builtins/*` import `AgentCore.shared.types` | execution -> shared | OK (intentional) |
| `orchestration/mission_layer.py` imports `system_config` | orchestration -> infra | MEDIUM |
| `execution/session_manager.py` imports `system_config` | execution -> infra | MEDIUM |
| `platform/artifacts/diff_engine.py` — unused, imports platform | platform -> execution | LOW |

### Circular dependencies:
- None detected in active path.

### Infrastructure leaking into domain:
- `domain/` models are never imported by active path — they're dead code.
- `system_config` called from orchestration layer — should be abstracted.

---

## 27. Test Coverage Analysis

### Tests present:
| Test File | Tests | Covers What? |
|-----------|-------|-------------|
| `test_execution_history.py` | Context compaction | PARTIAL |
| `test_m5_integration.py` | M5 integration | PARTIAL |
| `test_milestone_2.py` | M2 milestone | STUB tests |
| `test_milestone_3.py` | M3 milestone | STUB tests |
| `test_milestone_4.py` | M4 milestone | PARTIAL |
| `test_milestone_4_5.py` | M4.5 milestone | PARTIAL |
| `test_milestone_5.py` | M5 milestone | PARTIAL |
| `test_runtime_concurrency.py` | Concurrency | PARTIAL |
| `test_runtime_correctness.py` | Correctness | PARTIAL |
| `test_runtime_governance.py` | Governance | PARTIAL |
| `test_runtime_performance.py` | Performance | PARTIAL |
| `test_runtime_recoverability.py` | Recovery | STUB |
| `test_runtime_reliability.py` | Reliability | PARTIAL |

### Important runtime behaviors with NO tests:
- Tool validation failure path
- Permission denied path
- LLM failure + retry + fallback
- Context compaction (sliding window truncation)
- Cancellation propagation
- Session persistence/recovery
- Section dependency ordering
- Multi-worker dispatch

---

## 28. Coding-Agent Capability Matrix

| Capability | Exists | Wired | Reliable | Production Ready | Evidence |
|-----------|--------|-------|----------|-----------------|----------|
| Autonomous agent loop | YES | YES | PARTIAL | NO | ExecutionEngine + QueryLoop |
| Multi-turn tool use | YES | YES | YES | YES | QueryLoop _execute_tools |
| Repository exploration | PARTIAL | YES | PARTIAL | NO | RepositoryQueryEngine (stub find_callers) |
| Code search | YES | YES | YES | YES | Search builtin |
| Symbol/reference understanding | PARTIAL | YES | NO | NO | find_symbol works, find_callers is stub |
| Context selection | YES | YES | PARTIAL | PARTIAL | Sliding window, last 5 turns |
| Context compaction | YES | PARTIAL | PARTIAL | NO | ContextCompactPipeline exists but unused |
| File editing | YES | YES | PARTIAL | NO | FileEdit — no diff/stale detection |
| Patch/diff | NO | NO | NO | NO | diff_engine.py is stub |
| Shell execution | YES | YES | YES | YES | Bash builtin with timeout |
| Git operations | PARTIAL | YES | YES | YES | Via Bash tool |
| Test execution | PARTIAL | YES | YES | YES | Via Bash tool |
| Automatic verification | NO | NO | NO | NO | VerifierEngine is stub |
| Automatic repair | NO | NO | NO | NO | RepairEngine is stub |
| Failure recovery | PARTIAL | PARTIAL | NO | NO | RetryManager exists but unused |
| Permission approval | PARTIAL | PARTIAL | NO | NO | PermissionManager skeleton |
| Cancellation | YES | YES | PARTIAL | PARTIAL | AbortController |
| Pause/resume | PARTIAL | PARTIAL | PARTIAL | NO | Checked at section boundary only |
| Session persistence | YES | YES | YES | YES | GenerationSessionManager |
| Checkpoint/resume | NO | NO | NO | NO | checkpoint_manager.py unused |
| Agent trace | PARTIAL | PARTIAL | NO | NO | SessionManager logs, no full trace |
| Streaming events | YES | YES | YES | YES | SSE streaming |
| Sub-agents | NO | NO | NO | NO | AgentSpawner is stub |
| Context isolation | PARTIAL | NO | NO | NO | context_isolation.py exists but unused |
| Token/cost budgets | PARTIAL | NO | NO | NO | BudgetManager exists but unused |
| Long-running tasks | PARTIAL | PARTIAL | NO | NO | Sliding window, no compaction |

---

## 29. Behavioral Gap Analysis

### Simple task: "Fix the typo in README.md"

**Expected:** Read README -> Detect typo -> Edit -> Verify diff -> Done

**Actual:**
1. Route creates MissionOrchestrator for the project
2. MissionParser reads template sections (not README-related)
3. TaskPlanner creates section tasks (not typo fix tasks)
4. Each section gets 20 turns of LLM interaction
5. LLM receives section-specific developer instructions
6. FileEdit tool is available but...
7. **The system is built for document generation, not bug fixing**

**Gap:** The system has a **fixed document generation workflow** hardcoded in routes.py and MissionOrchestrator. There is no general-purpose task understanding. The system always generates SRS sections, never adapts to arbitrary user requests.

### Missing behavioral capability:
The system is a **document generation pipeline**, not a **general-purpose coding agent**. There is no "understand task -> inspect repo -> plan -> execute" flow. Every request goes through the same document generation path regardless of what the user actually wants.

---

## 30. Missing Runtime Concepts

### GAP-001: Task Intent Understanding
- **Why needed:** System must understand what the user wants before executing
- **Current substitute:** Fixed document generation workflow
- **Why insufficient:** Cannot handle arbitrary coding tasks
- **Where it belongs:** Front of MissionParser or a new IntentParser
- **Priority:** P0

### GAP-002: General-Purpose Task Planning
- **Why needed:** Break down arbitrary tasks into executable steps
- **Current substitute:** Hardcoded section-by-section template generation
- **Why insufficient:** Only works for document generation
- **Where it belongs:** MissionParser or a new TaskPlanner
- **Priority:** P0

### GAP-003: Verification Cycle
- **Why needed:** Ensure produced output meets quality criteria
- **Current substitute:** None
- **Why insufficient:** Bad LLM output is accepted without checking
- **Where it belongs:** cognitive/verifier_engine.py (needs implementation)
- **Priority:** P1

### GAP-004: Automatic Repair
- **Why needed:** When verification fails, the agent should attempt to fix
- **Current substitute:** None
- **Why insufficient:** Once LLM produces output, it's done regardless of quality
- **Where it belongs:** cognitive/repair_engine.py (needs implementation)
- **Priority:** P1

### GAP-005: Repository Context
- **Why needed:** Agent should understand repo structure before editing
- **Current substitute:** None
- **Why insufficient:** LLM guesses at repo structure
- **Where it belongs:** injection into ExecutionEngine messages
- **Priority:** P1

### GAP-006: Full Agent Trace
- **Why needed:** Reconstruct every decision for debugging
- **Current substitute:** Partial logging
- **Why insufficient:** Cannot trace full decision flow
- **Where it belongs:** observability/ or a new trace module
- **Priority:** P1

### GAP-007: Checkpoint/Resume
- **Why needed:** Survive process interruption
- **Current substitute:** None
- **Why insufficient:** All progress lost on crash
- **Where it belongs:** runtime/checkpoint_manager.py (needs implementation)
- **Priority:** P1

### GAP-008: Diff-Based Editing
- **Why needed:** Safe, reversible file edits
- **Current substitute:** Range-based FileEdit
- **Why insufficient:** No patch tracking, no concurrent modification detection
- **Where it belongs:** execution/builtins/file_edit.py or platform/artifacts/diff_engine.py
- **Priority:** P1

### GAP-009: Permission Approval Flow
- **Why needed:** Prevent dangerous operations
- **Current substitute:** Empty REQUIRE_PROMPT set
- **Why insufficient:** All tools execute without approval
- **Where it belongs:** execution/permission_manager.py
- **Priority:** P1

---

## 31. Gap Priority

### P0 — Fundamental (system cannot behave like a coding agent without these):

| ID | Name | Impact |
|----|------|--------|
| GAP-001 | Task Intent Understanding | System only generates documents, nothing else |
| GAP-002 | General-Purpose Task Planning | No arbitrary task execution |

### P1 — Major (required for strong coding-agent behavior):

| ID | Name | Impact |
|----|------|--------|
| GAP-003 | Verification Cycle | Bad output accepted without checking |
| GAP-004 | Automatic Repair | No recovery from failures |
| GAP-005 | Repository Context | Agent blind to repo structure |
| GAP-006 | Full Agent Trace | Debugging impossible for complex failures |
| GAP-007 | Checkpoint/Resume | All progress lost on crash |
| GAP-008 | Diff-Based Editing | Unsafe file modifications |
| GAP-009 | Permission Approval | No guardrails on dangerous operations |

### P2 — Advanced (useful after core is reliable):

| ID | Name | Impact |
|----|------|--------|
| - | Multi-Agent Runtime | Currently all stubs |
| - | Advanced Knowledge Graph | knowledge/ is dead code |
| - | Long-Term Memory | memory/ stores are dead code |
| - | Budget Enforcement | BudgetManager exists but unused |
| - | Performance Optimization | No profiling or caching |

---

## 32. Target Architecture

The current architecture is a **document generation pipeline** that needs to become a **general-purpose coding agent runtime**.

### Conceptual target:
```
                         USER
                           |
                           v
                      ┌──────────┐
                      │  ROUTES  │  (FastAPI SSE streaming)
                      └────┬─────┘
                           v
                      ┌──────────┐
                      │  AGENT   │  (IntentParser + TaskPlanner)
                      │  KERNEL  │
                      └────┬─────┘
                           v
                      ┌──────────┐
                      │  AGENT   │  (ExecutionEngine + QueryLoop)
                      │   LOOP   │
                      └────┬─────┘
                           |
              ┌────────────┼────────────┐
              v            v            v
           CONTEXT      PLANNER      MEMORY
              |            |            |
              └────────────┼────────────┘
                           v
                           LLM
                           |
                           v
                      TOOL CALL
                           |
                           v
                    PERMISSION/POLICY
                           |
                           v
                       EXECUTOR
                           |
           ┌───────────────┼───────────────┐
           v               v               v
        SEARCH           EDIT            BASH
           |               |               |
           └───────────────┼───────────────┘
                           v
                      OBSERVATION
                           |
                           v
                         STATE
                           |
                           v
                       VERIFY
                      /       \
                   PASS       FAIL
                    |           |
                    v           v
                  DONE        REPAIR
                                |
                                └─────► AGENT LOOP
```

### Adaptation to actual codebase:
1. `routes.py` stays as HTTP entry point (or add new agent route)
2. `MissionOrchestrator` needs to become `AgentKernel` (general-purpose, not document-specific)
3. `ExecutionEngine` + `QueryLoop` are the active loop — keep and extend
4. `RuntimeAdapter` can be kept as execution boundary
5. Cognitive engines need real implementation (not stubs)
6. Tool system is good — just needs permission wiring + new tools
7. Context system needs repository intelligence injection
8. Memory system needs to replace dead code with working implementation

---

## 33. File-to-Target Classification

### CORE_RUNTIME (actively powers the agent):
- `agents/routes.py` — HTTP entry point + SSE streaming
- `execution/query_loop.py` — LLM interaction loop
- `execution/tool_executor.py` — Tool invocation
- `execution/tool_registry.py` — Tool registration
- `execution/session_manager.py` — Session progress tracking
- `execution/system_prompt.py` — System prompt builder
- `execution/abort_controller.py` — Cancellation
- `execution/pause_manager.py` — Pause/resume
- `execution/transcript_writer.py` — Session transcripts
- `execution/token_usage_tracker.py` — Token tracking
- `execution/builtins/file_read.py` — File reading
- `execution/builtins/file_write.py` — File writing
- `execution/builtins/file_edit.py` — File editing
- `execution/builtins/bash.py` — Bash execution
- `execution/builtins/glob.py` — File pattern matching
- `execution/builtins/search.py` — Code search
- `execution/builtins/request_user_input.py` — User interaction
- `execution/builtins/propose_content_edit.py` — Content editing
- `execution/builtins/send_message.py` — Messaging
- `core/execution_engine.py` — Turn management
- `core/agent_state.py` — Agent state store
- `core/execution_history.py` — Turn history + context management
- `shared/types.py` — Input model schemas
- `shared/exceptions.py` — Custom exceptions

### AGENT_CAPABILITY (actively used but needs enhancement):
- `orchestration/orchestrator.py` — Mission control (needs de-document-gen focus)
- `orchestration/mission_layer.py` — Task planning (needs general-purpose)
- `orchestration/runtime_adapter.py` — Execution boundary
- `orchestration/lease_manager.py` — Task queue + dispatch
- `orchestration/scheduling_manager.py` — Scheduling policy
- `orchestration/contracts.py` — Agent contracts
- `orchestration/worker_management.py` — Worker catalog
- `orchestration/section_registry.py` — Section parsing
- `orchestration/dependency_graph.py` — Dependency tracking
- `orchestration/traceability_builder.py` — Traceability data
- `observability/agent_kernel.py` — Task execution kernel
- `observability/blackboard.py` — Shared state (unused by active path)
- `observability/budget_manager.py` — Budget tracking (unused)
- `event_bus.py` — Event publishing (partially used)
- `platform/artifacts/diff_engine.py` — Diff engine (stub)
- `platform/artifacts/artifact_manager.py` — Artifact management (stub)
- `execution/context_compaction.py` — Context compaction (partially used)
- `execution/session_memory.py` — Session memory (partially used)
- `execution/message_manager.py` — Message handling (partially used)
- `execution/context_isolation.py` — Context isolation (stub)
- `knowledge/*` — Knowledge graph (all stubs)

### DOMAIN_MODEL (data structures, not executable):
- `domain/action_result.py` — Dead code
- `domain/action_decision.py` — Dead code
- `domain/execution_plan.py` — Dead code
- `domain/reasoning_state.py` — Dead code
- `domain/runtime_policy.py` — Dead code

### INFRASTRUCTURE (supporting services):
- `repository/repo_index.py` — Code indexing
- `repository/repo_query_engine.py` — Code queries
- `repository/repo_snapshot.py` — Repo snapshots
- `repository/test_repo_intelligence.py` — Tests
- `prompt/prompt_template.py` — Prompt templates
- `prompt/prompt_registry.py` — Prompt registry

### SUPPORTING (utilities, config, helpers):
- `platform/llm/adapter.py` — LLM provider adapter
- `platform/llm/builder.py` — Prompt builder
- `platform/llm/interfaces.py` — LLM interfaces
- `platform/llm/parser.py` — Response parser
- `platform/llm/renderer.py` — Output renderer

### LEGACY (from previous milestones):
- `context/context_builder.py` — M2/M3 context builder
- `context/execution_context.py` — M2/M3 execution context
- `context/context_selector.py` — M2/M3 context selector
- `core/agent_session_manager.py` — Old session manager
- `prompt/prompt_manager.py` — Old prompt manager
- `execution/builtins/agent.py` — Agent spawning (stub)
- `execution/builtins/tasks.py` — Task helpers (internal)

### DUPLICATE (overlap with active code):
- `memory/store_manager.py` — Overlaps with session_manager
- `memory/mission_store.py` — Overlaps with mission_layer
- `memory/working_store.py` — Overlaps with session_memory
- `memory/scratchpad_store.py` — No working equivalent
- `knowledge/observation_bus.py` — Overlaps with event_bus.ObservationBus
- `knowledge/observation_manager.py` — Overlaps with session_memory
- `knowledge/observation_engine.py` — No active equivalent
- `knowledge/observation_parser.py` — No active equivalent
- `knowledge/evidence_manager.py` — No active equivalent
- `knowledge/knowledge_manager.py` — No active equivalent
- `reasoning/reason_engine.py` — Overlaps with QueryLoop
- `reasoning/turn_manager.py` — No active equivalent
- `action/action_planner.py` — No active equivalent
- `action/action_executor.py` — No active equivalent
- `action/tool_router.py` — No active equivalent
- `orchestration/planner_engine.py` — No active equivalent
- `orchestration/task_planner.py` — No active equivalent
- `orchestration/workflow.py` — No active equivalent
- `cognitive/reflection_engine.py` — No active equivalent
- `cognitive/repair_engine.py` — No active equivalent
- `cognitive/verifier_engine.py` — No active equivalent
- `infrastructure/policy_manager.py` — No active equivalent
- `infrastructure/telemetry_manager.py` — No active equivalent
- `journal/execution_journal.py` — No active equivalent
- `runtime/dispatch_manager.py` — No active equivalent
- `runtime/interrupt_manager.py` — No active equivalent
- `runtime/checkpoint_manager.py` — No active equivalent
- `runtime/replay_engine.py` — No active equivalent
- `runtime/failure_classifier.py` — Partial (used by RetryManager)
- `observability/agent_kernel.py` — Only GenerationAgentKernel is used

### TEST_ONLY:
- All files in `_Testing_milestone/`

### UNCLEAR:
- `execution/agent_spawner.py` — Stub, but agent.py in builtins may use it
- `execution/agent_cleanup.py` — Unknown who calls it
- `execution/budget_manager.py` — Not present (in observability/)
- `orchestration/context_builder.py` — Used by mission_layer but unclear by whom

---

## CURRENT vs TARGET Side-by-Side

### CURRENT: "Fix a typo in README.md"

```
1. POST /generate-document-stream with project_id
2. MissionOrchestrator created for project
3. MissionParser reads template sections from project directory
4. TaskPlanner creates tasks for each section
5. TaskGraphBuilder builds dependency DAG
6. For each section:
   a. Build task with section context (template, knowledge, memory)
   b. Dispatch to RuntimeAdapter
   c. GenerationAgentKernel executes with LLM
   d. LLM receives: goal + template content + knowledge + developer instructions
   e. LLM may call FileRead, Glob, Search (tools)
   f. LLM returns text (section markdown)
   g. Text saved to versioned JSON
7. SSE stream emits section chunks
8. Done
```

### TARGET: "Fix a typo in README.md"

```
1. User submits request
2. IntentParser understands: "Fix typo in README.md" = file edit task
3. TaskPlanner breaks into: Read README.md -> Find typo -> Edit file -> Verify
4. AgentKernel starts loop:
   a. Build context from repo state + task plan
   b. LLM reads README.md
   c. LLM identifies typo
   d. LLM plans edit
   e. ToolExecutor applies FileEdit
   f. Verification: Read file, confirm fix
   g. If verification passes: return "Fixed: [description]"
   h. If verification fails: Repair -> retry
5. SSE stream emits progress events
6. Done
```

### The Difference = The Backlog

The gap between these two flows is **the actual AgentCore development backlog**. The current system is a document generation pipeline. The target is a general-purpose coding agent.

The backlog is not "add more files" — it's "restructure the existing pipeline to be task-agnostic and verification-driven."

---

## Recommended Implementation Roadmap

### PHASE 0 — Stabilize and Clean

**Goal:** Establish clean foundation by removing dead code and clarifying active path.

**Existing components to reuse:**
- `execution/query_loop.py` — Keep as-is
- `execution/tool_executor.py` — Keep as-is
- `execution/tool_registry.py` — Keep as-is
- `execution/builtins/*` — Keep as-is
- `core/execution_engine.py` — Keep as-is
- `event_bus.py` — Keep AsyncEventBus + ObservationBus, de InfraEventBus

**Components to merge:**
- `orchestration/mission_layer.py:TaskPlanner` -> rename to general TaskPlanner
- `orchestration/runtime_adapter.py` -> keep as execution boundary wrapper

**Components to deprecate:**
- All of `context/` (3 files) -> merge into `orchestration/context_builder.py`
- All of `knowledge/` (6 files) -> not needed for M6
- All of `reasoning/` (2 files) -> not needed
- All of `action/` (3 files) -> not needed
- All of `cognitive/` (3 files) -> needs real implementation in Phase 4
- All of `memory/` (4 files) -> merge working_store into session_memory
- `prompt/` (3 files) -> merge into execution/system_prompt.py
- `domain/` (5 files) -> not needed
- `infrastructure/` (2 files) -> not needed
- `journal/` (1 file) -> not needed
- `orchestration/planner_engine.py`, `task_planner.py`, `workflow.py` -> not needed
- `platform/llm/` (5 files) -> not needed
- `platform/artifacts/` (2 files) -> not needed
- `platform/execution/` (1 file) -> not needed
- `core/agent_session_manager.py` -> merge into execution/session_manager.py
- `observability/budget_manager.py` -> keep but wire in
- `observability/blackboard.py` -> keep, wire into ExecutionEngine

**New concepts required:** None (just cleanup)

**Dependencies:** None

**Risks:** None — this is dead code removal only.

**Validation tests:** All existing tests should still pass.

**Completion criteria:** 0 unused imports, all active imports point to verified files.

---

### PHASE 1 — General-Purpose Task Intent

**Goal:** System can understand and process arbitrary user requests, not just document generation.

**Existing components to reuse:**
- `agents/routes.py` — Keep, add new endpoint

**Components to merge:**
- Replace MissionOrchestrator with a general-purpose AgentRouter

**New concepts required:**
- IntentParser — understands user requests
- GeneralTaskPlanner — breaks down arbitrary tasks
- TaskResultAggregator — collects results from subtasks

**Dependencies:** Phase 0

**Risks:** Major — changes the fundamental behavior of the system

**Validation tests:** Test with: "fix typo in README", "add a function to X", "explain Y module"

**Completion criteria:** System processes arbitrary text requests, not just document generation.

---

### PHASE 2 — Wire and Implement Verification

**Goal:** Every task output is verified before being returned.

**Existing components to reuse:**
- `cognitive/verifier_engine.py` — needs real implementation
- `cognitive/repair_engine.py` — needs real implementation
- `cognitive/reflection_engine.py` — needs real implementation

**New concepts required:**
- VerificationResult model
- RepairPlan model
- Verification loop in ExecutionEngine

**Dependencies:** Phase 1

**Risks:** Medium — adds complexity to execution loop

**Validation tests:** Test with: "generate incorrect content" -> verification should catch and repair

**Completion criteria:** System verifies its own output and repairs failures autonomously.

---

### PHASE 3 — Repository Intelligence Upgrade

**Goal:** Agent can understand code structure, not just files.

**Existing components to reuse:**
- `repository/repo_index.py` — Keep
- `repository/repo_query_engine.py` — Fix find_callers() stub

**New concepts required:**
- Symbol-aware reference resolution
- AST-based import/dependency analysis

**Dependencies:** Phase 0

**Risks:** Low — extends existing repo intelligence

**Validation tests:** Test: "who calls X?" returns correct results

**Completion criteria:** Agent can answer "who calls this function" and "what depends on this module".

---

### PHASE 4 — Safe File Editing

**Goal:** File edits are safe, traceable, and reversible.

**Existing components to reuse:**
- `execution/builtins/file_edit.py` — extends

**Components to merge:**
- `platform/artifacts/diff_engine.py` — needs implementation

**New concepts required:**
- Stale file detection
- Edit verification (re-read after edit)
- Atomic writes with rollback

**Dependencies:** Phase 0

**Risks:** Low — replaces current file editing

**Validation tests:** Test: concurrent edits, stale files, syntax errors

**Completion criteria:** All file edits go through safe editing pipeline.

---

### PHASE 5 — Permission and Safety System

**Goal:** Dangerous operations require approval.

**Existing components to reuse:**
- `execution/permission_manager.py` — wire up

**New concepts required:**
- Policy definitions
- Permission UI integration

**Dependencies:** Phase 0

**Risks:** Low — just populates REQUIRE_PROMPT set

**Validation tests:** Test: Bash execute dangerous command -> blocked until approved

**Completion criteria:** All dangerous tools require user approval in REQUIRE_PROMPT mode.

---

### PHASE 6 — Agent Trace + Streaming UX

**Goal:** Full observability of agent decisions.

**Existing components to reuse:**
- `execution/transcript_writer.py` — extend
- `observability/agent_kernel.py` — wire into execution path

**New concepts required:**
- AgentTrace class — captures full decision flow
- SSE event taxonomy

**Dependencies:** Phase 0

**Risks:** Low — observability only

**Validation tests:** Test: full decision reconstruction from trace

**Completion criteria:** Every agent action is traceable from user request to final output.

---

### PHASE 7 — Recovery and Checkpointing

**Goal:** Agent survives process interruption.

**Existing components to reuse:**
- `runtime/checkpoint_manager.py` — needs implementation
- `runtime/replay_engine.py` — needs implementation

**New concepts required:**
- Checkpoint serialization
- Recovery point identification

**Dependencies:** Phase 6

**Risks:** Medium — adds persistence layer

**Validation tests:** Test: kill agent mid-task, resume from checkpoint

**Completion criteria:** Agent can resume from last checkpoint after crash.

---

### PHASE 8 — Multi-Agent Runtime

**Goal:** Agent can spawn sub-agents for parallel work.

**Existing components to reuse:**
- `execution/agent_spawner.py` — needs real implementation
- `execution/agent_mailbox.py` — needs real implementation
- `orchestration/worker_management.py` — extends

**New concepts required:**
- Sub-agent lifecycle
- Inter-agent communication protocol
- Task decomposition for parallelization

**Dependencies:** Phase 2

**Risks:** High — adds concurrency complexity

**Validation tests:** Test: parallel file edits by different sub-agents

**Completion criteria:** Agent can safely spawn and coordinate sub-agents.

---

## Most Important Question

### "If I gave this AgentCore to a developer and asked it to 'fix a bug in an unfamiliar repository', what exact sequence of events would happen today?"

1. Developer calls POST /generate-document-stream with project_id
2. MissionOrchestrator initializes with 3 dummy workers
3. MissionParser reads template sections from the project's template directory
4. TaskPlanner creates tasks based on section definitions (NOT based on the bug description)
5. For each section, an LLM is called with section-specific instructions (e.g., "Generate functional requirements for Section 06")
6. The LLM reads template content and knowledge data — NOT the repository's code
7. The LLM produces section-specific markdown (e.g., functional requirement text)
8. This is saved to a versioned JSON file and streamed back as SSE events

**Result:** The agent generates a document section. It does NOT inspect the repository, find the bug, or fix it. The entire system is a document generation pipeline with no general-purpose task understanding.

### "What exact sequence should happen in the target Claude/Cursor/Codex-like runtime?"

1. Developer submits: "Fix the login API bug in auth.py"
2. IntentParser understands: this is a code fix task, not document generation
3. TaskPlanner breaks into: Read auth.py -> Understand the bug -> Find related tests -> Fix -> Run tests -> Verify
4. AgentKernel executes:
   a. LLM reads auth.py via FileRead
   b. LLM runs grep/glob to find call sites
   c. LLM reads related tests
   d. LLM creates plan for the fix
   e. LLM applies FileEdit to auth.py
   f. LLM runs tests via Bash
   g. If tests pass -> Done
   h. If tests fail -> Repair loop: read failure -> fix -> re-test
   i. If verification fails -> Another repair attempt
5. Result: Bug fixed, tests passing, changes tracked

### The difference:
- Current: Fixed document generation pipeline
- Target: Task-agnostic, verification-driven, repair-capable agent runtime

**The backlog is the gap between these two flows.**
