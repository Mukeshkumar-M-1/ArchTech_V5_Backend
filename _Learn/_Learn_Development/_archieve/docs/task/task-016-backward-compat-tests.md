# Task 016: Backward Compatibility + Testing

> Design Doc: [daemon-restructure-design.md](../features/daemon-restructure-design.md) § V
> Dependency: Task 014, Task 015
> Branch: `feat/integrate-5-branches`

## Goal

Ensure backward compatibility for old commands (deprecation warning + normal proxying), and write tests for the restructured command architecture.

## File List

### New

| File | Description |
|------|------|
| `src/daemon/__tests__/daemonMain.test.ts` | Tests for daemonMain subcommand routing |
| `src/cli/bg/__tests__/engine.test.ts` | Tests for BgEngine selection logic |
| `src/cli/bg/__tests__/detached.test.ts` | Tests for DetachedEngine start/stop |
| `src/cli/bg/__tests__/tail.test.ts` | Tests for log tail functionality |

### Modified

| File | Change |
|------|------|
| `src/entrypoints/cli.tsx` | Confirm correct proxying for deprecation paths |

## Implementation Plan

### 1. Backward Compatibility Matrix

| Old Command | New Command | Handling |
|--------|--------|---------|
| `claude ps` | `claude daemon status` | Output `[deprecated] Use: claude daemon status` to stderr, then execute |
| `claude logs <x>` | `claude daemon logs <x>` | Same as above |
| `claude attach <x>` | `claude daemon attach <x>` | Same as above |
| `claude kill <x>` | `claude daemon kill <x>` | Same as above |
| `claude --bg` | `claude daemon bg` | Retain as a shortcut; **do not** deprecate (too commonly used) |
| `claude new <t>` | `claude job new <t>` | stderr deprecation + execute |
| `claude list` | `claude job list` | stderr deprecation + execute |
| `claude reply <id>` | `claude job reply <id>` | stderr deprecation + execute |

**Key**: Output deprecation to stderr rather than stdout so it doesn't affect script piping.

### 2. Testing Plan

#### 2.1 daemonMain Routing Tests

```typescript
describe('daemonMain', () => {
  test('default to status with no parameters', async () => { ... })
  test('start calls runSupervisor', async () => { ... })
  test('stop calls handleDaemonStop', async () => { ... })
  test('bg delegates to bg.handleBgStart', async () => { ... })
  test('attach delegates to bg.attachHandler', async () => { ... })
  test('logs delegates to bg.logsHandler', async () => { ... })
  test('kill delegates to bg.killHandler', async () => { ... })
  test('unknown subcommand sets exitCode=1', async () => { ... })
})
```

#### 2.2 Engine Selection Tests

```typescript
describe('selectEngine', () => {
  test('win32 returns DetachedEngine', async () => { ... })
  test('darwin + tmux available returns TmuxEngine', async () => { ... })
  test('darwin + tmux unavailable returns DetachedEngine', async () => { ... })
  test('linux + tmux available returns TmuxEngine', async () => { ... })
})
```

#### 2.3 DetachedEngine Tests

```typescript
describe('DetachedEngine', () => {
  test('available always returns true', async () => { ... })
  test('start creates detached sub-process and writes to log', async () => { ... })
  test('PID file returned by start exists', async () => { ... })
})
```

#### 2.4 Tail Tests

```typescript
describe('tailLog', () => {
  test('output existing log content', async () => { ... })
  test('output in real-time when content is appended', async () => { ... })
  test('SIGINT exits tail', async () => { ... })
})
```

### 3. Integrated Verification Script

Optional: Add a manual verification script under `scripts/`:

```bash
#!/bin/bash
# scripts/verify-daemon-restructure.sh
echo "=== 1. claude daemon status ==="
bun run dev -- daemon status

echo "=== 2. claude daemon bg (should start) ==="
bun run dev -- daemon bg --help

echo "=== 3. claude ps (deprecated) ==="
bun run dev -- ps 2>&1 | head -1

echo "=== 4. claude job list ==="
bun run dev -- job list

echo "=== 5. claude list (deprecated) ==="
bun run dev -- list 2>&1 | head -1
```

## Verification Checklist

- [ ] All old commands work normally (with only one extra stderr warning line).
- [ ] `--bg` remains warning-free.
- [ ] All new tests pass.
- [ ] No regressions in existing 2695 tests.
- [ ] zero errors with `tsc --noEmit`.
- [ ] Manually verify critical paths on Windows + macOS/Linux.
