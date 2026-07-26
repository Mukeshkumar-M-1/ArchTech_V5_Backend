# Phase 1: Detailed explanation of startup process

> The complete path from `bun run dev` to the interactive interface that the user sees

## Start link overview

```
bun run dev
  → package.json scripts.dev: "bun run src/entrypoints/cli.tsx"
    → cli.tsx: polyfill injection + fast path checking
      → import("../main.jsx") → cliMain()
        → main.tsx: main() → run()
          → Commander parameter parsing → preAction hook
            → action handler: service initialization → showSetupScreens
              → launchRepl()
                → replLauncher.tsx: <App><REPL /></App>
                  → REPL.tsx: Render the interactive interface and wait for user input
```

---

## 1. cli.tsx (line 321) - entry and fast path distribution

**File path**: `src/entrypoints/cli.tsx`

### 1.1 Global Polyfill (Lines 1-53)

A side-effect that is executed immediately when the module is loaded, before `main()`.

#### feature() stub function (line 3)

```ts
const feature = (_name: string) => false;
```

When the original Claude Code is built, the Bun bundler provides the `feature()` function through `bun:bundle` for **compile-time feature flag** (similar to C's `#ifdef`). The decompiled version has no build process, so it is directly defined to always return `false`.

**Effect**: All Anthropic internal feature branches are disabled, including:
- `COORDINATOR_MODE` — coordinator mode
- `KAIROS` — assistant mode
- `DAEMON` — background daemon process
- `BRIDGE_MODE` — remote control
- `SSH_REMOTE` — SSH remote
- `BG_SESSIONS` — background sessions
- ...etc. 20+ flags

#### MACRO global object (lines 4-14)

```ts
globalThis.MACRO = {
    VERSION: "2.1.888",
    BUILD_TIME: new Date().toISOString(),
    FEEDBACK_CHANNEL: "",
    ISSUES_EXPLAINER: "",
    NATIVE_PACKAGE_URL: "",
    PACKAGE_URL: "",
    VERSION_CHANGELOG: "",
};
```

In vanilla builds Bun will inline these values into the code. Simulate injection here so that subsequent code can get the value when reading `MACRO.VERSION`.

#### Build constants (lines 16-18)

```ts
BUILD_TARGET = "external"; // Mark as "external" build (not internal to Anthropic)
BUILD_ENV = "production"; // Production environment
INTERFACE_TYPE = "stdio"; //Standard input and output mode
```

These three global variables are read throughout the code to distinguish the running environment. `"external"` means that many `("external" as string) === 'ant'` checks will return false.

#### Environment patching (lines 22-33)

- Disable corepack auto-pin (to prevent pollution of package.json)
- Set Node.js heap memory limit to 8GB in remote mode

#### ABLATION_BASELINE (lines 40-53)

```ts
if (feature("ABLATION_BASELINE") && ...) { ... }
```

`feature()` returns false and **never executes**. Anthropic internal A/B testing code.

### 1.2 main() function (lines 60-317)

Design pattern: **Hierarchical fast path (fast path cascading)** - Check the cost step by step from low to high, and return if it hits.

#### Fast path list

| priority | line number | check condition | function | overhead | executable |
|--------|------|---------|------|------|--------|
| 1 | 64-72 | `--version` / `-v` | Print version number and exit | **zero import** | Yes |
| 2 | 81-94 | `feature("DUMP_SYSTEM_PROMPT")` | Export system prompt | - | No (flag) |
| 3 | 95-99 | `--claude-in-chrome-mcp` | Chrome MCP Service | Dynamic import | Yes |
| 4 | 101-105 | `--chrome-native-host` | Chrome Native Host | Dynamic import | Yes |
| 5 | 108-116 | `feature("CHICAGO_MCP")` | Computer Use MCP | - | No (flag) |
| 6 | 123-127 | `feature("DAEMON")` | Daemon Worker | - | No (flag) |
| 7 | 133-178 | `feature("BRIDGE_MODE")` | Remote control | - | No (flag) |
| 8 | 181-190 | `feature("DAEMON")` | Daemon main process | - | No (flag) |
| 9 | 195-225 | `feature("BG_SESSIONS")` | ps/logs/attach/kill | - | no (flag) |
| 10 | 228-240 | `feature("TEMPLATES")` | Template tasks | - | No (flag) |
| 11 | 244-253 | `feature("BYOC_ENVIRONMENT_RUNNER")` | BYOC runner | - | no (flag) |
| 12 | 258-264 | `feature("SELF_HOSTED_RUNNER")` | Self-hosted runner | - | no (flag) |
| 13 | 267-293 | `--tmux` + `--worktree` | tmux worktree | dynamic import | yes |

#### Parameter correction (lines 296-307)

```ts
// --update/--upgrade → rewritten as update subcommand
if (args[0] === "--update") process.argv = [..., "update"];
// --bare → Set simple mode environment variables
if (args.includes("--bare")) process.env.CLAUDE_CODE_SIMPLE = "1";
```

#### Final exit (lines 310-316)

```ts
const { startCapturingEarlyInput } = await import("../utils/earlyInput.js");
startCapturingEarlyInput(); // Capture what the user inputs in advance
const { main: cliMain } = await import("../main.jsx");
await cliMain(); // Enter main.tsx heavy initialization
```

Just got here when all the fast paths missed (99% of the time).

### 1.3 Startup (line 320)

```ts
void main();
```

`void` means not caring about the Promise return value.

### 1.4 Key design ideas

- **Fast path**: `--version` returns with zero overhead and does not load any modules
- **Dynamic import**: `await import()` replaces static import, and each path only loads the modules it needs.
- **feature flag filter**: `feature()` returns false making a lot of internal features dead code

---

## 2. main.tsx (line 4683) — Heavy initialization and Commander CLI

**File path**: `src/main.tsx`

The largest single file in the entire project, but the structure is clear: **auxiliary function → main() → run()**.

### 2.1 Import area (lines 1-215)

200+ lines of import, loading almost every subsystem. The key is the first three **side-effect import** (import is execution):

```ts
// Line 9: Record timestamp
profileCheckpoint('main_tsx_entry');

// Line 16: Start MDM subprocess reading (macOS plutil)
startMdmRawRead();

// Line 20: Start keychain pre-reading (OAuth token, API key)
startKeychainPrefetch();
```

These three **start subprocesses in parallel** during the import phase, and proceed at the same time as the subsequent ~135ms module loading - **use parallelism to hide delays**.

### 2.2 Helper functions (lines 216-584)

| function | line number | function |
|------|------|------|
| `logManagedSettings()` | 216 | Logging enterprise managed settings to the analytics log |
| `isBeingDebugged()` | 232 | Detect debug mode, **exit(1) directly under external build** (line 266) |
| `logSessionTelemetry()` | 279 | Session telemetry (skills, plug-ins) |
| `getCertEnvVarTelemetry()` | 291 | SSL certificate environment variable collection |
| `runMigrations()` | 326 | Data migration (model renaming, setting format upgrade, etc.) |
| `prefetchSystemContextIfSafe()` | 360 | Safely prefetch the system context after the trust relationship is established |
| `startDeferredPrefetches()` | 388 | REPL Delayed prefetching after first render |
| `eagerLoadSettings()` | 502 | Easily load the `--settings` parameter before init() |
| `initializeEntrypoint()` | 517 | Set `CLAUDE_CODE_ENTRYPOINT` according to the running mode |

There are also three status variables `_pendingConnect`, `_pendingSSH`, and `_pendingAssistantChat` (lines 542-583), which are used to temporarily store subcommand parameters.

### 2.3 main() function (lines 585-856)

`main()` itself is not long. After completing the environment detection, call `run()`:

```
main()
├── Security settings (NoDefaultCurrentDirectoryInExePath)
├── Signal processing (SIGINT → exit, exit → restore cursor)
├── Special paths protected by feature flag (skip all)
├── Detect -p/--print / --init-only → Determine whether interactive mode
├── clientType judgment (cli / sdk-typescript / remote / github-action, etc.)
├── eagerLoadSettings()
└── await run() ← Enter the real logic
```

### 2.4 run() function (lines 884-4683)

Occupying 3800 lines, it is the core of the entire file.

#### Commander initialization + preAction hook (lines 884-967)

```ts
const program = new CommanderCommand()
    .configureHelp(createSortedHelpConfig())
    .enablePositionalOptions();
```

**preAction hook** (will be run before all commands are executed):

```
preAction
├── await ensureMdmSettingsLoaded() ← Wait for the MDM child process to complete
├── await ensureKeychainPrefetchCompleted() ← Wait for keychain pre-reading to be completed
├── await init() ← One-time initialization
├── initSinks() ← Analysis log receiver
├── runMigrations() ← Data migration
├── loadRemoteManagedSettings() ← Enterprise remote settings (non-blocking)
└── loadPolicyLimits() ← Policy limits (non-blocking)
```

#### Main command Option definition (lines 968-1006)

40+ CLI parameters are defined, key ones include:

| Parameters | Function |
|------|------|
| `-p, --print` | Non-interactive mode, exit after output |
| `--model <model>` | Specify model (such as sonnet, opus) |
| `--permission-mode <mode>` | Permission mode |
| `-c, --continue` | Continue the latest conversation |
| `-r, --resume` | Resume the specified conversation |
| `--mcp-config` | MCP server configuration file |
| `--allowedTools` | List of allowed tools |
| `--system-prompt` | Customize system prompts |
| `--dangerously-skip-permissions` | Skip all permission checks |
| `--output-format` | Output format (text/json/stream-json) |
| `--effort <level>` | Reasoning effort level (low/medium/high/max) |
| `--bare` | Minimal mode |

#### action handler (lines 1006-3808)

The execution logic of the main command is internally branched according to stages and scenarios:

```
action(async (prompt, options) => {
    │
    ├── [1007-1600] Parameter analysis and preprocessing
    │ ├── --bare mode
    │ ├── Analysis model / permission-mode / thinking / effort
    │ ├── Analyze MCP configuration, tool list, system prompts
    │ └── Initialize tool permission context
    │
    ├── [1600-2220] Service initialization
    │ ├── MCP client connection
    │ ├── Plug-in loading + skill initialization
    │ ├── Tool list assembly
    │ └── Initial AppState build
    │
    ├── [2220-2315] UI initialization (interactive mode)
    │ ├── createRoot() — Create an Ink rendering root node
    │ ├── showSetupScreens() — Trust dialog, OAuth login, boot
    │ └── Refresh various services after logging in
    │
    ├── [2315-2582] Subsequent initialization
    │ ├── LSP manager, plug-in version management
    │ ├── session registration, telemetry log
    │ └── Telemetry reporting
    │
    ├── [2584-3050] --print non-interactive mode branch
    │ ├── Build headless AppState + store
    │ └── Leave it to print.ts for execution
    │
    └── [3050-3808] Interactive mode: start REPL (7 branches)
        ├── --continue → Load recent conversations → launchRepl()
        ├── DIRECT_CONNECT → ❌ flag close
        ├── SSH_REMOTE → ❌ flag close
        ├── KAIROS assistant → ❌ flag close
        ├── --resume <id> → Resume the specified conversation → launchRepl()
        ├── --resume no ID → show dialog selector
        └── Default (no parameters) → launchRepl() ★The most common path
})
```

#### Subcommand registration (lines 3808-4683)

| Subcommand | Line number | Function |
|--------|------|------|
| `claude mcp` | 3892 | MCP server management (serve/add/remove/list/get) |
| `claude server` | 3960 | Session server (❌ flag off) |
| `claude auth` | 4098 | Authentication management (login/logout/status/token) |
| `claude plugin` | 4148 | Plug-in management (install/uninstall/list/update) |
| `claude setup-token` | 4267 | Set up long-term authentication token |
| `claude agents` | 4278 | List configured agents |
| `claude doctor` | 4346 | Health check |
| `claude update` | 4362 | Check for updates |
| `claude install` | 4394 | Install native build |
| `claude log` | 4411 | View conversation log (internal) |
| `claude completion` | 4491 | Shell auto-completion |

Finally perform parsing:

```ts
await program.parseAsync(process.argv);
```

### 2.5 main.tsx learning suggestions

- **Don't read through**. Remember the three-section structure: auxiliary function → main() → run()
- `feature()` returns false branches and all branches are skipped, 50%+ code can be ignored
- `("external" as string) === 'ant'` branches are also skipped (only for internal builds)
- When you need to delve deeper into a certain function, locate the corresponding code segment through search

---

## 3. replLauncher.tsx (line 22) — Glue layer

**File path**: `src/replLauncher.tsx`

It's extremely simple, just do one thing:

```tsx
export async function launchRepl(root, appProps, replProps, renderAndRun) {
  const { App } = await import('./components/App.js');
  const { REPL } = await import('./screens/REPL.js');
  await renderAndRun(root, <App {...appProps}><REPL {...replProps} /></App>);
}
```

- `App` — Global Provider (AppState, Stats, FpsMetrics)
- `REPL` — interactive interface component
- `renderAndRun` — Render React elements to the Ink terminal

Dynamic import maintains the on-demand loading strategy.

---

## 4. REPL.tsx (line 5009) — interactive interface

**File path**: `src/screens/REPL.tsx`

The second largest file in the project is the interface for direct user interaction. A giant React functional component.

### 4.1 File structure

```
REPL.tsx (line 5009)
├── [1-310] Import area (150+ import)
├── [312-525] Auxiliary components
│ ├── median() — mathematical utility function
│ ├── TranscriptModeFooter — Transcript mode bottom bar
│ ├── TranscriptSearchBar — Transcript search bar
│ └── AnimatedTerminalTitle — terminal title animation
├── [527-571] Props type definition
└── [573-5009] REPL() component body
    ├── [600-900] State declarations (50+ useState/useRef/useAppState)
    ├── [900-2750] Side effects and callbacks (useEffect/useCallback)
    ├── [2750-2860] onQueryImpl — Core: Execute API query
    ├── [2860-3030] onQuery — Query guard and concurrency control
    ├── [3030-3145] Query related auxiliary callbacks
    ├── [3146-3550] onSubmit — User submission processing
    ├── [3550-4395] More side effects and status management
    └── [4396-5009] JSX rendering
```

### 4.2 Props

Passed in via launchRepl() from main.tsx:

| Prop | Type | Meaning |
|------|------|------|
| `commands` | `Command[]` | Available slash commands |
| `debug` | `boolean` | debug mode |
| `initialTools` | `Tool[]` | Initial toolset |
| `initialMessages` | `MessageType[]` | Initial message (value when resuming the conversation) |
| `pendingHookMessages` | `Promise<...>` | Lazy loaded hook messages |
| `mcpClients` | `MCPServerConnection[]` | MCP server connection |
| `systemPrompt` | `string` | Customized system prompt |
| `appendSystemPrompt` | `string` | Append system prompts |
| `onBeforeQuery` | `fn` | Callback before query, return false to prevent query |
| `onTurnComplete` | `fn` | Round completion callback |
| `mainThreadAgentDefinition` | `AgentDefinition` | Main thread Agent definition |
| `thinkingConfig` | `ThinkingConfig` | Thinking mode configuration |
| `disabled` | `boolean` | Disabled input |

### 4.3 Status Management

Divided into three layers:

**Global AppState (read via useAppState selector):**

```ts
const toolPermissionContext = useAppState(s => s.toolPermissionContext);
const verbose = useAppState(s => s.verbose);
const mcp = useAppState(s => s.mcp);
const plugins = useAppState(s => s.plugins);
const agentDefinitions = useAppState(s => s.agentDefinitions);
```

**Local state (useState):**

```ts
const [messages, setMessages] = useState(initialMessages ?? []);
const [inputValue, setInputValue] = useState('');
const [screen, setScreen] = useState<Screen>('prompt');
const [streamingText, setStreamingText] = useState(null);
const [streamingToolUses, setStreamingToolUses] = useState([]);
// ... 50+ states
```

**Key Ref:**

```ts
const queryGuard = useRef(new QueryGuard()).current; // Query concurrency control
const messagesRef = useRef(messages); // Synchronized reference of messages (to avoid closure problems)
const abortController = ...; // Cancel request controller
const responseLengthRef = useRef(0); // Response length tracking
```

### 4.4 Core Data Flow: User Input → API Call

```
User presses Enter
    │
    ▼
onSubmit (line 3146)
    ├── Slash command? → immediate command direct execution or handlePromptSubmit routing
    ├── Empty input? → ignore
    ├── Idle detection → The "Do you want to start a new conversation" dialog box may pop up
    ├── Add to history
    │
    ▼
handlePromptSubmit (external function, src/utils/handlePromptSubmit.ts)
    ├── Slash command → route to the corresponding Command handler
    ├── Normal text → Build UserMessage and call onQuery()
    │
    ▼
onQuery (line 2860) — concurrency guard layer
    ├── queryGuard.tryStart() → Already have a query? Waiting in line
    ├── setMessages([...old, ...newMessages]) — append user messages
    ├── onQueryImpl()
    │
    ▼
onQueryImpl (line 2750) — actually performs the API call
    │
    ├── 1. Load context in parallel:
    │ await Promise.all([
    │ getSystemPrompt(), // Build system prompt
    │ getUserContext(), // User context
    │ getSystemContext(), // System context (git, platform, etc.)
    │ ])
    │
    ├── 2. buildEffectiveSystemPrompt() — synthesize the final system prompt
    │
    ├── 3. for await (const event of query({...})) ★Core★
    │ │ Call query() AsyncGenerator of src/query.ts
    │ │ Streaming output events
    │ │
    │ └── onQueryEvent(event) — Handle each streaming event
    │ ├── Update streamingText (typewriter effect)
    │ ├── Update messages (tool call result)
    │ └── Update inProgressToolUseIDs
    │
    └── 4. Closing: resetLoadingState(), onTurnComplete()
```

**Core code (lines 2797-2807)**:

```ts
for await (const event of query({
    messages: messagesIncludingNewMessages,
    systemPrompt,
    userContext,
    systemContext,
    canUseTool,
    toolUseContext,
    querySource: getQuerySourceForREPL()
})) {
    onQueryEvent(event);
}
```

`query()` comes from `src/query.ts` and is the core function to be learned in the second stage.

### 4.5 QueryGuard Concurrency Control

State machine to prevent multiple API requests from being made simultaneously:

```
idle ──tryStart()──▶ running ──end()──▶ idle
                        │
                        └── tryStart() returns null (already running)
                            → New messages are queued
```

- `tryStart()` — Atomic operation, check and convert idle→running, return generation number
- `end(generation)` — Check generation matching and convert running→idle
- Prevent cancel+resubmit race condition

### 4.6 JSX Rendering

Two mutually exclusive rendering branches:

#### Transcript mode (lines 4396-4493)

Press the `v` key to switch, read-only browsing of the conversation history, and support search:

```tsx
<KeybindingSetup>
  <AnimatedTerminalTitle />
  <GlobalKeybindingHandlers />
  <ScrollKeybindingHandler />
  <CancelRequestHandler />
  <FullscreenLayout
    scrollable={<Messages />}
    bottom={<TranscriptSearchBar /> or <TranscriptModeFooter />}
  />
</KeybindingSetup>
```

#### Prompt mode (lines 4552-5009)

Main interactive interface, from top to bottom:

```tsx
<KeybindingSetup>
  <AnimatedTerminalTitle /> // Terminal tab title
  <GlobalKeybindingHandlers /> // Global shortcut keys
  <CommandKeybindingHandlers /> //Command shortcut keys
  <ScrollKeybindingHandler /> //Scrolling shortcut key
  <CancelRequestHandler /> // Ctrl+C Cancel
  <MCPConnectionManager> // MCP connection management
    <FullscreenLayout
      overlay={<PermissionRequest />} // Permission approval overlay
      scrollable={ // scrollable area
        <>
          <Messages /> // ★ Conversation message rendering
          <UserTextMessage /> //User input placeholder
          {toolJSX} // Tool UI
          <SpinnerWithVerb /> // Loading animation
        </>
      }
      bottom={ // Fixed bottom
        <>
          {/* Various dialog boxes */}
          <SandboxPermissionRequest />
          <PromptDialog />
          <ElicitationDialog />
          <CostThresholdDialog />
          <FeedbackSurvey />

          {/* ★ User input box */}
          <PromptInput
            onSubmit={onSubmit}
            commands={commands}
            isLoading={isLoading}
            messages={messages}
            // ... 20+ props
          />
        </>
      }
    />
  </MCPConnectionManager>
</KeybindingSetup>
```

### 4.7 REPL.tsx Learning Suggestions

- There is only one line in the core: `onSubmit → onQuery → query() → onQueryEvent → update message`
- The remaining 4000+ lines are UI details: shortcut keys, dialog boxes, animations, edge case handling
- `feature('...')` protected JSX skips all
- `("external" as string) === 'ant'` branches are also skipped

---

## Summary of key design patterns

| Mode | Location | Description |
|------|------|------|
| Fast path | cli.tsx | Check step by step from low to high cost, processing simple requests with zero overhead |
| Dynamic import | cli.tsx / main.tsx | `await import()` lazy loading, each path only loads the required modules |
| Side-effect import | main.tsx top | Start the child processes in parallel during the import phase, using parallelism to hide delays |
| feature flag | global | `feature()` always returns false, eliminating dead code during compilation |
| preAction hook | main.tsx run() | Commander.js unified initialization before command execution |
| QueryGuard | REPL.tsx | State machine to prevent concurrent API requests, with generation count to prevent race conditions |
| React/Ink | UI layer | Use React component model to render terminal UI, supporting full screen and virtual scrolling |

## Code patterns to ignore

| Schema | Source | Description |
|------|------|------|
| `_c(N)` call | React Compiler | The memoization boilerplate code generated by decompilation |
| The code behind `feature('FLAG')` | Bun bundler | All is dead code and will not be executed in the current version |
| `("external" as string) === 'ant'` | Build target check | Always false (external !== ant) |
| tsc type error | Decompilation | `unknown`/`never`/`{}` type, does not affect Bun operation |
| `packages/@ant/` | stub package | Empty implementation, only satisfying import dependencies |