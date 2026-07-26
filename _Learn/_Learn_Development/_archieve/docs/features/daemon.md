# DAEMON — Background Daemon Process

> Feature Flag: `FEATURE_DAEMON=1`
> Implementation Status: Supervisor and remoteControl Worker are implemented.
> Reference Count: 3

## I. Feature Overview

`DAEMON` enables Claude Code to run as a background daemon process. A main process (supervisor) manages the lifecycles of multiple worker subprocesses, communicating via filesystem state files. This is ideal for persistent background services, such as providing remote control services in conjunction with `BRIDGE_MODE`.

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status |
| :--- | :--- | :--- |
| **Daemon Supervisor** | `src/daemon/main.ts` | **Implemented** — Supervisor includes subcommands, worker lifecycle management, and exponential backoff restarts. |
| **Worker Registry** | `src/daemon/workerRegistry.ts` | **Implemented** — remoteControl Worker (headless bridge). |
| **Daemon State** | `src/daemon/state.ts` | **Implemented** — PID/state file read, write, and query operations. |
| **CLI Routing** | `src/entrypoints/cli.tsx` | **Wired** — Handles `--daemon-worker` and `daemon` subcommands. |
| **Command Registration**| `src/commands.ts` | **Wired** — Gated by `DAEMON` + `BRIDGE_MODE`. |

### 2.2 CLI Entry Points

```bash
# Start the daemon
claude daemon start

# View status (default subcommand)
claude daemon status
claude daemon ps

# Stop the daemon
claude daemon stop

# Start as a worker (automatically called by the supervisor)
claude --daemon-worker=remoteControl

# Background session management
claude daemon bg
claude daemon attach <session>
claude daemon logs <session>
claude daemon kill <session>
```

### 2.3 Architecture

```
Supervisor (daemonMain)
      │
      ├── Worker: remoteControl
      │   └── runBridgeHeadless() — Remote control headless mode
      │       Receives remote sessions, processes messages, handles permission approvals.
      │
      ▼
Filesystem State File (daemon-state.json)
  - PID, CWD, start time, worker type.
  - queryDaemonStatus() / stopDaemonByPid()
```

### 2.4 Worker Lifecycle Management

The supervisor implements the following for each worker:
- **Exponential Backoff Restart**: Initial 2s, cap at 120s, multiplier of ×2.
- **Fast Failure Detection**: Parking (stopping restarts) if the process crashes 5 times within 10 seconds.
- **Permanent Error Exit Codes**: Exit code 78 (`EXIT_CODE_PERMANENT`) triggers immediate parking.
- **Graceful Shutdown**: `SIGTERM`/`SIGINT` triggers an abort signal, with a 30s timeout followed by a forced `SIGKILL`.

### 2.5 Relationship with BRIDGE_MODE

`DAEMON` and `BRIDGE_MODE` are frequently used together:

```ts
// src/commands.ts
if (feature('DAEMON') && feature('BRIDGE_MODE')) {
  // Load remoteControlServer command
}
```

This dual-gating ensures that both features must be enabled to use the remote control server.

## III. Key Design Decisions

1.  **Multi-Process Architecture**: One supervisor managing multiple workers with process isolation.
2.  **Filesystem State Communication**: State is shared via a `daemon-state.json` file (rather than Unix domain sockets).
3.  **Tight Integration with BRIDGE_MODE**: The most common use case for the daemon is providing remote control services.
4.  **CLI Subcommand Routing**: Both the `daemon` subcommand and the `--daemon-worker` parameter are routed within `cli.tsx`.
5.  **Worker Environment Variables**: The supervisor passes configurations to workers via environment variables (prefixed with `DAEMON_WORKER_*`).

## IV. Usage

```bash
# Enable daemon mode
FEATURE_DAEMON=1 FEATURE_BRIDGE_MODE=1 bun run dev

# Start the daemon
claude daemon start

# Check status
claude daemon status

# Stop the daemon
claude daemon stop

# Start as a specific worker (typically called automatically by the supervisor)
claude --daemon-worker=remoteControl
```

## V. File Index

| File | Responsibility |
| :--- | :--- |
| `src/daemon/main.ts` | Daemon Supervisor: Subcommand dispatch, worker lifecycle management, backoff restarts. |
| `src/daemon/workerRegistry.ts` | Worker Entry Points: Implementation of the remoteControl worker. |
| `src/daemon/state.ts` | Daemon State Management: PID file operations and status queries. |
| `src/entrypoints/cli.tsx` | CLI Routing logic. |
| `src/commands.ts` | Command registration (dual-gating). |
```
