# Daemon Restructuring Design Proposal

> **Branch**: `feat/integrate-5-branches`
> **Base**: `f41745cb` (= main `11bb3f62` content)
> **Date**: 2026-04-13

## I. Problem Overview

### 1.1 Scattered Command Structure

Currently, commands related to background processes are distributed across three different locations without a unified namespace:

| Command | Registration Location | Entry Point |
| :--- | :--- | :--- |
| `claude daemon start/status/stop` | `cli.tsx` fast path L203 | `daemon/main.ts` |
| `claude ps` | `cli.tsx` fast path L220 | `cli/bg.ts` |
| `claude logs <x>` | `cli.tsx` fast path L232 | `cli/bg.ts` |
| `claude attach <x>` | `cli.tsx` fast path L236 | `cli/bg.ts` |
| `claude kill <x>` | `cli.tsx` fast path L238 | `cli/bg.ts` |
| `claude --bg` | `cli.tsx` fast path L244 | `cli/bg.ts` |
| `claude new/list/reply` | `cli.tsx` fast path L250 | `cli/handlers/templateJobs.ts` |
| `claude rollback` | `main.tsx` Commander.js L6525 | `cli/rollback.ts` |
| `claude up` | `main.tsx` Commander.js L6511 | `cli/up.ts` |

**Issues**:
- `ps/logs/attach/kill` and `daemon` are logically related to background process management but are currently disconnected.
- These commands **only have CLI entry points**; typing `/daemon` or `/ps` in the REPL does not work.
- `new/list/reply` are top-level commands for the template task system, making them prone to conflicts (especially `list`).

### 1.2 Lack of Windows Support

`--bg` and `attach` have hard dependencies on `tmux`:
- `bg.ts:handleBgFlag()` checks for `tmux` as the first step and exits with an error if it's unavailable.
- `bg.ts:attachHandler()` uses `tmux attach-session`, with no alternative for systems without `tmux`.
- Windows users (including those using VS Code terminals) are completely unable to use background session features.

### 1.3 Missing REPL Entry Points

Comparing this with the dual-registration model used for `/mcp`:
- **CLI**: `claude mcp serve/add/remove/list` (Commander.js, `main.tsx:5760`).
- **REPL**: `/mcp enable/disable/reconnect` (Slash command, `commands/mcp/index.ts`).

The `daemon`/`bg`/`job` series only has CLI fast paths and is entirely unavailable within the REPL.

## II. Objectives

1.  **Hierarchical Command Structure**: Follow the `/mcp` model by centralizing background management under `/daemon` and template tasks under `/job`.
2.  **Cross-Platform Background Sessions**: Enable starting, attaching to, and terminating background sessions on Windows, macOS, and Linux.
3.  **Dual Registration**: Ensure availability via both the CLI (`claude daemon ...`) and the REPL (`/daemon ...`).
4.  **Backward Compatibility**: Retain old commands while outputting deprecation notices.

## III. Command Structure Design

### 3.1 `/daemon` — Background Process Management

Merge the daemon supervisor and background sessions into a unified namespace:

```
claude daemon <subcommand>     ← CLI entry (cli.tsx fast path)
/daemon <subcommand>           ← REPL entry (slash command, local-jsx)

Subcommands:
  status                       Comprehensive status panel (daemon + all sessions)
  start [--dir <path>]         Start the daemon supervisor
  stop                         Stop the daemon
  bg [args...]                 Start a background session
  attach [target]              Attach to a background session
  logs [target]                View session logs
  kill [target]                Terminate a session
  (No arguments)               Equivalent to 'status'
```

**CLI Fast Path Routing** (`cli.tsx`):
```typescript
// NEW: Unified entry point
if (feature('DAEMON') && args[0] === 'daemon') {
  const sub = args[1] || 'status'
  switch (sub) {
    case 'start': case 'stop': case 'status':
      await daemonMain([sub, ...args.slice(2)])
      break
    case 'bg':
      await bg.handleBgStart(args.slice(2))
      break
    case 'attach': case 'logs': case 'kill':
      await bg[`${sub}Handler`](args[2])
      break
  }
}

// Backward Compatibility (Deprecated)
if (feature('BG_SESSIONS') && ['ps','logs','attach','kill'].includes(args[0])) {
  console.warn(`[deprecated] Use: claude daemon ${args[0] === 'ps' ? 'status' : args[0]}`)
  // ... delegate to daemon subcommand
}
```

**REPL Slash Command** (`commands/daemon/index.ts`):
```typescript
const daemon = {
  type: 'local-jsx',
  name: 'daemon',
  description: 'Manage background sessions and daemon',
  argumentHint: '[status|start|stop|bg|attach|logs|kill]',
  isEnabled: () => feature('DAEMON') || feature('BG_SESSIONS'),
  load: () => import('./daemon.js'),
} satisfies Command
```

### 3.2 `/job` — Template Task Management

```
claude job <subcommand>        ← CLI entry
/job <subcommand>              ← REPL entry

Subcommands:
  list                         List templates and active tasks
  new <template> [args]        Create a task from a template
  reply <id> <text>            Reply to a task
  status <id>                  View task status
  (No arguments)               Equivalent to 'list'
```

### 3.3 Standalone Commands (Unchanged)

```
claude up                      Remains top-level (concise bootstrap command)
claude rollback [target]       Remains top-level (low-frequency maintenance command)
```

## II. Cross-Platform Background Engine

### 4.1 Engine Abstraction

```typescript
// src/cli/bg/engine.ts
export interface BgEngine {
  readonly name: string

  /** Whether the engine is available on the current platform */
  available(): Promise<boolean>

  /** Start a background session */
  start(opts: BgStartOptions): Promise<BgStartResult>

  /** Attach to a background session (blocking) */
  attach(session: SessionEntry): Promise<void>
}

export interface BgStartOptions {
  sessionName: string
  args: string[]
  env: Record<string, string | undefined>
  logPath: string
  cwd: string
}

export interface BgStartResult {
  pid: number
  sessionName: string
  logPath: string
  engineUsed: string
}
```

### 4.2 Implementation Engines

| Engine | Platform | Start Method | Attach Method |
| :--- | :--- | :--- | :--- |
| **TmuxEngine** | macOS/Linux (with tmux) | `tmux new-session -d` | `tmux attach-session` |
| **DetachedEngine** | Windows / macOS/Linux without tmux | `spawn({ detached, stdio→logFile })` | `tail -f` log file |

#### DetachedEngine Detailed Design

**Start (`start`)**:
1. Open the log file file descriptor (`fd`).
2. Perform a detached `spawn`, redirecting `stdout`/`stderr` to the log.
3. Save the session info to `sessions/<PID>.json`.

**Attach (`attach`)**:
1. Implement a cross-platform `tail -f`.
2. Output existing log content to `stdout`.
3. Use `fs.watch(logPath)` to monitor changes.
4. Read and output new content as it arrives.
5. Exit `tail` on `Ctrl+C` (without killing the background process).

#### Engine Selection Logic

```typescript
// src/cli/bg/engines/index.ts
export async function selectEngine(): Promise<BgEngine> {
  if (process.platform === 'win32') {
    return new DetachedEngine()
  }

  const tmux = new TmuxEngine()
  if (await tmux.available()) {
    return tmux
  }

  return new DetachedEngine()
}
```

### 4.3 `SessionEntry` Extension

```typescript
interface SessionEntry {
  // ... existing fields
  engine: 'tmux' | 'detached'   // NEW: Records the engine used
  tmuxSessionName?: string       // Specific to TmuxEngine
  logPath?: string               // Available for both engines
}
```

Upon attachment, the strategy is selected based on `session.engine`.

## V. File Change List

### New Files (10)

| File | Description |
| :--- | :--- |
| `src/cli/bg/engine.ts` | `BgEngine` interface definition. |
| `src/cli/bg/engines/tmux.ts` | `TmuxEngine` (extracted from `bg.ts`). |
| `src/cli/bg/engines/detached.ts` | `DetachedEngine` (new implementation). |
| `src/cli/bg/engines/index.ts` | Engine selection and re-exports. |
| `src/cli/bg/tail.ts` | Cross-platform log `tail` (for detached attach). |
| `src/commands/daemon/index.ts` | Registration for `/daemon` REPL slash command. |
| `src/commands/daemon/daemon.tsx` | Routing for `/daemon` subcommands + status UI. |
| `src/commands/job/index.ts` | Registration for `/job` REPL slash command. |
| `src/commands/job/job.tsx` | Routing for `/job` subcommands + UI. |
| `docs/features/daemon-restructure-design.md`| This design document. |

### Modified Files (6)

| File | Change |
| :--- | :--- |
| `src/cli/bg.ts` | Refactor: Handler functions now call `BgEngine`. |
| `src/entrypoints/cli.tsx` | Fast Path: Unified `daemon` entry + backward compatibility. |
| `src/commands.ts` | Register `/daemon` and `/job` slash commands. |
| `src/daemon/main.ts` | `daemonMain()`: Add sub-dispatching for `bg`/`ps`/`logs`. |
| `src/main.tsx` | Commander.js: Optional registration of `daemon`/`job` subcommands. |
| `src/cli/handlers/templateJobs.ts` | Adapt to `/job` entry point (minimal changes). |

### Unchanged Files

- `src/daemon/state.ts` (Daemon PID management).
- `src/jobs/state.ts` (Job state management).
- `src/jobs/templates.ts` (Template discovery).
- `src/jobs/classifier.ts` (Task classifier).
- `src/cli/rollback.ts` (Top-level command).
- `src/cli/up.ts` (Top-level command).

## VI. Feasibility Analysis

### 6.1 Risk Assessment

| Risk | Level | Mitigation |
| :--- | :--- | :--- |
| `cli.tsx` modifications impacting startup speed | Low | Changes limited to routing logic; imports remain lazy. |
| Unreliable `fs.watch` for `DetachedEngine` on Windows | Medium | Implement polling fallback (`setInterval` + `fs.stat`). |
| Backward compatibility warnings breaking scripts | Low | Old commands remain functional; warnings sent to `stderr`. |
| `spawn` subprocesses in REPL via `/daemon bg` | Medium | Precedent exists (e.g., `NewInstallWizard` in `/assistant`). |
| `tsc` type compatibility | Low | Interface definitions are clear; avoids `any`. |

### 6.2 Effort Estimation

| Task | Files | Complexity |
| :--- | :--- | :--- |
| **BgEngine Abstraction + Implementations** | 5 New + 1 Mod | Medium |
| **Hierarchical /daemon Commands** | 3 New + 3 Mod | Medium |
| **Hierarchical /job Commands** | 2 New + 2 Mod | Low |
| **Compatibility + Testing** | 0 New + 2 Mod | Low |

## VII. Design Decision Log

### D1: Why merge daemon and background sessions into one namespace?
From the user's perspective, both represent "things running in the background." Splitting them (e.g., `claude daemon status` for the supervisor and `claude ps` for sessions) creates a disjointed experience. Merging them allows `claude daemon status` to display both the supervisor status and a list of all active sessions in one view.

### D2: Why keep `rollback`/`up` out of the `daemon` namespace?
These are essentially for **version management and environment initialization**, not background process management. `claude up` is a synchronous, blocking setup script that does not involve the daemon or background sessions. Keeping them at the top level is more intuitive.

### D3: Why use `tail` instead of IPC for `DetachedEngine` attachment?
1.  Log files are the simplest cross-platform solution with zero extra dependencies.
2.  The UDS Pipe IPC system (`usePipeIpc`) is designed for instance-to-instance communication, not terminal attachment.
3.  The full PTY experience of `tmux attach` cannot be replicated in pure detached mode; `tail` is the most straightforward alternative.

### D4: Why not use the Windows Terminal tab/pane API?
The `wt.exe` functionality of Windows Terminal for new windows/tabs is not universal—users might be using VS Code, ConEmu, cmder, or other terminals. A detached process writing to a log is the only truly cross-terminal solution.
