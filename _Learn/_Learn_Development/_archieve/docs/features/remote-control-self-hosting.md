# Remote Control Server Self-Hosting Guide

This guide explains how to deploy the Remote Control Server (RCS) in a private environment and use it with the Claude Code CLI.

## Architecture Overview

```
┌──────────────────┐                    ┌──────────────────────┐
│  Claude Code CLI  │ ◄── HTTP/SSE/WS ─►│  Remote Control      │
│  (Bridge Worker)  │     Long-poll +   │  Server (RCS)        │
│                   │     Heartbeat     │                      │
└──────────────────┘                    │  ┌──────────────┐    │
                                        │  │ In-Memory    │    │
┌──────────────────┐   HTTP/SSE        │  │ Store        │    │
│  Web UI Panel     │ ◄─────────────── │  └──────────────┘    │
│  (/code/*)       │                   │  ┌──────────────┐    │
│  (React + Vite)  │                   │  │ JWT Auth     │    │
└──────────────────┘                   │  └──────────────┘    │
                                        │  ┌──────────────┐    │
┌──────────────────┐                   │  │ ACP Handler  │    │
│  acp-link        │ ◄── ACP Relay ─── │  └──────────────┘    │
│  + ACP Agent     │     WebSocket      │                      │
└──────────────────┘                    └──────────────────────┘
```

**RCS is a purely in-memory intermediary service** responsible for:
- Receiving environment registrations and work polling from the Claude Code CLI.
- Receiving ACP agent registrations from `acp-link`, supporting WebSocket relay bridging.
- Providing a Web UI for operators to remotely monitor and approve actions.
- Facilitating bidirectional message transmission via WebSocket/SSE.
- Managing sessions, environments, and permission requests.
- Providing an ACP SSE event stream for external consumers to subscribe to channel group events.

## Prerequisites

- A server accessible by both the Claude Code CLI and a web browser (physical machine, VM, or container).
- [Docker](https://www.docker.com/).
- A Claude Code build with the `BRIDGE_MODE` feature flag enabled.

## Deployment

### Build the Docker Image

Execute the following in the project root:

```bash
docker build -t rcs:latest -f packages/remote-control-server/Dockerfile .
```

### Start the Container

```bash
docker run -d \
  --name rcs \
  -p 3000:3000 \
  -e RCS_API_KEYS=sk-rcs-your-secret-key-here \
  -e RCS_BASE_URL=https://rcs.example.com \
  -v rcs-data:/app/data \
  --restart unless-stopped \
  rcs:latest
```

### Docker Compose

```yaml
version: "3.8"
services:
  rcs:
    build:
      context: .
      dockerfile: packages/remote-control-server/Dockerfile
      args:
        VERSION: "0.1.0"
    ports:
      - "3000:3000"
    environment:
      - RCS_API_KEYS=sk-rcs-your-secret-key-here
      - RCS_BASE_URL=https://rcs.example.com
    volumes:
      - rcs-data:/app/data
    restart: unless-stopped

volumes:
  rcs-data:
```

Start the service:

```bash
docker compose up -d
```

## Environment Variable Reference

### Server-Side

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `RCS_API_KEYS` | **Yes** | _(None)_ | Comma-separated list of API keys for client authentication and JWT signing. **Ensure strong keys are used.** |
| `RCS_PORT` | No | `3000` | Port the service listens on. |
| `RCS_HOST` | No | `0.0.0.0` | Address the service listens on. |
| `RCS_BASE_URL` | No | `http://localhost:3000` | External access URL. Used to generate WebSocket connection addresses; must match the actual URL accessed by clients. |
| `RCS_VERSION` | No | `0.1.0` | Version number returned in `/health` responses. |
| `RCS_POLL_TIMEOUT` | No | `8` | V1 work polling timeout (in seconds). |
| `RCS_HEARTBEAT_INTERVAL` | No | `20` | Heartbeat interval (in seconds). |
| `RCS_JWT_EXPIRES_IN` | No | `3600` | JWT token validity duration (in seconds). |
| `RCS_DISCONNECT_TIMEOUT` | No | `300` | Disconnect detection timeout (in seconds). |
| `RCS_WS_IDLE_TIMEOUT` | No | `30` | WebSocket idle timeout (in seconds); Bun sends protocol-level pings. |
| `RCS_WS_KEEPALIVE_INTERVAL`| No | `20` | Interval for keep-alive frames from server to client to prevent proxy disconnects. |

### Client-Side (Claude Code CLI)

| Variable | Required | Description |
| :--- | :--- | :--- |
| `CLAUDE_BRIDGE_BASE_URL` | **Yes** | RCS server address (e.g., `https://rcs.example.com`). Setting this enables self-hosted mode and skips GrowthBook gating. |
| `CLAUDE_BRIDGE_OAUTH_TOKEN` | **Yes** | Authentication token; must match one of the keys in `RCS_API_KEYS`. |
| `CLAUDE_BRIDGE_SESSION_INGRESS_URL` | No | WebSocket ingress address (defaults to `CLAUDE_BRIDGE_BASE_URL`). |
| `CLAUDE_CODE_REMOTE` | No | Set to `1` to mark as remote execution mode. |

## Claude Code Client Connection

### 1. Set Environment Variables

Set these on the machine running Claude Code:

```bash
export CLAUDE_BRIDGE_BASE_URL="https://rcs.example.com"
export CLAUDE_BRIDGE_OAUTH_TOKEN="sk-rcs-your-secret-key-here"
```

### 2. Start Claude Code

```bash
# Use dev mode (BRIDGE_MODE enabled by default)
bun run dev

# Or use the built product
bun run dist/cli.js
```

### 3. Execute `/remote-control`

In the Claude Code REPL, type:

```
/remote-control
```

Environment-style Remote Control (e.g., via the `claude remote-control` subcommand) will register the environment with RCS and display a connection URL in the terminal upon success:

```
https://rcs.example.com/code?bridge=<environmentId>
```

Interactive REPL mode (`--remote-control` or `/remote-control`) may also provide a session URL directly in certain bridge modes:

```
https://rcs.example.com/code/session_<id>
```

Both URLs allow for remote control via a browser. Environment-mode registrations will appear in the Web UI's environment list.

If already connected, running `/remote-control` again will show a dialog with the following options:
- **Disconnect this session**: Terminates the remote connection.
- **Show QR code**: Toggles the visibility of the QR code.
- **Continue**: Maintains the connection and continues use.

You can also start directly via the CLI:

```bash
claude remote-control
# Short-hand:
claude rc
# Or:
claude bridge
```

## Web UI Control Panel

Open the URL provided by the `/remote-control` command in your browser.

### Tech Stack (v2 Refactor, 2026-04-18)

The Web UI has been refactored from native JS to **React + Vite + Radix UI**:

- **Framework**: React 19 + Vite for builds, TypeScript.
- **UI Components**: Radix UI primitives (Dialog, Tabs, Select, Popover, etc.).
- **Chat Interface**: Full ACP chat interface supporting Plan visualization, tool call displays, and permission approvals.
- **AI Elements**: Independent AI interaction component library (message, reasoning, tool, code-block, prompt-input, etc.).
- **Direct ACP Access**: Support for automatic redirects to the ACP direct view (`ACPDirectView`) via QR code scans.
- **Theme System**: Dark/Light mode support following the Impeccable design system.

### Features

- View registered environments (Environment mode), distinguishing between ACP Agents and Claude Code.
- Create and manage sessions.
- Monitor conversation messages and tool calls in real-time.
- View Autopilot status (`standby` / `sleeping`) and autonomous run indicators.
- Access the Tasks panel driven by authoritative task snapshots.
- Approve tool permission requests from Claude Code.
- Permission mode selector (6 modes: Default, Auto-accept edits, Skip permissions, Planning, Never ask, Auto-determine).
- Model selector for available models.
- Plan visualization (progress bars, status icons, priority labels).
- ACP QR scanning for quick navigation to the ACP chat interface.

The Web UI uses UUID authentication (no user accounts required), making it suitable for trusted network environments.

## ACP Support

RCS supports ACP (Agent Client Protocol) agents connected via the `acp-link` package.

### Architecture

```
acp-link ──REST Registration──► RCS POST /v1/environments/bridge
acp-link ──WS Identify────────► RCS WebSocket (with agentId)
acp-link ◄──ACP Relay─────────► RCS ◄──Web UI WS──► Browser
```

### Backend Components

| File | Responsibility |
| :--- | :--- |
| `src/routes/acp/index.ts` | ACP REST routes: agent lists, channel groups, and relay. |
| `src/transport/acp-ws-handler.ts` | ACP WebSocket handling: registration, heartbeats, message forwarding. |
| `src/transport/acp-relay-handler.ts` | Frontend WS → `acp-link` transparent transmission + EventBus inbound forwarding. |
| `src/transport/acp-sse-writer.ts` | SSE event stream for external consumers. |

ACP agents, channel groups, relays, and channel-group SSE endpoints all require a valid API key. Note that browser `EventSource` cannot send `Authorization` headers; external subscriptions to `/acp/channel-groups/:id/events` should use `fetch` + `ReadableStream` with the `Authorization: Bearer <api-key>` header.

### acp-link Connection

See the [acp-link Documentation](./acp-link.md) for details.

```bash
# Start acp-link in the RCS environment
# Note: Claude itself does not support ACP; use ccb-bun --acp
ACP_RCS_URL=http://localhost:3000 \
ACP_RCS_TOKEN=sk-rcs-your-key \
acp-link ccb-bun -- --acp
```

ACP sessions are displayed in the Web UI with branded color tags to distinguish them from standard Claude Code sessions.

## Workflow Details

```
1. Claude Code CLI starts, environment variables point to self-hosted RCS.

2. User executes the /remote-control command.

3. Environment Registration:
   CLI ──POST /v1/environments/bridge──► RCS
   CLI ◄── { environment_id, environment_secret } ── RCS

4. Terminal displays connection URL:
   https://rcs.example.com/code?bridge=<environmentId>

5. Work Polling (Loop):
   CLI ──GET /v1/environments/:id/work/poll──► RCS
        (Long-polling for tasks; retries after 8s timeout)

6. URL opened in browser → Web UI creates session:
   Browser ──POST /web/sessions──► RCS
   RCS assigns work to the polling CLI.

7. CLI receives task and acknowledges:
   CLI ◄── { id, data: { type, sessionId } } ── RCS
   CLI ──POST /v1/environments/:id/work/:workId/ack──► RCS

8. Establish session connection:
   CLI ──WebSocket /v1/session_ingress──► RCS
        (Or uses V2 SSE + HTTP POST)

9. Bidirectional Communication:
   CLI ──Messages/Tool results──► RCS ──► Browser
   CLI ◄──Permissions/Directives── RCS ◄── Browser
   CLI ──automation_state/task_state──► RCS ──► Browser

10. Heartbeat (Every 20s):
    CLI ──POST /v1/environments/:id/work/:workId/heartbeat──► RCS

11. Task completion → Session archived → Environment deregistered.
```

## Troubleshooting

### Web UI Does Not Show Autopilot Status
- **`standby`**: Proactive mode is on; waiting for the next tick.
- **`sleeping`**: The model is in a `SleepTool` wait window.

These states are reported via worker `external_metadata.automation_state`. If the page only shows a standard working spinner, check if the worker metadata `PUT` between the CLI and RCS is successful.

### CLI Cannot Connect
```
Error: Remote Control is not available in this build.
```
- **Cause**: The `BRIDGE_MODE` feature flag is not enabled.
- **Solution**: Use dev mode (enabled by default) or ensure the build includes the `BRIDGE_MODE` flag.

### Authentication Failure (401)
```
Error: Unauthorized
```
- **Checks**:
    1. Does `CLAUDE_BRIDGE_OAUTH_TOKEN` match a value in `RCS_API_KEYS`?
    2. Does the API key contain extra spaces or newlines?
    3. Are both environment variables set correctly?

### WebSocket Interruptions
- **Checks**:
    1. If using a reverse proxy, ensure WebSocket upgrades (`Upgrade`/`Connection` headers) are configured.
    2. Ensure the proxy's `proxy_read_timeout` is sufficient (recommended: 86400s).
    3. Verify that network firewalls permit WebSocket traffic.

### Health Check
```bash
curl https://rcs.example.com/health
# Expected: {"status":"ok","version":"0.1.0"}
```

## Limitations and Considerations

| Item | Description |
| :--- | :--- |
| **Storage** | Purely in-memory (Map); all session and environment data is lost upon server restart. |
| **Scaling** | Does not support horizontal scaling (no shared state); deploy as a single instance. |
| **Concurrency**| Suitable for small to medium scale use; high volumes of concurrent sessions may require performance tuning. |
| **Persistence**| The `/app/data` volume is reserved but currently unused; intended for future persistence features. |
| **UI Auth** | Based on UUID; no account system; suitable for trusted networks. |

## Comparison: Cloud vs. Self-Hosted

| Feature | Cloud (Anthropic CCR) | Self-Hosted (RCS) |
| :--- | :--- | :--- |
| **Auth** | claude.ai OAuth subscription | API Key |
| **Gating** | Requires `tengu_ccr_bridge` | Bypassed automatically |
| **Flag** | Requires `BRIDGE_MODE=1` | Required |
| **Deployment** | Anthropic Cloud | User's own server |
| **Data Flow** | Anthropic infrastructure | User's private network |
| **Dependency** | claude.ai account + OAuth | API Key only |

The primary advantage of the self-hosted mode is that setting `CLAUDE_BRIDGE_BASE_URL` causes `isSelfHostedBridge()` to return `true`, bypassing all GrowthBook and subscription checks. This allows use without a `claude.ai` account.
