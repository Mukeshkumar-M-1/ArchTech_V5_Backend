# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and other AI coding agents when working with code in this repository.

## Project Overview

This is a **reverse-engineered / decompiled** version of Anthropic's official Claude Code CLI tool. The goal is to restore core functionality while trimming secondary capabilities. Many modules are stubbed or feature-flagged off. TypeScript strict mode is enforced — **`bunx tsc --noEmit` must pass with zero errors**.

## Git Commit Message Convention

use **Conventional Commits** specification:

```
<type>: <describe>
```

Common types: `feat`, `fix`, `docs`, `chore`, `refactor`

Example:
- `feat: add model 1M context switch`
- `fix: fix the verification problem on first login`
- `chore: remove prefetchOfficialMcpUrls call on startup`
## Commands

```bash
# Install dependencies
bun install

# Dev mode (runs cli.tsx with MACRO defines injected via -d flags)
bun run dev

# Dev mode with debugger (set BUN_INSPECT=9229 to pick port)
bun run dev:inspect

# Pipe mode
echo "say hello" | bun run src/entrypoints/cli.tsx -p

# Build (code splitting, outputs dist/cli.js + chunk files)
bun run build

# Build with Vite (alternative build pipeline)
bun run build:vite

# Test
bun test                                    # run all tests
bun test src/utils/__tests__/hash.test.ts   # run single file
bun test --coverage                         # with coverage report

# Lint & Format (Biome)
bun run lint              # check only
bun run lint:fix          # auto-fix
bun run format            # format all src/

# Health check
bun run health

# Check unused exports
bun run check:unused

# Full check (typecheck + lint + test) — run after completing any task
bun run test:all
bun run typecheck

# Remote Control Server
bun run rcs

# Docs dev server (Mintlify)
bun run docs:dev
```

Detailed test specifications, coverage status and improvement plans can be found in `docs/testing-spec.md`.

## Architecture

### Runtime & Build

- **Runtime**: Bun (not Node.js). All imports, builds, and execution use Bun APIs.
- **Build**: `build.ts` executes `Bun.build()` with `splitting: true`, entry `src/entrypoints/cli.tsx`, output `dist/cli.js` + chunk files. Build enables 19 features by default (see Feature Flag section below). After building, `import.meta.require` is automatically replaced with the Node.js compatible version (the product can run on both bun/node).
- **Dev mode**: `scripts/dev.ts` injects `MACRO.*` defines via Bun `-d` flag, runs `src/entrypoints/cli.tsx`. All features are enabled by default.
- **Module system**: ESM (`"type": "module"`), TSX with `react-jsx` transform.
- **Monorepo**: Bun workspaces — 15 workspace packages + several auxiliary directories in `packages/` resolved via `workspace:*`.
- **Lint/Format**: Biome (`biome.json`). `bun run lint` / `bun run lint:fix` / `bun run format`.
- **Defines**: Centrally managed in `scripts/defines.ts`. Current version `2.1.888`.
- **CI**: GitHub Actions — `ci.yml` (build + test), `release-rcs.yml` (RCS releases), `update-contributors.yml` (automatically update contributors).

### Entry & Bootstrap

1. **`src/entrypoints/cli.tsx`** — True entrypoint. The `main()` function processes multiple fast paths according to priority:
   - `--version` / `-v` — zero module loading
   - `--dump-system-prompt` — feature-gated (DUMP_SYSTEM_PROMPT)
   - `--claude-in-chrome-mcp` / `--chrome-native-host`
   - `--computer-use-mcp` — standalone MCP server mode
   - `--daemon-worker=<kind>` — feature-gated (DAEMON)
   - `remote-control` / `rc` / `remote` / `sync` / `bridge` — feature-gated (BRIDGE_MODE)
   - `daemon` [subcommand] — feature-gated (DAEMON)
   - `ps` / `logs` / `attach` / `kill` / `--bg` — feature-gated (BG_SESSIONS)
   - `new` / `list` / `reply` — Template job commands
   - `environment-runner` / `self-hosted-runner` — BYOC runner
   - `--tmux` + `--worktree` combination
   - Default path: load `main.tsx` to start the full CLI
2. **`src/main.tsx`** (~line 6981) — Commander.js CLI definition. Register a large number of subcommands: `mcp` (serve/add/remove/list...), `server`, `ssh`, `open`, `auth`, `plugin`, `agents`, `auto-mode`, `doctor`, `update`, etc. The main `.action()` handler is responsible for permissions, MCP, session recovery, REPL/Headless mode distribution.
3. **`src/entrypoints/init.ts`** — One-time initialization (telemetry, config, trust dialog).

### Core Loop

- **`src/query.ts`** — The main API query function. Sends messages to Claude API, handles streaming responses, processes tool calls, and manages the conversation turn loop.
- **`src/QueryEngine.ts`** — Higher-level orchestrator wrapping `query()`. Manages conversation state, compaction, file history snapshots, attribution, and turn-level bookkeeping. Used by the REPL screen.
- **`src/screens/REPL.tsx`** — The interactive REPL screen (React/Ink component). Handles user input, message display, tool permission prompts, and keyboard shortcuts.

### API Layer

- **`src/services/api/claude.ts`** — Core API client. Builds request params (system prompt, messages, tools, betas), calls the Anthropic SDK streaming endpoint, and processes `BetaRawMessageStreamEvent` events.
- **7 providers**: `firstParty` (Anthropic direct), `bedrock` (AWS), `vertex` (Google Cloud), `foundry`, `openai`, `gemini`, `grok` (xAI)。
- Provider selection in `src/utils/model/providers.ts`. Priority: modelType parameters > environment variables > default firstParty.

### Tool System

- **`src/Tool.ts`** — Tool interface definition (`Tool` type) and utilities (`findToolByName`, `toolMatchesName`).
- **`src/tools.ts`** — Tool registry. Assembles the tool list; tools are imported from `@claude-code-best/builtin-tools` package. Some tools are conditionally loaded via `feature()` flags or `process.env.USER_TYPE`.
- **`packages/builtin-tools/src/tools/`** — 59 subdirectories (including tool directories such as shared/testing), exported through the `@claude-code-best/builtin-tools` package. Main categories:
  - **File operations**: FileEditTool, FileReadTool, FileWriteTool, GlobTool, GrepTool
  - **Shell/implement**: BashTool, PowerShellTool, REPLTool
  - **Agent system**: AgentTool, TaskCreateTool, TaskUpdateTool, TaskListTool, TaskGetTool
  - **Planning**: EnterPlanModeTool, ExitPlanModeV2Tool, VerifyPlanExecutionTool 
- **Web/MCP**: WebFetchTool, WebSearchTool, MCPTool, McpAuthTool 
- **Scheduling**: CronCreateTool, CronDeleteTool, CronListTool 
- **Others**: LSPTool, ConfigTool, SkillTool, EnterWorktreeTool, ExitWorktreeTool, etc. 
- **`src/tools/shared/`** / **`packages/builtin-tools/src/tools/shared/`** — Tool shared tool functions.
### UI Layer (Ink)

- **`src/ink.ts`** — Ink render wrapper with ThemeProvider injection. 
- **`packages/@ant/ink/`** — Custom Ink framework (forked/internal), including components, core, hooks, keybindings, theme, utils. Note: not `src/ink/`. 
- **`src/components/`** — 149 component directories/files, rendered in the terminal Ink environment. Key components: 
- `App.tsx` — Root provider (AppState, Stats, FpsMetrics) 
- `Messages.tsx` / `MessageRow.tsx` — Conversation message rendering 
- `PromptInput/` — User input handling 
- `permissions/` — Tool permission approval UI 
- `design-system/` — Reuse UI components (Dialog, FuzzyPicker, ProgressBar, ThemeProvider, etc.) 
- Components use React Compiler runtime (`react/compiler-runtime`) — decompiled output has `_c()` memoization calls throughout.

### State Management

- **`src/state/AppState.tsx`** — Central app state type and context provider. Contains messages, tools, permissions, MCP connections, etc.
- **`src/state/AppStateStore.ts`** — Default state and store factory.
- **`src/state/store.ts`** — Zustand-style store for AppState (`createStore`).
- **`src/state/selectors.ts`** — State selectors.
- **`src/bootstrap/state.ts`** — Module-level singletons for session-global state (session ID, CWD, project root, token counts, model overrides, client type, permission mode).

### Workspace Packages
| Package | Description | 
|---------|------| 
| `packages/@ant/ink/` | Forked Ink framework (components, hooks, keybindings, theme) | 
| `packages/@ant/computer-use-mcp/` | Computer Use MCP server (screenshot/keyboard and mouse/clipboard/application management) | 
| `packages/@ant/computer-use-input/` | Keyboard and mouse simulation (dispatcher + darwin/win32/linux backend) | 
| `packages/@ant/computer-use-swift/` | Screenshot + application management (dispatcher + per-platform backend) | 
| `packages/@ant/claude-for-chrome-mcp/` | Chrome Browser Control (enabled with `--chrome`) | 
| `packages/@ant/model-provider/` | Model provider abstraction layer | 
| `packages/builtin-tools/` | Built-in toolset (60 tool implementations, exported through `@claude-code-best/builtin-tools`) | 
| `packages/agent-tools/` | Agent toolset | 
| `packages/acp-link/` | ACP proxy server (WebSocket → ACP agent bridge) | 
| `packages/cc-knowledge/` | Claude Code knowledge base (non-workspace package) | 
| `packages/langfuse-dashboard/` | Langfuse Observability Dashboard (non-workspace package) | 
| `packages/mcp-client/` | MCP client library | 
| `packages/mcp-server/` | MCP server library (non-workspace package) | 
| `packages/remote-control-server/` | Self-hosted Remote Control Server (Docker deployment, including Web UI) - Web UI has been refactored into React + Vite + Radix UI, supporting ACP agent access | 
| `packages/swarm/` | Swarm decoupling module (non-workspace package) | 
| `packages/shell/` | Shell abstraction (non-workspace package) | 
| `packages/audio-capture-napi/` | Native audio capture (restored) | 
| `packages/color-diff-napi/` | Color difference calculation (full implementation, 11 tests) | 
| `packages/image-processor-napi/` | Image processing (restored) | 
| `packages/modifiers-napi/` | Keyboard modifier key detection (macOS FFI implementation) | 
| `packages/url-handler-napi/` | URL scheme processing (environment variable + CLI parameter reading) |
### Bridge/Remote Control 

- **`src/bridge/`** — Remote Control / Bridge mode. feature-gated by `BRIDGE_MODE`. Includes bridge API, session management, JWT authentication, message transmission, permission callback, etc. Entry: `bridgeMain.ts`. 
- **`packages/remote-control-server/`** — Self-hosted RCS, supports Docker deployment, includes Web UI control panel (React 19 + Vite + Radix UI). Support ACP agent access through acp-link (ACP WebSocket handler, relay handler, SSE event stream). Start via `bun run rcs`. 
- CLI fast path: `claude remote-control` / `claude rc` / `claude bridge`. 
- See `docs/features/remote-control-self-hosting.md` for details. 

### ACP Protocol (Agent Client Protocol) 

- **`src/services/acp/`** — ACP agent implementation, including `agent.ts` (AcpAgent class), `bridge.ts` (Claude Code ↔ ACP bridge), `permissions.ts` (permission processing), `entry.ts` (entry). 
- **`packages/acp-link/`** — ACP proxy server, bridges WebSocket clients to the ACP agent. Provides `acp-link` CLI command, supports custom port/HTTPS/authentication/session management, RCS integration (REST registration + WS identify two-step process), permission mode transparent transmission (fallback: client value > config > `ACP_PERMISSION_MODE` environment variable). 
- ACP permission pipeline improvements: `createAcpCanUseTool` unified permission pipeline, `applySessionMode` mode synchronization, `bypassPermissions` availability detection (non-root/sandbox environment). 
- ACP Plan visualization already supports `session/update plan` type of message display (PlanView component, including progress bar/status icon/priority label). 

### Daemon Mode 

- **`src/daemon/`** — Daemon mode (resident supervisor). feature-gated by `DAEMON`. Contains `main.ts` (entry) and `workerRegistry.ts` (worker management). 

### Context & System Prompt 

- **`src/context.ts`** — Builds system/user context for the API call (git status, date, CLAUDE.md contents, memory files). 
- **`src/utils/claudemd.ts`** — Discovers and loads CLAUDE.md files from project hierarchy.
### Feature Flag System 

Feature flags control which functionality is enabled at runtime. The code is uniformly imported through `import { feature } from 'bun:bundle'`, and calling `feature('FLAG_NAME')` returns `boolean`. 

**Enabled method**: Environment variable `FEATURE_<FLAG_NAME>=1`. For example `FEATURE_BUDDY=1 bun run dev`. 

**Build default features** (19, see `build.ts`): 
- Basics: `BUDDY`, `TRANSCRIPT_CLASSIFIER`, `BRIDGE_MODE`, `AGENT_TRIGGERS_REMOTE`, `CHICAGO_MCP`, `VOICE_MODE` 
- Statistics/Cache: `SHOT_STATS`, `PROMPT_CACHE_BREAK_DETECTION`, `TOKEN_BUDGET` 
- P0 local: `AGENT_TRIGGERS`, `ULTRATHINK`, `BUILTIN_EXPLORE_PLAN_AGENTS`, `LODESTONE` 
- P1 API dependencies: `EXTRACT_MEMORIES`, `VERIFICATION_AGENT`, `KAIROS_BRIEF`, `AWAY_SUMMARY`, `ULTRAPLAN` 
- P2: `DAEMON` 

**Dev mode default**: all enabled (see `scripts/dev.ts`). 

**Type declaration**: The `feature` function signature of the `bun:bundle` module is declared in `src/types/internal-modules.d.ts`. 

**Correct way to add new features**: Keep the standard mode of `import { feature } from 'bun:bundle'` + `feature('FLAG_NAME')` and control it through environment variables or configuration at runtime. Do not bypass the feature flag and import directly. 

### Multi-API Compatibility Layer 

All compatibility layers adopt the stream adapter mode: the third-party API format is converted into Anthropic's internal format, and the downstream code is not changed at all. Configured through the `/login` command. 

#### OpenAI Compatibility Layer 

Enabled by `CLAUDE_CODE_USE_OPENAI=1`, supports any OpenAI Chat Completions protocol endpoint such as Ollama/DeepSeek/vLLM. Contains DeepSeek thinking mode support. 

- **`src/services/api/openai/`** — client, message/tool conversion, stream adaptation, model mapping 
- Key environment variables: `CLAUDE_CODE_USE_OPENAI`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` 

#### Gemini Compatibility Layer 

Enabled via `CLAUDE_CODE_USE_GEMINI=1`. Independent environment variable system. 

- **`src/services/api/gemini/`** — client, model mapping, type definition 
- Key environment variables: `GEMINI_API_KEY` (required), `GEMINI_MODEL` (directly specified), `GEMINI_DEFAULT_SONNET_MODEL`/`GEMINI_DEFAULT_OPUS_MODEL` (mapping by capability) 
- Model mapping priority: `GEMINI_MODEL` > `GEMINI_DEFAULT_*_MODEL` > `ANTHROPIC_DEFAULT_*_MODEL` (deprecated) > Return as is 

#### Grok Compatibility Layer 

Enabled via `CLAUDE_CODE_USE_GROK=1`. Custom model mapping supports xAI Grok API. 

- **`src/services/api/grok/`** — client, model mapping 

See the docs documentation of each compatibility layer for details. 

### Budget Mode 

- Switch through the `/poor` command and persist to `settings.json`. 
- Skip `extract_memories`, `prompt_suggestion` and `verification_agent` after enabling, significantly reducing token consumption. 
- Implemented in `src/commands/poor/poorMode.ts`. 

### Stubbed/Deleted Modules 

| Module | Status | 
|--------|--------| 
| Computer Use (`@ant/*`) | Restored — macOS + Windows + Linux (backend completeness varies) | 
| `*-napi` packages | All restored/implemented: `audio-capture-napi`, `image-processor-napi` restored; `color-diff-napi` complete; `modifiers-napi` (macOS FFI); `url-handler-napi` (environment variables + CLI) | 
| Voice Mode | Restored — Push-to-Talk voice input (requires Anthropic OAuth) | 
| OpenAI/Gemini/Grok compatibility layer | Restored | 
| Remote Control Server | Restored — Self-hosted RCS + Web UI | 
| Analytics / GrowthBook / Sentry | Empty implementations | 
| Magic Docs / LSP Server | Restored — Magic Docs Automatic Updates + LSP Server Manager | 
| Plugins / Marketplace | Restored — Plugin installation/uninstallation/enable/disable + Marketplace browsing | 
| MCP OAuth | Simplified |
### Key Type Files 

- **`src/types/global.d.ts`** — Declares `MACRO`, `BUILD_TARGET`, `BUILD_ENV` and internal Anthropic-only identifiers. 
- **`src/types/internal-modules.d.ts`** — Type declarations for `bun:bundle`, `bun:ffi`, `@anthropic-ai/mcpb`. 
- **`src/types/message.ts`** — Message type hierarchy (UserMessage, AssistantMessage, SystemMessage, etc.). 
- **`src/types/permissions.ts`** — Permission mode and result types. 

## Testing 

- **Framework**: `bun:test` (built-in assertion + mock) 
- **Unit test**: placed nearby `src/**/__tests__/`, file name `<module>.test.ts` 
- **Integration tests**: `tests/integration/` — 4 files (cli-arguments, context-build, message-pipeline, tool-chain) 
- **Shared mock/fixture**: `tests/mocks/` (api-responses, file-system, fixtures/) 
- **Naming**: `describe("functionName")` + `test("behavior description")`, English 
- **Package Test**: Each package under `packages/` also has independent tests (such as `color-diff-napi` 11 tests) 

### Mock usage specifications 

**Only mock dependency chains with side effects, not pure function/pure data modules. ** 

Source of forced mock: `log.ts` / `debug.ts` → `bootstrap/state.ts` (module-level `realpathSync` / `randomUUID` side effects). Modules that must be mocked: `log.ts`, `debug.ts`, `bun:bundle`, `settings/settings.js`, `config.ts`, `auth.ts`, and third-party network libraries. 

**`log.ts` and `debug.ts` use shared mocks** (`tests/mocks/log.ts` / `tests/mocks/debug.ts`), do not inline mock definitions in test files. How to use: 

```ts 
import { logMock } from "../../../tests/mocks/log"; 
mock.module("src/utils/log.ts", logMock); 

import { debugMock } from "../../../../tests/mocks/debug"; 
mock.module("src/utils/debug.ts", debugMock); 
``` 

When the source file exports changes, you only need to update the corresponding files under `tests/mocks/`, and there is no need to modify the tests one by one. 

Do not mock: pure function modules (`errors.ts`, `stringUtils.js`), modules whose mock value is the same as the real implementation, modules whose mock path does not match the actual import. 

Path rules: Use `.ts` extension + `src/*` alias path, and double mocking of the same module is prohibited. 

### Type checking 

The project uses TypeScript strict mode, **tsc must have zero errors**. Run after each modification: 

```bash 
bun run typecheck 
``` 

**Type specification**: 
- `as any` is prohibited in production code; `as any` is available for mock data in test files 
- For type mismatch, use `as unknown as SpecificType` double assertion first, or add interface 
- Use `Record<string, unknown>` instead of `any` for unknown structure objects 
- Use type guard to narrow the union type, do not force it 
- `msg.request` property access: `const req = msg.request as Record<string, unknown>` 
- Ink `color` prop: use `as keyof Theme` instead of `as any` 

## Working with This Codebase 

- **tsc must pass** — `bun run typecheck` must have zero errors, and any modifications cannot introduce new type errors. 
- **Feature flags** — All turned off by default (`feature()` returns `false`). Dev/build each have their own default enabled list. Do not redefine `feature` functions in `cli.tsx`. 
- **React Compiler output** — Components have decompiled memoization boilerplate (`const $ = _c(N)`). This is normal. 
- **`bun:bundle` import** — `import { feature } from 'bun:bundle'` is a Bun built-in module and is resolved by the runtime/builder. Don't replace it with a custom function. **`feature()` can only be used directly in the conditional position of an `if` statement or a ternary expression** (Bun compiler restriction). It cannot be assigned to a variable, cannot be placed in the body of an arrow function, and cannot be used as part of an `&&` chain. Correct: `if (feature('X')) {}` or `feature('X') ? a : b`. 
- **`src/` path alias** — tsconfig maps `src/*` to `./src/*`. Imports like `import { ... } from 'src/utils/...'` are valid. 
- **MACRO defines** — Centrally managed in `scripts/defines.ts`. Dev mode is injected through `bun -d`, and build is injected through `Bun.build({ define })`. Modifying constants such as the version number only changes this file. 
- **Build products are compatible with Node.js** — `build.ts` will automatically post-process `import.meta.require`, and the product can be run directly with `node dist/cli.js`. 
- **Biome Configuration** — A large number of lint rules are turned off (decompiled code is not suitable for strict lint). `.tsx` files use 120 line width + mandatory semicolon; other files use 80 line width + semicolon on demand. 
- **Ink framework is in `packages/@ant/ink/`** — not `src/ink/` (that directory does not exist). Ink-related components, hooks, and keybindings are all in packages. 
- **Provider Priority** — `modelType` parameters > Environment variables > Default `firstParty`. New providers need to be registered in `src/utils/model/providers.ts`. 

## Design Context 

The Impeccable design context is stored in `.impeccable.md`. This file must be referenced when designing the web UI (RCS control panel, documentation site, landing page). 

### Core Design Principles 

1. **Considered over clever** — Every design choice should feel intentional, not trend-chasing 
2. **Warmth through subtlety** — Convey warmth through orange-toned neutral colors, blank layout, and warm copywriting 
3. **Density with clarity** — Technical users need information density, but not clutter 
4. **Community voice** — Design should feel like it was created by the users, not a distant design team 
5. **Anthropic's shadow** — Follow Anthropic's design intuition: clean layout, ample spacing, warm color temperature 

### Brand Color 

- Main color: Claude Orange `#D77757` (terra cotta) 
- Secondary color: Claude Blue `#5769F7` 
- Dark mode uses warm dark surfaces (not cold blue-black) 

### Target users 

Technical teams/enterprises using AI-assisted programming in professional workflows. Friendly open source community atmosphere, non-enterprise SaaS style. 

### Visual Reference 

Anthropic's design style—clean, sophisticated, with warm undertones. A lot of white space, with typography as the core. Avoid common design routines for AI products (gradient text, glassy, ​​neon colors).