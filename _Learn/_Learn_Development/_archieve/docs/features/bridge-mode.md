# BRIDGE_MODE — Remote Control

> Feature Flag: `FEATURE_BRIDGE_MODE=1`
> Implementation Status: Fully functional (v1 + v2 implementations)
> Reference Count: 28

## I. Feature Overview

`BRIDGE_MODE` registers the local CLI as a "bridge environment" that can be driven remotely from claude.ai or other control planes. The local terminal becomes an "executor" that receives and executes remote instructions.

### Core Features

- **Environment Registration**: The local CLI registers with Anthropic servers as an available bridge environment.
- **Work Polling**: Long polling for remote task assignments.
- **Session Management**: Create, resume, and archive remote sessions.
- **Permission Passthrough**: Remote permission requests are sent to the control plane, where users can approve or deny them on claude.ai.
- **Heartbeat Maintenance**: Regularly sends heartbeats to extend task leases.
- **Trusted Devices**: v2 supports trusted device tokens for enhanced security.

## II. Implementation Architecture

### 2.1 Version Evolution

| Version | Implementation | Characteristics |
| :--- | :--- | :--- |
| v1 (env-based) | `src/bridge/replBridge.ts` | Traditional environment-variable-based bridge. |
| v2 (env-less) | `src/bridge/remoteBridgeCore.ts` | Safer bridge implementation that does not require environment variables. |

### 2.2 API Protocol

File: `src/bridge/bridgeApi.ts`

The Bridge API Client provides 9 core operations:

| Operation | HTTP | Description |
| :--- | :--- | :--- |
| `registerBridgeEnvironment` | POST `/v1/environments/bridge` | Registers the local environment and obtains `environment_id` + `environment_secret`. |
| `pollForWork` | GET `/v1/environments/{id}/work/poll` | Long polls for tasks (10s timeout). |
| `acknowledgeWork` | POST `/v1/environments/{id}/work/{workId}/ack` | Acknowledges receipt of a task. |
| `stopWork` | POST `/v1/environments/{id}/work/{workId}/stop` | Stops a task. |
| `heartbeatWork` | POST `/v1/environments/{id}/work/{workId}/heartbeat` | Renews a task lease. |
| `deregisterEnvironment` | DELETE `/v1/environments/bridge/{id}` | Deregisters the environment. |
| `archiveSession` | POST `/v1/sessions/{id}/archive` | Archives a session (409 = already archived, idempotent). |
| `sendPermissionResponseEvent` | POST `/v1/sessions/{id}/events` | Sends permission approval results. |
| `reconnectSession` | POST `/v1/environments/{id}/bridge/reconnect` | Reconnects to an existing session. |

### 2.3 Authentication Flow

```
Registration: OAuth Bearer Token → Obtains environment_secret
Polling: environment_secret used as Authorization header
  ├── 401 → Attempt OAuth token refresh (onAuth401)
  └── Successful refresh → Retry once
```

**OAuth Refresh**: The API client has a built-in `withOAuthRetry` mechanism. Upon a 401 error, it calls `handleOAuth401Error` (similar to the v1/messages mode in `withRetry.ts`) and retries once after refreshing.

### 2.4 Security Design

- **Path Traversal Protection**: `validateBridgeId()` uses an allowlist (`/^[a-zA-Z0-9_-]+$/`) to validate all server-side IDs.
- **BridgeFatalError**: Non-retryable errors (401/403/404/410) are thrown immediately to stop the retry loop.
- **Trusted Device Token**: v2 enhances security via the `X-Trusted-Device-Token` header.
- **Idempotent Registration**: Supports `reuseEnvironmentId` for session recovery, avoiding redundant environment creation.

### 2.5 Data Flow

```
claude.ai user selects a remote environment
         │
         ▼
POST /v1/environments/bridge (Registration)
         │
         ◀── environment_id + environment_secret
         │
         ▼
GET .../work/poll (Long Polling)
         │
         ◀── WorkResponse { id, data: { type, sessionId } }
         │
         ▼
POST .../work/{id}/ack (Acknowledgment)
         │
         ▼
sessionRunner creates REPL session
         │
         ├── Permission request → sendPermissionResponseEvent
         ├── Heartbeat → heartbeatWork (Renewal)
         └── Task completion → Automatic archiving
```

### 2.6 Module Structure

| Module | File | Responsibility |
| :--- | :--- | :--- |
| API Client | `bridgeApi.ts` | HTTP communication (registration/polling/ack/heartbeat/deregistration). |
| Session Runner | `sessionRunner.ts` | Creates/restores REPL sessions. |
| Bridge Config | `bridgeConfig.ts` | Configuration management (machine name, max sessions, etc.). |
| Transport | `replBridgeTransport.ts` | Bridge transport layer. |
| Permission Callbacks | `bridgePermissionCallbacks.ts` | Permission request handling. |
| Pointer | `bridgePointer.ts` | Pointer to the current active bridge state. |
| Flush Gate | `flushGate.ts` | Flush control. |
| JWT Utils | `jwtUtils.ts` | JWT token utilities. |
| Trusted Device | `trustedDevice.ts` | Trusted device management. |
| Debug Utils | `debugUtils.ts` | Debug logging. |
| Types | `types.ts` | Type definitions. |

## III. Key Design Decisions

1.  **Long Polling over WebSocket**: `pollForWork` uses HTTP GET with a 10s timeout. This is simple and reliable, avoiding the need to maintain a persistent WebSocket connection.
2.  **Embedded OAuth Refresh**: The API client includes its own `withOAuthRetry`, eliminating the need for external retry logic.
3.  **ETag Conditional Requests**: Registration supports `reuseEnvironmentId` for idempotent session recovery.
4.  **Coexistence of v1/v2**: Both implementations exist in the codebase, with v2 serving as a more secure upgrade.
5.  **Bidirectional Permission Flow**: Local permission requests are sent to claude.ai for user approval on the web interface.

## IV. Usage

```bash
# Enable bridge mode
FEATURE_BRIDGE_MODE=1 bun run dev

# Connect remotely from claude.ai/code
# Select the registered environment in the web interface

# Use in conjunction with DAEMON (background supervisor)
FEATURE_BRIDGE_MODE=1 FEATURE_DAEMON=1 bun run dev
```

## V. External Dependencies

| Dependency | Description |
| :--- | :--- |
| Anthropic OAuth | Login for claude.ai subscriptions. |
| GrowthBook | `tengu_ccr_bridge` feature gate. |
| Bridge API | Endpoints under `/v1/environments/bridge`. |

## VI. File Index

| File | Line Count | Responsibility |
| :--- | :--- | :--- |
| `src/bridge/bridgeApi.ts` | 541 | API Client (Core). |
| `src/bridge/sessionRunner.ts` | — | Session runner. |
| `src/bridge/bridgeConfig.ts` | — | Configuration management. |
| `src/bridge/replBridgeTransport.ts` | — | Transport layer. |
| `src/bridge/bridgePermissionCallbacks.ts` | — | Permission callbacks. |
| `src/bridge/bridgePointer.ts` | — | State pointer. |
| `src/bridge/flushGate.ts` | — | Flush control. |
| `src/bridge/jwtUtils.ts` | — | JWT utilities. |
| `src/bridge/trustedDevice.ts` | — | Trusted device management. |
| `src/bridge/remoteBridgeCore.ts` | — | v2 core implementation. |
| `src/bridge/types.ts` | — | Type definitions. |
| `src/bridge/debugUtils.ts` | — | Debugging tools. |
| `src/bridge/pollConfigDefaults.ts` | — | Default polling configurations. |
| `src/bridge/bridgeUI.ts` | — | UI components. |
| `src/bridge/codeSessionApi.ts` | — | Code session API. |
| `src/bridge/peerSessions.ts` | — | Peer session management. |
| `src/bridge/sessionIdCompat.ts` | — | Session ID compatibility layer. |
| `src/bridge/createSession.ts` | — | Session creation. |
| `src/bridge/replBridgeHandle.ts` | — | Bridge handle. |
