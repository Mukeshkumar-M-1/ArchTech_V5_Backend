# Plan: Explore How Claude Code CLI Uses Tools in the Agent Loop

## Context

The user wants to understand the internal mechanics of how the **claude-code** CLI project (a reverse-engineered Claude Code CLI) handles tools and agents during its multi-turn inference loop. They've already read `_Learn/API.md` which documents the API request structure. Now they need a deeper understanding of the **runtime behavior** — how tools are selected, how errors are handled in the loop, how user intent is processed, and how tool failures are recovered.

## Findings

### 1. How Tools Are Chosen by Agents

**Tool definition & selection flow:**

- **Built-in tools** are defined in `packages/builtin-tools/src/tools/` (e.g., Bash, FileRead, FileEdit, Agent, ExitPlanModeV2, TaskOutput, ToolSearch, ComputerUse, Sleep, SyntheticOutput). Each tool is created via `buildTool()` factory which defines name, schema (zod/v4), description, and execution logic.

- **Tool pool assembly** happens in `src/utils/toolPool.ts` (`mergeAndFilterTools()` and `assembleToolPool()`): built-in tools + MCP tools are merged, deduplicated by name, partitioned (built-in prefix, then MCP tools) for prompt-cache stability, and sorted alphabetically by name.

- **Tool choice for the model** is sent via the `tool_choice` API parameter in `src/services/api/claude.ts`:
  - `{type: 'auto'}` — model decides which tools to call (default)
  - `{type: 'any'}` — model must call at least one tool
  - `{type: 'tool', name: '...'}` — model must call a specific tool

- **Dynamic tool loading** via `ToolSearch`: tools can be deferred (not sent in the initial request). The model first calls `ToolSearch` to discover available tools, then uses them. Controlled by `defer_loading: true` on tool schemas (`src/utils/api.ts` → `toolToAPISchema()`).

- **Subagent tool selection** (`packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx`): When the model calls the `Agent` tool, it resolves a `subagent_type` (e.g., "explore", "plan", "general-purpose") from agent definitions. Each agent has its own tool pool, permission mode, and system prompt — independent of the parent.

### 2. How Errors Occur and Are Solved in the Loop

**Error lifecycle — full flow:**

1. **Tool execution** in `src/services/tools/toolExecution.ts` (`runToolUse()`): errors are caught and classified via `classifyToolError()` (line ~179-200) into telemetry-safe strings like `Error:ENOENT`, `ShellError`, etc.

2. **Error message creation** in `src/utils/toolErrors.ts` (`formatError()`): structured error message with exit code, stderr, stdout, and errno codes.

3. **Tool result with `is_error: true`** — the error is returned as a `tool_result` block:
   ```typescript
   { type: 'tool_result', content: errorMessage, is_error: true, tool_call_id: ... }
   ```
   (line ~1801-1823 in `toolExecution.ts`)

4. **Loop continuation** — the error tool_result is appended to `messages` and the loop continues back to `while(true)` in `src/query.ts` (line ~1977). The model sees the error in its context and decides how to self-correct.

5. **Hook-based recovery** — `PostToolUseFailure` hooks in `toolExecution.ts` (line ~1786-1799) inject additional context when tools fail.

**Advanced error recovery in the query loop** (`src/query.ts`):
- **Model Fallback** (line ~1123-1180): On `FallbackTriggeredError`, switches to fallback model and retries
- **Prompt-too-Long Recovery** (line ~1318-1416): Context collapse drain → reactive compact
- **Max Output Tokens Recovery** (line ~1421-1489): Injects "Output token limit hit. Resume directly..." message, retries up to 3 times with 64k max
- **API Retry** in `src/services/api/withRetry.ts`: Up to 10 retries with exponential backoff, handles 429/529/401/403/ECONNRESET
- **Missing Tool Result Blocks** in `yieldMissingToolResultBlocks()`: Generates synthetic tool_results for aborted tools

### 3. How User Intent Is Identified and Processed in the Loop

**Input processing** in `src/utils/processUserInput/processUserInput.ts`:

1. **Input string detection** (line ~324-355): Normalizes input — extracts string from text blocks, handles images (resize/downsample)

2. **Routing logic** — sequential checks:
   - **Bash mode** (line ~531): Routes to `processBashCommand()` for shell commands
   - **Slash commands** (line ~547): Routes to `processSlashCommand()` for `/command` syntax
   - **Ultraplan keyword** (line ~480): Special routing for "plan" detection
   - **Agent mentions** (line ~569): `@agent-<type>` syntax for subagent spawning
   - **Regular prompt** (line ~592): Routes to `processTextPrompt()` which wraps input as a `UserMessage`

3. **Hooks** in `processUserInput()` (line ~189-272): `UserPromptSubmit` hooks can add context, block execution, or inject additional messages

4. **Message construction**: Input becomes a `UserMessage` → sent to `QueryEngine.submitMessage()` → enters the `query()` loop

5. **Intent decomposition**: The model itself decomposes user intent into subtasks — it decides which tools to call, in what order, based on its system prompt and conversation context. There's no hardcoded intent parser beyond the routing above.

### 4. How Tool Failures Are Handled with Tool Dependencies

**Sequential execution via conversation turns:**

The core mechanism is the **infinite `while(true)` loop** in `src/query.ts` (line ~451). Each iteration is one "turn":

1. **Model calls tools** → returns `tool_use` blocks
2. **Tools execute** → `runTools()` in `src/query.ts` (line ~1617) or `streamingToolExecutor` collects results
3. **Results (including errors)** → appended as `tool_result` blocks
4. **Next iteration** → model sees all previous tool results, decides next action

**For tool dependencies within a single turn:**
- The API model **decides tool order** — it doesn't auto-parallelize. It sees tool_result from tool A, then decides to call tool B.
- If tool A fails with an error, the model sees `is_error: true` + error message, reasons about what went wrong, and issues a corrected tool call in the next turn.

**For tool waiting on failed tools:**
- The model **never waits** — it just receives the error and re-evaluates. If tool B depends on tool A, the model will see A's error result and not call B (or will call B differently after fixing A).
- There's no dependency graph — the model's reasoning is the dependency resolver.

**Streaming tool execution** (`streamingToolExecutor`): When `eager_input_streaming: true` is set on tools, the model can receive `input_json_delta` events for large tool inputs, but the actual execution still waits for the full `message_stop` event.

## Verification Plan

1. **Read the key source files** to verify line numbers and code:
   - `src/query.ts` — the `while(true)` loop at line 451
   - `src/utils/processUserInput/processUserInput.ts` — input routing
   - `src/services/tools/toolExecution.ts` — error handling in tool execution
   - `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx` — agent tool execution
   - `src/utils/toolPool.ts` — tool pool assembly
   - `src/utils/toolErrors.ts` — error formatting

2. **Run with debug logging**: `CLAUDE_CODE_DEBUG_LOGGING=1 npx ccb` to observe the actual tool selection and error handling in action

3. **Check the `_Learn/` directory** for additional learned documentation that complements this analysis
