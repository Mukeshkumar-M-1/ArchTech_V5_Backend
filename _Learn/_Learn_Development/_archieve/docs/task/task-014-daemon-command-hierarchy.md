# Task 014: /daemon Command Hierarchization

> Design Doc: [daemon-restructure-design.md](../features/daemon-restructure-design.md) § III.1
> Dependency: Task 013 (BgEngine Abstraction)
> Branch: `feat/integrate-5-branches`

## Goal

Consolidate scattered commands `daemon start/stop/status` + `ps/logs/attach/kill` + `--bg` into a unified `/daemon` namespace, implementing both CLI and REPL registration.

## Background

Currently, these commands are registered in two unrelated locations:
- `cli.tsx:203-212`: `daemon [start|status|stop]` → `daemon/main.ts`
- `cli.tsx:217-246`: `ps|logs|attach|kill|--bg` → `cli/bg.ts`

They need to be merged into a unified `claude daemon <subcommand>` entry point, and a new REPL `/daemon` slash command should be added.

## File List

### New

| File | Description |
|------|------|
| `src/commands/daemon/index.ts` | `/daemon` REPL slash command registration (type: local-jsx) |
| `src/commands/daemon/daemon.tsx` | `/daemon` subcommand routing + status UI component |

### Modified

| File | Change |
|------|------|
| `src/entrypoints/cli.tsx` | Unify daemon fast-path: Route `daemon <sub>` to corresponding handlers. Legacy commands `ps/logs/attach/kill` are retained but proxied after outputting a deprecation warning. |
| `src/commands.ts` | Register `/daemon` slash command (feature-gated: DAEMON \|\| BG_SESSIONS) |
| `src/daemon/main.ts` | `daemonMain()` extension: Support `bg/attach/logs/kill/ps` subcommands (delegated to bg.ts handlers). |

## Implementation Plan

### 1. Unified CLI Fast-path (`cli.tsx`)

**Before** (Two independent routes):
```typescript
// Part 1: daemon
if (feature('DAEMON') && args[0] === 'daemon') {
  await daemonMain(args.slice(1))
}
// Part 2: bg sessions
if (feature('BG_SESSIONS') && ['ps','logs','attach','kill'].includes(args[0])) {
  // ...switch/case
}
```

**After** (Unified entry point):
```typescript
// Unified daemon entry — Merging daemon supervisor + bg sessions
if (
  (feature('DAEMON') || feature('BG_SESSIONS')) &&
  args[0] === 'daemon'
) {
  profileCheckpoint('cli_daemon_path')
  const { enableConfigs } = await import('../utils/config.js')
  enableConfigs()
  const { initSinks } = await import('../utils/sinks.js')
  initSinks()
  const { daemonMain } = await import('../daemon/main.js')
  await daemonMain(args.slice(1))
  return
}

// --bg shortcut → daemon bg
if (
  feature('BG_SESSIONS') &&
  (args.includes('--bg') || args.includes('--background'))
) {
  profileCheckpoint('cli_daemon_path')
  const { enableConfigs } = await import('../utils/config.js')
  enableConfigs()
  const bg = await import('../cli/bg.js')
  await bg.handleBgStart(args.filter(a => a !== '--bg' && a !== '--background'))
  return
}

// Backward compatibility: ps/logs/attach/kill → daemon <sub> (deprecated)
if (
  feature('BG_SESSIONS') &&
  ['ps', 'logs', 'attach', 'kill'].includes(args[0] ?? '')
) {
  const mapped = args[0] === 'ps' ? 'status' : args[0]
  console.error(`[deprecated] Use: claude daemon ${mapped} ${args.slice(1).join(' ')}`.trim())
  const { enableConfigs } = await import('../utils/config.js')
  enableConfigs()
  const { daemonMain } = await import('../daemon/main.js')
  await daemonMain([args[0]!, ...args.slice(1)])
  return
}
```

### 2. daemonMain Extension (`daemon/main.ts`)

```typescript
export async function daemonMain(args: string[]): Promise<void> {
  const subcommand = args[0] || 'status'

  switch (subcommand) {
    // --- Supervisor Management ---
    case 'start':
      await runSupervisor(args.slice(1))
      break
    case 'stop':
      await handleDaemonStop()
      break

    // --- Session Management (Delegated to bg.ts) ---
    case 'status':
    case 'ps':
      await showUnifiedStatus()  // New: daemon status + session list
      break
    case 'bg':
      const bg = await import('../cli/bg.js')
      await bg.handleBgStart(args.slice(1))
      break
    case 'attach':
      const bg2 = await import('../cli/bg.js')
      await bg2.attachHandler(args[1])
      break
    case 'logs':
      const bg3 = await import('../cli/bg.js')
      await bg3.logsHandler(args[1])
      break
    case 'kill':
      const bg4 = await import('../cli/bg.js')
      await bg4.killHandler(args[1])
      break

    case '--help': case '-h': case 'help':
      printHelp()
      break
    default:
      console.error(`Unknown daemon subcommand: ${subcommand}`)
      printHelp()
      process.exitCode = 1
  }
}
```

### 3. Unified Status Panel (`showUnifiedStatus`)

```typescript
async function showUnifiedStatus(): Promise<void> {
  // 1. Daemon supervisor status
  const daemonResult = queryDaemonStatus()
  console.log('=== Daemon Supervisor ===')
  switch (daemonResult.status) {
    case 'running':
      console.log(`  Status: running (PID: ${daemonResult.state!.pid})`)
      console.log(`  Workers: ${daemonResult.state!.workerKinds.join(', ')}`)
      break
    case 'stopped':
      console.log('  Status: stopped')
      break
    case 'stale':
      console.log('  Status: stale (cleaned up)')
      break
  }

  // 2. Background session list
  console.log('\n=== Background Sessions ===')
  const bg = await import('../cli/bg.js')
  await bg.psHandler([])
}
```

### 4. REPL Slash Command Registration

**`src/commands/daemon/index.ts`**:
```typescript
import type { Command } from '../../commands.js'
import { feature } from 'bun:bundle'

const daemon = {
  type: 'local-jsx',
  name: 'daemon',
  description: 'Manage background sessions and daemon',
  argumentHint: '[status|start|stop|bg|attach|logs|kill]',
  isEnabled: () => {
    if (feature('DAEMON')) return true
    if (feature('BG_SESSIONS')) return true
    return false
  },
  load: () => import('./daemon.js'),
} satisfies Command

export default daemon
```

**`src/commands/daemon/daemon.tsx`**:
```typescript
export async function call(
  onDone: LocalJSXCommandOnDone,
  context: LocalJSXCommandContext,
  args: string,
): Promise<React.ReactNode> {
  const parts = args.trim().split(/\s+/)
  const sub = parts[0] || 'status'

  switch (sub) {
    case 'status':
    case 'ps':
      // Call showUnifiedStatus, capture output
      // Return text result
      break
    case 'bg':
      // Start background session in REPL
      break
    case 'start':
    case 'stop':
    case 'attach':
    case 'logs':
    case 'kill':
      // Delegate to corresponding handler
      break
    default:
      onDone(`Unknown: ${sub}. Use: status|start|stop|bg|attach|logs|kill`)
      return null
  }
}
```

**`src/commands.ts`** Add:
```typescript
// Conditional import
const daemonCmd =
  feature('DAEMON') || feature('BG_SESSIONS')
    ? require('./commands/daemon/index.js').default
    : null

// Add to COMMANDS array:
...(daemonCmd ? [daemonCmd] : []),
```

### 5. Update Help Text (`daemon/main.ts`)

```
Claude Code Daemon — background process management

USAGE
  claude daemon [subcommand]

SUBCOMMANDS
  status      Show daemon and session status (default)
  start       Start the daemon supervisor
  stop        Stop the daemon
  bg          Start a background session
  attach      Attach to a background session
  logs        Show session logs
  kill        Kill a session
  help        Show this help

REPL
  /daemon [subcommand]    Same commands available in interactive mode
```

## Verification Checklist

- [ ] `claude daemon` (no parameters) displays unified status panel.
- [ ] `claude daemon status` displays supervisor + session list.
- [ ] `claude daemon start/stop` behavior remains consistent.
- [ ] `claude daemon bg` starts background session (calls BgEngine).
- [ ] `claude daemon attach/logs/kill <target>` functions correctly.
- [ ] `claude ps` outputs deprecation warning + works correctly.
- [ ] `claude logs/attach/kill` same as above.
- [ ] `claude --bg` shortcut works normally.
- [ ] `/daemon` available in REPL, tab completion works.
- [ ] `/daemon status` displays status info in REPL.
- [ ] zero errors with `tsc --noEmit`.
- [ ] `bun test` passes.
