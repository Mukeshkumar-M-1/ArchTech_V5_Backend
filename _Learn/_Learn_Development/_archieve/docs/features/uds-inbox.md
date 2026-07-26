# UDS_INBOX / Pipes — Local IPC and Multi-Instance Collaboration

## Overview

`UDS_INBOX` is no longer just an "empty flag" but a fully implemented set of local IPC (Inter-Process Communication) capabilities. It serves two distinct purposes that must be understood separately:

1.  **UDS Peer Messaging**
    - Targets any Claude Code process.
    - Utilizes `src/utils/udsMessaging.ts` and `src/utils/udsClient.ts`.
    - Exposed via the `/peers` command and the `uds:<socket-path>` scheme in `SendMessageTool`.
2.  **Pipes Control Plane**
    - Designed for master-slave collaboration between interactive REPL sessions.
    - Utilizes `src/utils/pipeTransport.ts`, `src/utils/pipeRegistry.ts`, and the inline bootstrap within `src/screens/REPL.tsx`.
    - Exposed via commands like `/pipes`, `/attach`, `/detach`, `/send`, `/pipe-status`, `/history`, and `/claim-main`.

While both layers rely on local sockets, their responsibilities differ: `/peers` focuses on "finding other sessions to send messages to," while `/pipes` focuses on "turning one REPL into a controlled worker for another."

## Why a Separate `pipes` Layer?

There are three practical reasons for maintaining a separate `pipes` layer:

1.  **Different Naming and Role Models**:
    - The UDS Peer layer uses `messagingSocketPath` for addressing.
    - The Pipes layer operates based on `cli-xxxxxxxx` session names, `main`/`sub`/`master`/`slave` roles, and a `machineId` registry.
2.  **Different Interaction Semantics**:
    - The Peer layer provides general message delivery.
    - The Pipes layer supports attachment/detachment, history collection, selective broadcasting, status bars, and REPL shortcuts.
3.  **Different UI Integration**:
    - The Peer layer primarily serves tool calls.
    - The Pipes layer directly influences the REPL submission path and the `PromptInput` footer.

Merging these two would cause general addressing in `SendMessageTool` and master-slave control in the REPL to conflict, leading to confusing command semantics.

## Current Communication Models

### 1. UDS Peer Messaging
- **Server**: `src/utils/udsMessaging.ts`.
- **Client**: `src/utils/udsClient.ts`.
- **Discovery**: Reads session files from `~/.claude/sessions/*.json`.
- **Addressing**: `uds:<socket-path>`.
- **Transport**: **Local Unix Socket / Windows Named Pipe**.
- This layer acts as the "General Inbox."

### 2. Pipes Control Plane
- **Server/Client**: `src/utils/pipeTransport.ts`.
- **Registry**: `src/utils/pipeRegistry.ts`.
- **Entry Point**: `src/screens/REPL.tsx`.
- **Discovery**: Scans `~/.claude/pipes/` and `registry.json`.
- **Session Name**: `cli-${sessionId.slice(0, 8)}`.
- **Transport**: **Local Unix Socket / Windows Named Pipe**.
- This layer acts as the "Master-Slave REPL Coordination Plane."

## Facts about "Local Network Communication"

The current implementation is **NOT** a true local network (LAN) transport.

While the following fields are recorded:
- `localIp`
- `hostname`
- `machineId`
- `mac`

They are currently used **only** for:
1. Registry display.
2. `main`/`sub` role determination.
3. Machine-level ownership switching in `/claim-main`.
4. Status output and troubleshooting information.

They are **NOT** used to establish TCP or WebSocket connections. All transport still occurs via the local socket path returned by `getPipePath(name)`.

Accurate descriptions are:
- `pipes` supports **Local Multi-Instance Collaboration**.
- `registry` contains **Machine Identity Metadata**.
- **Cross-machine LAN transport is NOT yet implemented.**

Implementing true LAN support would require:
1. TCP/WebSocket transport.
2. Authentication and session authorization.
3. Discovery and address exchange.
4. Handling timeouts, reconnection, and security boundaries.

## Current REPL Behavior

Current behavior is managed by the inline implementation in `src/screens/REPL.tsx`:
1. Creates a pipe server for the current REPL upon startup.
2. Determines the `main`/`sub` role via `pipeRegistry`.
3. Handles `attach_request`, `detach`, and `prompt` messages.
4. The main instance heartbeats and maintains its `slaves`.
5. `/pipes` toggles the status bar and manages the selection state.
6. Standard messages are broadcast **only** to **connected and selected** pipes.

**Recent Improvements**:
- Removed legacy un-wired hook solutions.
- Explicitly established the `REPL.tsx` inline bootstrap as the sole active implementation.
- Pipes that are selected but not connected no longer cause local processing to be incorrectly skipped.

## Documentation and Code Alignment

Future documentation regarding `UDS_INBOX` / `pipes` should follow these conventions:
1. Use terms like "Local IPC" or "Local Multi-Instance Collaboration."
2. Avoid describing `localIp`/`hostname` metadata as completed LAN transport.
3. Clearly distinguish the responsibilities of `/peers` and `/pipes`.
4. Treat `REPL.tsx`, `pipeTransport.ts`, and `pipeRegistry.ts` as the sources of truth.
