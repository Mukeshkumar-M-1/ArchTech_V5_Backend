# LSP Integration

Claude Code includes built-in Language Server Protocol (LSP) integration, providing code intelligence features (Go-to-Definition, Find References, Hover information, Document Symbols, etc.) and passive diagnostic feedback.

## Quick Start

### 1. Install an LSP Plugin

Use the `/plugin` command in the Claude Code REPL to search for and install LSP plugins:

```
/plugin
```

Search for `lsp` to find plugins for your languages (e.g., `typescript-lsp`) and install them. After installation, run `/reload-plugins` to activate the new plugins.

Once installed, the background **LSP Server Manager** automatically loads and starts the corresponding language servers—no manual configuration is required.

### 2. Enable the LSP Tool

To allow Claude to proactively trigger code intelligence queries, the LSP Tool must be explicitly enabled via an environment variable:

```bash
ENABLE_LSP_TOOL=1 bun run dev
```

If not enabled, the LSP server still runs in the background to provide passive diagnostic feedback (e.g., type errors).

## Auto-Recommendation

In addition to manual searches via `/plugin`, Claude Code automatically detects needs during file editing:

1.  Monitors `fileHistory.trackedFiles` for newly edited files.
2.  Scans the marketplace for LSP plugins that support the edited file's extension.
3.  Checks if the corresponding LSP binary (e.g., `typescript-language-server`) is installed on the system.
4.  Pops up a recommendation dialog if criteria are met:

```
┌───── LSP Plugin Recommendation ─────────────┐
│                                               │
│  LSP provides code intelligence like          │
│  go-to-definition and error checking          │
│                                               │
│  Plugin: typescript-lsp                       │
│  Triggered by: .ts files                     │
│                                               │
│  Would you like to install this LSP plugin?   │
│                                               │
│  > Yes, install typescript-lsp               │
│    No, not now                                │
│    Never for typescript-lsp                   │
│    Disable all LSP recommendations            │
└───────────────────────────────────────────────┘
```

- Closes automatically after 30 seconds (treated as "No").
- Selecting "Never" stops recommendations for that specific plugin.
- Selecting "Disable" turns off all LSP recommendations globally.
- Recommendations are automatically disabled after 5 consecutive ignores.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    LSP Tool                         │
│  packages/builtin-tools/src/tools/LSPTool/LSPTool.ts│
│  (Tools callable by Claude; 9 operations)           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              LSP Server Manager (Singleton)          │
│  src/services/lsp/manager.ts                        │
│  - initializeLspServerManager()                     │
│  - reinitializeLspServerManager()                   │
│  - shutdownLspServerManager()                       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              LSP Server Manager (Instance)          │
│  src/services/lsp/LSPServerManager.ts               │
│  - Manages multiple LSPServerInstances              │
│  - Routes requests by file extension                │
│  - File sync (didOpen/didChange/didSave/didClose)   │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ LSPServer    │ │ LSPServer    │ │ LSPServer    │
│ Instance     │ │ Instance     │ │ Instance     │
│ (typescript) │ │ (python)     │ │ (rust...)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
│ LSPClient    │ │ LSPClient    │ │ LSPClient    │
│ (JSON-RPC)   │ │ (JSON-RPC)   │ │ (JSON-RPC)   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
   Child Proc       Child Proc       Child Proc
    (stdio)          (stdio)          (stdio)
```

### Passive Diagnostic Feedback

```
LSP Server ──publishDiagnostics──▶ passiveFeedback.ts
                                          │
                                          ▼
                                   LSPDiagnosticRegistry
                                   (Deduplication, Limits)
                                          │
                                          ▼
                                   Attachment System
                                   (Async injection into chat)
```

LSP servers asynchronously push `textDocument/publishDiagnostics` notifications, which are deduplicated and limited before being injected as attachments into Claude's conversation context.

## Core Modules

| File | Responsibility |
| :--- | :--- |
| `src/services/lsp/manager.ts` | Global singleton; lifecycle management (Init/Re-init/Shutdown). |
| `src/services/lsp/LSPServerManager.ts` | Multi-server management and file extension routing. |
| `src/services/lsp/LSPServerInstance.ts` | Single LSP server lifecycle (Start/Stop/Restart/Health). |
| `src/services/lsp/LSPClient.ts` | JSON-RPC layer (`vscode-jsonrpc`) and child process management. |
| `src/services/lsp/config.ts` | Loading LSP server configurations from plugins. |
| `src/services/lsp/LSPDiagnosticRegistry.ts` | Registration, deduplication, and capacity limits for diagnostics. |
| `src/services/lsp/passiveFeedback.ts` | Registration of `publishDiagnostics` notification handlers. |
| `packages/builtin-tools/src/tools/LSPTool/LSPTool.ts` | Tool implementation (exposed to Claude). |
| `packages/builtin-tools/src/tools/LSPTool/schemas.ts` | Input schemas (9 operations via discriminated unions). |
| `src/utils/plugins/lspPluginIntegration.ts` | Plugin loading, validation, env var parsing, and scoping. |

## LSP Tool Supported Operations

| Operation | LSP Method | Description |
| :--- | :--- | :--- |
| `goToDefinition` | `textDocument/definition` | Jump to a symbol's definition. |
| `findReferences` | `textDocument/references` | Find all references to a symbol. |
| `hover` | `textDocument/hover` | Get hover info (documentation, types). |
| `documentSymbol` | `textDocument/documentSymbol`| List all symbols within a document. |
| `workspaceSymbol` | `workspace/symbol` | Search for symbols across the workspace. |
| `goToImplementation`| `textDocument/implementation`| Find implementations of interfaces/abstract methods. |
| `prepareCallHierarchy`| `textDocument/prepareCallHierarchy`| Get call hierarchy items at a position. |
| `incomingCalls` | `callHierarchy/incomingCalls` | Find functions that call the current function. |
| `outgoingCalls` | `callHierarchy/outgoingCalls` | Find functions called by the current function. |

All operations require `filePath`, `line` (1-based), and `character` (1-based) parameters.

## Plugin Development: LSP Server Configuration

LSP servers are provided via plugins. A plugin's `manifest.json` can declare LSP servers in three formats:

**1. Inline Configuration**
```json
{
  "lspServers": {
    "typescript": {
      "command": "typescript-language-server",
      "args": ["--stdio"],
      "extensionToLanguage": {
        ".ts": "typescript",
        ".tsx": "typescriptreact"
      }
    }
  }
}
```

**2. Reference an external `.lsp.json` file**
```json
{
  "lspServers": "path/to/.lsp.json"
}
```

**3. Mixed Array Format**
```json
{
  "lspServers": [
    "path/to/.lsp.json",
    {
      "another-server": { "command": "...", "extensionToLanguage": { "...": "..." } }
    }
  ]
}
```

You can also place a `.lsp.json` file directly in the plugin directory without declaring it in the manifest.

### LSP Server Configuration Schema

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `command` | string | Yes | The executable command for the LSP server. |
| `args` | string[] | No | Command-line arguments. |
| `extensionToLanguage` | `Record<string, string>` | Yes | Mapping of file extensions to Language IDs. |
| `transport` | `"stdio" \| "socket"` | No | Communication method (defaults to `stdio`). |
| `env` | `Record<string, string>` | No | Environment variables for the server process. |
| `initializationOptions`| unknown | No | Initialization options passed to the server. |
| `settings` | unknown | No | Settings passed via `workspace/didChangeConfiguration`. |
| `startupTimeout` | number | No | Timeout for startup (ms). |
| `maxRestarts` | number | No | Maximum restart attempts (defaults to 3). |

### Environment Variable Substitution
Fields support:
- `${CLAUDE_PLUGIN_ROOT}`: Plugin root directory.
- `${CLAUDE_PLUGIN_DATA}`: Plugin data directory.
- `${user_config.KEY}`: User-configured values during plugin enablement.
- `${VAR}`: System environment variables.

## Lifecycle Management

### Server State Machine
`stopped` → `starting` → `running`
`running` → `stopping` → `stopped`
`any` → `error` (on failure)
`error` → `starting` (on retry)

### Crash Recovery
- If an LSP server crashes, its state is set to `error`.
- Automatic restarts are attempted on the next request (via `ensureServerStarted`).
- Restarts stop after `maxRestarts` attempts.

### Transient Error Retries
- `ContentModified` errors (LSP error code -32801) are automatically retried up to 3 times.
- Uses exponential backoff: 500ms → 1000ms → 2000ms.
- Common in servers like `rust-analyzer` that index projects while processing requests.

### Diagnostic Capacity Limits
- Maximum **10 diagnostics per file**.
- Maximum **30 diagnostics total** across all files.
- Excess diagnostics are truncated based on severity (Error > Warning > Info > Hint).
- Cross-turn deduplication: Identical diagnostics are not resent.
- Sent records are cleared when a file is edited, allowing new diagnostics through.

### Plugin Refreshing
Running `/reload-plugins` calls `reinitializeLspServerManager()`:
1. Asynchronously shuts down old server instances.
2. Resets status to `not-started`.
3. Calls `initializeLspServerManager()` to reload plugin configurations.
