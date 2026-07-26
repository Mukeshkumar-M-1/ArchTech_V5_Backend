# Task 001: daemon status / stop

> Source: [stub-recovery-design-1-4.md](../features/stub-recovery-design-1-4.md) Item 1
> Priority: P0 (Preferred implementation item)
> Effort: Small
> Status: DONE

## Goal

Ensure `claude daemon status` and `claude daemon stop` work correctly from any CLI process, without depending on the TUI memory state.

## Background

- The `start` path already has a complete supervisor + worker lifecycle (`src/daemon/main.ts`, `src/daemon/workerRegistry.ts`).
- `status` / `stop` are currently only placeholder outputs (`src/daemon/main.ts:49`).
- `/remote-control-server` has its own in-command UI state but only maintains the `daemonProcess` within the current process, making it unsuitable for cross-process management.

## Implementation Plan

### New Files

| File | Description |
|------|------|
| `src/daemon/state.ts` | Daemon state file read/write module |

### Modified Files

| File | Change |
|------|------|
| `src/daemon/main.ts` | `start` writes to the state file; `status`/`stop` call the state module |
| `src/commands/remoteControlServer/remoteControlServer.tsx` | Reads the same state file (lightweight change) |

### State File

Path: `~/.claude/daemon/remote-control.json`

```json
{
  "pid": 12345,
  "cwd": "/path/to/project",
  "startedAt": "2026-04-12T10:00:00Z",
  "workerKinds": ["bridge", "rcs"],
  "lastStatus": "running"
}
```

### status Logic

1. Read the state file.
2. Use process detection to verify if the pid is alive.
3. Output `running` / `stopped` / `stale`.
4. Automatically clean up the state file when `stale`.

### stop Logic

1. Read the pid.
2. Send `SIGTERM`.
3. Wait for exit (with timeout fallback).
4. `SIGKILL` after timeout.
5. Clean up the state file.

## Verification Steps

- [ ] `claude daemon start` starts normally and writes to the state file.
- [ ] Executing `claude daemon status` in a new terminal displays `running`.
- [ ] Executing `claude daemon stop` exits the daemon normally.
- [ ] Executing `claude daemon status` again returns `stopped` or `stale cleaned`.
- [ ] Stop timeout fallback works correctly on Windows.

## Risks

- The signal model on Windows differs from Unix; `stop` requires a timeout fallback.
- Current design defaults to a single supervisor and does not handle multi-instance concurrency.

## Dependencies

No external dependencies; can be implemented independently.
