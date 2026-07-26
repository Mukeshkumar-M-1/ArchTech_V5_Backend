# MCP_SKILLS — MCP Skill Discovery

> Feature Flag: `FEATURE_MCP_SKILLS=1`
> Implementation Status: Functional implementation (config gating and filters are complete; core fetcher is a stub).
> Reference Count: 9

## I. Feature Overview

`MCP_SKILLS` discovers resources exposed by MCP servers (via the `skill://` URI scheme) and converts them into callable skill commands. MCP servers can simultaneously provide tools, prompts, and resources; when this feature is enabled, resources with a `skill://` URI are identified as skills.

### Core Features

- **Automatic Discovery**: Automatically fetches `skill://` resources when an MCP server connects.
- **Command Conversion**: Converts MCP resources into `prompt`-type `Command` objects.
- **Real-Time Refresh**: Re-fetches skills whenever the prompts or resources list changes.
- **Cache Consistency**: Clears the skill cache when a connection is closed.

## II. Implementation Architecture

### 2.1 Data Flow

```
MCP Server Connection
      │
      ▼
client.ts: connectToServer / setupMcpClientConnections
  ├── fetchToolsForClient     (MCP tools)
  ├── fetchCommandsForClient   (MCP prompts → Command objects)
  ├── fetchMcpSkillsForClient  (MCP skill:// resources → Command objects) [MCP_SKILLS]
  └── fetchResourcesForClient  (MCP resources)
      │
      ▼
commands = [...mcpPrompts, ...mcpSkills]
      │
      ▼
AppState.mcp.commands updated
      │
      ▼
getMcpSkillCommands() filtering → SkillTool call
```

### 2.2 Skill Filtering

File: `src/commands.ts:604-616`

Criteria for `getMcpSkillCommands(mcpCommands)`:

```ts
cmd.type === 'prompt'                  // Must be of type 'prompt'
cmd.loadedFrom === 'mcp'               // Must originate from an MCP server
!cmd.disableModelInvocation            // Must be invocable by the model
feature('MCP_SKILLS')                  // Feature flag must be enabled
```

### 2.3 Conditional Loading

File: `src/services/mcp/client.ts:129-133`

`fetchMcpSkillsForClient` is conditionally loaded via `require()`. No modules are loaded if the feature flag is disabled:

```ts
const fetchMcpSkillsForClient = feature('MCP_SKILLS')
  ? require('../../skills/mcpSkills.js').fetchMcpSkillsForClient
  : null
```

### 2.4 Cache Management

The skill fetching function maintains a `.cache` (Map), which is cleared under the following conditions:

| Event | Behavior |
| :--- | :--- |
| **Connection Closed** | Clears the skill cache for that client. |
| `disconnectMcpServer()` | Clears the skill cache. |
| `prompts/list_changed` Notification | Refreshes prompts and fetches skills in parallel. |
| `resources/list_changed` Notification | Refreshes resources, prompts, and skills. |

### 2.5 Integration Points

| File | Lines | Description |
| :--- | :--- | :--- |
| `src/commands.ts` | 604-616, 620-633 | Command filtering and `SkillTool` command collection. |
| `src/services/mcp/client.ts` | 129-133, 1394, 1672, 2176 | Skill fetching, cache clearing, and fetching on connection. |
| `src/services/mcp/useManageMCPConnections.ts` | 22-26, 682-740 | Real-time refresh (on prompt/resource changes). |

## III. Key Design Decisions

1.  **Feature Gate Isolation**: `feature('MCP_SKILLS')` guards the conditional `require()` and all call sites. When off, no modules are loaded, and no fetching occurs.
2.  **Resource-to-Skill Mapping**: Skills are discovered from `skill://` URI resources on the MCP server. `fetchMcpSkillsForClient` handles the conversion (currently a stub).
3.  **Circular Dependency Avoidance**: `mcpSkillBuilders.ts` acts as a leaf node in the dependency graph to avoid circularities between `client.ts`, `mcpSkills.ts`, and `loadSkillsDir.ts`.
4.  **Server Capability Checks**: Skill fetching also requires the MCP server to support resources (`!!client.capabilities?.resources`).

## IV. Usage

```bash
# Enable the feature
FEATURE_MCP_SKILLS=1 bun run dev

# Prerequisites:
# 1. An MCP server configured with skill:// resources.
# 2. The MCP server must declare resource capabilities.
```

## V. Missing Implementations

| File | Status | Required Implementation |
| :--- | :--- | :--- |
| `src/skills/mcpSkills.ts` | **Stub** | `fetchMcpSkillsForClient()`: Filter `skill://` URIs from MCP resource lists and convert them into `Command` objects. |
| `src/skills/mcpSkillBuilders.ts` | **Stub** | Skill builder registration (to prevent circular dependencies). |

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `src/commands.ts:547-608` | Skill command filtering. |
| `src/services/mcp/client.ts:117-2358` | Skill fetching and cache management. |
| `src/services/mcp/useManageMCPConnections.ts` | Real-time refresh logic. |
| `src/skills/mcpSkills.ts` | Core conversion logic (stub). |
