# Phase 2: Detailed Explanation of Core Conversation Loop

> How a user's sentence turns into an API request, how to handle streaming responses, and how tool calls are managed

## Conversation Loop Overview

```
User inputs: "Help me read README.md"
  │
  ▼
REPL.tsx: onSubmit → handlePromptSubmit → onQuery → onQueryImpl
  │
  ├── 1. Parallel Context Loading:
  │     getSystemPrompt() + getUserContext() + getSystemContext()
  │
  ├── 2. buildEffectiveSystemPrompt() — Synthesize final system prompt
  │
  ├── 3. for await (const event of query({...}))  ★ Core Loop
  │     │
  │     │  query.ts: queryLoop()
  │     │    ├── while (true) {
  │     │    │     ├── autocompact / microcompact processing
  │     │    │     ├── deps.callModel() → claude.ts streaming API call
  │     │    │     │     └── for await (message of stream) { yield message }
  │     │    │     │
  │     │    │     ├── Collect tool_use blocks from assistant messages
  │     │    │     │
  │     │    │     ├── needsFollowUp?
  │     │    │     │     ├── true → Execute tool → Collect results → state = next → continue
  │     │    │     │     └── false → Check error recovery → return { reason: 'completed' }
  │     │    │     }
  │     │
  │     └── onQueryEvent(event) — Update UI state
  │
  └── 4. Cleanup: resetLoadingState(), onTurnComplete()
```

### Two Data Paths

| Path | Caller | Description |
|------|--------|------|
| **Interactive (REPL)** | REPL.tsx → `query()` | Directly calls `query()` AsyncGenerator |
| **Non-interactive (SDK/print)** | print.ts → `QueryEngine.submitMessage()` → `query()` | Wrapped via QueryEngine, adding session persistence, usage tracking, etc. |

---

## 1. query.ts (line 1732) — Core Query Loop

**File Path**: `src/query.ts`

### 1.1 File Structure

```
query.ts (1732 lines)
├── [0-120]      Import area + feature flag conditional module loading
├── [122-148]    yieldMissingToolResultBlocks() — Generates error tool_results for unpaired tool_uses
├── [150-178]    Constants and helper functions (MAX_OUTPUT_TOKENS_RECOVERY_LIMIT, isWithheldMaxOutputTokens)
├── [180-198]    QueryParams type definition
├── [200-216]    State type — Mutable state between loop iterations
├── [218-238]    query() — Exported AsyncGenerator, delegates to queryLoop()
├── [240-1732]   queryLoop() — Core while(true) loop
│   ├── [241-306]    Initialize State + memory prefetch
│   ├── [307-448]    Loop start: Destructure state, message preprocessing (snip/microcompact/context collapse)
│   ├── [449-578]    System prompt construction (L449) + autocompact (L453) + StreamingToolExecutor initialization (L562)
│   ├── [650-866]    ★ deps.callModel() (L659) + streaming response processing + tool_use collection
│   ├── [896-956]    Error handling (FallbackTriggeredError, general errors)
│   ├── [1002-1054]  Interruption handling (abortController.signal.aborted)
│   ├── [1065-1360]  Termination/recovery logic when no follow-up
│   │   ├── prompt-too-long recovery
│   │   ├── max_output_tokens recovery (upgrade + multi-round)
│   │   ├── stop hooks execution
│   │   └── return { reason: 'completed' }
│   └── [1360-1732]  Tool execution + Next round preparation when follow-up required
│       ├── Tool execution (streaming or sequential)
│       ├── Attachment injection (queued commands, memory prefetch, skill discovery)
│       ├── maxTurns check
│       └── state = next → continue
```

### 1.2 Entry: query() Function (Line 219)

```ts
export async function* query(params: QueryParams):
  AsyncGenerator<StreamEvent | Message | ..., Terminal> {
  const consumedCommandUuids: string[] = []
  const terminal = yield* queryLoop(params, consumedCommandUuids)
  // Notify that all consumed queued commands are completed
  for (const uuid of consumedCommandUuids) {
    notifyCommandLifecycle(uuid, 'completed')
  }
  return terminal
}
```

`query()` itself is thin, doing only two things:
1. Delegates to `queryLoop()` for actual logic.
2. Notifies the lifecycle of queued commands after normal return.

### 1.3 QueryParams (Line 181)

```ts
type QueryParams = {
  messages: Message[]           // Current conversation messages
  systemPrompt: SystemPrompt    // System prompt
  userContext: { [k: string]: string }  // User context (CLAUDE.md, etc.)
  systemContext: { [k: string]: string }  // System context (git status, etc.)
  canUseTool: CanUseToolFn      // Tool permission check function
  toolUseContext: ToolUseContext // Tool execution context
  fallbackModel?: string        // Fallback model
  querySource: QuerySource      // Query source identifier
  maxTurns?: number             // Maximum turns limit
  taskBudget?: { total: number }  // Token budget
}
```

### 1.4 State — Mutable State between Loop Iterations (Line 204)

```ts
type State = {
  messages: Message[]               // Accumulated message list
  toolUseContext: ToolUseContext     // Tool execution context
  autoCompactTracking: ...          // Auto-compaction tracking
  maxOutputTokensRecoveryCount: number  // Max output token recovery attempt count
  hasAttemptedReactiveCompact: boolean  // Whether reactive compact was attempted
  maxOutputTokensOverride: number | undefined  // Output token override
  pendingToolUseSummary: Promise<...>   // Pending tool use summary
  stopHookActive: boolean | undefined   // Whether stop hook is active
  turnCount: number                     // Current turn
  transition: Continue | undefined      // Why the last iteration continued
}
```

**Design Key**: All states are updated at once via `state = { ... }` upon each `continue`, rather than 9 scattered assignments. The `transition` field records why the loop continued (facilitates debugging and testing).

### 1.5 queryLoop() Core Flow (Line 241)

Each iteration of the `while (true)` loop (Line 307) represents one API call. The loop continues until:
- Model requires no tool call → `return { reason: 'completed' }`
- Interrupted by user → `return { reason: 'aborted_*' }`
- Max turns reached → `return { reason: 'max_turns' }`
- Unrecoverable error encountered → `return { reason: 'model_error' }`

#### Step 1: Message Preprocessing

```
Start of each iteration:
  ├── Destructure state → messages, toolUseContext, tracking, ...
  ├── getMessagesAfterCompactBoundary() — Keep only messages after compact boundary
  ├── snip processing (feature flag, skipped)
  ├── microcompact processing (feature flag, skipped)
  └── autocompact check — Automatically compact if messages are too long
```

#### Step 2: System Prompt Construction (Line 449)

```ts
const fullSystemPrompt = asSystemPrompt(
  appendSystemContext(systemPrompt, systemContext),
)
```

Appends system context (git status, date, etc.) to the system prompt. Note: User context (CLAUDE.md, etc.) is not injected here, but rather at the very beginning of the message array via `prependUserContext(messagesForQuery, userContext)` when `deps.callModel()` is called (Line 660).

#### Step 3: Autocompact (Lines 454-543)

Automatically compacts when message history is too long:

```
autocompact flow:
  ├── Check if token count exceeds threshold
  ├── If exceeded → Call compact API (summarize history with Haiku)
  │   ├── yield compactBoundaryMessage  ← Mark compact boundary
  │   └── Update messages to compacted version
  └── If not exceeded → Continue
```

#### Step 4: Call API (Lines 559-708) — Core

StreamingToolExecutor initializes at Line 562, and the API call begins at Line 659:

```ts
// Line 562: Initialize streaming tool executor
let streamingToolExecutor = useStreamingToolExecution
  ? new StreamingToolExecutor(
      toolUseContext.options.tools, canUseTool, toolUseContext,
    )
  : null

// Line 659: Call API
for await (const message of deps.callModel({
  messages: prependUserContext(messagesForQuery, userContext),  // ← User context injected at the very beginning
  systemPrompt: fullSystemPrompt,
  thinkingConfig: toolUseContext.options.thinkingConfig,
  tools: toolUseContext.options.tools,
  signal: toolUseContext.abortController.signal,
  options: { model: currentModel, querySource, fallbackModel, ... }
})) {
  // Process each streaming message (Lines 708-866)
}
```

`deps.callModel()` ultimately calls `queryModelWithStreaming()` in `claude.ts`.

#### Step 5: Streaming Response Processing (Lines 708-866)

Processing logic is inside the `for await` loop body (from after `})` on Line 708 to Line 866):

```
for await (const message of stream):
  ├── message.type === 'assistant'?
  │   ├── Record in assistantMessages[]
  │   ├── Extract tool_use blocks → toolUseBlocks[]
  │   ├── needsFollowUp = true (if tool_use exists)
  │   └── streamingToolExecutor.addTool()  ← Parallel streaming tool execution
  │
  ├── withheld? (prompt-too-long / max_output_tokens)
  │   └── Withhold and do not yield, wait for subsequent recovery logic
  │
  └── yield message  ← Yield to upper layer (REPL/QueryEngine) as normal
```

**StreamingToolExecutor**: Starts executing tools (e.g., reading files) as soon as they are returned by the API stream, without waiting for the stream to end. Tools to be executed are added via `addTool()`, and completed results are retrieved via `getCompletedResults()`.

#### Step 6A: No followUp — Termination/Recovery (Lines 1065-1360)

When the model does not request a tool call (`needsFollowUp === false`):

```
No followUp:
  ├── prompt-too-long recovery?
  │   ├── context collapse drain (feature flag, skipped)
  │   ├── reactive compact → Compact messages and retry
  │   └── All failed → yield error + return
  │
  ├── max_output_tokens recovery?
  │   ├── First time → Upgrade to 64k token limit, continue
  │   ├── Subsequent → Inject recovery message ("Continue, no apologies"), continue
  │   └── Over 3 times → yield error + return
  │
  ├── stop hooks execution
  │   ├── preventContinuation? → return
  │   └── blockingErrors? → Add errors to messages, continue
  │
  └── return { reason: 'completed' }  ★ Normal end
```

**Recovery message content (Line 1229)**:
```
"Output token limit hit. Resume directly — no apology, no recap of what
you were doing. Pick up mid-thought if that is where the cut happened.
Break remaining work into smaller pieces."
```

#### Step 6B: FollowUp Required — Tool Execution + Next Round (Lines 1363-1731)

When the model requests a tool call (`needsFollowUp === true`):

```
With followUp:
  ├── Tool execution (two modes)
  │   ├── streamingToolExecutor? → getRemainingResults() (streaming already started)
  │   └── No → runTools() (traditional sequential execution)
  │
  ├── for await (const update of toolUpdates):
  │   ├── yield update.message  ← Tool result message
  │   └── toolResults.push(...)  ← Collect tool results
  │
  ├── Interruption check (abortController.signal.aborted)
  │   └── return { reason: 'aborted_tools' }
  │
  ├── Attachment injection
  │   ├── Queued commands (messages submitted by other threads)
  │   ├── Memory prefetch (related memory files)
  │   └── Skill discovery prefetch
  │
  ├── maxTurns check
  │   └── Exceeded → yield max_turns_reached + return
  │
  └── state = { messages: [...old, ...assistant, ...toolResults], turnCount: +1 }
      → continue  ★ Back to top of loop, initiate next API call
```

### 1.6 Error Handling and Model Downgrade (Lines 897-956)

```
API call error:
  ├── FallbackTriggeredError (529 Overloaded)?
  │   ├── Switch to fallbackModel
  │   ├── Clear assistant/tool messages for this round
  │   ├── yield system message "Switched to X due to high demand for Y"
  │   └── continue (Retry entire request)
  │
  └── Other errors
      ├── ImageSizeError/ImageResizeError → yield friendly error + return
      ├── yieldMissingToolResultBlocks() — Complete unpaired tool_results
      └── yield API error message + return
```

### 1.7 Key Design Ideas

| Design | Description |
|------|------|
| **AsyncGenerator Pattern** | `query()` is an `async function*`, producing events one by one via `yield`, consumed by caller via `for await`. |
| **while(true) + state object** | A new State object is built upon each `continue` to avoid scattered state modifications. |
| **transition field** | Records why the loop continued (`next_turn`, `max_output_tokens_recovery`, `reactive_compact_retry`...), facilitating debugging. |
| **StreamingToolExecutor** | Executes tools in parallel as the API returns streaming data, without waiting for the stream to end. |
| **Withheld messages** | Withholds recoverable errors; swallows if recovery succeeds, yields only if it fails. |

---

## 2. QueryEngine.ts (line 1320) — High-level Orchestrator

**File Path**: `src/QueryEngine.ts`

### 2.1 Positioning

QueryEngine is a **high-level wrapper** for `query()`, primarily used for:
- **print mode** (`claude -p`): via `ask()` → `QueryEngine.submitMessage()`
- **SDK mode**: Called by external programs via SDK
- **Not used by REPL**: REPL calls `query()` directly

### 2.2 File Structure

```
QueryEngine.ts (1320 lines)
├── [0-130]      Import area + feature flag conditional modules
├── [131-174]    QueryEngineConfig type definition
├── [185-1202]   QueryEngine class
│   ├── [185-208]    Member variables + constructor
│   ├── [210-1181]   submitMessage() — Core method (~970 lines)
│   │   ├── [210-400]    Parameter parsing + processUserInputContext construction
│   │   ├── [400-465]    User input processing + session persistence
│   │   ├── [465-660]    Slash command processing + fast return without query
│   │   ├── [660-690]    File history snapshots
│   │   ├── [679-1074]   ★ for await (const message of query({...})) — Consuming query()
│   │   └── [1074-1181]  Result extraction + yield result
│   ├── [1183-1202]  interrupt() / getMessages() / setModel() helper methods
├── [1210-1320]  ask() — Convenience wrapper function
```

### 2.3 QueryEngineConfig

```ts
type QueryEngineConfig = {
  cwd: string                    // Working directory
  tools: Tools                   // Tool list
  commands: Command[]            // Slash commands
  mcpClients: MCPServerConnection[]  // MCP server connections
  agents: AgentDefinition[]      // Agent definitions
  canUseTool: CanUseToolFn       // Permission check
  getAppState / setAppState      // Global state accessors
  initialMessages?: Message[]    // Initial messages (resume conversation)
  readFileCache: FileStateCache  // File read cache
  customSystemPrompt?: string    // Custom system prompt
  thinkingConfig?: ThinkingConfig // Thinking mode configuration
  maxTurns?: number              // Maximum turns
  maxBudgetUsd?: number          // USD budget limit
  jsonSchema?: Record<...>       // Structured output schema
  // ... more configs
}
```

### 2.4 submitMessage() Core Flow

```
submitMessage(prompt)
  │
  ├── 1. Parameter Preparation
  │   ├── Destructure config to get tools, commands, model, ...
  │   ├── Build wrappedCanUseTool (wraps permission check, tracks denials)
  │   ├── fetchSystemPromptParts() — Get system prompt parts
  │   └── Build processUserInputContext
  │
  ├── 2. User Input Processing
  │   ├── processUserInput(prompt) — Parse slash commands / plain text
  │   ├── mutableMessages.push(...messagesFromUserInput)
  │   └── recordTranscript(messages) — Persist to JSONL
  │
  ├── 3. yield buildSystemInitMessage() — SDK initialization message
  │
  ├── 4. shouldQuery === false? (Local execution results of slash commands)
  │   ├── yield command output
  │   ├── yield { type: 'result', subtype: 'success' }
  │   └── return
  │
  ├── 5. ★ for await (const message of query({...}))
  │   │   Consume each message produced by query()
  │   │
  │   ├── message.type === 'assistant'
  │   │   ├── mutableMessages.push(msg)
  │   │   ├── recordTranscript()  ← fire-and-forget
  │   │   ├── yield* normalizeMessage(msg) — Convert to SDK format
  │   │   └── Capture stop_reason
  │   │
  │   ├── message.type === 'user' (Tool results)
  │   │   ├── mutableMessages.push(msg)
  │   │   ├── turnCount++
  │   │   └── yield* normalizeMessage(msg)
  │   │
  │   ├── message.type === 'stream_event'
  │   │   ├── Track usage (message_start/delta/stop)
  │   │   └── includePartialMessages? → yield stream event
  │   │
  │   ├── message.type === 'system'
  │   │   ├── compact_boundary → GC old messages + yield to SDK
  │   │   └── api_error → yield retry info
  │   │
  │   └── maxBudgetUsd check → yield error + return if over budget
  │
  └── 6. yield { type: 'result', subtype: 'success', result: textResult }
```

### 2.5 ask() Convenience Function (Line 1211)

```ts
export async function* ask({ prompt, tools, ... }) {
  const engine = new QueryEngine({ ... })
  try {
    yield* engine.submitMessage(prompt)
  } finally {
    setReadFileCache(engine.getReadFileState())
  }
}
```

`ask()` is a one-time wrapper for `QueryEngine`: creates engine → submits message → cleans up. Used for the `--print` mode in `print.ts`.

### 2.6 QueryEngine vs Direct REPL call to query()

| Feature | QueryEngine (SDK/print) | Direct REPL call to query() |
|------|------------------------|---------------------|
| Session Persistence | Automatic recordTranscript | Handled by useLogMessages |
| Usage Tracking | Internal totalUsage accumulation | Handled by outer cost-tracker |
| Permission Denial Tracking | Records permissionDenials[] | Direct UI interaction |
| Result Format | Yields SDKMessage format | Original Message format |
| Message GC | Releases old messages after compact_boundary | UI needs to keep full history |

---

## 3. claude.ts (line 3420) — API Client

**File Path**: `src/services/api/claude.ts`

### 3.1 File Structure

```
claude.ts (3420 lines)
├── [0-260]      Import area (Large number of SDK types, utility functions)
├── [272-331]    getExtraBodyParams() — Builds extra request body parameters
├── [333-502]    Caching related (getPromptCachingEnabled, getCacheControl, should1hCacheTTL, configureEffortParams, configureTaskBudgetParams)
├── [504-587]    verifyApiKey() — API key verification
├── [589-675]    Message conversion (userMessageToMessageParam, assistantMessageToMessageParam)
├── [677-708]    Options type definition
├── [710-781]    queryModelWithoutStreaming / queryModelWithStreaming — Two public entries
├── [783-813]    Helper functions (shouldDeferLspTool, getNonstreamingFallbackTimeoutMs)
├── [819-918]    executeNonStreamingRequest() — Non-streaming request helper
├── [920-999]    More helper functions (getPreviousRequestIdFromMessages, stripExcessMediaItems)
├── [1018-3420]  ★ queryModel() — Core private function (2400 lines)
│   ├── [1018-1370]   Pre-checks + tool schema construction + message normalization + system prompt assembly
│   ├── [1539-1730]   paramsFromContext() — Builds API request parameters
│   ├── [1777-2100]   withRetry + streaming API call (anthropic.beta.messages.create + stream)
│   ├── [1941-2300]   Streaming event processing (for await of stream)
│   └── [2300-3420]   Non-streaming fallback + logging, analytics, cleanup
```

### 3.2 Two Public Entries

```ts
// Entry 1: Streaming (Main path)
export async function* queryModelWithStreaming({
  messages, systemPrompt, thinkingConfig, tools, signal, options
}) {
  yield* withStreamingVCR(messages, async function* () {
    yield* queryModel(messages, systemPrompt, thinkingConfig, tools, signal, options)
  })
}

// Entry 2: Non-streaming (Internal use for compaction, etc.)
export async function queryModelWithoutStreaming({
  messages, systemPrompt, thinkingConfig, tools, signal, options
}) {
  let assistantMessage
  for await (const message of ...) {
    if (message.type === 'assistant') assistantMessage = message
  }
  return assistantMessage
}
```

Both delegate to the internal `queryModel()`. `withStreamingVCR` is a VCR (record/playback) wrapper for debugging.

### 3.3 Options Type (Line 677)

```ts
type Options = {
  getToolPermissionContext: () => Promise<ToolPermissionContext>
  model: string                      // Model name
  toolChoice?: BetaToolChoiceTool    // Force specific tool use
  isNonInteractiveSession: boolean   // Whether non-interactive mode
  fallbackModel?: string             // Fallback model
  querySource: QuerySource           // Query source
  agents: AgentDefinition[]          // Agent definitions
  enablePromptCaching?: boolean      // Enable prompt caching
  effortValue?: EffortValue          // Reasoning effort level
  mcpTools: Tools                    // MCP tools
  fastMode?: boolean                 // Fast mode
  taskBudget?: { total: number; remaining?: number }  // Token budget
}
```

### 3.4 queryModel() Core Flow (Line 1018)

The heart of the entire API call, 2400 lines. Key steps:

#### Phase 1: Preparation (Lines 1018-1400)

```
queryModel()
  ├── off-switch check (Global shutdown switch for Opus overload)
  ├── beta headers assembly (getMergedBetas)
  │   ├── Base betas
  │   ├── advisor beta (if enabled)
  │   ├── tool search beta (if enabled)
  │   ├── cache scope beta
  │   └── effort / task budget betas
  │
  ├── Tool filtering
  │   ├── tool search enabled → Include only discovered deferred tools
  │   └── tool search disabled → Filter out ToolSearchTool
  │
  ├── toolToAPISchema() — Convert each tool to API format
  │
  ├── normalizeMessagesForAPI() — Convert messages to API format
  │   ├── UserMessage → { role: 'user', content: ... }
  │   ├── AssistantMessage → { role: 'assistant', content: ... }
  │   └── Skip internal message types (system/attachment/progress, etc.)
  │
  └── Final system prompt assembly
      ├── getAttributionHeader(fingerprint)
      ├── getCLISyspromptPrefix()
      ├── ...systemPrompt
      └── advisor instructions (if enabled)
```

#### Phase 2: Build Request Parameters — paramsFromContext() (Lines 1539-1730)

```ts
const paramsFromContext = (retryContext: RetryContext) => {
  // ... dynamic beta headers, effort, task budget configs ...
  
  // Thinking mode config (adaptive or enabled + budget)
  let thinking = undefined
  if (hasThinking && modelSupportsThinking(options.model)) {
    if (modelSupportsAdaptiveThinking(options.model)) {
      thinking = { type: 'adaptive' }
    } else {
      thinking = { type: 'enabled', budget_tokens: thinkingBudget }
    }
  }

  return {
    model: normalizeModelStringForAPI(options.model),
    messages: addCacheBreakpoints(messagesForAPI, ...),  // Messages with cache breakpoints
    system,                           // Pre-built system prompt blocks
    tools: allTools,                  // Tool schemas
    tool_choice: options.toolChoice,
    max_tokens: maxOutputTokens,
    thinking,
    ...(temperature !== undefined && { temperature }),
    ...(useBetas && { betas: betasParams }),
    metadata: getAPIMetadata(),
    ...extraBodyParams,
    ...(speed !== undefined && { speed }),  // Fast mode
  }
}
```

#### Phase 3: Streaming API Call (Lines 1779-1858)

```ts
// Wrapped with withRetry for automatic retries
const generator = withRetry(
  () => getAnthropicClient({ maxRetries: 0, model, source: querySource }),
  async (anthropic, attempt, context) => {
    const params = paramsFromContext(context)

    // ★ Core API Call (Line 1823)
    // Uses .create() + stream: true (rather than .stream())
    // Avoids O(n²) partial JSON parsing overhead of BetaMessageStream
    const result = await anthropic.beta.messages
      .create(
        { ...params, stream: true },
        { signal, ...(clientRequestId && { headers: { ... } }) },
      )
      .withResponse()

    return result.data  // Stream<BetaRawMessageStreamEvent>
  },
  { model, fallbackModel, thinkingConfig, signal, querySource }
)

// Consume system error messages from withRetry (retry notifications, etc.)
let e
do {
  e = await generator.next()
  if (!('controller' in e.value)) yield e.value  // yield API error message
} while (!e.done)
stream = e.value  // Get final Stream object

// Handle streaming events (Line 1941)
for await (const part of stream) {
  switch (part.type) {
    case 'message_start':    // Record request_id, usage
    case 'content_block_start':  // New content block start (text/thinking/tool_use)
    case 'content_block_delta':  // Incremental content → yield stream_event to UI
    case 'content_block_stop':   // Content block complete → yield AssistantMessage
    case 'message_delta':    // stop_reason, usage updates
    case 'message_stop':     // Entire message complete
  }
}
```

#### Phase 4: withRetry Strategy

```
withRetry logic:
  ├── 429 (Rate Limit) → Wait for Retry-After then retry
  ├── 529 (Overloaded) → Switch to fallbackModel, throw FallbackTriggeredError
  ├── 500 (Server Error) → Exponential backoff retry
  ├── 408 (Timeout) → Retry
  ├── Other errors → Do not retry, throw directly
  └── Max retries: Dynamically calculated based on model and error type
```

#### Phase 5: Non-streaming Fallback

If a streaming request fails mid-way, it may fallback to a non-streaming request:

```
Streaming failure (partial response already received):
  ├── Received content → yield to upper layer
  ├── Remaining portion → Fallback to non-streaming request (anthropic.beta.messages.create)
  └── Non-streaming result → Convert format and yield
```

### 3.5 Message Conversion Functions

```ts
// UserMessage → API Format
userMessageToMessageParam(message, addCache, enablePromptCaching, querySource)
  → { role: 'user', content: [...] }
  // Adds cache_control to the last content block if addCache=true

// AssistantMessage → API Format
assistantMessageToMessageParam(message, addCache, enablePromptCaching, querySource)
  → { role: 'assistant', content: [...] }
  // No cache_control added to thinking/redacted_thinking blocks
```

### 3.6 Prompt Caching Strategy

```
Caching Strategy:
  ├── cache_control: { type: 'ephemeral' }  — Default, 5-minute TTL
  ├── cache_control: { type: 'ephemeral', ttl: '1h' }  — Subscribers/Ant, 1-hour
  ├── cache_control: { ..., scope: 'global' }  — Shared across sessions (when no MCP tools)
  └── Disabling conditions:
      ├── DISABLE_PROMPT_CACHING environment variable
      ├── DISABLE_PROMPT_CACHING_HAIKU (Haiku only)
      └── DISABLE_PROMPT_CACHING_SONNET (Sonnet only)
```

### 3.7 Multi-Provider Support

`getAnthropicClient()` returns different SDK clients based on configuration:

| Provider | Entry | Description |
|----------|------|------|
| Anthropic | Direct API | Default, `api.anthropic.com` |
| AWS Bedrock | Via Bedrock | Uses `@anthropic-ai/bedrock-sdk` |
| Google Vertex | Via Vertex | Uses `@anthropic-ai/vertex-sdk` |
| Azure | Via Azure | Wrapper similar to Bedrock |

Provider selection logic resides in `getAPIProvider()` in `src/utils/model/providers.ts`.

---

## Complete Data Flow: Lifecycle of a Tool Call

Example: User inputs "Read README.md"

```
1. REPL.tsx: User presses Enter
   onSubmit("Read README.md")
     └── handlePromptSubmit()
           └── onQuery([userMessage])

2. REPL.tsx: onQueryImpl()
   ├── getSystemPrompt() + getUserContext() + getSystemContext()
   └── for await (event of query({messages, systemPrompt, ...}))

3. query.ts: queryLoop() — 1st Iteration
   ├── messagesForQuery = [...messages]  // Contains user message
   ├── deps.callModel({...})
   │     └── claude.ts: queryModel()
   │           ├── Build API parameters
   │           └── anthropic.beta.messages.create({ ...params, stream: true })
   │
   ├── API Streaming return:
   │   content_block_start: { type: 'tool_use', name: 'Read', id: 'toolu_123' }
   │   content_block_delta: { input: '{"file_path": "/path/to/README.md"}' }
   │   content_block_stop
   │   message_delta: { stop_reason: 'tool_use' }
   │
   ├── Collection: toolUseBlocks = [{ name: 'Read', id: 'toolu_123', input: {...} }]
   ├── needsFollowUp = true
   │
   ├── Tool execution:
   │   streamingToolExecutor.getRemainingResults()
   │     └── Read tool executes → Returns file content
   │   yield toolResultMessage  ← Contains file content
   │
   └── state = { messages: [...old, assistantMsg, toolResultMsg], turnCount: 2 }
       → continue

4. query.ts: queryLoop() — 2nd Iteration
   ├── messagesForQuery now contains:
   │   [userMsg, assistantMsg(tool_use), userMsg(tool_result)]
   │
   ├── deps.callModel({...})  ← Call API again
   │
   ├── API returns:
   │   content_block_start: { type: 'text' }
   │   content_block_delta: { text: "The content of README.md is..." }
   │   content_block_stop
   │   message_delta: { stop_reason: 'end_turn' }
   │
   ├── toolUseBlocks = []  ← No tool call
   ├── needsFollowUp = false
   │
   └── return { reason: 'completed' }  ★ Loop ends

5. REPL.tsx: onQueryEvent(event)
   ├── Update streamingText (Typewriter effect)
   ├── Update messages array
   └── Re-render UI
```

---

## Summary of Key Design Patterns

| Pattern | Location | Description |
|------|------|------|
| AsyncGenerator chaining | query.ts → claude.ts | `yield*` passes low-level events to the upper layer, forming an event stream pipeline. |
| while(true) + State object | query.ts queryLoop | Transfers via immutable State between iterations; transition field records why. |
| StreamingToolExecutor | query.ts | Executes tools in parallel as the API stream returns, without waiting for the stream to end. |
| Withheld messages | query.ts | Recoverable errors are withheld; swallowed if recovery succeeds. |
| withRetry retries | claude.ts | Automatic retries for 429/500/529; 529 triggers model downgrade. |
| Prompt Caching | claude.ts | Caches system prompts and history to reduce API token consumption. |
| Non-streaming fallback | claude.ts | Falls back to non-streaming to complete the remainder if a streaming request fails mid-way. |
| QueryEngine wrapper | QueryEngine.ts | Provides session management, persistence, and usage tracking for SDK/print. |

## Code to Ignore

| Pattern | Description |
|------|------|
| `feature('REACTIVE_COMPACT')` / `feature('CONTEXT_COLLAPSE')` etc. | All code protected by feature flags — entirely dead code. |
| `feature('CACHED_MICROCOMPACT')` | Cached micro-compaction — dead code. |
| `feature('HISTORY_SNIP')` / `snipModule` | History truncation — dead code. |
| `feature('TOKEN_BUDGET')` / `budgetTracker` | Token budget — dead code. |
| `feature('BG_SESSIONS')` / `taskSummaryModule` | Background sessions — dead code. |
| `process.env.USER_TYPE === 'ant'` | Anthropic internal-only code. |
| VCR (withStreamingVCR/withVCR) | Debugging record/playback wrappers; does not affect normal flow. |