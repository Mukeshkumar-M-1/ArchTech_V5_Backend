# Phase 1 Q&A

## Q1: What exactly is the fast path distribution in cli.tsx doing?

**Core Idea**: Based on the command parameters input by the user, decide which path to take as early as possible to avoid loading unnecessary code. `cli.tsx` acts as a lightweight router, handling simple requests on the spot and loading `main.tsx` only when a full CLI is truly required.

### Scenario Comparison

#### Scenario 1: `claude --version` (Fast path hit)

```
cli.tsx main() starts execution
  ├── args = ["--version"]
  ├── Hit line 64: args[0] === "--version" ✅
  ├── console.log("2.1.888 (Claude Code)")
  └── return  ← Exit immediately, zero imports, ~10ms
```

#### Scenario 2: `claude --claude-in-chrome-mcp` (Middle path hit)

```
cli.tsx main() starts execution
  ├── Line 64: --version? ❌
  ├── Line 75: Load profileCheckpoint (only this one import)
  ├── Line 81: feature("DUMP_SYSTEM_PROMPT") → false ❌
  ├── Line 95: --claude-in-chrome-mcp? ✅ Hit
  ├── await import("../utils/claudeInChrome/mcpServer.js")  ← Only load this one module
  └── return  ← Does not load the 200+ imports of main.tsx
```

#### Scenario 3: `claude` (No parameters, most common, all misses)

```
cli.tsx main() starts execution
  ├── --version?           ❌
  ├── profileCheckpoint loaded
  ├── feature(DUMP)?       ❌ (feature=false)
  ├── --chrome-mcp?        ❌
  ├── --chrome-native?     ❌
  ├── feature(CHICAGO)?    ❌ (feature=false)
  ├── feature(DAEMON)?     ❌ (feature=false)
  ├── feature(BRIDGE)?     ❌ (feature=false)
  ├── ... All fast paths checked sequentially, all misses
  │
  ├── Reach line 310 ← Final exit
  ├── await import("../main.jsx")  ← Load full CLI (200+ imports, ~135ms)
  └── await cliMain()              ← Enter heavy initialization in main.tsx
```

### Performance Comparison

| Method | `claude --version` Time |
|------|------------------------|
| No fast path (all go through main.tsx) | ~200ms (Load 200+ imports → Initialize Commander → Parse parameters → Print) |
| With fast path (Intercepted by cli.tsx) | ~10ms (Read args → Print → Exit) |

### Acceleration Effect of `feature()`

Many fast paths are guarded by `feature()`:

```ts
if (feature("DAEMON") && args[0] === "daemon") { ... }
```

`feature()` returns false → `&&` short-circuits → `args[0]` is not even checked, skipped directly. In the decompiled version, these paths effectively do not exist, further accelerating the "all misses → take default path" process.

---

## Q2: What is the specific execution flow for different commands in main.tsx?

All commands go through `main()` → `run()`, but are routed to different branches inside `run()` according to Commander.

### Scenario 1: `claude` (No parameters — Start interactive REPL)

The most common scenario, follows the full main command path:

```
main() (Line 585)
  ├── Signal handler registration (SIGINT, exit)
  ├── All feature flag paths skipped
  ├── isNonInteractive = false (Has TTY, no -p)
  ├── clientType = 'cli'
  └── await run()
       │
       ▼
  run() (Line 884)
  ├── Commander initialization + preAction hook + Main command option registration
  ├── isPrintMode = false → Register all subcommands
  └── program.parseAsync(process.argv)
       │  Commander matches main command, executes preAction first
       ▼
  preAction (Line 907)
  ├── await ensureMdmSettingsLoaded()        ← Wait for side-effect import subprocess
  ├── await ensureKeychainPrefetchCompleted() ← Wait for keychain prefetch
  ├── await init()                            ← Telemetry, config, trust
  ├── initSinks()                             ← Analytics logs
  ├── runMigrations()                         ← Data migration
  └── loadRemoteManagedSettings() / loadPolicyLimits() ← Non-blocking
       │  Then execute action handler
       ▼
  action(undefined, options) (Line 1007)     ← prompt = undefined
  ├── [Parameter Parsing] permissionMode, model, thinkingConfig...
  ├── [Tool Loading] tools = getTools(toolPermissionContext)
  ├── [Parallel Initialization]
  │   ├── setup()        ← worktree, CWD
  │   ├── getCommands()  ← Load slash commands
  │   └── getAgentDefinitionsWithOverrides() ← Load agent definitions
  ├── [MCP Connection] Connect to configured MCP servers
  ├── [Build Initial State] initialState = { tools, mcp, permissions, ... }
  │
  ├── [UI Initialization] (Interactive mode only)
  │   ├── createRoot()          ← Create Ink rendering root
  │   └── showSetupScreens()    ← Trust dialog / OAuth / Onboarding
  │
  ├── [Post-initialization] LSP, plugin versions, session registration
  │
  └── Default branch (Line 3760) ← No --continue/--resume/--print
      └── await launchRepl(root, {
              initialState
          }, {
              ...sessionConfig,
              initialMessages: undefined  ← Fresh conversation, no history
          }, renderAndRun)
            │
            ▼
          REPL.tsx renders, user sees blank conversation interface
```

### Scenario 2: `echo "explain this" | claude -p` (Pipe/Non-interactive mode)

```
main() →
  ├── isNonInteractive = true (-p flag + stdin is not TTY)
  ├── clientType = 'sdk-cli'
  └── run()
       │
       ▼
  run()
  ├── Commander initialization + preAction + Main command options
  ├── isPrintMode = true
  │   → ★ Skip all subcommand registration (Saves ~65ms)
  └── program.parseAsync()  ← Parse directly, Commander routes to main command action
       │
       ▼
  preAction → init, migration, etc. (Same as Scenario 1)
       │
       ▼
  action("", { print: true, ... })
  ├── inputPrompt = await getInputPrompt("")
  │   ├── stdin.isTTY = false → Read data from stdin
  │   ├── Wait up to 3s for input: "explain this"
  │   └── Return "explain this"
  ├── tools = getTools()
  ├── setup() + getCommands() (Parallel)
  │
  ├── isNonInteractiveSession = true → Take --print branch (Line 2584)
  │   ├── applyConfigEnvironmentVariables() ← Trust implied in -p mode
  │   ├── Build headlessInitialState (No UI)
  │   ├── headlessStore = createStore(headlessInitialState)
  │   │
  │   ├── await import('src/cli/print.js')
  │   └── runHeadless(inputPrompt, ...)  ★ Does not go through REPL
  │       ├── Send API request
  │       ├── Stream output to stdout
  │       └── Exit with process.exit() upon completion
  │
  └── ← Does not go through createRoot(), showSetupScreens(), launchRepl()
```

**Key Differences**:
- Skip subcommand registration after detecting `-p` (Saves ~65ms)
- No Ink UI created, no `showSetupScreens()` called
- Read input from stdin (`getInputPrompt` line 857)
- Path through `print.js` executes query and outputs directly to stdout

### Scenario 3: `claude -c` (Continue latest conversation)

```
... main() → run() → preAction → action (First half same as Scenario 1)
       │
       ▼
  action(undefined, { continue: true, ... })
  ├── [Parameter Parsing + Tool Loading + Parallel Init + UI Init] (Same as Scenario 1)
  │
  ├── options.continue = true → Hit line 3101
  │   ├── clearSessionCaches()       ← Clear expired caches
  │   ├── result = await loadConversationForResume()
  │   │   └── Read latest conversation JSONL from ~/.claude/projects/<cwd>/
  │   │
  │   ├── result is null? → exitWithError("No conversation found")
  │   │
  │   ├── loaded = await processResumedConversation(result)
  │   │   ├── Parse JSONL → messages[]
  │   │   ├── Restore file history snapshots
  │   │   └── Rebuild initialState
  │   │
  │   └── await launchRepl(root, {
  │           initialState: loaded.initialState
  │       }, {
  │           ...sessionConfig,
  │           initialMessages: loaded.messages,            ★ Include history messages
  │           initialFileHistorySnapshots: loaded.fileHistorySnapshots,
  │           initialAgentName: loaded.agentName
  │       }, renderAndRun)
  │         │
  │         ▼
  │       REPL.tsx renders, shows historical conversation, user continues chat
  │
  └── ← Other branches do not execute
```

**Key Difference**: `initialMessages` has a value (history messages), so REPL renders previous conversation content upon startup.

### Scenario 4: `claude mcp list` (Subcommand)

```
main() → run()
       │
       ▼
  run()
  ├── Commander initialization + preAction hook
  ├── Register main command .action(...)
  ├── isPrintMode = false → Register all subcommands
  │   ├── program.command('mcp') (Line 3894)
  │   │   ├── mcp.command('serve').action(...)
  │   │   ├── mcp.command('add').action(...)
  │   │   ├── mcp.command('list').action(async () => {  ★
  │   │   │       const { mcpListHandler } = await import('./cli/handlers/mcp.js');
  │   │   │       await mcpListHandler();
  │   │   │   })
  │   │   └── ...
  │   ├── program.command('auth')
  │   ├── program.command('doctor')
  │   └── ...
  │
  └── program.parseAsync(["node", "claude", "mcp", "list"])
       │  Commander matches mcp → list
       ▼
  preAction (Line 907)     ← Subcommand also triggers preAction
  ├── await init()
  ├── initSinks()
  ├── runMigrations()
  └── ...
       │
       ▼  Execute subcommand's own action (does not go through main command action)
  mcp list action
  ├── await import('./cli/handlers/mcp.js')
  └── await mcpListHandler()
      ├── Read MCP config (user/project/local tiers)
      ├── Connect to each server for health check
      ├── Format output to terminal
      └── Exit
```

**Key Differences**:
- Commander routes to the subcommand, **main command action is skipped entirely**
- `preAction` still executes (basic initialization required for all commands)
- Subcommands have their own independent, lightweight actions

### Comparison of Four Scenarios

| | `claude` | `claude -p` | `claude -c` | `claude mcp list` |
|---|---------|------------|------------|-------------------|
| preAction | Execute | Execute | Execute | Execute |
| Main command action | Execute | Execute | Execute | **Skip** |
| Subcommand registration | Register | **Skip** | Register | Register |
| showSetupScreens | Execute | **Skip** | Execute | **Skip** |
| createRoot (Ink) | Execute | **Skip** | Execute | **Skip** |
| Load history messages | No | No | **Yes** | No |
| Final exit | launchRepl | print.js | launchRepl | Subcommand action |