---
title: "MCP Configuration - Multi-source Merging, Scopes, and Policy Control"
description: "Detailed explanation of Claude Code MCP configuration sources, merging priority, transport types, enterprise policy control, plugin integration, and reserved name mechanisms."
keywords: ["MCP", "Configuration", "settings.json", ".mcp.json", "Enterprise Policy", "Plugin"]
---

## Configuration Sources and Scopes

Claude Code's MCP configurations come from multiple sources, each corresponding to a `scope`. Configurations are merged based on priority, with higher-priority sources overwriting configurations with the same name from lower-priority ones.

### Source List

| Source | Scope | File/Interface | Description |
| :--- | :--- | :--- | :--- |
| Enterprise Control | `enterprise` | `managed-mcp.json` | **Exclusive Mode**: Ignores all other sources if present. |
| Local Project | `local` | `<project>/.claude/settings.local.json` | Project-level private config (not committed to VCS). |
| Project Config | `project` | `<project>/.mcp.json` | Project-level shared config (can be committed to VCS). |
| User Global | `user` | `~/.claude/settings.json` | User-level config, shared across all projects. |
| Plugins | `dynamic` | `.mcp.json` / `.mcpb` in manifest | MCP servers provided by plugins. |
| claude.ai | `claudeai` | Fetched via API | Connectors configured on the claude.ai web interface. |
| Built-in Dynamic | `dynamic` | Registered in code | Built-in servers like Computer Use / Chrome. |
| IDE SDK | `sdk` | Passed by IDE | Embedded mode for VS Code / JetBrains. |

### Merging Priority (Lowest to Highest)

```
claude.ai Connectors        ← Lowest priority
    ↓ De-duplication
Plugin Servers
    ↓ De-duplication
User Global Configuration
    ↓
Project Configuration (.mcp.json)    ← Requires user approval
    ↓
Local Project Configuration
    ↓
Dynamic Configuration (Built-in MCP) ← Highest priority
```

Merging is implemented using `Object.assign({}, dedupedPluginServers, userServers, approvedProjectServers, localServers)`—later keys overwrite earlier ones with the same name.

## Enterprise Control Mode

When the `managed-mcp.json` file exists, the system enters **Exclusive Mode**:

```typescript
// config.ts:1084
if (doesEnterpriseMcpConfigExist()) {
  // Only returns the enterprise configuration, ignoring all user/project/plugin/claude.ai configurations
  return { servers: filtered, errors: [] }
}
```

Features:
- Path is determined by system management (`getManagedFilePath()` + `managed-mcp.json`).
- Overwrites all user-level, project-level, plugin, and claude.ai configurations.
- Policy filtering (allowlist/denylist) still applies.
- New servers cannot be added via the CLI (`addMcpConfig` will reject the request).

## Transport Types and Configuration Schema

### stdio (Default)

Starts a subprocess and communicates via stdin/stdout using JSON-RPC.

```json
{
  "my-server": {
    "command": "npx",
    "args": ["-y", "@my-org/mcp-server"],
    "env": { "API_KEY": "..." }
  }
}
```

The `type` field can be omitted (defaults to `stdio`). Environment variables are passed to the subprocess via `env` and merged with the current process environment.

**Windows Note**: Using `npx` requires wrapping it as `cmd /c npx`; otherwise, it will error.

### SSE (Server-Sent Events)

Connects to a remote MCP server via HTTP SSE.

```json
{
  "my-remote": {
    "type": "sse",
    "url": "https://mcp.example.com/sse",
    "headers": { "Authorization": "Bearer ..." },
    "oauth": {
      "clientId": "...",
      "authServerMetadataUrl": "https://auth.example.com/.well-known/oauth-authorization-server"
    }
  }
}
```

Supports OAuth authentication flows. If authentication fails, the server enters a `needs-auth` state, with a 15-minute TTL cache to avoid repeated prompts.

### HTTP (Streamable HTTP)

HTTP streaming transport.

```json
{
  "my-http": {
    "type": "http",
    "url": "https://mcp.example.com/mcp",
    "headers": { "X-API-Key": "..." }
  }
}
```

Supports the same OAuth configuration as SSE.

### WebSocket

```json
{
  "my-ws": {
    "type": "ws",
    "url": "wss://mcp.example.com/ws"
  }
}
```

### IDE-Specific Types (Internal)

`sse-ide` and `ws-ide` are dedicated types for IDE extensions and are not configured directly by users.

- `sse-ide`: Authenticated using a lockfile token.
- `ws-ide`: Authenticated using the `X-Claude-Code-Ide-Authorization` header.

### SDK Type (Internal)

`type: "sdk"` is passed via IDE embedded mode and bypasses reserved name checks and enterprise control exclusion limits.

### claude.ai Proxy Type (Internal)

`type: "claudeai-proxy"` is used by connectors configured on the claude.ai web interface, authenticated via an OAuth bearer token and supporting 401 retries.

## Configuration Operations

### Adding an MCP Server

Use the CLI command `claude mcp add` or the API call `addMcpConfig()`:

```bash
# Add to user configuration
claude mcp add my-server -s user -- npx @my-org/mcp-server

# Add to project configuration
claude mcp add my-server -s project -- npx @my-org/mcp-server

# Add HTTP type
claude mcp add my-remote -s user -t http -u https://mcp.example.com/mcp
```

Validation flow during addition:

1.  **Name Validation**: Only letters, numbers, hyphens, and underscores are allowed.
2.  **Reserved Name Check**: `claude-in-chrome` and `computer-use` are reserved.
3.  **Enterprise Control Check**: Additions are rejected in enterprise mode.
4.  **Schema Validation**: Zod validates the configuration format.
5.  **Policy Check**: Rejected by denylist, validated by allowlist.

### Removing an MCP Server

```bash
claude mcp remove my-server -s user
```

### Listing MCP Servers

```bash
claude mcp list
```

## Project Configuration Approval

Project configurations in `.mcp.json` require explicit user approval to take effect:

```typescript
// config.ts:1166
const approvedProjectServers: Record<string, ScopedMcpServerConfig> = {}
for (const [name, config] of Object.entries(projectServers)) {
  if (getProjectMcpServerStatus(name) === 'approved') {
    approvedProjectServers[name] = config
  }
}
```

When a project is first opened, Claude Code prompts the user to approve each server in `.mcp.json`. Approval status is persisted in the local configuration.

## Plugin MCP Integration

Plugins declare MCP servers via `.mcp.json` or `.mcpb` files in their manifest:

```typescript
// Plugin MCP loading flow
const pluginResult = await loadAllPluginsCacheOnly()
const pluginServerResults = await Promise.all(
  pluginResult.enabled.map(plugin => getPluginMcpServers(plugin, mcpErrors))
)
```

### Plugin Namespace

Plugin MCP server names follow the format `plugin:<pluginName>:<serverName>` to avoid conflicts with manual configurations.

### De-duplication Mechanism

Plugin servers are de-duplicated via content signatures (`dedupPluginMcpServers`):

- **stdio Type**: Signature = `stdio:` + JSON.stringify([command, ...args])
- **URL Type**: Signature = `url:` + original URL (unwrapped CCR proxy URL)
- **sdk Type**: Signature is null; no de-duplication.

De-duplication rules:
1.  Manual configuration takes precedence over plugin configuration.
2.  Plugins loaded earlier take precedence over those loaded later.
3.  Suppressed plugin servers display a hint in the `/plugin` UI.

### claude.ai Connector De-duplication

claude.ai connectors use the same content signature mechanism for de-duplication (`dedupClaudeAiMcpServers`):
- Only enabled manual configurations participate in de-duplication (disabled manual configs should not suppress connectors).
- Connector names follow the format `claude.ai <DisplayName>`.

## Policy Control

### Allowlist / Denylist

Enterprise policies control available MCP servers via allowlists and denylists:

```typescript
// config.ts:1243 - Final policy filtering
for (const [name, serverConfig] of Object.entries(configs)) {
  if (!isMcpServerAllowedByPolicy(name, serverConfig)) {
    continue  // Skip servers prohibited by policy
  }
  filtered[name] = serverConfig
}
```

Policy checks consider:
- Server name matching.
- `command` + `args` matching for `stdio` types.
- URL pattern matching for URL types (supports wildcards).

### Plugin-only Mode

When `isRestrictedToPluginOnly('mcp')` is enabled, only MCP servers provided by plugins are allowed—user/project-level configurations are ignored.

## Environment Variable Expansion

Environment variables in MCP configurations support expansion using `$VAR` and `${VAR}` syntax:

```json
{
  "my-server": {
    "command": "npx",
    "args": ["@my-org/mcp-server"],
    "env": {
      "API_KEY": "$MY_API_KEY",
      "DB_URL": "${DATABASE_URL}"
    }
  }
}
```

Missing variables generate warnings during expansion but do not prevent the configuration from loading.

## Dynamic Registration of Built-in MCPs

Built-in MCP server configurations are dynamically injected during the `main.tsx` startup flow:

### Computer Use MCP

```typescript
// src/utils/computerUse/setup.ts
export function setupComputerUseMCP(): {
  mcpConfig: Record<string, ScopedMcpServerConfig>
  allowedTools: string[]
} {
  return {
    mcpConfig: {
      "computer-use": {
        type: "stdio",
        command: process.execPath,
        args: ["--computer-use-mcp"],
        scope: "dynamic",
      }
    },
    allowedTools: ["mcp__computer-use__screenshot", ...]
  }
}
```

Enabling conditions:
- Feature flag `CHICAGO_MCP` is on.
- `getPlatform() !== "unknown"` (macOS/Windows/Linux).
- Not a non-interactive session.
- GrowthBook gate `getChicagoEnabled()` returns true.

### Claude in Chrome MCP

```typescript
// Similar to Computer Use, registered in main.tsx
const { mcpConfig, allowedTools, systemPrompt } = setupClaudeInChrome()
dynamicMcpConfig = { ...dynamicMcpConfig, ...mcpConfig }
```

Enabling conditions:
- `--chrome` parameter or `claudeInChromeDefaultEnabled` configuration.
- Chrome extension is installed.

### VSCode SDK MCP

IDE embedded mode passes a configuration with `type: 'sdk'` via an initialization message, with `setupVscodeSdkMcp()` setting up bidirectional notifications.

## Reserved Names

The following MCP server names are reserved and cannot be configured manually by users:

| Name | Purpose | Check Condition |
| :--- | :--- | :--- |
| `claude-in-chrome` | Chrome browser control | Always checked |
| `computer-use` | Desktop automation | Checked when `CHICAGO_MCP` feature flag is on |
| `claude-vscode` | VSCode IDE integration | Passed by SDK, bypasses name check |

Reserved name checks occur in two places:
1.  `addMcpConfig()` (`config.ts:636-648`) — Runtime rejection.
2.  `main.tsx` startup check (`main.tsx:2351-2368`) — Exits on startup.

## Key Source File Index

| File | Responsibility |
| :--- | :--- |
| `src/services/mcp/config.ts` | Configuration management core: merging, de-duplication, policies, adding/deleting. |
| `src/services/mcp/types.ts` | Zod Schema definitions, type declarations. |
| `src/services/mcp/client.ts` | Connection management, transport layer selection. |
| `src/utils/plugins/mcpPluginIntegration.ts` | Loading plugin MCP configurations. |
| `src/utils/computerUse/setup.ts` | Dynamic registration of Computer Use. |
| `src/utils/claudeInChrome/common.ts` | Chrome MCP reserved names and tool names. |
| `src/services/mcp/vscodeSdkMcp.ts` | VSCode SDK bidirectional notifications. |
