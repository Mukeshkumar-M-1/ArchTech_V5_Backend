# Plan: Tool Orchestration Layer for ArchTech V5

## Context

You've studied how the **claude-code** CLI orchestrates tools and agents in its multi-turn inference loop. Your **ArchTech V5** backend has an LLM API handler and agent classes (TemplateAnalysisAgent, ContentKnowledgeAgent, ExtractionEventLoop) but lacks a proper **tool orchestration layer** — the infrastructure that connects tools, manages execution, handles errors, and runs the retry loop. You need to build this layer from scratch, inspired by CCB's architecture.

---

## Part 1: What You're Missing (Gap Analysis)

### Gap 1: No Tool Registry / Schema System
**CCB:** Tools are registered with Zod schemas, `tool.prompt()` descriptions, `isConcurrencySafe()` checks, and `inputSchema` conversion to JSON Schema. Every tool is a first-class object with metadata.

**ArchTech:** Tools (file read, file write, Bash, Agent spawn) are scattered across `llm_api_handler.py` (function calling) and individual agent classes. There's no central registry, no schema definition, no way for the LLM to discover available tools dynamically.

**Impact:** The model can't make informed decisions about which tool to call because it doesn't know what tools exist or what their input contracts are.

### Gap 2: No Multi-Turn Tool Execution Loop
**CCB:** The `while(true)` query loop in `query.ts` runs indefinitely: model → tool_use → execute → tool_result → model → ... until the model returns text only. Tool results (including errors) are fed back to the model each turn.

**ArchTech:** `llm_request_with_tool_calls()` has a **single loop of 5 rounds** (`max_tool_rounds = 5`). Tool definitions are hardcoded with a single `file_path` parameter. Errors are caught but not fed back to the model in a structured way for self-correction.

**Impact:** No true agentic loop. The model can't iteratively solve complex tasks that require multiple tool calls based on previous results.

### Gap 3: No Tool Partitioning / Concurrency Control
**CCB:** `partitionToolCalls()` separates read-only tools (can run in parallel) from write tools (must run sequentially). Max 10 concurrent read-only tools.

**ArchTech:** `extraction_event_loop.py` has a `WorkerPool` with semaphore-based concurrency, but this is only for the extraction pipeline. No concurrency awareness for LLM tool calls — if the model calls 3 tools at once, they could conflict on file writes.

**Impact:** Race conditions on file operations, no parallelism optimization for independent read operations.

### Gap 4: No Structured Error Feedback to LLM
**CCB:** Tool errors become `tool_result` blocks with `is_error: true`, formatted by `formatError()`/`formatZodValidationError()`. The LLM sees the exact error (exit code, stderr, missing params) and self-corrects in the next turn.

**ArchTech:** Tool errors are logged and returned as string messages (`f"Error: {e}"`). No structured format, no error classification, no Zod validation before execution. The LLM gets a vague error message with no structured guidance.

**Impact:** LLM can't reliably self-correct. Missing parameter names, exact error types, and structured context are lost.

### Gap 5: No Error Recovery / Retry at the Orchestration Level
**CCB:** Multi-tiered recovery: API retry (withRetry) → prompt-too-long (context collapse) → output token limit (escalation + recovery message) → model fallback (529 → different model).

**ArchTech:** Only retry in `llm_api_handler.py` (`_retry_with_backoff`). No recovery for tool execution failures, no output token recovery, no model fallback chain integration.

**Impact:** Any persistent failure (API overloaded, context too long, tool fails) causes complete task failure.

### Gap 6: No Agent Spawning / Subagent Delegation
**CCB:** The `Agent` tool spawns independent subagents with their own tool pool, system prompt, messages, and query loop. The parent sees only the final result.

**ArchTech:** `TemplateAnalysisAgent` directly instantiates `ContentKnowledgeAgent` and calls its methods synchronously. No isolation, no independent query loop, no subagent context.

**Impact:** No ability to delegate complex subtasks to specialized agents with independent context.

### Gap 7: No Message Normalization / Conversation History Management
**CCB:** `normalizeMessagesForAPI()` converts internal message types to API format. Caching on last block. Context collapse when near limits. Tool-reference stripping.

**ArchTech:** Messages are raw dicts (`{"role": "user", "content": "..."}`). No normalization, no caching, no context management.

**Impact:** No prompt caching optimization, no context window management for long conversations.

---

## Part 2: Tool Orchestration Layer Design

### Architecture Overview

```
OrchestratorLayer (new module)
├── ToolRegistry       — Central registry of all available tools
├── ToolExecutor       — Execute tools with validation, permission, error handling
├── ConcurrencyManager — Partition & run tools (parallel read, serial write)
├── QueryLoop          — The infinite while(true) inference loop
├── ErrorRecovery      — Multi-tiered error handling and retry
├── AgentSpawner       — Subagent delegation with independent context
└── MessageManager     — Normalize, cache, compact conversation history
```

### Layer 1: ToolRegistry — Central Tool Definitions

**File:** `backend/tools/registry.py`

```python
# Every tool is registered with:
class ToolDefinition:
    name: str                         # "Bash", "FileRead", "Agent", etc.
    description: str                  # What this tool does (shown to LLM)
    input_schema: dict                # JSON Schema for validation (Pydantic → JSON)
    is_concurrency_safe: bool         # Can this run in parallel?
    execute: Callable                 # The actual execution function
    prompt: Callable                  # Dynamic description builder
```

**Key features:**
- Auto-register via decorator: `@registry.register()`
- Pydantic models for schemas → auto-convert to JSON Schema
- Dynamic descriptions via `tool.prompt(context)` (like CCB's Agent tool listing available agents)

### Layer 2: ToolExecutor — Execution with Validation

**File:** `backend/tools/executor.py`

```python
class ToolExecutionResult:
    tool_call_id: str
    content: str                      # Success output or error message
    is_error: bool
    tool_name: str
    execution_time_ms: float
    context_updates: dict             # State changes (file modified, etc.)
```

**Execution flow:**
```
1. Validate input against Pydantic schema → structured error if invalid
2. Check tool.is_concurrency_safe() → classify for partitioning
3. Execute tool → catch all exceptions
4. Format error with details (exit code, stderr, missing params)
5. Return ToolExecutionResult with is_error flag
```

### Layer 3: ConcurrencyManager — Safe Parallel Execution

**File:** `backend/tools/concurrency.py`

```python
# Partition tool calls into batches:
def partition_calls(tool_calls: list[ToolCall]) -> list[Batch]:
    # [Read, Read, Glob] → concurrent batch (read-only)
    # [Write, Bash, Edit] → serial batch (write operations)
    # [Read, Read] → concurrent batch (read-only)
```

### Layer 4: QueryLoop — The Multi-Turn Inference Loop

**File:** `backend/tools/query_loop.py`

```python
class QueryLoop:
    async def run(self, messages: list[dict], tools: list[ToolDefinition], ...) -> str:
        while True:
            # 1. Build API request (messages + tool definitions)
            # 2. Call LLM (via llm_api_handler)
            # 3. Check response: tool_use blocks or text?
            # 4. If tool_use: execute tools → collect results
            # 5. If text only: return (task complete)
            # 6. Append tool_results to messages
            # 7. Continue loop
```

**This is the core missing piece.** Your current `llm_request_with_tool_calls()` is a 3-round loop with hardcoded tools. This replaces it with a proper N-turn loop that feeds results back each turn.

### Layer 5: ErrorRecovery — Multi-Tiered Recovery

**File:** `backend/tools/error_recovery.py`

| Tier | Trigger | Action |
|---|---|---|
| API Retry | Rate limit, timeout, 529 | Exponential backoff (like `_retry_with_backoff`) |
| Model Fallback | Persistent API failure | Switch model (sonnet → opus) |
| Output Recovery | Token limit hit | Inject "resume directly" message |
| Tool Recovery | Tool execution error | Feed error to LLM for self-correction |
| Context Collapse | Context too long | Summarize old messages, remove from history |

### Layer 6: AgentSpawner — Subagent Delegation

**File:** `backend/tools/agent_spawner.py`

```python
class AgentSpawner:
    async def spawn(self, agent_type: str, prompt: str, ...) -> AgentResult:
        # Create independent context for subagent
        # Run independent query loop
        # Return structured result to parent
```

### Layer 7: MessageManager — History & Context

**File:** `backend/tools/message_manager.py`

- Normalize messages for API format
- Add prompt caching markers to last block
- Context collapse when near token limit
- Strip orphaned tool calls

---

## Implementation Steps

### Step 1: Create the Tool Orchestration Package

```
backend/tools/
├── __init__.py
├── registry.py       — ToolDefinition dataclass, @register decorator
├── executor.py       — ToolExecutionResult, validation, error formatting
├── concurrency.py    — partitionToolCalls, run parallel/serial
├── query_loop.py     — QueryLoop class, main while(true) loop
├── error_recovery.py — Multi-tiered error handling
├── agent_spawner.py  — Subagent delegation
├── message_manager.py — Message normalization, caching
└── models.py         — Pydantic models for tool inputs
```

### Step 2: Define Built-in Tools

```python
# registry.py
class FileReadInput(BaseModel):
    file_path: str

class FileWriteInput(BaseModel):
    file_path: str
    content: str

class BashInput(BaseModel):
    command: str
    timeout: int = 30

class AgentInput(BaseModel):
    subagent_type: str
    prompt: str
    run_in_background: bool = False
```

### Step 3: Build the Query Loop

Replace `llm_request_with_tool_calls()` with `QueryLoop.run()`:
- Takes messages + tool definitions + max_turns
- Runs the while(true) loop
- Feeds tool results back each turn
- Returns final text when model stops calling tools

### Step 4: Integrate with Existing Code

- `TemplateAnalysisAgent.execute_generation_plan()` → use QueryLoop instead of direct `llm_request()` calls
- `ContentKnowledgeAgent.generate_document()` → use QueryLoop instead of direct `llm_request()` calls
- `ExtractionEventLoop` → already has its own pipeline; keep as-is but use QueryLoop for LLM-dependent stages

### Step 5: Wire Up Error Recovery

Replace the current `_retry_with_backoff()` calls in `llm_api_handler.py` with the new `ErrorRecovery` layer that handles tool-level, API-level, and context-level errors.

### Step 6: Add Agent Spawning

Replace direct agent instantiation (`ContentKnowledgeAgent(...)`) with the Agent tool that spawns independent query loops.

---

## Critical Files to Create/Modify

**New files:**
- `backend/tools/__init__.py`
- `backend/tools/registry.py` — Tool registry + definitions
- `backend/tools/executor.py` — Tool execution + validation + error formatting
- `backend/tools/concurrency.py` — Partitioning + parallel/serial execution
- `backend/tools/query_loop.py` — Main multi-turn loop
- `backend/tools/error_recovery.py` — Multi-tiered recovery
- `backend/tools/agent_spawner.py` — Subagent delegation
- `backend/tools/message_manager.py` — Message normalization + context
- `backend/tools/models.py` — Pydantic input models

**Modified files:**
- `backend/llm_api_handler.py` — Replace `llm_request_with_tool_calls()` usage
- `backend/Memory_Management/document_architect_agent.py` — Use QueryLoop
- `backend/Memory_Management/content_knowledge_agent.py` — Use QueryLoop

---

## Verification

1. **Unit test the QueryLoop**: Create a test that exercises the while(true) loop with mock tools (file read, file write, Bash) and verify tool results are fed back correctly
2. **Integration test with real LLM**: Use a simple task ("read file X, write to file Y, execute script Z") and verify the loop runs end-to-end
3. **Error recovery test**: Force a tool to fail, verify the LLM receives the structured error and self-corrects in the next turn
4. **Concurrency test**: Issue 3 read tools + 1 write tool, verify reads run in parallel and write runs serially
5. **Benchmark**: Compare iteration count and success rate between old `llm_request_with_tool_calls()` and new `QueryLoop`
