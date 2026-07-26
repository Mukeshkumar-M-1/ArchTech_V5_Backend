# Task 015: /job Command Hierarchization

> Design Doc: [daemon-restructure-design.md](../features/daemon-restructure-design.md) § III.2
> Dependency: None (can be parallelized with Task 013)
> Branch: `feat/integrate-5-branches`

## Goal

Consolidate `claude new/list/reply` into a unified `/job` namespace, implementing both CLI and REPL registration.

## Background

Currently, `new`, `list`, and `reply` are top-level CLI commands (`cli.tsx:250-261`), which easily conflict with other commands (especially common words like `list`). They need to be consolidated under `claude job <subcommand>`, and a new REPL `/job` entry point should be added.

## File List

### New

| File | Description |
|------|------|
| `src/commands/job/index.ts` | `/job` REPL slash command registration |
| `src/commands/job/job.tsx` | `/job` subcommand routing |

### Modified

| File | Change |
|------|------|
| `src/entrypoints/cli.tsx` | Add `job` fast-path + legacy `new/list/reply` deprecation proxy |
| `src/commands.ts` | Register `/job` slash command |

### No Change

| File | Description |
|------|------|
| `src/cli/handlers/templateJobs.ts` | Internal handler remains unchanged, only how it is called changes |
| `src/jobs/state.ts` | Job state management remains unchanged |
| `src/jobs/templates.ts` | Template discovery remains unchanged |
| `src/jobs/classifier.ts` | Task classifier remains unchanged |

## Implementation Plan

### 1. CLI Fast-path (`cli.tsx`)

**After Change**:
```typescript
// New: claude job <subcommand>
if (
  feature('TEMPLATES') &&
  args[0] === 'job'
) {
  profileCheckpoint('cli_templates_path')
  const { templatesMain } = await import('../cli/handlers/templateJobs.js')
  await templatesMain(args.slice(1))
  process.exit(0)
}

// Backward compatibility (deprecated)
if (
  feature('TEMPLATES') &&
  (args[0] === 'new' || args[0] === 'list' || args[0] === 'reply')
) {
  console.error(`[deprecated] Use: claude job ${args[0]} ${args.slice(1).join(' ')}`.trim())
  profileCheckpoint('cli_templates_path')
  const { templatesMain } = await import('../cli/handlers/templateJobs.js')
  await templatesMain(args)
  process.exit(0)
}
```

### 2. Add status subcommand to templateJobs.ts

In the existing `switch`, add:
```typescript
case 'status':
  handleStatus(args.slice(1))
  break
```

```typescript
function handleStatus(args: string[]): void {
  const jobId = args[0]
  if (!jobId) {
    console.error('Usage: claude job status <job-id>')
    process.exitCode = 1
    return
  }
  const state = readJobState(jobId)
  if (!state) {
    console.error(`Job not found: ${jobId}`)
    process.exitCode = 1
    return
  }
  console.log(`Job: ${state.jobId}`)
  console.log(`  Template: ${state.templateName}`)
  console.log(`  Status: ${state.status}`)
  console.log(`  Created: ${state.createdAt}`)
  console.log(`  Updated: ${state.updatedAt}`)
}
```

### 3. REPL Slash Command

**`src/commands/job/index.ts`**:
```typescript
import type { Command } from '../../commands.js'
import { feature } from 'bun:bundle'

const job = {
  type: 'local-jsx',
  name: 'job',
  description: 'Manage template jobs',
  argumentHint: '[list|new|reply|status]',
  isEnabled: () => {
    if (feature('TEMPLATES')) return true
    return false
  },
  load: () => import('./job.js'),
} satisfies Command

export default job
```

**`src/commands/job/job.tsx`**:
```typescript
export async function call(
  onDone: LocalJSXCommandOnDone,
  _context: LocalJSXCommandContext,
  args: string,
): Promise<React.ReactNode> {
  const parts = args.trim().split(/\s+/)
  const sub = parts[0] || 'list'

  // Delegate to templatesMain
  const { templatesMain } = await import('../../cli/handlers/templateJobs.js')

  // Capture console.log output to return to REPL as results
  const lines: string[] = []
  const origLog = console.log
  const origError = console.error
  console.log = (...a: unknown[]) => lines.push(a.join(' '))
  console.error = (...a: unknown[]) => lines.push(a.join(' '))

  try {
    await templatesMain([sub, ...parts.slice(1)])
  } finally {
    console.log = origLog
    console.error = origError
  }

  onDone(lines.join('\n') || 'Done.', { display: 'system' })
  return null
}
```

### 4. Registration in commands.ts

```typescript
const jobCmd = feature('TEMPLATES')
  ? require('./commands/job/index.js').default
  : null

// COMMANDS array:
...(jobCmd ? [jobCmd] : []),
```

## Verification Checklist

- [ ] `claude job list` lists templates.
- [ ] `claude job new <template>` creates task.
- [ ] `claude job reply <id> <text>` replies to task.
- [ ] `claude job status <id>` displays task status.
- [ ] `claude job` (no parameters) equivalent to `claude job list`.
- [ ] `claude new/list/reply` outputs deprecation warning + works correctly.
- [ ] `/job` available in REPL.
- [ ] `/job list` displays template list in REPL.
- [ ] zero errors with `tsc --noEmit`.
- [ ] `bun test` passes.
