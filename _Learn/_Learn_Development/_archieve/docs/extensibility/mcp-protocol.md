---
title: "MCP Protocol - Connection Management, Tool Discovery, and Execution Pipeline"
description: "Analyzing Claude Code's MCP integration from a source code perspective: the difference between built-in and external MCPs, 7 transport layer implementations, memoize caching for connectToServer, LRU strategy for tool discovery, authentication state machines, and how MCP tools enter the permission check pipeline."
keywords:
  [
    "MCP",
    "Model Context Protocol",
    "Tool Extension",
    "MCP Client",
    "Tool Discovery",
    "Built-in MCP",
    "External MCP",
  ]
---

{/* Goal: Reveal the two operating modes (built-in/external) of the MCP client, connection management, tool discovery protocol, and execution pipeline from a source code perspective */}

## Architectural Overview: From Config to Available Tools

```
Configuration Layer (Multi-source Merging)
  ├── settings.json: { mcpServers: { "my-db": { command: "npx", args: [...] } } }   ← External
  ├── .mcp.json: Project-level MCP configuration                                      ← External
  ├── Plugin manifest (.mcp.json / .mcpb)                                             ← External (Plugin)
  ├── claude.ai connectors                                                            ← External (Remote)
  ├── Enterprise managed-mcp.json                                                     ← External (Enterprise Control)
  ├── setupComputerUseMCP() / setupClaudeInChrome()                                   ← Built-in (Dynamic Registration)
  └── SDK Input (type:'sdk')                                                          ← Built-in (IDE Embedded)
  ↓
getAllMcpConfigs()                    ← Enterprise exclusive OR merge user/project/local + plugin + claude.ai
  ↓
useManageMCPConnections()             ← React Hook managing connection lifecycle
  ↓
connectToServer(name, config)         ← Memoized cache (lodash memoize)
  ├── Logic: Built-in MCP → InProcessTransport (In-process)
  ├── Logic: External stdio → StdioClientTransport (Subprocess)
  ├── Logic: Remote SSE/HTTP/WS → Network transport
  └── Returns MCPServerConnection     ← { connected | failed | needs-auth | pending | disabled }
  ↓
fetchToolsForClient(client)           ← LRU(20) cache
  ├── client.request({ method: 'tools/list' })
  └── Each tool wrapped as an MCPTool  ← Unified Tool interface
  ↓
assembleToolPool()                    ← Merge built-in tools + MCP tools
  ↓
Tool name format: mcp__<serverName>__<toolName>  ← buildMcpToolName()
```

## Two MCP Modes: Built-in vs External

Claude Code's MCP implementation distinguishes between **built-in MCP servers** and **external MCP servers**. They use the same client protocol and tool discovery mechanism but differ completely in connection method, lifecycle management, and configuration source.

### Built-in MCP Servers

Built-in MCP servers are provided by Claude Code itself and do not require manual configuration by the user. They are automatically registered as `dynamic` scope configurations at startup and run within the same process.

| Server | Name | Package Path | Feature Flag | Activation Method |
| :--- | :--- | :--- | :--- | :--- |
| Computer Use | `computer-use` | `@ant/computer-use-mcp` | `CHICAGO_MCP` | GrowthBook gate + macOS + interactive |
| Claude in Chrome | `claude-in-chrome` | `@ant/claude-for-chrome-mcp` | — | `--chrome` parameter or `claudeInChromeDefaultEnabled` config |
| VSCode SDK | `claude-vscode` | — | — | IDE Embedded mode (type:`sdk`) |

#### InProcessTransport: Zero-Overhead In-Process Communication

Built-in servers run via `InProcessTransport` (`src/services/mcp/InProcessTransport.ts`) **without starting a subprocess**:

```typescript
// Create a pair of linked transports — messages pass directly between them
const [clientTransport, serverTransport] = createLinkedTransportPair()

// Server side connects to serverTransport
inProcessServer = createComputerUseMcpServerForCli()
await inProcessServer.connect(serverTransport)

// Client side uses clientTransport (same interface as external MCP clients)
transport = clientTransport
```

Core design of `InProcessTransport`:
- `send()` uses `queueMicrotask()` to asynchronously deliver messages to the peer, avoiding stack depth issues with synchronous request/responses.
- `close()` is bidirectional; closing either end triggers `onclose` callbacks on both ends.
- Zero network overhead, zero IPC serialization, and zero process startup time.

#### Dynamic Registration Flow

Built-in servers are registered during the startup flow in `main.tsx`, injecting into `dynamicMcpConfig`:

```typescript
// main.tsx: Computer Use MCP dynamic registration
if (feature("CHICAGO_MCP") && getPlatform() !== "unknown" && !getIsNonInteractiveSession()) {
  const { getChicagoEnabled } = await import("src/utils/computerUse/gates.js")
  if (getChicagoEnabled()) {
    const { setupComputerUseMCP } = await import("src/utils/computerUse/setup.js")
    const { mcpConfig, allowedTools } = setupComputerUseMCP()
    dynamicMcpConfig = { ...dynamicMcpConfig, ...mcpConfig }
    allowedTools.push(...cuTools)
  }
}
```

The configuration returned by `setupComputerUseMCP()` (`src/utils/computerUse/setup.ts`):

```typescript
{
  "computer-use": {
    type: "stdio",           // Type marked as stdio (but intercepted by client.ts as InProcessTransport)
    command: process.execPath,
    args: ["--computer-use-mcp"],
    scope: "dynamic",        // Dynamic scope, not persisted
  }
}
```

#### Interception at Connection Time

`connectToServer()` (in `src/services/mcp/client.ts`) intercepts built-in servers based on their name:

```typescript
// Chrome MCP — Runs in-process to avoid ~325MB subprocess overhead
if (isClaudeInChromeMCPServer(name)) {
  const { createChromeContext } = await import('../../utils/claudeInChrome/mcpServer.js')
  const { createClaudeForChromeMcpServer } = await import('@ant/claude-for-chrome-mcp')
  const { createLinkedTransportPair } = await import('./InProcessTransport.js')
  const context = createChromeContext(config.env)
  inProcessServer = createClaudeForChromeMcpServer(context)
  const [clientTransport, serverTransport] = createLinkedTransportPair()
  await inProcessServer.connect(serverTransport)
  transport = clientTransport
}

// Computer Use MCP — Similar logic
if (feature('CHICAGO_MCP') && isComputerUseMCPServer(name)) {
  const { createComputerUseMcpServerForCli } = await import('../../utils/computerUse/mcpServer.js')
  const { createLinkedTransportPair } = await import('./InProcessTransport.js')
  inProcessServer = await createComputerUseMcpServerForCli()
  const [clientTransport, serverTransport] = createLinkedTransportPair()
  await inProcessServer.connect(serverTransport)
  transport = clientTransport
}
```

#### Reserved Name Protection

The names of built-in servers are reserved; users cannot manually add configurations with the same name (`src/services/mcp/config.ts`):

```typescript
// Check for reserved names when adding MCP configuration
if (isClaudeInChromeMCPServer(name)) {
  throw new Error(`Cannot add MCP server "${name}": this name is reserved.`)
}
if (feature('CHICAGO_MCP') && isComputerUseMCPServer(name)) {
  throw new Error(`Cannot add MCP server "${name}": this name is reserved.`)
}
```

There is also a global check at startup (`main.tsx`): if a reserved name (not of `type:'sdk'`) is found in the user's configuration, the process exits with code 1.

#### VSCode SDK MCP

VSCode SDK MCP is a special built-in mode. IDEs (e.g., VS Code, JetBrains) start Claude Code in an embedded fashion and pass an MCP configuration of `type:'sdk'`. This type:
- Bypasses reserved name checks (IDEs can use any name).
- Is not subject to exclusive control by enterprise MCP.
- Connects via the VSCode SDK transport.
- Supports bidirectional notifications (e.g., `file_updated`, `experiment_gates`).

```typescript
// src/services/mcp/vscodeSdkMcp.ts
export function setupVscodeSdkMcp(sdkClients: MCPServerConnection[]): void {
  const client = sdkClients.find(client => client.name === 'claude-vscode')
  if (client && client.type === 'connected') {
    // Register log_event notification handler
    client.client.setNotificationHandler(LogEventNotificationSchema(), ...)
    // Send experiment gates to VSCode
    client.client.notification({ method: 'experiment_gates', params: { gates } })
  }
}
```

### External MCP Servers

External MCP servers are declared by users in configuration files and run via subprocesses or network connections.

#### Configuration Sources

| Source | Scope | File Location | Priority |
| :--- | :--- | :--- | :--- |
| Project Config | `project` | `<project>/.mcp.json` | Highest (overwrites same names) |
| Local Config | `local` | `<project>/.claude/settings.local.json` | High |
| User Config | `user` | `~/.claude/settings.json` | Medium |
| Plugins | `dynamic` | `.mcp.json` in manifest | Medium |
| claude.ai | `claudeai` | Fetched via API | Low |
| Enterprise Control | `enterprise` | `managed-mcp.json` | Exclusive (overwrites all if present) |

#### Configuration Example

```json
// MCP configuration in settings.json / .mcp.json
{
  "mcpServers": {
    // stdio type — Starts a subprocess
    "my-database": {
      "command": "npx",
      "args": ["@my-org/db-mcp-server"],
      "env": { "DB_URL": "postgres://..." }
    },

    // HTTP Stream type — Remote server
    "remote-api": {
      "type": "http",
      "url": "https://api.example.com/mcp"
    },

    // SSE type — Server-Sent Events
    "realtime-feed": {
      "type": "sse",
      "url": "https://feed.example.com/sse"
    },

    // WebSocket type
    "ws-service": {
      "type": "ws",
      "url": "wss://ws.example.com/mcp"
    }
  }
}
```

#### Merging and De-duplication

`getAllMcpConfigs()` (in `src/services/mcp/config.ts`) merges configurations from multiple sources by priority:

1.  If an enterprise control configuration exists, it is returned **exclusively** (ignoring all other sources).
2.  Otherwise, sources are merged: `user` → `project` → `local` → `plugin` → `claude.ai`.
3.  Plugin configurations are de-duplicated against manual ones via `getMcpServerSignature()` (based on command/args/url); plugin configurations are suppressed by manual ones of the same name.
4.  `addScopeToServers()` tags each configuration item with its source scope.

## 7 Transport Layer Implementations

`connectToServer()` (in `src/services/mcp/client.ts`) dispatches to different transport implementations based on `config.type`:

| Transport Type | Transport Class | Use Case | Authentication |
| :--- | :--- | :--- | :--- |
| `stdio` (default) | `StdioClientTransport` | External local subprocess | None |
| `sse` | `SSEClientTransport` | Remote SSE service | `ClaudeAuthProvider` + OAuth |
| `http` | `StreamableHTTPClientTransport` | HTTP Stream | `ClaudeAuthProvider` + OAuth |
| `sse-ide` | `SSEClientTransport` | IDE integration | Lockfile token |
| `ws-ide` | `WebSocketTransport` | IDE WebSocket | `X-Claude-Code-Ide-Authorization` |
| `ws` | `WebSocketTransport` | WebSocket service | Session ingress token |
| `claudeai-proxy` | `StreamableHTTPClientTransport` | claude.ai proxy | OAuth bearer + 401 retry |
| InProcess (Built-in) | `InProcessTransport` | Computer Use / Chrome | None (In-process) |

### Process Management for stdio Transport

`stdio` MCP servers run as subprocesses. Cleanup follows a **signal escalation strategy** (in `src/services/mcp/client.ts`):

```
SIGINT (100ms) → SIGTERM (400ms) → SIGKILL
```

Total cleanup time is capped at 600ms to prevent MCP servers from blocking CLI exit.

### Authentication State Machine for Remote Transports

SSE/HTTP types use `ClaudeAuthProvider` for OAuth authentication. If authentication fails, the server enters a `needs-auth` state and is written to a 15-minute TTL cache file (`mcp-needs-auth-cache.json`) to avoid repeated prompts.

```
Connection attempt → 401 Unauthorized
  ↓
handleRemoteAuthFailure()
  ├── logEvent('tengu_mcp_server_needs_auth')
  ├── setMcpAuthCacheEntry(name)         ← Write to 15min TTL cache
  └── return { type: 'needs-auth' }      ← UI displays authentication prompt
```

## Connection Caching and Reconnection Mechanism

`connectToServer` uses lodash `memoize` to cache connection objects, with a cache key of `${name}-${JSON.stringify(config)}`.

### Cache Invalidation

When a connection closes (`client.onclose`), all related caches are cleared:

```typescript
client.onclose = () => {
  const key = getServerCacheKey(name, serverRef)
  fetchToolsForClient.cache.delete(name)      // Tool cache
  fetchResourcesForClient.cache.delete(name)  // Resource cache
  fetchCommandsForClient.cache.delete(name)   // Command cache
  connectToServer.cache.delete(key)           // Connection cache
}
```

### Connection Degradation Detection

Remote transports use a **consecutive error counter**:

```typescript
let consecutiveConnectionErrors = 0
const MAX_ERRORS_BEFORE_RECONNECT = 3
```

After 3 consecutive terminal errors (ECONNRESET, ETIMEDOUT, EPIPE, etc.), the transport is actively closed to trigger a reconnection. For HTTP transport, session expiration (404 + JSON-RPC code -32001) is also detected.

### Request-level Timeout Protection

Each HTTP request uses an independent `setTimeout` timeout (`wrapFetchWithTimeout` in `src/services/mcp/client.ts`), rather than a shared `AbortSignal.timeout()`. This is because Bun's garbage collection for `AbortSignal.timeout` is lazy—consuming ~2.4KB of native memory per request, which is only reclaimed after 60s even if the request finishes in milliseconds.

```typescript
const controller = new AbortController()
const timer = setTimeout(c => c.abort(...), MCP_REQUEST_TIMEOUT_MS, controller)
timer.unref?.()  // Does not block process exit
```

## Tool Discovery: From MCP to Tool Interface

`fetchToolsForClient()` (in `src/services/mcp/client.ts`) uses a `memoizeWithLRU` cache (cap of 100) and converts MCP tools into Claude Code's unified `Tool` interface:

```typescript
const fullyQualifiedName = buildMcpToolName(client.name, tool.name)
// Result: "mcp__my-database__query"
```

### Tool Discovery for Built-in MCPs

Although built-in MCP servers use `InProcessTransport`, their tool discovery process is identical to that of external servers:

- **Computer Use**: `createComputerUseMcpServerForCli()` (in `src/utils/computerUse/mcpServer.ts`) constructs an MCP Server object and registers a `ListToolsRequestSchema` handler. The tool description includes a platform-specific list of installed applications (enumerated with a 1s timeout).
- **Claude in Chrome**: `createClaudeForChromeMcpServer()` (in the `@ant/claude-for-chrome-mcp` package) provides 17+ browser control tools.
- **VSCode SDK**: The IDE side provides the tool list via the SDK transport.

### Tool Description Truncation

MCP tool descriptions are capped at 2048 characters (`MAX_MCP_DESCRIPTION_LENGTH`). Some OpenAPI-generated MCP servers have been observed to have descriptions of 15-60KB.

### Tool Capability Annotation

Each MCP tool is automatically annotated based on `tool.annotations`:

| Annotation | Maps to | Meaning |
| :--- | :--- | :--- |
| `readOnlyHint` | `isReadOnly()` + `isConcurrencySafe()` | Read-only, safe for parallel execution |
| `destructiveHint` | `isDestructive()` | Destructive operation |
| `openWorldHint` | `isOpenWorld()` | Open world (not enumerable) |
| `title` | `userFacingName()` | Display name |

### Permission Checks for MCP Tools

MCP tools default to returning `{ behavior: 'passthrough' }`, meaning they always enter the permission confirmation flow. Tool names use the `mcp__` prefix for precise matching against permission rules.

Built-in MCP server tools are automatically authorized via the `allowedTools` list added at startup in `main.tsx`, bypassing normal permission prompts. For example, the `request_access` tool for Computer Use handles its own session-level approvals.

## Execution Pipeline of MCP Tools

```
AI generates tool_use: { name: "mcp__my-db__query", input: { sql: "..." } }
  ↓
MCPTool.call()                               ← src/services/mcp/client.ts:1835
  ├── ensureConnectedClient()                ← Ensures connection is valid (reconnects if needed)
  ├── callMCPToolWithUrlElicitationRetry()   ← Retry with Elicitation
  │   ├── client.request({ method: 'tools/call' })
  │   ├── Handle image results (resize + persist)
  │   └── Content truncation (mcpContentNeedsTruncation)
  ├── McpSessionExpiredError → Retry once
  └── Returns { data: content, mcpMeta }
```

### Auto-retry on Session Expiration

MCP sessions for HTTP transport may expire. If an `McpSessionExpiredError` is detected, the system retries once because `ensureConnectedClient()` has already cleared the cache and established a new connection.

### Content Truncation and Persistence

Large MCP tool outputs are truncated via `truncateMcpContentIfNeeded`. Binary content (images) is written to files via `persistBinaryContent`, and the file paths are returned. Images are automatically resized via `maybeResizeAndDownsampleImageBuffer`.

## Concurrency Control for MCP Connections

```typescript
// Local server concurrent connection batch size
getMcpServerConnectionBatchSize()    // Default is 3

// Remote server concurrent connection batch size
getRemoteMcpServerConnectionBatchSize()  // Default is 20
```

Local MCP servers (stdio) are heavy subprocesses, so they are limited to 3 concurrent connections by default. Remote servers are lightweight HTTP requests, allowing for 20 concurrent connections.

## Summary: Built-in vs External MCP

| Dimension | Built-in MCP | External MCP |
| :--- | :--- | :--- |
| **Transport** | `InProcessTransport` (In-process) | stdio / SSE / HTTP / WebSocket |
| **Config Source** | Dynamic registration (Computer Use, etc.) | settings.json / .mcp.json / Plugins / claude.ai |
| **Scope** | `dynamic` | `user` / `project` / `local` / `enterprise` / `claudeai` |
| **Process Model** | In-process, zero overhead | Subprocess (stdio) or network connection |
| **Name Protection** | Reserved names; cannot be added by user | Freely named (alphanumeric + `-_`) |
| **Lifecycle** | Follows CLI startup/shutdown | Connection cache + on-demand reconnection |
| **Permissions** | `allowedTools` auto-authorization | `passthrough` to permission confirmation |
| **Feature Flag** | `CHICAGO_MCP` (Computer Use), etc. | None (always available) |
| **Tool Discovery** | Same as external (MCP protocol) | Standard MCP `tools/list` |
| **Cleanup** | `inProcessServer.close()` | Signal escalation: SIGINT→SIGTERM→SIGKILL |

## Key Source File Index

| File | Responsibility |
| :--- | :--- |
| `src/services/mcp/client.ts` | Core client: connectToServer, fetchToolsForClient, MCPTool.call |
| `src/services/mcp/config.ts` | Config management: getAllMcpConfigs, addMcpConfig, removeMcpConfig |
| `src/services/mcp/types.ts` | Type definitions: Config Schema, connection status types |
| `src/services/mcp/InProcessTransport.ts` | Built-in MCP transport layer: linked transport pair |
| `src/services/mcp/vscodeSdkMcp.ts` | VSCode SDK MCP: Bidirectional notifications, experiment gates |
| `src/services/mcp/useManageMCPConnections.ts` | React Hook: Connection lifecycle, reconnection |
| `src/utils/computerUse/mcpServer.ts` | Computer Use MCP Server construction |
| `src/utils/computerUse/setup.ts` | Dynamic registration of Computer Use |
| `src/utils/claudeInChrome/mcpServer.ts` | Chrome MCP Server construction + Bridge configuration |
| `src/tools/MCPTool/MCPTool.ts` | MCP tool wrapper: Unified Tool interface |
| `src/entrypoints/mcp.ts` | MCP server entry (Claude Code as MCP server) |
