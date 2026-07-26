# Claude Code Source Code Learning Route

> Source code learning tracking based on the decompiled version of Claude Code CLI (v2.1.888)
>
> For detailed notes on each stage, see the `phase-*.md` files in the same directory.

## The First Stage: Startup Process (Entry Link) ✅

Detailed notes: [phase-1-startup-flow.md](phase-1-startup-flow.md)

Understand the complete path from command line startup to the user seeing the interactive interface.

- [x] `src/entrypoints/cli.tsx` — real entry, polyfill injection + fast path distribution
  - [x] Global polyfill: `feature()` always returns false, `MACRO` global objects, `BUILD_*` constants
  - [x] Fast path design: check from low to high cost, return as early as possible
  - [x] Dynamic import mode: `await import()` delays loading and reduces startup time
  - [x] Final exit: `import("../main.jsx")` → `cliMain()`
- [x] `src/main.tsx` — Commander.js CLI definition, heavy initialization (line 4683)
  - [x] Three-stage structure: auxiliary functions (1-584) → main() (585-856) → run() (884-4683)
  - [x] Side-effect imports: profileCheckpoint, startMdmRawRead, startKeychainPrefetch parallel preloading
  - [x] preAction hook: MDM wait, init(), migration, remote setup
  - [x] Commander parameter definitions: 40+ CLI options
  - [x] action handler (line 2800): parameter parsing → service initialization → showSetupScreens → launchRepl()
  - [x] --print branch goes to print.ts; interactive branch goes to launchRepl() (7 scene branches)
  - [x] Subcommand registration: mcp/auth/plugin/doctor/update/install, etc.
- [x] `src/replLauncher.tsx` — bridge (line 22), combines `<App>` + `<REPL>` to render to the terminal
- [x] `src/screens/REPL.tsx` — interactive REPL interface (line 5009)
  - [x] Props: commands, tools, messages, systemPrompt, thinkingConfig, etc.
  - [x] 50+ states: messages, inputValue, screen, streamingText, queryGuard, etc.
  - [x] Core data flow: onSubmit → handlePromptSubmit → onQuery → onQueryImpl → query() → onQueryEvent
  - [x] QueryGuard concurrency control: idle → running → idle, to prevent repeated queries
  - [x] Rendering: Transcript mode (read-only history) / Prompt mode (Messages + PermissionRequest + PromptInput)

**Data flow**: `bun run dev` → `package.json scripts.dev` → `bun run src/entrypoints/cli.tsx` → Fast path check → `main.tsx:main()` → `launchRepl()` → `<App><REPL /></App>`

---

## Phase 2: Core Conversation Loop ✅

Detailed notes: [phase-2-conversation-loop.md](phase-2-conversation-loop.md)

Understand how a user's sentence turns into an API request, how to handle streaming responses, and how tool calls are managed.

- [x] `src/query.ts` — core query loop (line 1732)
  - [x] `query()` AsyncGenerator entry, delegated to `queryLoop()`
  - [x] `queryLoop()` — while(true) main loop, State object manages iteration state
  - [x] Message preprocessing (autocompact, compact boundary)
  - [x] `deps.callModel()` → streaming API call
  - [x] StreamingToolExecutor — Parallel tool execution as API streaming returns
  - [x] Tool call loop (tool use → execute → result → continue)
  - [x] Error recovery (prompt-too-long, max_output_tokens upgrade + multiple rounds of recovery)
  - [x] Model downgrade (FallbackTriggeredError → switch fallbackModel)
  - [x] Withheld message mode (withholding recoverable errors)
- [x] `src/QueryEngine.ts` — high-level orchestrator (line 1320)
  - [x] QueryEngine class — one instance per conversation
  - [x] `submitMessage()` — handle user input → call `query()` → consume event stream
  - [x] SDK/print mode only (REPL calls query() directly)
  - [x] Session persistence (recordTranscript)
  - [x] Usage tracking, permission denial logging
  - [x] `ask()` convenience wrapper function
- [x] `src/services/api/claude.ts` — API client (line 3420)
  - [x] `queryModelWithStreaming` / `queryModelWithoutStreaming` — two public entries
  - [x] `queryModel()` — core private function (line 2400)
  - [x] Request parameter assembly (system prompt, betas, tools, cache control)
  - [x] Anthropic SDK streaming call (`anthropic.beta.messages.stream()`)
  - [x] `BetaRawMessageStreamEvent` event handling (message_start/content_block_*/message_delta/stop)
  - [x] withRetry retry strategy (429/500/529 + model downgrade)
  - [x] Prompt Caching strategy (ephemeral/1h TTL/global scope)
  - [x] Multi-provider support (Anthropic/Bedrock/Vertex/Azure)

**Data flow**: REPL.onSubmit → handlePromptSubmit → onQuery → onQueryImpl → `query()` AsyncGenerator → `queryLoop()` while(true) → `deps.callModel()` → `claude.ts queryModel()` → `anthropic.beta.messages.stream()` → Streaming events → tool_use collection → Tool execution → append results to messages → continue → return when no tool is called

---

## The Third Stage: Tool System

Understand how Claude defines, registers, and calls tools. Read the framework first, then specific tool implementations.

- [ ] `src/Tool.ts` — Tool interface definition
  - [ ] `Tool` type structure (name, description, inputSchema, call)
  - [ ] `findToolByName`, `toolMatchesName` utility functions
- [ ] `src/tools.ts` — Tool registry
  - [ ] Tool list assembly logic
  - [ ] Conditional loading (feature flags, USER_TYPE)
- [ ] Specific tool implementations (pick 2-3 for in-depth reading):
  - [ ] `src/tools/BashTool/` — Executes shell commands, the most commonly used tool
  - [ ] `src/tools/FileReadTool/` — Reads files, simple and intuitive, good for understanding the tool pattern
  - [ ] `src/tools/FileEditTool/` — Edits files; understand the diff/patch mechanism
  - [ ] `src/tools/AgentTool/` — Sub-Agent mechanism, complex but core

---

## Stage 4: Context and System Prompts

Understand how Claude "knows" project context, user preferences, and more.

- [ ] `src/context.ts` — System/user context construction
  - [ ] git status injection
  - [ ] CLAUDE.md content loading
  - [ ] Memory file injection
  - [ ] Date, platform, and other environment information
- [ ] `src/utils/claudemd.ts` — CLAUDE.md discovery and loading
  - [ ] Project-level search logic
  - [ ] Multi-level CLAUDE.md merging

---

## The Fifth Stage: UI Layer (Optional Reading)

Understand the rendering mechanism of the terminal UI (React/Ink).

- [ ] `src/components/App.tsx` — root component, Provider injection
- [ ] `src/state/AppState.tsx` — Global state type and Context
- [ ] `src/components/permissions/` — Tool permission approval UI
- [ ] `src/components/messages/` — Message rendering components

---

## Stage 6: Peripheral Systems (Explore as Needed)

- [ ] `src/services/mcp/` — MCP Protocol (Model Context Protocol)
- [ ] `src/skills/` — Skills system (/commit and other slash commands)
- [ ] `src/commands/` — CLI subcommands
- [ ] `src/tasks/` — Background task system
- [ ] `src/utils/model/providers.ts` — Multi-provider selection logic

---

## Study Notes

### Key Design Patterns

| Pattern | Location | Description |
|------|------|------|
| Fast path | cli.tsx | Sequential checks from low to high cost to reduce unnecessary module loading |
| Dynamic import | cli.tsx / main.tsx | `await import()` lazy loading to optimize startup time |
| Feature flag | global | `feature()` always returns false; all internal features are disabled |
| React/Ink | UI layer | Rendering terminal UI using the React component model |
| Tool loop | query.ts | AI returns tool call → Execute → Return result → Continue until no tool is called |
| AsyncGenerator chain | query.ts → claude.ts | `yield*` transparently passes the event stream to form a pipeline |
| State object | query.ts queryLoop | State transfer between loops via immutable State + transition fields |
| StreamingToolExecutor | query.ts | Parallel tool execution while API streaming returns |
| Withheld message | query.ts | Withhold errors for recovery; swallow if successful |
| withRetry | claude.ts | 429/500/529 automatic retry + model downgrade |
| Prompt Caching | claude.ts | Caching system prompts and historical messages to reduce token consumption |

### Content to Ignore

- `_c()` calls — React Compiler decompilation artifacts
- Code blocks following `feature('...')` — all dead code
- tsc type errors — caused by decompilation; does not affect Bun execution
- `packages/@ant/` — stub packages with no actual implementation