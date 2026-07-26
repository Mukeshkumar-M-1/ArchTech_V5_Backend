---
title: "Architecture Panorama - Detailed Explanation of Claude Code's Five-Layer Architecture"
description: "Detailed explanation of Claude Code's five-layer architecture design, from the interaction layer to the infrastructure layer. Source-code level data flow analysis based on src/main.tsx, src/QueryEngine.ts, src/query.ts, src/tools.ts, and src/services/api/claude.ts."
keywords:
  ["Claude Code Architecture", "Five-Layer Architecture", "QueryEngine", "Agentic Loop", "Data Flow"]
---

{/* Chapter Goal: Explain the overall architecture with one diagram, setting the coordinate system for subsequent chapters */}

## Five-Layer Architecture

Claude Code is divided into five layers from top to bottom, each with clear responsibilities and distinct boundaries:

<Frame caption="Claude Code Five-Layer Architecture">
  <img
    src="/docs/images/architecture-layers.png"
    alt="Claude Code Five-Layer Architecture Diagram"
  />
</Frame>

| Layer | Responsibility | Entry Source Code | Keywords |
| -------------- | --------------------------------------- | ------------------------------ | ----------------------- |
| **Interaction Layer** | Terminal UI, user input, message display | `src/screens/REPL.tsx` | React/Ink, PromptInput |
| **Orchestration Layer** | Multi-turn dialogue, session persistence, cost tracking | `src/QueryEngine.ts` | QueryEngine, transcript |
| **Core Loop Layer** | Single turn: Send request → Get response → Execute tool → Loop | `src/query.ts` | Agentic Loop, State |
| **Tool Layer** | AI's "hands"—reading/writing files, executing commands | `src/tools.ts` → `src/Tool.ts` | Tool interface, MCP |
| **Communication Layer** | Streaming communication with Claude API | `src/services/api/claude.ts` | Streaming, Provider |

## Source Code Tracing of a Main Data Flow

<Frame caption="Core Data Flow">
  <img src="/docs/images/data-flow.png" alt="Claude Code Core Data Flow" />
</Frame>

The operation of the entire system can be condensed into a core data flow. Below are the source code paths corresponding to each step:

### 1. User Input → REPL

`src/screens/REPL.tsx` is a terminal UI component based on React/Ink. User input is processed by `processUserInput()` (`src/utils/processUserInput/processUserInput.ts`), supporting slash commands, file attachments, images, etc.

### 2. QueryEngine Orchestration

`src/QueryEngine.ts` is the intermediate layer between the REPL and `query()`, managing:

- **Session State**: Message arrays, tool permission context (`ToolPermissionContext`), file history snapshots.
- **Cost Tracking**: `accumulateUsage()` / `getTotalCost()` to accumulate token usage.
- **Transcript Persistence**: `recordTranscript()` serializes conversations to disk, supporting `--resume`.
- **File History**: `fileHistoryMakeSnapshot()` creates a snapshot before modification, supporting undo.

Key method: `queryEngine.query()` constructs `QueryParams` and calls the `query()` async generator.

### 3. Agentic Loop (`src/query.ts`)

`query()` is an `AsyncGenerator`. Each iteration of the `while(true)` loop includes:

```
① Context Pre-processing Pipeline:
   applyToolResultBudget → snipCompact → microcompact → contextCollapse → autocompact

② Streaming API Call:
   deps.callModel() → AsyncGenerator<StreamEvent | Message>
   Collecting assistantMessages[], toolUseBlocks[]

③ Tool Execution:
   StreamingToolExecutor (Parallel) or runTools (Serial)
   → toolResults[]

④ Termination/Continuation Determination:
   needsFollowUp ? continue : return { reason }
```

The complete state machine is passed between iterations via the `State` type (`src/query.ts:207`), which contains 10 fields (messages, autoCompactTracking, maxOutputTokensRecoveryCount, etc.).

### 4. Tool Layer (`src/tools.ts` → `src/Tool.ts`)

`getAllBaseTools()` (`src/tools.ts:195`) assembles a list of 50+ tools, which is passed to the API after being filtered by `filterToolsByDenyRules()`.

Each tool implements the `Tool<Input, Output, Progress>` interface (`src/Tool.ts:368`). Core method chain:

```
validateInput() → canUseTool() (UI layer) → checkPermissions() → call() → ToolResult
```

### 5. Communication Layer (`src/services/api/claude.ts`)

The API client supports 7 types of Providers:

- **Anthropic Direct (firstParty)**: Default
- **AWS Bedrock**: `ANTHROPIC_BEDROCK_BASE_URL`
- **Google Vertex**: `ANTHROPIC_VERTEX_PROJECT_ID`
- **Foundry**: `ANTHROPIC_CODE_USE_FOUNDRY`
- **OpenAI**: Compatibility layer
- **Gemini**: Compatibility layer
- **Grok (xAI)**: Compatibility layer

`deps.callModel()` initiates a streaming request and returns a `BetaRawMessageStreamEvent` event stream. Supports Prompt Cache (`cache_control`), thinking blocks, and multi-turn tool use.

## Four Core Design Principles

<AccordionGroup>
  <Accordion title="Streaming-first">
    All API communication is streaming—`deps.callModel()` returns an AsyncGenerator, and the user sees the AI "type out" the answer character by character. StreamingToolExecutor starts executing tools in parallel during the streaming process without waiting for the stream to end. Upon model fallback, collected assistantMessages are marked as tombstones and cleared, and the entire streaming request is retried.
  </Accordion>
  <Accordion title="Tool as Capability">
    Each tool is a `Tool<Input, Output, Progress>` structured type created via a `buildTool()` factory. `getTools()` assembles them during each API call (not globally cached) because `isEnabled()` may change with runtime state. MCP tools are marked by the `mcpInfo` field to identify their source, supporting server-level blanket deny.
  </Accordion>
  <Accordion title="Permission as Boundary">
    Every tool call passes through a double check: `validateInput() → checkPermissions()`. Permission rules aggregate from 5 sources (session → project → user → managed → default), supporting matching by tool name, command patterns, path prefixes, etc. Plan Mode switches to read-only mode via `prepareContextForPlanMode()` and automatically restores upon exit.
  </Accordion>
  <Accordion title="Context as Memory">
    The System Prompt is dynamically assembled by `fetchSystemPromptParts()`, including CLAUDE.md, git status, date, and MCP server list. Auto-compact evaluates the token threshold before each iteration and triggers compression when exceeded. Compressed summaries replace original messages via `buildPostCompactMessages()`, with `taskBudgetRemaining` accumulating across compression boundaries.
  </Accordion>
</AccordionGroup>

## Entry and Bootstrap

| Entry | File | Description |
| ------------ | ------------------------- | ----------------------------------------------------------- |
| CLI Startup | `src/entrypoints/cli.tsx` | Inject `feature()` polyfill (always returns false), MACRO global variables |
| Command Definition | `src/main.tsx` | Commander.js parses arguments, initializes auth/analytics/policy |
| One-time Initialization | `src/entrypoints/init.ts` | Telemetry configuration, trust dialog |
| Pipe Mode | `src/main.tsx` `-p` flag | `echo "say hello" \| bun run dev -p` |
