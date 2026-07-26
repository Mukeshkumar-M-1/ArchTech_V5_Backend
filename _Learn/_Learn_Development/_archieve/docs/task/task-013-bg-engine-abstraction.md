# Task 013: BgEngine Cross-platform Background Engine Abstraction

> Design Doc: [daemon-restructure-design.md](../features/daemon-restructure-design.md) § IV
> Dependency: None
> Branch: `feat/integrate-5-branches`

## Goal

Extract the hardcoded tmux logic in `src/cli/bg.ts` into an engine abstraction layer, implementing TmuxEngine + DetachedEngine, so that background session features work on Windows / macOS / Linux.

## Background

Currently, `handleBgFlag()` and `attachHandler()` in `bg.ts` call tmux commands directly. On Windows, `--bg` directly errors out and exits. An engine abstraction layer is needed to automatically select the best solution based on the platform and available tools.

## File List

### New

| File | Description |
|------|------|
| `src/cli/bg/engine.ts` | BgEngine interface + BgStartOptions/BgStartResult types |
| `src/cli/bg/engines/tmux.ts` | TmuxEngine: Extract tmux-related logic from `bg.ts` |
| `src/cli/bg/engines/detached.ts` | DetachedEngine: spawn({ detached }) + logFile redirection |
| `src/cli/bg/engines/index.ts` | selectEngine() auto-selection + re-export |
| `src/cli/bg/tail.ts` | Cross-platform log tail: fs.watch + polling fallback |

### Modified

| File | Change |
|------|------|
| `src/cli/bg.ts` | Change `handleBgFlag()` to call `selectEngine().start()`; change `attachHandler()` to call `engine.attach()` |

## Implementation Plan

### 1. BgEngine Interface (`src/cli/bg/engine.ts`)

```typescript
export interface BgEngine {
  readonly name: string
  available(): Promise<boolean>
  start(opts: BgStartOptions): Promise<BgStartResult>
  attach(session: SessionEntry): Promise<void>
}

export interface BgStartOptions {
  sessionName: string
  args: string[]         // CLI args (with --bg removed)
  env: Record<string, string | undefined>
  logPath: string
  cwd: string
}

export interface BgStartResult {
  pid: number
  sessionName: string
  logPath: string
  engineUsed: 'tmux' | 'detached'
}
```

### 2. TmuxEngine (`src/cli/bg/engines/tmux.ts`)

Extract from `bg.ts:handleBgFlag()` and `bg.ts:attachHandler()`:
- `available()`: `execFileNoThrow('tmux', ['-V'])` returns code === 0.
- `start()`: `tmux new-session -d -s <name> <cmd>`.
- `attach()`: `tmux attach-session -t <session.tmuxSessionName>`.

### 3. DetachedEngine (`src/cli/bg/engines/detached.ts`)

```typescript
export class DetachedEngine implements BgEngine {
  readonly name = 'detached'

  async available(): Promise<boolean> {
    return true  // Always available
  }

  async start(opts: BgStartOptions): Promise<BgStartResult> {
    const logFd = openSync(opts.logPath, 'a')
    const child = spawn(process.execPath, [process.argv[1]!, ...opts.args], {
      detached: true,
      stdio: ['ignore', logFd, logFd],
      env: opts.env,
      cwd: opts.cwd,
    })
    child.unref()
    closeSync(logFd)

    return {
      pid: child.pid!,
      sessionName: opts.sessionName,
      logPath: opts.logPath,
      engineUsed: 'detached',
    }
  }

  async attach(session: SessionEntry): Promise<void> {
    // Delegate to tail.ts
    await tailLog(session.logPath!)
  }
}
```

### 4. Log Tail (`src/cli/bg/tail.ts`)

```typescript
/**
 * Cross-platform real-time log output. Exit with Ctrl+C without killing the background process.
 *
 * Strategies:
 * 1. Read existing content and output it.
 * 2. Use fs.watch() to listen for file changes (primary solution).
 * 3. Fallback to 500ms polling if fs.watch is unreliable (some Windows network drives).
 */
export async function tailLog(logPath: string): Promise<void>
```

### 5. Engine Selection (`src/cli/bg/engines/index.ts`)

```typescript
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

### 6. bg.ts Refactoring

Rename `handleBgFlag()` to `handleBgStart()`, internal logic:
```typescript
export async function handleBgStart(args: string[]): Promise<void> {
  const engine = await selectEngine()
  const sessionName = `claude-bg-${randomUUID().slice(0, 8)}`
  const logPath = join(getClaudeConfigHomeDir(), 'sessions', 'logs', `${sessionName}.log`)

  const result = await engine.start({
    sessionName,
    args: filteredArgs,
    env: { ...process.env, CLAUDE_CODE_SESSION_KIND: 'bg', ... },
    logPath,
    cwd: process.cwd(),
  })

  console.log(`Background session started: ${result.sessionName}`)
  console.log(`  Engine: ${result.engineUsed}`)
  console.log(`  Log: ${result.logPath}`)
  console.log(`  Use \`claude daemon attach ${result.sessionName}\` to reconnect.`)
}
```

`attachHandler()` selects engine based on `session.engine` field:
```typescript
export async function attachHandler(target: string | undefined): Promise<void> {
  // ... find session
  if (session.engine === 'tmux' && session.tmuxSessionName) {
    const tmux = new TmuxEngine()
    await tmux.attach(session)
  } else {
    const detached = new DetachedEngine()
    await detached.attach(session)
  }
}
```

## SessionEntry Extension

`sessions/<PID>.json` adds `engine` field:

```json
{
  "pid": 12345,
  "engine": "detached",
  "logPath": "~/.claude/sessions/logs/claude-bg-a1b2c3d4.log",
  "sessionId": "...",
  "cwd": "..."
}
```

Backward compatibility: If the `engine` field is missing, it's `tmux` if `tmuxSessionName` exists, otherwise `detached`.

## Verification Checklist

- [ ] Windows: `claude daemon bg` starts a background session without tmux dependency.
- [ ] Windows: `claude daemon attach <name>` attaches in tail mode; Ctrl+C exits without killing the process.
- [ ] macOS/Linux (with tmux): Behavior remains consistent with current.
- [ ] macOS/Linux (without tmux): Automatically falls back to the detached engine.
- [ ] `claude daemon status` correctly displays engine type.
- [ ] Backward compatibility for old format session JSON (without engine field).
- [ ] zero errors with `tsc --noEmit`.
- [ ] `bun test` passes.
