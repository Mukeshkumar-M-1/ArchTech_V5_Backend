# Claude Panel — Interactive UI Rendering Architecture (Select Lists, Radio Buttons, Choice Controls)

## Context

This plan documents how Claude API responses are rendered as interactive UI elements (select lists, radio buttons, checkboxes, dropdowns, option pickers) in the Claude Code panel (REPL). The Claude Code CLI is built with **Ink** (React-based terminal UI library), and Claude's API responses flow through a multi-stage pipeline that converts streaming LLM tokens into structured tool calls, then renders them as interactive React components in the terminal panel.

---

## 1. How It Works — End-to-End Flow

### Stage 1: API Response Streaming

**File:** `src/services/api/claude.ts`

The Anthropic API returns a `BetaRawMessageStreamEvent` stream. Each event maps to a content block type:

```
message_start
  ├── content_block_start (text, tool_use, thinking, server_tool_use, connector_text)
  │   ├── content_block_delta (text_delta, input_json_delta, thinking_delta)
  │   └── content_block_stop
  └── message_delta (stop_reason + usage)
message_stop
```

- **text blocks** → rendered as Markdown in `AssistantTextMessage.tsx`
- **tool_use blocks** → rendered as tool invocation UI in `AssistantToolUseMessage.tsx`
- **thinking blocks** → rendered in `AssistantThinkingMessage.tsx` or `AssistantRedactedThinkingMessage.tsx`

### Stage 2: Tool Use Block Processing

**File:** `src/components/messages/AssistantToolUseMessage.tsx`

When Claude emits a `tool_use` block, the REPL renders it through this flow:

1. `findToolByName()` resolves the tool definition from `Tool` interface
2. `tool.inputSchema.safeParse()` validates streaming input (partial JSON as it streams in)
3. `tool.renderToolUseMessage(input, options)` → **this is the JSX rendering entry point**
4. Status states: `queued` → `waiting for permission` → `executing` (with progress dots) → `completed`
5. Progress messages are streamed via `renderToolUseProgressMessage()`

### Stage 3: Tool Result Rendering

**File:** `src/components/messages/UserToolResultMessage/UserToolResultMessage.tsx`

When the tool completes, a `tool_result` block is returned:

1. `useGetToolFromMessages()` resolves the original `tool_use` by `tool_call_id`
2. Branches based on result type:
   - Cancelled → `UserToolCanceledMessage`
   - Rejected → `UserToolRejectMessage`
   - Error → `UserToolErrorMessage`
   - Success → `UserToolSuccessMessage`

3. In `UserToolSuccessMessage.tsx`:
   - `tool.renderToolResultMessage(content, progressMessages, options)` → **this renders the final output**
   - `tool.outputSchema.safeParse()` validates the output before rendering

### Stage 4: The Tool Interface — The Rendering Contract

**File:** `src/Tool.ts` (lines 383-716)

Every tool implements this **Tool** interface with these key rendering methods:

```typescript
type Tool = {
  // Called during streaming to show what the tool is doing
  renderToolUseMessage(input, { theme, verbose, commands }): React.ReactNode

  // Called after completion to show the result
  renderToolResultMessage(content, progressMessages, { style, theme, tools, verbose, isTranscriptMode, input }): React.ReactNode

  // Called while executing to show progress
  renderToolUseProgressMessage(progressMessages, { tools, verbose, terminalSize, inProgressToolCallCount }): React.ReactNode

  // Called when tool is queued (waiting to execute)
  renderToolUseQueuedMessage(): React.ReactNode

  // Called when tool is rejected
  renderToolUseRejectedMessage(input, options): React.ReactNode

  // Called when tool errors
  renderToolUseErrorMessage(result, options): React.ReactNode

  // Render multiple parallel tool calls as a group
  renderGroupedToolUse(toolUses, options): React.ReactNode | null

  // For tools that delegate rendering to inner tools (e.g., REPL wrapper)
  isTransparentWrapper(): boolean

  // Human-readable name displayed in the panel
  userFacingName(input): string
}
```

### Stage 5: JSX Injection via setToolJSX

**File:** `src/Tool.ts` (line 105-116)

```typescript
type SetToolJSXFn = (args: {
  jsx: React.ReactNode | null
  shouldHidePromptInput: boolean
  shouldContinueAnimation?: true
  showSpinner?: boolean
  isLocalJSXCommand?: boolean
  isImmediate?: boolean
  clearLocalJSX?: boolean
}) => void
```

This is a callback on `ToolUseContext` that allows tools to inject arbitrary JSX directly into the panel. This is the **primary mechanism for interactive select lists and radio buttons** — tools can call `context.setToolJSX()` to render interactive React components inline in the panel.

---

## 2. How It Adapts Based on Conversation — Responsive UI for Select/Radio/Checkboxes

### Dynamic Tool Discovery → Dynamic UI

The Claude panel is **not** a static UI. The UI adapts based on Claude's tool_use choices in each conversation turn:

**Step 1: Claude decides which tool to call**
- The API returns tool_use blocks with `name`, `id`, and `input` (partial JSON while streaming)
- Each tool's `renderToolUseMessage()` determines what to display

**Step 2: The Tool's `renderToolUseMessage()` returns React.ReactNode**
- Each tool defines its own rendering logic
- For example, `BashTool` shows the command being run
- `FileReadTool` shows the file path
- A custom tool can return a **select list**, **radio buttons**, **checkboxes** by implementing `renderToolUseMessage()` to return Ink/React components

**Step 3: Tool results also render dynamically**
- `renderToolResultMessage()` renders the output of tool execution
- Can show tables, formatted diffs, status indicators, or interactive elements

### How a Select List / Radio Button Gets Rendered

The mechanism is:

1. **Tool calls Claude's API** → Claude responds with `tool_use` block
2. **StreamingToolExecutor** starts executing the tool (src/services/tools/StreamingToolExecutor.ts)
3. **During streaming**, `renderToolUseMessage()` is called with partial input → shows "Running Bash (cat file.ts)..."
4. **Tool execution produces output** → tool calls `setToolJSX` if it wants to inject custom UI
5. **After completion**, `renderToolResultMessage()` renders the result

For a select list specifically, a tool could:

1. In `renderToolUseMessage()`: Return an Ink `<Box>` with `<Select>` and `<Option>` components
2. In `renderToolResultMessage()`: Return what was selected
3. The tool can use `context.setToolJSX()` to show/hide the prompt input while the user interacts with the select UI
4. Tool permissions (`checkPermissions`) can be bypassed for tools that use this pattern

### Conversation-Responsive Behavior

The UI adapts based on:

| Conversation State | UI Behavior |
|---|---|
| `needsFollowUp = false` (Claude done) | Shows final text response, prompt input enabled |
| `needsFollowUp = true` (Claude called tools) | Shows tool blocks with spinner animation, prompt input hidden |
| Permission mode = `auto` | No permission prompts, tool runs immediately |
| Permission mode = `default` | Shows permission dialog before tool runs |
| Permission mode = `bypass` | All tools auto-allowed |
| Streaming fallback occurs | Tool results get synthetic error, re-attempts with non-streaming |
| Model switches mid-session | System prompt rebuilt, new tool schemas sent to API |
| Context window near limit | Auto-compact triggers, conversation summarized |
| Background agents active | Shows BackgroundAgentSelector below prompt input |
| LAN Pipes active | Shows pipe selection bar with routing mode |

### Key Responsive Components

| Component | What It Responds To |
|---|---|
| `AssistantToolUseMessage.tsx` | Tool type, streaming state, permission state, completion state |
| `UserToolResultMessage.tsx` | Success/error/reject/cancel state |
| `BackgroundAgentSelector.tsx` | Active background agents, cursor focus state |
| `MessageResponse.tsx` | Wraps each tool/result response for consistent spacing |
| `Markdown.tsx` | Renders assistant text responses |
| `ToolUseLoader.tsx` | Animated spinner for in-progress tools |
| `HookProgressMessage.tsx` | PreToolUse and PostToolUse hook progress |

---

## 3. Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLAUDE CODE PANEL ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │   Anthropic API  │    │   Claude Code    │    │   Panel (REPL)   │   │
│  │                  │    │   Core (Node.js) │    │   (Ink/React)    │   │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘   │
│           │                       │                       │             │
│           │  streaming SSE        │                       │             │
│           │──────────────────────▶│                       │             │
│           │  BetaRawMessageEvent  │                       │             │
│           │                       │                       │             │
│  ┌────────▼───────────────────────▼───────────────────────▼──────────┐   │
│  │                   STREAMING API LAYER                              │   │
│  │                                                                    │   │
│  │  src/services/api/claude.ts                                       │   │
│  │  ├── queryModelWithStreaming()                                     │   │
│  │  │   ├── message_start  → partialMessage, usage init              │   │
│  │  │   ├── content_block_start → contentBlocks[index] init          │   │
│  │  │   ├── content_block_delta → streamingDeltas.append()           │   │
│  │  │   ├── content_block_stop → yield AssistantMessage             │   │
│  │  │   ├── message_delta → stop_reason, final usage                 │   │
│  │  │   └── message_stop → stream end                                │   │
│  │  └── yield* AsyncGenerator<StreamEvent | AssistantMessage>        │   │
│  └────────────────────────────────┬─────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                   AGENTIC LOOP LAYER                               │   │
│  │                                                                    │   │
│  │  src/query.ts                                                     │   │
│  │  ├── queryLoop() while(true)                                      │   │
│  │  │   ├── Phase 1: Context Pre-Processing                           │   │
│  │  │   │   ├── applyToolResultBudget()                               │   │
│  │  │   │   ├── snipCompactIfNeeded()                                 │   │
│  │  │   │   ├── microcompact()                                        │   │
│  │  │   │   ├── applyCollapsesIfNeeded()                              │   │
│  │  │   │   └── autocompact()                                         │   │
│  │  │   ├── Phase 2: Streaming API call                               │   │
│  │  │   │   ├── deps.callModel() → AsyncGenerator                    │   │
│  │  │   │   ├── Collect AssistantMessage[]                            │   │
│  │  │   │   ├── Extract toolUseBlocks[] → StreamingToolExecutor      │   │
│  │  │   │   └── StreamingToolExecutor.addTool() starts in parallel   │   │
│  │  │   ├── Phase 3: Tool Execution                                   │   │
│  │  │   │   ├── StreamingToolExecutor.getRemainingResults()           │   │
│  │  │   │   └── Normalize → merge into messagesForQuery              │   │
│  │  │   └── Phase 4: Terminate or Continue                            │   │
│  │  └── queryModelWithoutStreaming() fallback                         │   │
│  └────────────────────────────────┬─────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                   TOOL EXECUTION LAYER                             │   │
│  │                                                                    │   │
│  │  src/services/tools/StreamingToolExecutor.ts                       │   │
│  │  ├── TrackedTool = { id, block, status, results }                  │   │
│  │  ├── addTool(block, assistantMessage)                              │   │
│  │  ├── executeTool(tool) → runToolUse()                              │   │
│  │  ├── Concurrent-safe tools run in parallel                         │   │
│  │  ├── Non-concurrent tools run sequentially                          │   │
│  │  └── getCompletedResults() → yield in order                        │   │
│  │                                                                    │   │
│  │  src/services/tools/toolExecution.ts                               │   │
│  │  ├── runToolUse(toolBlock, context, canUseTool)                    │   │
│  │  │   ├── tool.call(args, context, canUseTool, ...)                 │   │
│  │  │   ├── Returns ToolResult = { data, newMessages }                │   │
│  │  │   └── mapToolResultToToolResultBlockParam() → API format        │   │
│  │  └── Permissions: checkPermissions → canUseTool → execute          │   │
│  │                                                                    │   │
│  │  src/Tool.ts (Tool interface)                                      │   │
│  │  ├── Tool definition with rendering methods                        │   │
│  │  ├── buildTool(def) → merges with defaults                         │   │
│  │  ├── renderToolUseMessage() → JSX while streaming                   │   │
│  │  ├── renderToolResultMessage() → JSX after completion               │   │
│  │  ├── renderToolUseProgressMessage() → JSX during execution          │   │
│  │  ├── renderToolUseQueuedMessage() → JSX when waiting                │   │
│  │  ├── setToolJSX() → inject custom JSX into panel                    │   │
│  │  └── userFacingName() → display name in panel                       │   │
│  └────────────────────────────────┬─────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                   MESSAGE RENDERING LAYER (Ink/React)              │   │
│  │                                                                    │   │
│  │  src/components/messages/AssistantToolUseMessage.tsx               │   │
│  │  ├── renderToolUseMessage(tool, input) → React.ReactNode           │   │
│  │  ├── renderToolUseProgressMessage() → progress indicator           │   │
│  │  ├── States: queued → waiting → executing → completed              │   │
│  │  ├── ToolUseLoader (spinner animation)                             │   │
│  │  └── Classifier checking (auto mode)                               │   │
│  │                                                                    │   │
│  │  src/components/messages/AssistantTextMessage.tsx                  │   │
│  │  ├── Renders assistant text as <Markdown> component                │   │
│  │  ├── Special case handling (rate limit, API errors, abort)         │   │
│  │  └── EMPTY_TEXT handling                                           │   │
│  │                                                                    │   │
│  │  src/components/messages/UserToolResultMessage/                    │   │
│  │  ├── UserToolResultMessage.tsx → routes to specific types          │   │
│  │  ├── UserToolSuccessMessage.tsx → calls tool.renderToolResultMessage() │
│  │  ├── UserToolErrorMessage.tsx → error display                      │   │
│  │  ├── UserToolRejectMessage.tsx → rejection display                 │   │
│  │  └── UserToolCanceledMessage.tsx → cancellation display            │   │
│  │                                                                    │   │
│  │  src/components/messages/AssistantThinkingMessage.tsx              │   │
│  │  src/components/messages/AssistantRedactedThinkingMessage.tsx      │   │
│  │  └── Renders Claude's chain-of-thought                           │   │
│  │                                                                    │   │
│  │  src/components/MessageResponse.tsx                                │   │
│  │  └── Wraps each response block for consistent spacing              │   │
│  │                                                                    │   │
│  │  src/components/Markdown.tsx                                       │   │
│  │  └── Renders text content as Markdown with Ink components          │   │
│  │                                                                    │   │
│  │  src/components/ToolUseLoader.tsx                                  │   │
│  │  └── Animated spinner for in-progress tool calls                   │   │
│  └────────────────────────────────┬─────────────────────────────────┘   │
│                                    │                                     │
│  ┌────────────────────────────────▼─────────────────────────────────┐   │
│  │                   PANEL LAYER (Ink/React UI)                       │   │
│  │                                                                    │   │
│  │  src/screens/REPL.tsx                                              │   │
│  │  ├── Main screen with message list, tool calls, progress           │   │
│  │  ├── BackgroundAgentSelector.tsx (bottom selector)                 │   │
│  │  ├── PromptInput.tsx (user input)                                  │   │
│  │  └── View switching between main/conversation & agent transcripts  │   │
│  │                                                                    │   │
│  │  src/components/PromptInput/PromptInput.tsx                        │   │
│  │  ├── Header bar (model, context usage, permissions)                │   │
│  │  ├── Input area with history navigation                            │   │
│  │  ├── Footer pills (tasks, bg agents, pipes, etc.)                  │   │
│  │  └── Keyboard routing (↑/↓/Enter/Esc)                              │   │
│  │                                                                    │   │
│  │  src/state/AppState.ts                                             │   │
│  │  ├── Global state: tasks, messages, toolPermissionContext          │   │
│  │  ├── Footer selection state (bg_agent, tasks, pipes)               │   │
│  │  ├── Viewing agent state (viewingAgentTaskId)                      │   │
│  │  └── isBriefOnly state (Kairos brief mode)                         │   │
│  │                                                                    │   │
│  │  src/hooks/useBackgroundAgentTasks.ts                              │   │
│  │  └── Filters & sorts background agents for selector                │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    INTERACTIVE UI MECHANISMS                         │ │
│  │                                                                      │ │
│  │  Mechanism 1: Tool Rendering Methods                                │ │
│  │  ─────────────────────────────                                      │ │
│  │  Each tool implements renderToolUseMessage() and                     │ │
│  │  renderToolResultMessage() which return Ink/React components.       │ │
│  │  A tool can return <Select><Option> or <RadioGroup><RadioOption>    │ │
│  │  directly from these methods. The Ink library renders these as      │ │
│  │  interactive terminal components.                                     │ │
│  │                                                                      │ │
│  │  Mechanism 2: setToolJSX Injection                                  │ │
│  │  ─────────────────────────────                                      │ │
│  │  Tools receive context.setToolJSX() callback. They can call this    │ │
│  │  with arbitrary React nodes to inject interactive UI directly into  │ │
│  │  the panel. This is used for things like:                            │ │
│  │  - Custom permission confirmation dialogs                            │ │
│  │  - Interactive file path pickers                                     │ │
│  │  - Select lists for user choices                                     │ │
│  │  - Radio button groups for configuration                             │ │
│  │                                                                      │ │
│  │  Mechanism 3: Permission System                                     │ │
│  │  ─────────────────────────────                                      │ │
│  │  Permission modes (default/auto/bypass) control what UI shows:      │ │
│  │  - default: Shows permission prompt dialog                           │ │
│  │  - auto: Tools run without prompts (classifier checks)               │ │
│  │  - bypass: All tools auto-allowed                                    │ │
│  │                                                                      │ │
│  │  Mechanism 4: Streaming State                                       │ │
│  │  ─────────────────────────────                                      │ │
│  │  As tool_use blocks stream in from the API, the UI shows partial    │ │
│  │  input with spinner animation. Once complete, it transitions to     │ │
│  │  executing → completed, updating the visual state.                  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Files Reference

| File | Purpose |
|---|---|
| `src/services/api/claude.ts` | API streaming, event processing, content block assembly |
| `src/query.ts` | Agentic loop, context management, tool orchestration |
| `src/Tool.ts` | Tool interface definition with all rendering methods |
| `src/services/tools/StreamingToolExecutor.ts` | Concurrent tool execution with streaming results |
| `src/services/tools/toolExecution.ts` | Individual tool execution, result generation |
| `src/components/messages/AssistantToolUseMessage.tsx` | Renders tool_use blocks in panel |
| `src/components/messages/UserToolResultMessage/UserToolResultMessage.tsx` | Routes tool results to specific renderers |
| `src/components/messages/UserToolResultMessage/UserToolSuccessMessage.tsx` | Calls tool.renderToolResultMessage() |
| `src/components/messages/AssistantTextMessage.tsx` | Renders assistant text as Markdown |
| `src/components/MessageResponse.tsx` | Wraps response blocks |
| `src/components/Markdown.tsx` | Markdown rendering with Ink |
| `src/components/ToolUseLoader.tsx` | Tool execution spinner |
| `src/components/PromptInput/PromptInput.tsx` | User input with footer pills |
| `src/screens/REPL.tsx` | Main panel screen |
| `src/state/AppState.ts` | Global application state |
| `src/hooks/useBackgroundAgentTasks.ts` | Background agent filtering |
| `src/components/messages/GroupedToolUseContent.tsx` | Groups parallel tool uses |
| `src/components/BackgroundAgentSelector.tsx` | Bottom agent selector |
| `src/QueryEngine.ts` | Session management, submitMessage() |

---

## 5. How to Add New Interactive UI Elements

To add a select list, radio buttons, or other interactive elements to the Claude panel:

1. **Define a tool** (or extend an existing one) that implements `renderToolUseMessage()` returning Ink components like `<Select>`, `<RadioGroup>`, `<CheckboxGroup>`
2. **Use `setToolJSX()` callback** to inject custom interactive UI directly into the panel
3. **Handle user input** through the tool's `checkPermissions()` or a dedicated input handler
4. **Return results** via `ToolResult` with `newMessages` for the next API turn

The key insight: **every tool has full control over its rendering**. There's no separate "select list" or "radio button" concept — the UI is built entirely through React/Ink components returned by the tool's rendering methods.

---

## 6. Verification

To verify this architecture understanding:

1. Read `src/Tool.ts` — the Tool interface is the contract for all rendering
2. Check `src/services/api/claude.ts` — how streaming events become content blocks
3. Read `src/query.ts` — the agentic loop that orchestrates the conversation
4. Run `CLAUDE_CODE_DEBUG_LOGGING=1 npx ccb` to observe the message flow in real-time
5. Create a custom tool and implement `renderToolUseMessage()` to return `<Select>` components
6. Test with different permission modes to see UI differences
