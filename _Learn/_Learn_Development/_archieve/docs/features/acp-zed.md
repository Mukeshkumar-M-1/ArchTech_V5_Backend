# ACP (Agent Client Protocol) — Zed / IDE Integration

> Feature Flag: `FEATURE_ACP=1` (Enabled by default in build and dev modes)
> Implementation Status: Available (Supports Zed, Cursor, and other ACP clients)
> Source Directory: `src/services/acp/`

## I. Feature Overview

ACP (Agent Client Protocol) is a standardized stdio protocol that allows IDEs and editors to drive an AI Agent via NDJSON streams on stdin/stdout. CCB implements a complete ACP agent that can be directly invoked by ACP-supporting clients like Zed and Cursor.

### Core Features

- **Session Management**: Create, resume, load, fork, and close sessions.
- **History Replay**: Automatically loads and replays conversation history when resuming a session.
- **Permission Bridging**: Maps permission decisions from the ACP client to CCB's tool permission system.
- **Slash Commands & Skills**: Loads real command lists, supporting prompt-based skills like `/commit` and `/review`.
- **Context Window Tracking**: Precise `usage_update` including model prefix matching.
- **Prompt Queuing**: Supports sending multiple prompts sequentially with automatic queuing.
- **Mode Switching**: auto, default, acceptEdits, plan, dontAsk, bypassPermissions.
- **Model Switching**: Switch AI models at runtime.

## II. Architecture

```
┌──────────────┐    NDJSON/stdio    ┌──────────────────┐
│  Zed / IDE   │ ◄────────────────► │  CCB ACP Agent   │
│  (Client)    │   stdin / stdout   │  (Agent)         │
└──────────────┘                    │                  │
                                    │  entry.ts        │ ← stdio → NDJSON stream
                                    │  agent.ts        │ ← ACP protocol handler
                                    │  bridge.ts       │ ← SDKMessage → ACP SessionUpdate
                                    │  permissions.ts  │ ← Permission bridging
                                    │  utils.ts        │ ← Common utilities
                                    │                  │
                                    │  QueryEngine     │ ← Internal query engine
                                    └──────────────────┘
```

### File Responsibilities

| File | Responsibility |
| :--- | :--- |
| `entry.ts` | Entry point; creates stdio → NDJSON stream and starts `AgentSideConnection`. |
| `agent.ts` | Implements the ACP `Agent` interface: session CRUD, prompt, cancel, mode/model switching. |
| `bridge.ts` | `SDKMessage` → ACP `SessionUpdate` conversion: text/thought/tool/usage/edit diff. |
| `permissions.ts` | ACP `requestPermission()` → CCB `CanUseToolFn` bridging. |
| `utils.ts` | Pushables, stream conversion, permission mode parsing, session fingerprints, path display. |

## III. Configuring Zed Editor

### 3.1 Zed settings.json Configuration

Open Zed's `settings.json` (`Cmd+,` → Open Settings) and add the `agent_servers` configuration:

```json
{
  "agent_servers": {
    "ccb": {
      "type": "custom",
      "command": "ccb",
      "args": ["--acp"]
    }
  }
}
```

### 3.2 API Authentication Configuration

The CCB ACP agent automatically loads environment variables (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, etc.) from `settings.json` at startup. Ensure you have configured your API provider via `/login`.

Variables can also be passed via the `env` field:

```json
{
  "agent_servers": {
    "claude-code": {
      "command": "ccb",
      "args": ["--acp"],
      "env": {
        "ANTHROPIC_BASE_URL": "https://api.example.com/v1",
        "ANTHROPIC_AUTH_TOKEN": "sk-xxx"
      }
    }
  }
}
```

### 3.3 Using in Zed

1. Restart Zed after configuration is complete.
2. Open any project directory.
3. Press `Cmd+'` (macOS) or `Ctrl+'` (Linux) to open the Agent Panel.
4. Select **claude-code** from the dropdown menu at the top of the Agent Panel.
5. Start the conversation.

### 3.4 Feature Guide

| Feature | Action |
| :--- | :--- |
| Conversation | Input messages directly in the Agent Panel. |
| Slash Commands | Type `/` to see the list of available skills (e.g., `/commit`, `/review`). |
| Tool Permissions | Choose Allow / Reject / Always Allow when a permission request pops up. |
| Mode Switching | Switch between auto/default/plan modes via the Agent Panel's settings menu. |
| Model Switching | Switch AI models via the Agent Panel's settings menu. |
| Session Recovery | Previous sessions (including history) are automatically restored when reopening Zed. |

## IV. Configuring Other ACP Clients

ACP is an open protocol; any ACP-supporting client can connect to CCB. General configuration pattern:

```
Command: ccb --acp
Arguments: ["--acp"]
Communication: stdin/stdout NDJSON
Protocol Version: ACP v1
```

### 4.1 Cursor

Configure the MCP / Agent Server in Cursor settings using the same `ccb --acp` command.

### 4.2 Custom Clients

You can quickly build an ACP client using the `@agentclientprotocol/sdk`:

```typescript
import { ClientSideConnection, ndJsonStream } from '@agentclientprotocol/sdk'
import { spawn } from 'child_process'
import { Readable, Writable } from 'stream'

// Create connection (start ccb --acp as a subprocess)
const child = spawn('ccb', ['--acp'])
const stream = ndJsonStream(
  Writable.toWeb(child.stdin),
  Readable.toWeb(child.stdout),
)

const client = new ClientSideConnection(stream)

// Initialization
await client.initialize({ clientCapabilities: {} })

// Create session
const { sessionId } = await client.newSession({
  cwd: '/path/to/project',
})

// Send prompt
const response = await client.prompt({
  sessionId,
  prompt: [{ type: 'text', text: 'Hello, explain this project' }],
})

// Listen for session updates
client.on('sessionUpdate', (update) => {
  console.log('Update:', update)
})
```

## V. ACP Protocol Support Matrix

| Method | Status | Description |
| :--- | :--- | :--- |
| `initialize` | ✅ | Returns agent information and capabilities. |
| `authenticate` | ✅ | No authentication required (self-hosted). |
| `newSession` | ✅ | Create a new session. |
| `resumeSession` | ✅ | Restore an existing session (including history replay). |
| `loadSession` | ✅ | Load a specific session (including history replay). |
| `listSessions` | ✅ | List available sessions. |
| `forkSession` | ✅ | Fork a session. |
| `closeSession` | ✅ | Close a session. |
| `prompt` | ✅ | Send a message; supports queuing. |
| `cancel` | ✅ | Cancel the current/queued prompt. |
| `setSessionMode` | ✅ | Switch permission mode. |
| `setSessionModel` | ✅ | Switch AI model. |
| `setSessionConfigOption` | ✅ | Dynamically modify configuration. |

### SessionUpdate Types

| Type | Status | Description |
| :--- | :--- | :--- |
| `agent_message_chunk` | ✅ | Assistant text message. |
| `agent_thought_chunk` | ✅ | Thinking/reasoning content. |
| `user_message_chunk` | ✅ | User message (history replay). |
| `tool_call` | ✅ | Tool call begins. |
| `tool_call_update` | ✅ | Tool call result/status update. |
| `usage_update` | ✅ | Token usage + context window. |
| `plan` | ✅ | TodoWrite → plan entries. |
| `available_commands_update` | ✅ | Slash commands & skills list. |
| `current_mode_update` | ✅ | Mode switch notification. |
| `config_option_update` | ✅ | Configuration update notification. |
