---
title: "Agentic Loop: The core mechanism of AI autonomous loop"
description: "In-depth analysis of Claude Code's query() asynchronous generator loop - a complete state machine from streaming API calls, tool parallel execution, context compression, error recovery to termination conditions, based on source code level analysis of src/query.ts."
keywords:
  [
    "Agentic Loop",
    "query loop",
    "tool_use",
    "state machine",
    "auto-compact",
    "streaming",
    "recovery",
  ]
sourceRef: "3ec5675 (2026-04-08)"
---

{/_ The goal of this chapter: Reveal the complete state machine of Agentic Loop based on src/query.ts _/}

## What is Agentic Loop?

Traditional chatbot: you ask a question and it answers.
Claude Code is different: you say a requirement, and it may perform more than ten consecutive steps before giving you the final result.

The mechanism behind this is called **Agentic Loop** (agent loop), and the core is implemented in the `queryLoop()` asynchronous generator function in `src/query.ts`. It is a `while(true)` infinite loop, and each iteration represents a "think → act → observe" cycle.

<Frame caption="Agentic Loop loop diagram"> 
<img src="/docs/images/agentic-loop.png" alt="Agentic Loop loop diagram" /> 
</Frame>

## The complete structure of the loop

Each iteration of `queryLoop()` (the `while(true)` main loop in `src/query.ts`) contains the following stages:

### Phase 1: Context Pre-Processing (Pre-Processing Pipeline)

Before calling the API, 5 compression/optimization steps are performed in sequence:

```
messagesForQuery(original message)
↓ applyToolResultBudget() — tool result budget truncation (by maxResultSizeChars)
↓ snipCompactIfNeeded() — Historical Snip compression (HISTORY_SNIP feature)
↓ microcompact() — microcompact (summary of tool results)
↓ applyCollapsesIfNeeded() — Context folding (CONTEXT_COLLAPSE feature)
↓ autocompact() — automatic compaction (triggered when threshold is exceeded)
messagesForQuery (processed message) → sent to API
```

The output of each step is the input to the next step, forming a serial pipeline. The number of release tokens of Snip and Microcompact will be passed to the threshold calculation of autocompact (`snipTokensFreed`) to avoid repeated compression.

### Phase 2: Streaming API call (Streaming Loop)

`deps.callModel()` initiates a streaming request (inside the `attemptWithFallback` loop in `src/query.ts`) and returns an AsyncGenerator. During streaming:

- **AssistantMessage** is collected into the `assistantMessages[]` array
- **tool_use blocks** are extracted into `toolUseBlocks[]`, set `needsFollowUp = true`
- **StreamingToolExecutor** starts executing tools in parallel during the streaming process (without waiting for the end of the stream)
- Recoverable errors (prompt-too-long, max-output-tokens) are **withheld** (withheld), try to recover first

Key guards in streaming callbacks:

- `backfillObservableInput()` - backfill observable fields (such as file path expansion) for tool_use blocks, but only clone the message when new fields are added to avoid breaking the byte consistency of the prompt cache
- Streaming downgrade detection - if `streamingFallbackOccured`, collected messages are marked as tombstone, clear and try again

### Phase 3: Tool Execution

If `needsFollowUp` is true, the loop does not terminate, but the tool is executed:

```typescript
// Two tool executors (mutually exclusive)
const toolUpdates = streamingToolExecutor
  ? streamingToolExecutor.getRemainingResults() // Streaming: Get completed + waiting
  : runTools(toolUseBlocks, assistantMessages, canUseTool, toolUseContext);
```

After the tool results are normalized through `normalizeMessagesForAPI()`, they are merged with the original messages and enter the next round of loop iterations.

### Phase 4: Terminate or Continue

At the end of each iteration, `return` (termination) or `continue` (continue) is determined based on the condition:

## Termination condition (source code level)

There are multiple termination paths for loops, arranged by triggering time:

| Termination reason      | Trigger location | Mechanism                                                                                                            |
| ----------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| **blocking_limit**      | Line 686         | Token count exceeds hard limit (non-autocompact mode) → Generate PTL error message → Return                          |
| **image_error**         | Line 1021        | `ImageSizeError` / `ImageResizeError` exception → return directly                                                    |
| **model_error**         | Line 1040        | `callModel()` throws an unrecoverable exception → generate error message → return                                    |
| **aborted_streaming**   | Line 1095        | `abortController.signal.aborted` (streaming stage) → generate synthetic tool_result for unfinished tool_use → return |
| **prompt_too_long**     | Line 1219/1226   | 413 error and reactive compact cannot recover → suspended error message is released → return                         |
| **completed**           | Line 1308        | API error (current limiting, authentication failure, etc.) prevents continued → Return                               |
| **stop_hook_prevented** | Line 1323        | Stop hook returns `preventContinuation: true` → return                                                               |
| **completed**           | Line 1401        | Completed normally: AI did not issue tool_use → `needsFollowUp = false` → past stop hooks → return                   |
| **aborted_tools**       | Line 1559        | `abortController.signal.aborted` (tools execution phase) → return                                                    |
| **hook_stopped**        | Line 1564        | Hook returns `shouldPreventContinuation` during tool execution → return                                              |
| **max_turns**           | Line 1755        | Turn count exceeds `maxTurns` limit → return                                                                         |

## Continue conditions (recovery path)

The loop is not just a simple "continue with tool_use", it also contains multiple recovery/retry paths:

### 1. Normal tool loop (`next_turn`)

`needsFollowUp = true` → Execute tool → Append new messages to `messagesForQuery` → Reassign state → `continue`

### 2. max_output_tokens recovery (`max_output_tokens_escalate` / `max_output_tokens_recovery`)

When AI output is truncated (`apiError === 'max_output_tokens'`), recovery occurs in two stages:

- **Boost phase** (`max_output_tokens_escalate`): Boost `maxOutputTokens` from default to `ESCALATED_MAX_TOKENS` (64K) on first truncation. Retry silently without injecting meta messages.
- **Recovery phase** (`max_output_tokens_recovery`): When it is still truncated after promotion, the recovery message "Output token limit hit. Resume directly..." is injected, and the maximum retry is `MAX_OUTPUT_TOKENS_RECOVERY_LIMIT = 3` times. After recovery is exhausted, the pending error messages are released.

### 3. Prompt-Too-Long recovery (`collapse_drain_retry` / `reactive_compact_retry`)

When encountering a 413 error, two compression strategies are tried in order of priority:

- **Context Collapse Drain** (`collapse_drain_retry`): Submit all temporary collapses (collapse), free up space and try again. If the previous round is already `collapse_drain_retry`, skip it to avoid infinite loop.
- **Reactive Compact** (`reactive_compact_retry`): If the collapse drain cannot be recovered, trigger instant compression (reactive compact), generate a summary and try again. The `hasAttemptedReactiveCompact` flag prevents infinite loops.

### 4. Stop Hook blocking retry (`stop_hook_blocking`)

Stop hooks can inject blocking error messages, forcing the AI to rethink. New messages (including blocking errors) are appended to the conversation, `stopHookActive = true`, and enter the next iteration.

### 5. Token Budget continuation prompt (`token_budget_continuation`)

When the `TOKEN_BUDGET` feature is enabled, if the token consumption reaches the threshold but does not exceed the budget, a nudge message is injected to allow the AI to speed up the closing, and then continue.

## Model downgrade (Fallback)

When the main model is not available (`FallbackTriggeredError`, catch branch of `attemptWithFallback` loop in `src/query.ts`):

1. The collected `assistantMessages` are cleared, and the tool_use block receives the synthesized tool_result: "Model fallback triggered"
2. The thinking signature blocks are removed (`stripSignatureBlocks`) - because the thinking signature is bound to the model, cross-model playback will be 400
3. Switch to `fallbackModel` and update `toolUseContext.options.mainLoopModel`
4. Generate system message: "Switched to {fallback} due to high demand for {original}"
5. Re-initiate streaming request

## State machine: State object

The state for each iteration is passed through the `State` type (`src/query.ts`, type definition):

```typescript
// src/query.ts — State type definition
type State = {
messages: Message[] // Current conversation message
toolUseContext: ToolUseContext // Tool context (including permissions)
autoCompactTracking: AutoCompactTrackingState | undefined // Compression tracking
maxOutputTokensRecoveryCount: number //Output truncation recovery count
hasAttemptedReactiveCompact: boolean // Whether instant compression has been attempted
maxOutputTokensOverride: number | undefined // Output token upper limit override
pendingToolUseSummary: Promise<...> | undefined // Asynchronous tool summary
stopHookActive: boolean | undefined // Whether Stop hook is activated
turnCount: number // Turn count
transition: Continue | undefined // Reason for last continuation
}
```

Each `continue` creates a new State object (immutable update) instead of modifying it in place. The `transition` field records why to continue - allowing subsequent iterations to detect specific recovery paths (such as `collapse_drain_retry`) to avoid loops.

## Token Budget (Experimental)

When the `TOKEN_BUDGET` feature is enabled (budget check logic in the `!needsFollowUp` branch in `src/query.ts`), the loop checks token consumption before terminating:

- **continuation**: The budget has not been reached but the threshold has been exceeded → Inject nudge message to let AI speed up the closing
- **diminishing_returns**: Diminishing returns detected → early termination
- Budget data comes from `createBudgetTracker()`, accumulated across iterations

## Why not "plan once and execute in batches"

<Note> 
The source code reveals why Claude Code chose to cycle step by step: 
</Note>

- **Each step generates real information**: `runTools()` returns `toolResults` that are impossible to predict by the API - command output, file contents, error messages
- **Dynamic context management**: Re-evaluate compression requirements (autocompact → microcompact → snip) before each iteration, based on the latest token count
- **Instant Error Recovery**: If the tool fails, there is no need to reinvent the wheel - stop hook can inject blocking errors to allow the AI to correct the strategy
- **User Controllable**: `abortController.signal` is detected at multiple checkpoints in the loop (lines 1059, 1095, 1529) and can be aborted gracefully by the user pressing ESC
- **Cost Control**: Token Budget is checked before each round is terminated to prevent AI invalid loops

## A complete iteration example

> User: "Help me find all unused import statements in the project and delete them"

```
Iteration 1: Think → Act
Preprocessing pipeline: applyToolResultBudget → snipCompact(HISTORY_SNIP feature) → microcompact → applyCollapses(CONTEXT_COLLAPSE feature) → autocompact
→ The context is short and no compression is required
API call: return tool_use(Glob, "**/*.ts")
Tool execution: 42 file paths returned
→ needsFollowUp = true
→ transition: { reason: 'next_turn' }, continue

Iteration 2: Think → Act
Preprocessing pipeline: 42 files results still within budget
API call: return tool_use(Grep, "import.*from")
Tool execution: 120 imports found in 15 files
→ needsFollowUp = true
→ transition: { reason: 'next_turn' }, continue

Iteration 3: Think → Act (multiple rounds)
Preprocessing pipeline: 120 Grep results trigger microcompact → summary
API call: returns 3 tool_use(FileEdit, ...)
Tool execution: Delete 5 unused imports
→ needsFollowUp = true
→ transition: { reason: 'next_turn' }, continue

Iteration 4: Summary
API call: Returns plain text "Cleaned 5 unused imports in 3 files"
→ needsFollowUp = false
→ Stop hooks passed
→ Token Budget check passed (if enabled)
→ return { reason: 'completed' }
```
