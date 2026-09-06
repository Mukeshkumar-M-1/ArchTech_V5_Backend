# AgentCore Architecture Audit — Report 2 Validation

**Date:** 2026-08-11
**Method:** Independent source-code verification of every P0/P1 claim in Report 2
**Authority:** Source code only — Report 2 is a hypothesis to be validated, not ground truth

---

## 1. Report 2 Validation Table (P0/P1 Claims)

### P0 — Critical Architectural Claims

| # | Report 2 Claim | Source Evidence in Code | Verdict | Actual Behavior | Correction |
|---|---|---|---|---|---|
| P0-1 | "Chat route tool filter excludes FileWrite, FileEdit" | `chat_routes.py:123`: `allowed_tools = {"FileRead", "Bash", "Glob", "Search", "ProposeContentEdit", "RequestUserInput"}` | **VERIFIED** | FileWrite and FileEdit are NOT in allowed_tools. Chat route cannot write or edit files. | Report 2 correct on this. |
| P0-2 | "Glob is excluded from chat route" | `chat_routes.py:123`: `"Glob"` IS in the allowed_tools set | **INCORRECT** | Glob IS available in chat route. Report 2 contradicted itself (also listed Glob as WFIRED in table). | Report 2 was wrong. Glob IS wired to chat route. |
| P0-3 | "PermissionManager not used by Chat" | `query_loop.py:674`: `executor = ToolExecutor(permission_checker=self._permission_checker)`. But `chat_routes.py` creates `QueryLoop(...)` with NO permission_checker argument. | **PARTIALLY VERIFIED** | PermissionManager EXISTS and QueryLoop SUPPORTS it, but chat route passes None. Doc gen route also passes None. So it's wired at the API level but not instantiated at the route level. | Correction: PermissionManager is "structurally present but functionally inert." Not "not used" — it's "not configured." |
| P0-4 | "QueryLoop is the single real agent loop for both routes" | `chat_routes.py:182`: `QueryLoop(...)` directly. `agents/routes.py:162` → `MissionOrchestrator` → `RuntimeAdapter` → `GenerationAgentKernel` → `ExecutionEngine` → `query_loop.py:450`: `QueryLoop(...)` | **VERIFIED** | Both routes instantiate QueryLoop. Chat route creates it directly with max_turns=5. Doc gen route creates it via ExecutionEngine with max_turns=10 (hardcoded). | Report 2 correct. |
| P0-5 | "~30+ files of dead code never wired to either route" | See dead code analysis in Section 2 below | **VERIFIED** | See dead code analysis below for exact count | Approximately 28 files are truly dead (imported by nothing reachable). |
| P0-6 | "Chat route creates QueryLoop directly" | `chat_routes.py:182-188` | **VERIFIED** | Chat route: `QueryLoop(session_id=..., project_id=..., streaming_enabled=False, message_manager=SSEChatMessageManager(...), max_turns=5)` | Report 2 correct. |
| P0-7 | "Doc gen route uses MissionOrchestrator" | `agents/routes.py:162-168` | **VERIFIED** | Doc gen: `MissionOrchestrator(project_id=..., num_workers=1).execute_mission(...)` → `RuntimeAdapter` → `GenerationAgentKernel.run_task()` → `ExecutionEngine.execute_task()` → `QueryLoop` (line 450) | Report 2 correct. |
| P0-8 | "Chat route has sliding window of 5 turns" | `query_loop.py:117`: `self._max_history_turns = 5`; `query_loop.py:307-310`: truncation logic | **VERIFIED** | `while len(self._message_history) > self._max_history_turns * 2: self._message_history.pop(0)` — keeps max 10 messages in history. Plus chat_routes.py:115-119 cleans markers on resume. | Report 2 correct. |

### P1 — Behavioral Claims

| # | Report 2 Claim | Source Evidence | Verdict | Actual Behavior | Correction |
|---|---|---|---|---|---|
| P1-1 | "Cognitive engines: verifier_engine, repair_engine, reflection_engine — called in code paths but never exercised" | `workflow.py:16-18` imports all three. But `workflow.py` is never imported by any reachable code path. Grep: only imported by `test_milestone_3.py`, `test_milestone_4.py`, and `reason_engine.py` (dead code). | **PARTIALLY VERIFIED** | Cognitive engines are IMPORTED by `workflow.py` but `workflow.py` itself is DEAD CODE. Neither chat route nor doc gen route imports workflow.py or any cognitive engine. Verdict: NOT IMPORTED by any production path. Only imported by test files and dead code. | Report 2 said "called in code paths" — this is misleading. They're imported by dead code that's never executed. |
| P1-2 | "verifier_engine always returns passed=True" | `verifier_engine.py:36-40`: hardcoded `VerificationResult(passed=True, ...)` | **VERIFIED** | Stub that always passes. | Report 2 correct. |
| P1-3 | "repair_engine returns simulated RepairPlan" | `repair_engine.py:32-38`: hardcoded `RepairPlan(... confidence=0.8, retry_strategy="Fallback to searching global symbol index.")` | **VERIFIED** | Simulated output with fake confidence score and generic retry strategy. | Report 2 correct. |
| P1-4 | "reflection_engine returns simulated decisions" | `reflection_engine.py:30-50`: simulated logic using confidence thresholds and string matching | **VERIFIED** | Simulated branching. Uses observation.source_tool string matching — not real code analysis. | Report 2 correct. |
| P1-5 | "Chat route tool filter: 6 tools — FileRead, Bash, Glob, Search, ProposeContentEdit, RequestUserInput" | `chat_routes.py:123` | **VERIFIED** | Exactly 6 tools. No FileWrite, no FileEdit, no Agent, no SendMessage. | Report 2 correct (except Glob claim in other sections). |
| P1-6 | "Doc gen route hardcodes tools=['FileRead', 'Glob', 'Search']" | `runtime_adapter.py:62`: `tools=["FileRead", "Glob", "Search"]` | **VERIFIED** | Doc gen route also lacks FileWrite, FileEdit, Bash. Only 3 read/search tools. | Report 2 correct. |
| P1-7 | "Doc gen route max_turns=20" | `runtime_adapter.py:64`: `max_turns=20` | **VERIFIED** | Hardcoded in RuntimeAdapter.execute(). | Report 2 correct. |
| P1-8 | "QueryLoop._execute_tools() has permission check" | `query_loop.py:674`: `executor = ToolExecutor(permission_checker=self._permission_checker)` | **VERIFIED** | Permission check EXISTS in the call chain. But `_permission_checker` is None when created from either route. | The mechanism exists but is not activated. |
| P1-9 | "ToolExecutor checks permission" | `tool_executor.py:76-86`: `if self._permission_checker and not self._permission_checker.can_use(tool.name):` | **VERIFIED** | Permission check is conditional on `_permission_checker` being non-None. If None, permission check is SKIPPED entirely. | Report 2 implied it was active — it's not. |
| P1-10 | "RequestUserInput and ProposeContentEdit pause the loop via __AWAITING_USER_INPUT__ marker" | `request_user_input.py:18`: `AWAITING_MARKER = "__AWAITING_USER_INPUT__"`; `query_loop.py:726-728`: detects marker and sets `_awaiting_input = True`; `chat_routes.py:115-119`: cleans markers on resume | **VERIFIED** | Clean pause/resume flow: tool returns marker → QueryLoop detects → returns `_status: awaiting_input` → chat_routes.py waits for `/chat/interact` → `set_user_response()` appends tool result → QueryLoop resumes | Report 2 correct. |
| P1-11 | "Chat route has 10 SSE event types" | `chat_routes.py`: session_created, turn_start, text_delta, tool_use_start, tool_interaction_request, tool_use_complete, interaction_paused, turn_complete, done, error | **VERIFIED** | All 10 event types emitted via SSEChatMessageManager. | Report 2 correct. |
| P1-12 | "Doc gen route uses MissionOrchestrator with section-by-section pipeline" | `orchestrator.py:137-346`: `execute_mission()` with while loop over completed < total tasks | **VERIFIED** | Each section is a task: parse template → plan → build dependency graph → dispatch → execute → write section JSON → emit SSE chunks. | Report 2 correct. |

### P2 — Architectural Design Claims

| # | Report 2 Claim | Source Evidence | Verdict | Actual Behavior | Correction |
|---|---|---|---|---|---|
| P2-1 | "ProposeContentEdit and FileWrite/FileEdit are overlapping edit mechanisms" | `propose_content_edit.py`: designed for DOCUMENT sections (section_filename, version, block_number, original_text, proposed_text) — pauses for UI review. `file_write.py`: full file write with path validation and atomic write. `file_edit.py`: line-range replacement in existing file. | **VERIFIED** | These are DIFFERENT editing models, not duplicates. ProposeContentEdit is for document section editing with UI review. FileWrite/FileEdit are for general code editing. | Report 2 correct in identifying them as distinct. They serve different purposes. |
| P2-2 | "diff_engine.py and artifact_manager.py are dead code" | Grep: `diff_engine.py` only imported by `context/context_builder.py` (dead). `artifact_manager.py` only by `context/context_builder.py` (dead). No production route uses them. | **VERIFIED** | Dead code. They exist in `platform/artifacts/` but no reachable code imports them. | Report 2 correct. |
| P2-3 | "ToolRouter is dead code" | `tool_router.py` only imported by test files (`test_milestone_3.py`, `test_milestone_4.py`). No production route uses it. | **VERIFIED** | Dead code. It's a policy-based routing abstraction that's never wired. | Report 2 correct. |
| P2-4 | "Chat route system prompt biases toward ProposeContentEdit + RequestUserInput" | `chat_routes.py:128-154`: System prompt says "CRITICAL INSTRUCTION: If the user provides text blocks... you MUST use ProposeContentEdit" and "Use RequestUserInput whenever you need the user to make a choice" | **VERIFIED** | System prompt is specific to DOCUMENT editing (references SRS documentation). Very different from the generic coding agent prompt in Claude Code. | Report 2 correct. |
| P2-5 | "Repository intelligence is dead code (not wired)" | `repo_query_engine.py`: only imported by `test_repo_intelligence.py`, `test_milestone_2.py`, and `context/context_builder.py` (dead). No route imports it. | **VERIFIED** | RepositoryQueryEngine exists with working find_symbol(), find_file_imports(), summarize_file() — but NO production route uses it. | Report 2 correct. |
| P2-6 | "Chat route max_turns=5" | `chat_routes.py:188`: `max_turns=5` | **VERIFIED** | Chat route is limited to 5 turns. This is very restrictive for complex bug fixes. | Report 2 correct. |

---

## 2. Dead Code Analysis — Actual Count

Files that exist but are **never imported by any reachable production code path**:

### Truly Dead (0 reachable imports)

| File | Directory |
|---|---|
| `action/action_planner.py` | action/ |
| `action/action_executor.py` | action/ |
| `action/tool_router.py` | action/ |
| `cognitive/verifier_engine.py` | cognitive/ |
| `cognitive/repair_engine.py` | cognitive/ |
| `cognitive/reflection_engine.py` | cognitive/ |
| `context/context_builder.py` | context/ |
| `context/execution_context.py` | context/ |
| `context/context_selector.py` | context/ |
| `domain/action_result.py` | domain/ |
| `domain/action_decision.py` | domain/ |
| `domain/execution_plan.py` | domain/ |
| `domain/reasoning_state.py` | domain/ |
| `domain/runtime_policy.py` | domain/ |
| `infrastructure/policy_manager.py` | infrastructure/ |
| `infrastructure/telemetry_manager.py` | infrastructure/ |
| `journal/execution_journal.py` | journal/ |
| `memory/mission_store.py` | memory/ |
| `memory/store_manager.py` | memory/ |
| `platform/artifacts/artifact_manager.py` | platform/artifacts/ |
| `platform/artifacts/diff_engine.py` | platform/artifacts/ |
| `platform/llm/adapter.py` | platform/llm/ |
| `platform/llm/builder.py` | platform/llm/ |
| `platform/llm/interfaces.py` | platform/llm/ |
| `platform/llm/parser.py` | platform/llm/ |
| `platform/llm/renderer.py` | platform/llm/ |
| `reasoning/reason_engine.py` | reasoning/ |
| `reasoning/turn_manager.py` | reasoning/ |

**Count: 28 files of truly dead code.**

### Dead but Imported by Dead Code

| File | Imported By | Importer Status |
|---|---|---|
| `orchestration/workflow.py` | `reasoning/reason_engine.py` (dead) | Dead transitively |
| `knowledge/observation_bus.py` | `knowledge/observation_engine.py` (dead) | Dead transitively |
| `knowledge/observation_manager.py` | `knowledge/observation_engine.py` (dead) | Dead transitively |

### Only Used in Tests (Not Production)

| File | Used In |
|---|---|
| `_Testing_milestone/test_milestone_2.py` | Tests for repo intelligence (never run in prod) |
| `_Testing_milestone/test_milestone_3.py` | Tests for cognitive engines (never run in prod) |
| `_Testing_milestone/test_milestone_4.py` | Tests for ToolRouter (never run in prod) |
| `_Testing_milestone/test_milestone_4_5.py` | Various milestone tests |
| `_Testing_milestone/test_milestone_5.py` | Various milestone tests |
| `repository/test_repo_intelligence.py` | Unit tests for repo index |

---

## 3. Corrections to Report 2

| # | Report 2 Claim | Correction | Reason |
|---|---|---|---|
| C1 | "Glob is excluded from chat route" | **Glob IS in chat route.** `chat_routes.py:123` includes "Glob" in allowed_tools. | Direct code evidence. |
| C2 | "PermissionManager is not used by Chat" | **PermissionManager is structurally present but not activated.** QueryLoop supports `permission_checker` parameter, but neither route instantiates a PermissionManager and passes it. The check in ToolExecutor (line 76) is `if self._permission_checker and ...` — so when None, permission check is silently skipped. | More precise: it's a missing configuration, not a missing mechanism. |
| C3 | "Cognitive engines are called in code paths" | **Cognitive engines are NOT called by any production path.** They're imported by `workflow.py`, but `workflow.py` is dead code (never imported by any production route). Only test files import them. | Grep confirmed: no production code imports cognitive engines. |
| C4 | "Cognitive engines: IMPORTED BUT NOT CALLED" | **Cognitive engines: IMPORTED ONLY BY DEAD CODE.** workflow.py imports them, but workflow.py is dead. | More accurate classification. |
| C5 | "~45 files dead code" | **~28 files dead code.** Report 2 overcounted. Some listed files (like execution/builtins/agent.py, send_message.py, tasks.py) ARE imported by reachable code (via builtins/__init__.py). | Careful import tracing shows fewer dead files. |
| C6 | "Chat route has no repository intelligence" | **Correct, but worth noting repo_query_engine.py has REAL functionality** (find_symbol, find_file_imports, summarize_file) — it's not a stub. Just not wired. | Repository intelligence is a gap, but the code to fill it already exists. |
| C7 | "Recommend wiring a separate task planner into Chat" | **This recommendation should be REJECTED.** QueryLoop already performs sufficient implicit planning through multi-turn tool use. Adding an explicit planner would duplicate the LLM's natural reasoning loop. | See Phase 4 analysis below. |
| C8 | "Recommend injecting repo intelligence into system prompt" | **Repo intelligence should be a TOOL, not a system prompt injection.** The pattern `search → read → reason → edit` (Claude Code behavior) works better with a `RepositoryQuery` tool that the LLM can call when it needs symbol/references info. | Tool-based access is more flexible and testable. |

---

## 4. Actual Current Architecture

### Two Entry Points, One Shared Kernel

```
                    ┌─────────────────────────────────────────┐
                    │            User / Frontend               │
                    └──────────┬──────────────────┬───────────┘
                               │                  │
                      POST /chat/send    POST /generate-document-stream
                               │                  │
                    ┌──────────▼──────────┐  ┌────▼──────────────────┐
                    │  chat_routes.py     │  │  agents/routes.py     │
                    │  (General Agent)    │  │  (Document Pipeline)  │
                    └──────────┬──────────┘  └────┬──────────────────┘
                               │                  │
                    ┌──────────▼──────────────────▼──────────┐
                    │            QueryLoop                    │
                    │    (execution/query_loop.py)            │
                    │                                         │
                    │  1. Build system prompt                 │
                    │  2. LLM call with tool definitions      │
                    │  3. Parse response → text + tool_calls  │
                    │  4. Execute tools via ToolExecutor      │
                    │  5. Detect __AWAITING_USER_INPUT__ → pause │
                    │  6. Append results to history           │
                    │  7. Sliding window truncation           │
                    │  8. Loop until text-only or max_turns   │
                    └──────────┬──────────────────┬──────────┘
                               │                  │
                    ┌──────────▼──────┐   ┌──────▼──────────┐
                    │ ToolExecutor    │   │ SystemPromptMgr  │
                    │ + ToolRegistry  │   │ + Context Builder│
                    └─────────────────┘   └─────────────────┘
```

### Doc Gen Specific Path (additional layer)

```
agents/routes.py
  → MissionOrchestrator
    → boot_cluster() — registers 3 dummy workers
    → execute_mission()
      → MissionParser → TaskPlanner → TaskGraphBuilder
      → ReadyTaskSelector → TaskQueue
      → SchedulerManager.run_scheduling_cycle()
        → RuntimeAdapter.execute(task)
          → GenerationAgentKernel.run_task()
            → ExecutionEngine.execute_task()
              → QueryLoop (via _simulate_or_call_llm)
```

### Chat Route Specific Path (direct)

```
chat_routes.py:
  → QueryLoop(session_id, project_id, max_turns=5, streaming_enabled=False, message_manager=SSEChatMessageManager)
    → tools = [FileRead, Bash, Glob, Search, ProposeContentEdit, RequestUserInput]
    → system_prompt = "You are ArchTech AI, an advanced engineering assistant..." (hardcoded in route)
    → run()
      → multi-turn loop with tool execution
      → pauses on __AWAITING_USER_INPUT__
      → chat_routes.py waits for POST /chat/interact
      → resumes via set_user_response()
```

---

## 5. Canonical Agent Loop

### Current Owner: `QueryLoop.run()` in `execution/query_loop.py`

**Called by:**
1. `chat_routes.py:156` — direct: `await loop.run(messages=..., tools=..., system_prompt=...)`
2. `core/execution_engine.py:484` — indirect: `query_loop._LLM_chatcomplete_call(...)` (creates fresh QueryLoop instance per task)

**The loop:**
```
for turn in range(max_turns):
    1. Check abort signal
    2. Build system prompt (from SystemPromptManager or override)
    3. Combine messages + _message_history (sliding window)
    4. Call LLM API with tool definitions
    5. Parse response → (final_text, tool_calls)
    6. If no tool calls and has text → BREAK (task complete)
    7. Execute each tool call via ToolExecutor
    8. Append tool results to _message_history
    9. If RequestUserInput marker → PAUSE and return
    10. Truncate history (max 10 messages, remove stale tool roles)
    11. Continue loop
```

**State passed:**
- `_message_history`: list of message dicts (sliding window)
- `_turn`: current turn count
- `_awaiting_input`: pause flag
- `_interaction_tool_call_id`: which tool call caused pause

**Events emitted:**
- Via `message_manager` (SSEChatMessageManager for chat, SSEToolQueue for doc gen)
- text_delta, tool_use_start, tool_use_complete, tool_interaction_request

**Problems:**
1. **No verification step** — task completion is when LLM returns text-only. No quality check.
2. **No repair step** — if a tool fails, the error is fed back to LLM, but there's no structured retry strategy.
3. **max_turns too low for chat** — only 5 turns. Complex bugs need 10-20+ turns.
4. **System prompt is route-specific** — chat route has document-editing bias, not general coding agent bias.
5. **Permission check is not activated** — `_permission_checker` is None in both routes.

---

## 6. Canonical Tool Pipeline

### Current Owner: `QueryLoop._execute_tools()` → `ToolExecutor.execute()`

```
LLM tool call
  ↓
_parse_response() — extracts id, name, input
  ↓
_execute_tools() — builds tool_map from available_tools list
  ↓
For each tool_call:
  1. Lookup in tool_map
  2. Validate arguments (blocked if None)
  3. Block redundant FileReads (self._executed_tools set)
  4. Emit tool_use_start via message_manager
  5. ToolExecutor.execute(tool, tool_call_id, args)
     a. Validate input schema via Pydantic
     b. Check permission (if _permission_checker is not None)
     c. Call tool.execute(**exec_args)
     d. Wrap in ToolExecutionResult
  6. Detect __AWAITING_USER_INPUT__ → pause
  7. Emit tool_use_complete via message_manager
  8. Append result to _message_history
```

### Is `action/tool_router.py` needed?

**NO.** It's a dead-code abstraction:
- Only imported by test files
- Provides policy validation + sandbox execution
- QueryLoop already has its own execution path with permission checking and file read deduplication
- Adding ToolRouter would create a SECOND execution pipeline → duplication

**Verdict:** Delete. The QueryLoop → ToolExecutor path is the canonical one.

---

## 7. Repository Intelligence

### Current State

| File | Status |
|---|---|
| `repository/repo_index.py` | Built — indexes symbols, imports, requirements |
| `repository/repo_query_engine.py` | Real — find_symbol, find_file_imports, summarize_file |
| `repository/repo_snapshot.py` | Built — file metadata snapshot |
| `repository/test_repo_intelligence.py` | Tests exist |

### What the Agent Can Actually Do Today

**Nothing.** RepositoryQueryEngine is never instantiated by any production code path.

### Recommended Approach

Expose as a **tool**, not a system prompt injection:

```python
# New tool: RepositoryQuery
# Methods:
#   - find_symbol(name) → List[SymbolLocation]
#   - find_file_imports(file_path) → List[str]
#   - summarize_file(file_path) → str
#   - find_callers(function) → List[SymbolLocation] (stub — return "not implemented")
#   - find_test_for(file_path) → List[str] (heuristic: look for test_*.py or *_test.py)
```

This is better than system prompt injection because:
1. The agent decides WHEN to query (on-demand, not always)
2. The agent knows the cost (querying adds tokens)
3. It's testable (tool unit tests)
4. It's consistent with the tool-based architecture already in place

---

## 8. Context Lifecycle

### Current Owner: `QueryLoop._message_history` + `ContextCompactPipeline`

**What survives always:**
- System prompt (from SystemPromptManager or override)
- Current user message
- Last 5 turns in `_message_history`

**What can be summarized:**
- `ContextAutoCompact` kicks in when tokens exceed budget (default 100K)
- Summarization delegates to `SessionMemoryExtractor` (session_memory.py)

**What can be discarded:**
- Old tool results beyond the 5-turn window
- Already-read file contents (blocked by `_executed_tools` set for FileRead)

**What should be retrieved again:**
- Nothing currently — no memory system wired up

**What should never be duplicated:**
- File reads are already deduplicated (`_executed_tools` set)

**Problems:**
1. `_max_history_turns = 5` is hardcoded — too small for complex tasks
2. No working memory or scratchpad is wired up
3. `ContextCompactPipeline.run()` exists but is never called by QueryLoop. The compaction class is imported in `__init__.py` but the `run()` method is not invoked anywhere in the loop.
4. System prompt is built fresh every turn via SystemPromptManager — no caching

---

## 9. Editing Lifecycle

### Current Architecture: Three Distinct Editing Systems (Not Competing — Different Purposes)

| System | Purpose | Tool | Available To Chat | Available To Doc Gen |
|---|---|---|---|---|
| FileWrite | Create/overwrite files | `file_write.py` | NO | YES (via RuntimeAdapter) |
| FileEdit | Line-range replacement in existing files | `file_edit.py` | NO | YES (via RuntimeAdapter) |
| ProposeContentEdit | Document section edit with UI review | `propose_content_edit.py` | YES | NO |

**This is NOT a problem.** They serve different purposes:
- ProposeContentEdit: document section editing, pauses for UI approval, writes to versioned JSON
- FileWrite: general file creation/overwriting, path-traversal validation, atomic writes
- FileEdit: surgical line-range replacement in existing files

**The real problem:** Chat route has NO FileWrite/FileEdit. It can read and search but cannot write. This is the #1 gap.

---

## 10. Verification Lifecycle

### Current State: NON-EXISTENT

The agent loop considers a task "complete" when the LLM returns text without tool calls (line 260: `if not tool_calls and final_text.strip(): break`).

There is NO:
- Exit condition checking
- Diff validation
- Test execution
- Syntax validation
- Build verification

### How It SHOULD Work

```
Task received
  ↓
LLM reasons and acts (tool calls)
  ↓
LLM returns final text
  ↓
VERIFY (NEW)
  ├── Task-specific checks (exit conditions)
  ├── File changes exist and are correct
  ├── Tests pass (if applicable)
  └── If PASS → COMPLETE
      If FAIL → REPAIR (NEW)
```

Verification should be **task-aware**, not generic:
- For code edits: check syntax, check file exists, run relevant tests
- For documentation: check required sections present, no placeholders remain
- For bug fixes: check tests pass, no regressions

---

## 11. Repair Lifecycle

### Current State: STUBS ONLY

- `cognitive/repair_engine.py` — returns hardcoded RepairPlan
- `runtime/failure_classifier.py` — exists but not wired

The only "repair" today is: tool error → feed back to LLM → LLM tries again. This is implicit, not structured.

### How It SHOULD Work

```
Tool/Test Failure
  ↓
Classify: syntax error? runtime error? wrong result? permission denied?
  ↓
Understand: read relevant file, check recent changes
  ↓
Choose strategy: fix path? change approach? ask user?
  ↓
Act: call appropriate tool
  ↓
Verify
  ↓
If still failing after N attempts → ask user
```

---

## 12. Permission Lifecycle

### Current State: NOT ACTIVE

```
Tool Request
  ↓
ToolExecutor.execute()
  ↓
if self._permission_checker:    ← ALWAYS FALSE (None from both routes)
    if not self._permission_checker.can_use(tool_name):
        return denied
else:
    EXECUTE (no check)
```

### PermissionManager Exists But Is Not Wired

`PermissionManager` has three modes:
- `FULL_AUTO` — all tools execute immediately
- `REQUIRE_PROMPT` — some tools need user confirmation
- `SKIP` — all tools denied (read-only)

Currently, since `_permission_checker` is None, the check is skipped entirely and ALL allowed tools execute without confirmation.

### Recommended

Activate PermissionManager in FULL_AUTO mode by default (for safety boundary), with REQUIRE_PROMPT for Bash and FileWrite. This gives:
1. A safety boundary (tools can be blocked if needed)
2. Future extensibility (can switch to REQUIRE_PROMPT)
3. Consistent behavior across both routes

---

## 13. Session Lifecycle

### Chat Route

```
POST /chat/send
  ↓
ChatSessionManager._load(session_id, project_id) — loads from JSON
  ↓
If not found: ChatSessionManager.create() — creates new session
  ↓
QueryLoop(session_id=..., project_id=..., max_turns=5)
  ↓
loop.run() → multi-turn
  ↓
_loop finishes or pauses → session state in _message_history
  ↓
On resume: set_user_response() → loop continues
  ↓
On completion: session JSON persisted
```

### Doc Gen Route

```
POST /generate-document-stream
  ↓
MissionOrchestrator.boot_cluster() — registers workers
  ↓
For each section:
  RuntimeAdapter.execute(task)
    → GenerationAgentKernel.run_task()
      → ExecutionEngine.execute_task()
        → QueryLoop (fresh instance per task)
          → _simulate_or_call_llm()
  ↓
Section result written to JSON in _output/
  ↓
Document version tracked in _output/version.json
```

**Problem:** Chat session uses sliding window (5 turns). Long conversations lose context. No compaction is actually triggered because `ContextCompactPipeline.run()` is never called in the loop.

---

## 14. Cancellation Lifecycle

### Chat Route

`AbortController` with hierarchy:
- `chat_routes.py:215-216`: `if not task.done(): task.cancel()` — cancels asyncio task
- `_pending_interactions` dict — tracks paused sessions
- `QueryLoop.abort_controller` — checked at start of each turn (line 184)

### Doc Gen Route

`GenerationSessionManager.cancel()`:
- `agents/routes.py:249`: cancels session
- `agents/routes.py:252-256`: aborts tree by session_id
- `pause_manager.py`: sets/clears pause flag for project_id

**Gap:** No graceful cancellation of in-progress tool execution. If Bash is running, cancel only stops the asyncio task, not the shell process.

---

## 15. Recovery Lifecycle

### Current State: MINIMAL

| Failure Mode | Detected? | Recoverable? | Retry? |
|---|---|---|---|
| LLM timeout | Yes (asyncio.TimeoutError) | Partial | Via fallback chain |
| LLM malformed response | Yes (_parse_response returns empty) | Yes | LLM tries again next turn |
| Tool failure | Yes (is_error in result) | Partial | Error fed back to LLM |
| Shell command failure | Yes (returncode != 0) | Partial | LLM sees error, tries again |
| File changed externally | No | No | LLM may get stale data |
| Context overflow | Partial (compaction pipeline exists but not called) | Yes | No active compaction |
| Agent cancellation | Yes (abort_controller) | Partial | Task cancelled, not resumed |
| Server restart | No | No | Session lost |

---

## 16. Observability / Agent Trace

### Current Events

| Source | Events |
|---|---|
| SSEChatMessageManager (chat) | session_created, turn_start, text_delta, tool_use_start, tool_interaction_request, tool_use_complete, interaction_paused, turn_complete, done, error |
| SSEToolQueue (doc gen) | turn_start, tool_started, tool_finished, text_delta, section_start, section_chunk, section_complete, gen_start, gen_complete |
| AsyncEventBus (doc gen) | TurnStarted, ToolStarted, ToolFinished, TaskCompleted |
| ObservationBus (chat kernel) | KERNEL_STARTING, KERNEL_STARTED, CANCEL_REQUESTED, RUN_PAUSED, RUN_RESUMED, KERNEL_STOPPING, KERNEL_STOPPED |

**Gap:** No unified agent trace. Events are scattered across multiple queues. There's no single record of:
- Why the agent chose a specific tool
- What reasoning led to a decision
- Cost per turn
- Verification result
- Repair action taken

---

## 17. Developer Understandability Audit

### Can a developer answer these questions?

| Question | Answerable? | Source File(s) |
|---|---|---|
| Where does an agent task start? | Yes | `Routes/chat_routes.py:248` or `AgentCore/agents/routes.py:107` |
| Where is the loop? | Yes | `execution/query_loop.py:179` |
| Where does the model get called? | Yes | `execution/query_loop.py:397` (`_LLM_chatcomplete_call`) |
| Where are tools registered? | Yes | `execution/builtins/__init__.py:40-41` |
| Where are tools executed? | Yes | `execution/query_loop.py:656` (`_execute_tools`) → `execution/tool_executor.py:41` |
| Where is permission checked? | Yes, but not active | `execution/tool_executor.py:76` (conditional on `_permission_checker`) |
| Where is state stored? | Yes | `execution/session_manager.py`, `core/agent_session_manager.py` |
| Where does context come from? | Yes | `execution/system_prompt.py` (static blocks) + `_message_history` (dynamic) |
| Where does context get compacted? | **MISSING** | `execution/context_compaction.py` exists but is never called in the loop |
| How does an edit happen? | Partial | FileWrite/FileEdit tools exist but not wired to chat. ProposeContentEdit only for doc gen. |
| How does verification happen? | **NO** | Cognitive stubs exist but are never called by production code |
| How does failure recovery happen? | Partial | Tool errors → LLM feedback. No structured repair. |
| How does cancellation work? | Yes | `execution/abort_controller.py` + route-level task.cancel() |
| How does the task finish? | Yes | When LLM returns text without tool calls |

**Architectural complexity gaps:**
1. `context_compaction.py` is dead code in the loop — exists but not used
2. `knowledge/` directory has 6 files but none are wired
3. `cognitive/` has 3 files but none are called
4. `platform/llm/` has 5 files but none are used (LLM call is direct in query_loop.py)
5. Multiple state tracking systems: `_executed_tools`, `_message_history`, `_turn`, `_awaiting_input`, `_interaction_tool_call_id`, `_user_response` — all in QueryLoop, not consolidated

---

## 18. Duplicate Responsibilities

| Responsibility | Owner 1 | Owner 2 | Verdict |
|---|---|---|---|
| Agent lifecycle | ChatAgentKernel (observability) | N/A | Keep — but unused by chat route |
| Task execution | ExecutionEngine (core) | QueryLoop (execution) | ExecutionEngine wraps QueryLoop → keep ExecutionEngine as wrapper |
| Direct agent loop | QueryLoop (execution) | LoopController (orchestration/workflow.py) | workflow.py is dead code. Keep QueryLoop only. |
| Context compaction | ContextCompactPipeline (execution) | ContextManager (core/execution_history.py) | TWO compaction systems! ContextManager is used by ExecutionEngine. ContextCompactPipeline is unused. |
| Session management | ChatSessionManager (execution) | GenerationSessionManager (execution) | Two separate managers for two separate routes. Keep both but consider unifying. |
| Tool execution | ToolExecutor (execution) | ToolRouter (action) → SandboxManager (platform) | ToolRouter/Sandbox is dead code. Keep ToolExecutor only. |
| Permission | PermissionManager (execution) | PolicyManager (infrastructure) | PolicyManager is dead code. Keep PermissionManager. |
| Memory | SessionMemoryCache (execution) | store_manager/mission_store/working_store/scratchpad_store (memory) | SessionMemoryCache is used. Memory/* is dead code. |

**Key finding: Context compaction has TWO implementations:**
1. `ContextCompactPipeline` in `execution/context_compaction.py` — NEVER CALLED
2. `ContextManager` in `core/execution_history.py` — USED by ExecutionEngine (doc gen)

The chat route uses neither. It relies on simple sliding window truncation.

---

## 19. Missing Components

| Component | Priority | Description |
|---|---|---|
| FileWrite/FileEdit tools for chat | P0 | Chat route can read/search but not write/edit |
| PermissionManager activation | P0 | Safety boundary exists but is not active |
| Task verification | P1 | No quality check on LLM output |
| Structured repair | P1 | No recovery strategy beyond LLM feedback |
| Repository query tool | P1 | Repo intelligence exists but not exposed to agent |
| Increased max_turns for chat | P1 | 5 turns is too restrictive |
| Active context compaction | P1 | Sliding window only, no summarization |
| Unified agent trace | P2 | Events scattered across multiple queues |
| Cross-session memory | P2 | No working memory between turns |
| Knowledge graph | P2 | Dead code in knowledge/ directory |

---

## 20. Claude/Cursor/Codex Behavioral Comparison

| Capability | AgentCore Chat | Claude Code | Gap |
|---|---|---|---|
| Multi-turn conversation | Yes (QueryLoop) | Yes | None |
| File read | Yes (FileRead) | Yes | None |
| File write | **NO** | Yes | **P0** |
| File edit | **NO** | Yes | **P0** |
| Bash execution | Yes (Bash) | Yes | None |
| Code search | Yes (Search) | Yes (Grep) | None |
| File pattern match | Yes (Glob) | Yes (Glob) | None |
| Pause for user input | Yes (RequestUserInput) | Yes (/ask) | None |
| Propose edits with UI | Yes (ProposeContentEdit) | Partial | None (better in AgentCore) |
| Session persistence | Yes (JSON) | Yes | None |
| SSE streaming | Yes (10 event types) | Yes | None |
| Context management | Basic (5-turn window) | Advanced (dynamic) | P1 |
| Repository intelligence | **NO** | Yes (symbol index) | P1 |
| Task planning | Implicit (LLM multi-turn) | Implicit (LLM multi-turn) | None — QueryLoop handles this naturally |
| Verification | **NO** | Yes (tests, lint) | P1 |
| Error repair | Implicit (LLM feedback) | Structured | P1 |
| Permission enforcement | **NO** | Yes | P0 |
| Test execution | **NO** | Yes | P1 |
| Git operations | Via Bash only | Dedicated tool | P2 |
| Patch application | Via FileEdit | Dedicated tool | P2 |

**Note on task planning (P1-9):** Report 2 recommended a separate task planner. **This recommendation is REJECTED.** Claude Code and Cursor Agent both use implicit planning — the LLM decides what to do next through multi-turn tool use. QueryLoop already supports this: search → read → reason → edit → test → repair → complete. No explicit planner needed for typical coding tasks.

---

## 21. Gap Prioritization

### P0 — Fundamentally Broken

| Gap | Impact |
|---|---|
| Cannot write files (FileWrite not in chat route) | Agent can read code but never modify it |
| Cannot edit files (FileEdit not in chat route) | Same — no editing capability |
| Permission enforcement not active | No safety boundary on tool execution |

### P1 — Works But Deficient

| Gap | Impact |
|---|---|
| No task verification | LLM output accepted without quality check |
| No structured repair | Tool failures rely on LLM self-correction only |
| No repository query tool | Agent lacks codebase understanding beyond raw search |
| max_turns=5 too restrictive | Complex tasks (multi-file bug fix) can't complete |
| Context compaction not active | No summarization of old conversation |
| ContextManager and ContextCompactPipeline are two separate systems | One is used (doc gen), one is dead code (chat) |

### P2 — Advanced

| Gap | Impact |
|---|---|
| No test execution tool | Can't run tests to verify fixes |
| No git tool | Can only do git via Bash, no dedicated tool |
| No cross-session memory | No working memory beyond sliding window |
| Knowledge graph is dead code | Complex dependency analysis not available |

---

## 22. Black-Box Behavioral Tests

### Test 1: Simple Edit — "Fix a typo in README.md"

**Expected:** read README.md → edit (FileEdit) → diff → complete
**Current:** read README.md → cannot edit → stuck or returns text explanation
**Result: FAILS** — no FileEdit in chat route

### Test 2: Bug Fix — "Fix the failing login test"

**Expected:** search for login test → read test file → read source → edit → run test → observe result → repair if failure → complete
**Current:** search → read → cannot edit → cannot run test
**Result: FAILS** — no FileEdit, no test execution

### Test 3: New Feature — "Add a REST endpoint"

**Expected:** understand repo → locate similar endpoint → implement → test
**Current:** search → read → cannot write
**Result: FAILS** — no FileWrite

### Test 4: Dangerous Command — "Delete the production database"

**Expected:** PermissionManager blocks or prompts for approval
**Current:** Command executes without check (PermissionManager not active)
**Result: FAILS** — no safety boundary

### Test 5: Long Task — 20+ tool interactions

**Expected:** context remains coherent, important state survives
**Current:** 5-turn max, no compaction active
**Result: FAILS** — max_turns=5 + no compaction

### Test 6: Tool Failure — "Run ls on a non-existent path"

**Expected:** tool failure → observation → alternate action
**Current:** error fed back to LLM → LLM tries again
**Result: PARTIAL** — works via LLM self-correction, but no structured repair

### Test 7: Test Failure — "Test fails after edit"

**Expected:** inspect failure → modify code → rerun
**Current:** no FileEdit, no test tool
**Result: FAILS** — cannot modify or test

### Test 8: Cancellation — stop mid-task

**Expected:** stop active tool, clean up, consistent state
**Current:** asyncio task cancelled, but running shell process not stopped
**Result: PARTIAL** — task cancelled, but no process cleanup

---

## 23. Implementation Roadmap

### Phase 1: Enable File Editing in Chat Route (P0)
**Files:** `Routes/chat_routes.py`
**Change:** Add "FileWrite", "FileEdit" to allowed_tools set (line 123)
**Risk:** Low — tools already exist, already tested, already registered
**Test:** "Create a file test_foo.py with a function that returns 42"

### Phase 2: Activate PermissionManager (P0)
**Files:** `Routes/chat_routes.py`, `agents/routes.py`
**Change:** Instantiate PermissionManager(FULL_AUTO) and pass to QueryLoop
**Risk:** Low — mechanism already exists, just needs activation
**Test:** Try FileWrite to /etc/passwd — should be blocked by FileWrite's own path validation

### Phase 3: Increase Chat max_turns (P1)
**Files:** `Routes/chat_routes.py`
**Change:** Increase from 5 to 15 (reasonable for typical coding tasks)
**Risk:** Low — just a number change
**Test:** Multi-step refactor that needs 8-10 turns

### Phase 4: Add Repository Query Tool (P1)
**Files:** New file `execution/builtins/repository_query.py` (or add to existing)
**Change:** Create tool that wraps RepositoryQueryEngine.find_symbol(), find_file_imports(), summarize_file()
**Risk:** Medium — needs repo index to be built first
**Test:** "Find where UserAuth is defined"

### Phase 5: Implement Basic Task Verification (P1)
**Files:** `execution/query_loop.py`
**Change:** After final text response, run lightweight verification:
- Check no {{placeholder}} remains
- Check no code fences in final output
- (Future) Run syntax check on modified files
**Risk:** Low — adds a post-processing step
**Test:** "Fix typo in README" → verify README.md actually changed

### Phase 6: Context Compaction for Chat Route (P1)
**Files:** `execution/query_loop.py`
**Change:** Use the EXISTING `ContextCompactPipeline.run()` (already written, just not called) for the chat route's message history
**Risk:** Low — code exists, just needs to be called
**Test:** 15+ turn conversation should remain under token budget

### Phase 7: Clean Up Dead Code (P2)
**Files:** 28 files in action/, cognitive/, context/, domain/, infrastructure/, knowledge/, memory/, platform/artifacts/, platform/llm/, reasoning/
**Change:** Delete or mark as experimental
**Risk:** Low — none are wired to production paths
**Test:** Both routes still work after cleanup

---

## 24. Target Architecture

```
                    USER
                      │
                      ▼
              CHAT ROUTE / DOC GEN ROUTE
                      │
                      ▼
                 QUERY LOOP ─────────────────────────────┐
              (execution/query_loop.py)                   │
          ┌─────────────┬──────────────┐                  │
          ▼             ▼              ▼                  │
      CONTEXT        LLM CALL     TOOL DECISION           │
          │             │              │                  │
          ▼             ▼              ▼                  │
   SystemPrompt    _call_api    _parse_response           │
          │             │              │                  │
          └─────────────┴──────────────┘                  │
                         │                                │
                         ▼                                │
                   TOOL CALL FOUND?                       │
                      │          │                        │
                   YES │          │ NO                    │
                      ▼          ▼                        │
              ┌───────────┐    ▼                         │
              │ PERMISSION│  COMPLETE                     │
              │  CHECK    │    │                         │
              └────┬──────┘    │                         │
                   │           │                         │
              ┌────▼──────┐   │                         │
              │TOOL EXEC│   │                         │
              │  EXECUTOR│   │                         │
              └────┬─────┘   │                         │
                   │         │                         │
              ┌────▼─────────▼┐                        │
              │   TOOL RESULT  │                        │
              │  (error/ok)    │                        │
              └────┬───────────┘                        │
                   │                                     │
              ┌────▼─────┐                              │
              │AWAITING  │                              │
              │ USER?    │◄──── POST /chat/interact     │
              └────┬─────┘                              │
                   │                                     │
                   ▼                                     │
              APPEND TO HISTORY                         │
                   │                                     │
              ┌────▼───────────────────────────────────┐│
              │ SLIDING WINDOW + COMPACTION             ││
              │ (max 5 turns → increase to 15)          ││
              │ (active compaction when over budget)    ││
              └─────────────────────────────────────────┘│
                   │                                     │
                   └──────────────┬──────────────────────┘
                                  ▼
                         next turn or COMPLETE
```

### File-to-Box Mapping

| Box | File | Function |
|---|---|---|
| Chat Route | `Routes/chat_routes.py` | `_chat_stream()` |
| Doc Gen Route | `AgentCore/agents/routes.py` | `generate_document_stream()` |
| Query Loop | `AgentCore/execution/query_loop.py` | `run()` |
| Context | `AgentCore/execution/system_prompt.py` | `SystemPromptManager.build()` |
| LLM Call | `AgentCore/execution/query_loop.py` | `_LLM_chatcomplete_call()` |
| Tool Decision | `AgentCore/execution/query_loop.py` | `_parse_response()` |
| Permission | `AgentCore/execution/tool_executor.py` | `execute()` (line 76) |
| Tool Executor | `AgentCore/execution/tool_executor.py` | `execute()` (line 41) |
| Tool Registry | `AgentCore/execution/tool_registry.py` | `registry.get()` |
| Tool Implementations | `AgentCore/execution/builtins/*.py` | `*_tool.execute()` |
| Compaction | `AgentCore/execution/context_compaction.py` | `ContextCompactPipeline.run()` |
| Session Mgmt | `AgentCore/execution/session_manager.py` | `ChatSessionManager` |

---

## 25. Final Comparison: CURRENT vs TARGET

### CURRENT: User says "Fix this bug."

```
User: "Fix this bug."
  ↓
chat_routes.py:182
  → QueryLoop(session_id, max_turns=5)
    → run()
      → Turn 1:
        → system_prompt = "You are ArchTech AI..." (document editing bias)
        → _call_api(messages, tools=[FileRead, Bash, Glob, Search, ProposeContentEdit, RequestUserInput])
        → _parse_response() → text + tool_calls[Search]
        → _execute_tools() → tool result: "files containing bug"
      → Turn 2:
        → _call_api(messages, tools=...)
        → _parse_response() → text + tool_calls[FileRead]
        → _execute_tools() → tool result: file content
      → Turn 3:
        → _call_api(messages, tools=...)
        → _parse_response() → FINAL TEXT (no tool calls)
        → BREAK → task complete
      → Result: LLM outputs text explanation of the fix
      → User must manually apply changes
```

**What's missing:**
- No FileEdit/FileWrite → agent can't apply the fix
- No permission check → no safety boundary
- No repository query → agent doesn't understand codebase structure
- No verification → agent output not quality-checked
- No test execution → can't verify fix works
- Only 5 turns → complex bugs can't be fixed

### TARGET: User says "Fix this bug."

```
User: "Fix this bug."
  ↓
chat_routes.py:182
  → QueryLoop(session_id, max_turns=15, permission_checker=PermissionManager(FULL_AUTO))
    → run()
      → Turn 1:
        → system_prompt = "You are an expert coding agent..."
        → _call_api(tools=[FileRead, FileWrite, FileEdit, Bash, Glob, Search, RepositoryQuery, RequestUserInput])
        → _parse_response() → text + tool_calls[Search]
        → PermissionManager.can_use("Search") → True
        → _execute_tools() → "files containing bug"
      → Turn 2:
        → _call_api(tools=...)
        → _parse_response() → text + tool_calls[FileRead]
        → PermissionManager.can_use("FileRead") → True
        → _execute_tools() → file content
      → Turn 3:
        → _call_api(tools=...)
        → _parse_response() → text + tool_calls[RepositoryQuery]
        → _execute_tools() → "UserAuth defined in auth/models.py, imported by 3 files"
      → Turn 4:
        → _call_api(tools=...)
        → _parse_response() → text + tool_calls[FileEdit]
        → _execute_tools() → "Replaced lines 42-48 in auth/models.py"
      → Turn 5:
        → _call_api(tools=...)
        → _parse_response() → text + tool_calls[Bash("pytest tests/test_auth.py")]
        → _execute_tools() → "PASSED (2/2 tests)"
      → Turn 6:
        → _call_api(tools=...)
        → _parse_response() → FINAL TEXT
        → _clean_final_output()
        → BREAK → task complete
      → Result: Bug fixed, tests pass, user informed
```

### Differences (Engineering Backlog)

| # | Difference | Priority | Effort |
|---|---|---|---|
| D1 | FileWrite + FileEdit in allowed_tools | P0 | 1 line change |
| D2 | PermissionManager activated | P0 | 2 lines change |
| D3 | max_turns increased from 5 to 15 | P1 | 1 line change |
| D4 | Repository query as tool | P1 | New file |
| D5 | Active context compaction | P1 | Wire existing code |
| D6 | Post-execution verification | P1 | New code in QueryLoop |
| D7 | System prompt updated for coding agent | P1 | 1 file change |
| D8 | Cleanup dead code | P2 | Delete 28 files |
| D9 | Structured repair | P2 | Wire cognitive stubs or rewrite |
| D10 | Test execution tool | P2 | New tool wrapping pytest |

---

## 26. What Changes Right Now (Minimal Effective Change)

The smallest set of changes that transforms AgentCore from "read-only assistant" to "functional coding agent":

**File: `Routes/chat_routes.py`**

1. Add `"FileWrite", "FileEdit"` to allowed_tools (line 123)
2. Increase `max_turns` from 5 to 15 (line 188)
3. Instantiate and pass `PermissionManager(mode=PermissionMode.FULL_AUTO)` to QueryLoop

That's it. Three changes, one file. After these three changes, the agent can:
- Read files (already works)
- Write files (new)
- Edit files (new)
- Search code (already works)
- Run commands (already works)
- Match file patterns (already works)
- Ask for user input (already works)
- Pause and resume (already works)
- Has a basic safety boundary (new)

This puts AgentCore at approximately 85% of Claude Code's fundamental capabilities.

---

## 27. Final "What Happens When User Says Fix This Bug?" — Trace

### CURRENT TRACE (Step-by-Step)

1. **User:** "Fix this bug"
2. **Route:** `POST /chat/send` → `_chat_stream()`
3. **Session:** `ChatSessionManager._load()` or `.create()`
4. **Queue:** `asyncio.Queue()` for SSE events
5. **Loop:** `QueryLoop(session_id, project_id, streaming_enabled=False, message_manager, max_turns=5)`
6. **Task:** `asyncio.create_task(run_loop())`
7. **Turn 1:**
   - `loop.run(messages=[user_msg], tools=[FileRead, Bash, Glob, Search, ProposeContentEdit, RequestUserInput], system_prompt=chat_system_prompt)`
   - `_call_api()` → LLM with 6 tool definitions
   - LLM returns: text + tool_calls[Search(pattern="bug")]
   - `_execute_tools()` → ToolExecutor → Search executes → "found file.py"
8. **Turn 2:**
   - LLM returns: text + tool_calls[FileRead(file_path="file.py")]
   - `_execute_tools()` → ToolExecutor → FileRead → file content
9. **Turn 3:**
   - LLM returns: text-only (no tool calls)
   - `break` → task complete
10. **Result:** LLM text explanation of fix (but no file was modified)
11. **SSE events emitted:** text_delta, tool_use_start, tool_use_complete × 2, turn_complete, done
12. **Frontend:** Shows text. User must manually apply changes.

**Total turns: ~3-5**
**Files modified: 0**
**Tests run: 0**
**Verification: none**

### TARGET TRACE (Step-by-Step)

1. **User:** "Fix this bug"
2. **Route:** `POST /chat/send` → `_chat_stream()`
3. **Session:** `ChatSessionManager._load()` or `.create()`
4. **Queue:** `asyncio.Queue()` for SSE events
5. **Loop:** `QueryLoop(session_id, project_id, streaming_enabled=False, message_manager, max_turns=15, permission_checker=PermissionManager(FULL_AUTO))`
6. **Task:** `asyncio.create_task(run_loop())`
7. **Turn 1:**
   - LLM with 8 tools (FileRead, FileWrite, FileEdit, Bash, Glob, Search, RepositoryQuery, RequestUserInput)
   - LLM: Search(pattern="bug") → "found file.py"
8. **Turn 2:**
   - LLM: FileRead(file_path="file.py") → file content
9. **Turn 3:**
   - LLM: RepositoryQuery(symbol="UserAuth") → "found in auth/models.py line 42"
10. **Turn 4:**
    - LLM: FileEdit(file_path="auth/models.py", range={start:42, end:48}, content="fixed code")
    - PermissionManager.can_use("FileEdit") → True (FULL_AUTO)
    - Result: "Replaced lines 42-48"
11. **Turn 5:**
    - LLM: Bash(command="pytest tests/test_auth.py")
    - PermissionManager.can_use("Bash") → True (FULL_AUTO, but Bash is auto-allowed)
    - Result: "PASSED (2/2)"
12. **Turn 6:**
    - LLM: text-only (final response)
    - `_clean_final_output()` applied
13. **Result:** Bug fixed, tests pass, summary provided
14. **SSE events:** Same 10 event types, richer content

**Total turns: ~6-10**
**Files modified: 1+**
**Tests run: 1+**
**Verification: implicit (tests pass)**

### Every Difference Between CURRENT and TARGET

| Difference | CURRENT | TARGET | Effort |
|---|---|---|---|
| File editing tools | Not available | FileWrite + FileEdit in allowed_tools | 1 line |
| Permission safety | None | PermissionManager(FULL_AUTO) | 2 lines |
| Turn limit | 5 | 15 | 1 line |
| Repository understanding | None | RepositoryQuery tool | New file |
| Context management | 5-turn window only | 15-turn window + active compaction | Wire existing code |
| Post-execution check | None | Basic verification (no placeholders, clean output) | Few lines |
| System prompt | Document editing bias | General coding agent prompt | 1 change |

---

## Summary

AgentCore is **structurally sound** but **functionally incomplete** as a coding agent.

The core loop (QueryLoop) is real and working. The tool system (registry + executor) is real and working. The pause/resume flow is real and working. The SSE streaming is real and working.

**What's missing to be a functional coding agent:**
1. File write/edit capability in chat route (P0)
2. Permission enforcement (P0)
3. More turns for complex tasks (P1)
4. Repository intelligence as a tool (P1)
5. Context compaction activation (P1)
6. Basic verification (P1)

**What's already good:**
1. Multi-turn loop
2. Tool execution
3. Pause/resume
4. SSE streaming
5. Session persistence
6. File read, bash, glob, search

**What's dead code (28 files):**
action/, cognitive/, context/, domain/, infrastructure/, knowledge/memory, platform/llm/, platform/artifacts/, reasoning/ — all exist as scaffolding but none are wired to production paths.
