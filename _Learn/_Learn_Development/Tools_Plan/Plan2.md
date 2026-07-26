# Plan: Deep-Dive Analysis of How Claude Code CLI Uses Tools in the Agent Loop

## Context

The user wants a comprehensive deep-dive understanding of how the **claude-code** CLI project handles tools and agents during its multi-turn inference loop. They've already read `_Learn/API.md` (API request structure) and now need to understand the **runtime behavior**: how tools are selected, how errors are handled in the loop, how user intent is processed, and how tool failures are recovered. They want code snippets, data flow diagrams, and edge cases.

---

## TOPIC 1: How Tools Are Chosen by Agents

### 1.1 Tool Pool Assembly

**File:** `src/tools.ts` — `getAllBaseTools()` returns ~60+ built-in tool definitions.
**File:** `src/utils/toolPool.ts:55-79` — `mergeAndFilterTools()` merges built-in + MCP tools:
- Deduplicates by tool name (`uniqBy`)
- Partitions into built-in prefix (for prompt-cache stability) + MCP suffix
- Sorts alphabetically within each partition
- Applies coordinator-mode filtering (only a whitelist of tools)

```typescript
// src/utils/toolPool.ts:55-79
export function mergeAndFilterTools(initialTools, assembled, _mode): Tools {
  const [mcp, builtIn] = partition(uniqBy([...initialTools, ...assembled], 'name'), isMcpTool)
  const byName = (a, b) => a.name.localeCompare(b.name)
  const tools = [...builtIn.sort(byName), ...mcp.sort(byName)]
  // coordinator-mode filter applied here
  return tools
}
```

### 1.2 Tool-to-API Schema Conversion

**File:** `src/utils/api.ts:119-266` — `toolToAPISchema()` converts each tool to an Anthropic API `BetaTool`:
- Uses `tool.prompt()` to get the description (this is how the Agent tool dynamically lists available agents)
- Caches the base schema (session-stable) to prevent drift
- Adds per-request overlays: `defer_loading` (tool search), `cache_control` (prompt caching)
- Enables `strict` mode (feature-gated via `tengu_tool_pear`)
- Enables `eager_input_streaming` for large tool inputs

```typescript
// src/utils/api.ts:169-178
base = {
  name: tool.name,
  description: await tool.prompt({ /* context */ }),
  input_schema: 'inputJSONSchema' in tool ? tool.inputJSONSchema : zodToJsonSchema(tool.inputSchema),
}
```

### 1.3 Tool Choice Parameter

**File:** `src/services/api/claude.ts:1811` — `tool_choice` is passed through from options:
- `undefined` / `{type: 'auto'}` — model auto-decides (default at REPL level)
- `{type: 'any'}` — model must call at least one tool
- `{type: 'tool', name: '...'}` — model must call a specific tool

### 1.4 Dynamic Tool Loading (Tool Search)

**File:** `src/services/api/claude.ts:1190-1212` — When tool search mode is enabled:
- Deferred tools are hidden from the initial API request (marked with `defer_loading: true`)
- Model must first call `ToolSearch` to discover available tools
- Only discovered deferred tools are included in subsequent requests
- Undiscovered tool calls return a Zod error that tells the model to discover the tool first

### 1.5 Subagent Tool Selection

**File:** `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx:725` — When the Agent tool spawns a subagent:
```typescript
const workerTools = assembleToolPool(workerPermissionContext, appState.mcp.tools)
```
- Each subagent gets its **own independent tool pool**
- The `subagent_type` (explore, plan, general-purpose) determines the agent's system prompt and tool permissions
- Fork subagents (`fork: true`) inherit the parent's exact tool definitions for prompt cache hits

---

## TOPIC 2: How Errors Occur and Are Solved in the Loop

### 2.1 The Core Loop

**File:** `src/query.ts:451` — The infinite `while(true)` loop. Each iteration is one "turn":

```
turn 1: user prompt → model → tool_use[A] → execute A → tool_result[A] → continue
turn 2: ... + tool_use[B] → execute B → tool_result[B] → continue
turn 3: model returns text only → stop hooks → return {reason: 'completed'}
```

### 2.2 Tool-Level Errors

**File:** `src/services/tools/toolExecution.ts:366-519` — `runToolUse()` wraps each tool in try/catch:

```typescript
// Error handling in toolExecution.ts:1664-1831
catch (error) {
  // MCP auth errors update client status
  // Errors formatted via formatError() — truncated to 10k chars
  // Post-ToolUse-Failure hooks run for additional context
  return [{
    message: createUserMessage({
      content: [{ type: 'tool_result', content: errorMessage, is_error: true, tool_call_id }],
      toolUseResult: `Error: ${content}`,
    }),
  }]
}
```

**File:** `src/utils/toolErrors.ts:5-22` — Error formatting:
- `ShellError`: exit code + interrupted status + stderr + stdout
- `AbortError`: clean cancellation message
- `ZodError`: structured message with missing/extra/mis-typed parameters
- General `Error`: message + stderr/stdout if present

```typescript
// src/utils/toolErrors.ts:66-132
export function formatZodValidationError(toolName, error): string {
  // Identifies: missing params, unexpected params, type mismatches
  // Produces: "FileEdit failed due to the following issues:
  //   The required parameter `range` is missing
  //   The parameter `target_file` type is expected as `string` but provided as `number`"
}
```

### 2.3 Error Feedback to Model

The error `tool_result` block is appended to messages and the loop `continue`s. The model sees:
```json
{ "role": "user", "content": [{ "type": "tool_result", "content": "Exit code 1\n...stderr...\n", "is_error": true, "tool_call_id": "toolu_0123" }] }
```
The model reasons about the error and issues corrected tool calls in the next turn.

### 2.4 Advanced Error Recovery

**File:** `src/query.ts:1318-1489` — Multi-tiered recovery:

| Recovery | Condition | Action |
|---|---|---|
| Context Collapse Drain | Prompt too long (413), first attempt | Staged collapses committed, messages replaced with summaries |
| Reactive Compact | Prompt too long, second attempt | Summarizes conversation with Haiku |
| Output Token Escalation | Hit 8k output limit | Retry with 64k max tokens |
| Output Token Recovery | Hit 64k limit | Inject "Resume directly..." message, retry up to 3x |
| Model Fallback | 3 consecutive 529 errors | Switch from opus → sonnet |

### 2.5 API-Level Retry

**File:** `src/services/api/withRetry.ts:170` — Wraps every API call:
- Max 10 retries with exponential backoff
- 429 (rate limit): Wait + retry or fast-mode fallback
- 529 (overloaded): Retry with backoff; 3 consecutive → model fallback
- 401/403: Refresh auth tokens
- ECONNRESET/EPIPE: Disable keep-alive, recreate client

### 2.6 Stop Hook Integration

**File:** `src/query/stopHooks.ts` — Stop hooks run after model response:
- `SendUserMessage` → signals task complete, sets `shouldPreventContinuation`
- `Stop` hook → can inject blocking error messages
- The loop checks `shouldPreventContinuation` and handles accordingly

---

## TOPIC 3: How User Intent Is Identified and Processed in the Loop

### 3.1 Input Processing Pipeline

**File:** `src/utils/processUserInput/processUserInput.ts:89-620`

```
User input string
  ↓
processUserInputBase (line 290)
  ↓
Image processing: resize, downsample, store to disk (lines 326-429)
  ↓
Attachment extraction: files, images, IDE selection (lines 510-528)
  ↓
[ROUTE]
  ├── Bash mode (mode === 'bash')
  │     └── processBashCommand (line 531)
  ├── Ultraplan keyword detected (hasUltraplanKeyword)
  │     └── Rewrite to /ultraplan → processSlashCommand (lines 480-507)
  ├── Starts with "/" → processSlashCommand (line 552)
  ├── @agent-<type> mention
  │     └── Log event, pass to processTextPrompt with agent context (lines 569-589)
  └── Plain text → processTextPrompt (line 592)
  ↓
processTextPrompt (processTextPrompt.ts:19)
  ├── Check for negative/keep-going keywords
  ├── Create UserMessage with text + image blocks
  └── Return { messages: [...], shouldQuery: true }
  ↓
QueryEngine.submitMessage (QueryEngine.ts:217)
  ├── Wrap canUseTool for tracking
  ├── Fetch system prompt parts
  └── Call query() with assembled parameters
  ↓
query() → queryLoop() → while(true) loop (src/query.ts:267, 384)
```

### 3.2 Input String Extraction

**File:** `src/utils/processUserInput/processUserInput.ts:324-355`
- If input is plain string → use directly
- If input is content blocks → extract text from last block, keep preceding blocks as images/attachments
- For bridge/mobile inputs: normalizes `mediaType` → `media_type`

### 3.3 Slash Command Processing

**File:** `src/utils/processUserInput/processSlashCommand.tsx`
- Parses `/command --arg value` syntax
- Routes to registered commands in `src/commands.ts`
- Commands can be local-jsx (UI), terminal-only, or safe for remote bridge
- Each command can return messages, block execution, or trigger special behaviors

### 3.4 Hook Integration

**File:** `src/utils/processUserInput/processUserInput.ts:189-272`
- `UserPromptSubmit` hooks run after input processing
- Can add additional context (attachment messages)
- Can block execution (`blockingError`, `preventContinuation`)
- Can inject success/error messages

### 3.5 Message Construction for API

**File:** `src/services/api/claude.ts:1304-1447`
- `normalizeMessagesForAPI` converts internal message types to API format
- Tool-reference blocks stripped for non-tool-search models
- `ensureToolResultPairing` fixes orphaned tool_use/tool_result mismatches
- Excess media items stripped
- Last content block of each message gets `cache_control: {type: 'ephemeral'}`

---

## TOPIC 4: How Tool Failures Are Handled with Tool Dependencies

### 4.1 Concurrency Partitioning

**File:** `src/services/tools/toolOrchestration.ts:20-207`

```
model returns: [Edit(file), Read(file1), Bash(cmd), Read(file2), Bash(cmd)]
                    │                     │            │          │
                    │                     │            │          └─ read-only → batch3
                    │                     │            └─ read-only → batch3
                    │                     └─ write → batch2 (serial)
                    └─ write → batch2 (serial)
              batch1: no tools (empty prefix)
```

**`partitionToolCalls` (lines 106-131):**
```typescript
// Each tool checks tool.isConcurrencySafe(parsedInput)
// Read-only tools (Read, Glob, Bash with read-only commands) → concurrency-safe
// Write tools (Write, Edit) and write Bash → not concurrency-safe
// Consecutive safe tools are batched together
```

**Batch execution:**
- `runToolsConcurrently` (lines 169-196): Read-only batch runs in parallel (max 10 concurrent)
- `runToolsSerially` (lines 133-167): Non-read-only batch runs one at a time, applying context updates between each

### 4.2 Context Modifiers

- **Concurrent mode**: Context modifiers are queued and applied after all concurrent tools complete
- **Serial mode**: Each tool's context update is applied before the next tool runs

### 4.3 Error Recovery During Tool Execution

**File:** `src/services/tools/toolExecution.ts:1664-1831`

Each tool execution follows this path:
```
Pre-ToolUse hooks → if any hook returns "stop" → cancel early
Permission check → if denied → return tool_result with denial reason
Validate input (Zod) → if invalid → formatZodValidationError → tool_result with error
Execute tool → if error → formatError → runPostToolUseFailureHooks → tool_result with is_error:true
```

### 4.4 No Explicit Dependency Graph

Dependencies emerge through:
1. **Partition ordering**: Write tools always run serially between read-only batches
2. **Model reasoning**: The model sees tool results and decides subsequent calls
3. **Deferred tool loading**: Model must discover tools before using them
4. **Sequential turns**: Each API call includes ALL previous tool_results as context

### 4.5 Agent Tool as a Dependency Resolver

**File:** `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx:326-1456`

The Agent tool creates an entirely independent query loop:
- Spawns a subagent with its own tool pool, system prompt, messages
- Subagent runs `query()` which runs its own `while(true)` loop
- Result is returned as a single tool_result to the parent
- Parent model sees the result and decides next steps

### 4.6 Edge Cases

| Scenario | Handling |
|---|---|
| Agent MCP server not connected | Waits up to 30 seconds, then errors |
| Fork subagent with incomplete tool calls | `filterIncompleteToolCalls` strips orphaned tool_use blocks |
| Mid-turn user abort (ESC) | `getRemainingResults()` generates synthetic tool_results for in-progress tools |
| Max turns exceeded | Yields `max_turns_reached` attachment, returns `{reason: 'max_turns'}` |
| Budget exceeded | Yields `error_max_budget_usd` |
| Structured output retry limit | 5 retries (configurable), then yields error |

---

## Combined Data Flow Diagram

```
User types: "Fix the login bug in src/auth.ts"
    │
    ▼
processUserInput(processUserInput.ts:89)
  └── processUserInputBase (line 290)
        ├── Image processing (lines 326-429)
        ├── Attachment extraction (lines 510-528)
        └── Plain text → processTextPrompt (line 592)
              └── Returns { messages: [UserMessage], shouldQuery: true }
    │
    ▼
QueryEngine.submitMessage(QueryEngine.ts:217)
  └── Assembles: systemPrompt, messages, toolUseContext, options
  └── Calls query(state)
    │
    ▼
queryLoop — while(true) loop (src/query.ts:451)
    │
    ├── [Each iteration = one "turn"]
    │
    ├── Step 1: Compact checks (lines 509-713)
    │     └── Snip, microcompact, context-collapse, autocompact
    │
    ├── Step 2: Build API request (lines 716-800)
    │     ├── normalizeMessagesForAPI → API-compatible format
    │     ├── toolToAPISchema for each tool → BetaTool[]
    │     ├── filter deferred tools (tool search mode)
    │     └── Assemble: { model, messages, system, tools, tool_choice, betas, ... }
    │
    ├── Step 3: callModel → queryModel (claude.ts:1057)
    │     └── withRetry (withRetry.ts:170) [wraps everything, handles 429/529/401]
    │           └── API streaming → yields StreamEvent | AssistantMessage
    │
    ├── Step 4: Model returns assistant message
    │     ├── No tool_use blocks + text output → return {reason: 'completed'} ✓
    │     └── Has tool_use blocks → proceed to tool execution
    │
    ├── Step 5: Execute tools (toolOrchestration.ts:20)
    │     ├── partitionToolCalls → [read-only batch, write batch, read-only batch, ...]
    │     ├── runToolsConcurrently for read-only batches (max 10 parallel)
    │     ├── runToolsSerially for write batches (one at a time)
    │     └── For each tool: runToolUse (toolExecution.ts:366)
    │           ├── Pre-ToolUse hooks
    │           ├── Permission check
    │           ├── Zod input validation
    │           ├── tool.call() → on success: post hooks
    │           └── on error: formatError → tool_result with is_error:true
    │
    ├── Step 6: Collect tool_results
    │     └── Each tool_result normalized → UserMessage with tool_result content block
    │
    ├── Step 7: Mid-turn attachments (memory prefetch, queued commands, skill discovery)
    │
    ├── Step 8: Check limits (max turns, budget)
    │
    └── Step 9: Continue → state = { messages + assistantMessages + toolResults }
              [loop back to Step 1]
              │
              ▼
    [Loop continues until: model returns text only, or error, or max turns]
    │
    ▼
Stop hooks (stopHooks.ts)
  └── SendUserMessage → task complete
  └── Stop → blocking error
    │
    ▼
Return { reason: 'completed' | 'aborted' | 'max_turns' | 'prompt_too_long' | ... }
```

---

## Critical Files Summary

| File | Role | Key Lines |
|---|---|---|
| `src/query.ts` | Main while(true) loop, recovery, compaction | 1990 lines, loop at 451 |
| `src/services/api/claude.ts` | queryModel, tool schemas, dynamic tool loading | 3619 lines, 1190-1212, 1811 |
| `src/services/tools/toolExecution.ts` | Per-tool execution, validation, error handling | 1831 lines, 366-519, 1664-1831 |
| `src/services/tools/toolOrchestration.ts` | Tool partitioning, concurrent vs serial execution | 207 lines, 106-131 |
| `src/services/api/withRetry.ts` | API retry with exponential backoff | 819 lines, 170 |
| `src/utils/toolErrors.ts` | Error formatting (ShellError, ZodError) | 133 lines, 5-22, 66-132 |
| `src/utils/toolPool.ts` | Tool pool assembly and filtering | 80 lines, 55-79 |
| `src/utils/api.ts` | toolToAPISchema, system prompt building | 119-266 |
| `src/utils/processUserInput/processUserInput.ts` | Input processing and routing | 620 lines, 89-279, 290-604 |
| `src/utils/processUserInput/processTextPrompt.ts` | Text prompt → UserMessage | 19 lines |
| `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx` | Agent tool spawn, subagent lifecycle | 326-1456 |
| `packages/builtin-tools/src/tools/AgentTool/runAgent.ts` | Subagent query loop initialization | 959 lines |
| `src/query/stopHooks.ts` | Post-response stop hooks | Various |
| `src/QueryEngine.ts` | Top-level query submission | 217, 1032-1101 |

---

## Verification Steps

1. **Read the key source files** listed above to verify line numbers and understand the actual code
2. **Run with debug logging**: `CLAUDE_CODE_DEBUG_LOGGING=1 npx ccb` to observe actual tool selection and error handling
3. **Check `captureAPIRequest()` in `src/utils/log.ts`** for request body capture (used for bug reports)
4. **Check the `_Learn/` directory** for additional learned documentation that complements this analysis
