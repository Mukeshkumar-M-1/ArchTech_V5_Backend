---
title: "Custom Agents - From Markdown to Runtime"
description: "Revealing the full pipeline of custom agents in Claude Code: the Markdown data model for agent definition, the three loading sources, tool filtering strategies, and the integration mechanism with AgentTool."
keywords:
  [
    "Custom Agent",
    "Agent Definition",
    "Markdown Agent",
    "Agent Configuration",
    "Role Customization",
  ]
---

{/* Goal: Reveal the complete data model for Agent definitions, loading/discovery mechanisms, tool filtering, and integration with AgentTool */}

## Three Sources of Agent Definitions

Claude Code agents come from more than just user definitions—the system identifies three types of sources, merged by priority:

| Source                     | Location                                                         | Priority          |
| -------------------------- | ---------------------------------------------------------------- | ----------------- |
| **Built-in**               | Hardcoded in `packages/builtin-tools/src/tools/AgentTool/built-in/` | Lowest (Overridable) |
| **Plugin**                 | Registered via the plugin system                                  | Medium            |
| **User/Project/Policy**    | `.claude/agents/*.md` or `settings.json`                         | Highest           |

Merging logic resides in `getActiveAgentsFromList()`: agents are de-duplicated by `agentType`, with higher-priority sources overwriting lower ones. This means you can place an `Explore.md` file in `.claude/agents/` to completely replace the built-in Explore agent.

## Full Format of a Markdown Agent File

```markdown
---
# === Required Fields ===
name: "reviewer"                    # Agent identifier (agentType)
description: "Code review specialist, read-only analysis"

# === Tool Control ===
tools: "Read,Glob,Grep,Bash"        # List of allowed tools (comma-separated)
disallowedTools: "Write,Edit"       # Explicitly prohibited tools

# === Model Configuration ===
model: "haiku"                      # Specified model (or "inherit" to use the main thread model)
effort: "high"                      # Reasoning effort: low/medium/high or an integer

# === Behavior Control ===
maxTurns: 10                        # Maximum agentic turns
permissionMode: "plan"              # Permission mode: plan, bypassPermissions, etc.
background: true                    # Always run as a background task
initialPrompt: "/search TODO"       # Prefix for the first user message (supports slash commands)

# === Isolation & Persistence ===
isolation: "worktree"               # Run in an independent git worktree
memory: "project"                   # Persistent memory scope: user/project/local

# === MCP Servers ===
mcpServers:
  - "slack"                         # Reference a configured MCP server
  - database:                       # Inline definition
      command: "npx"
      args: ["mcp-db"]

# === Hooks ===
hooks:
  PreToolUse:
    - command: "audit-log.sh"
      timeout: 5000

# === Skills ===
skills: "code-review,security-review"  # Pre-loaded skills (comma-separated)

# === Display ===
color: "blue"                       # Agent color indicator in the terminal
---

You are a code review expert. Your responsibility is to...

(The body content = system prompt)
```

### Field Parsing Details

- **`tools`**: Parsed via `parseAgentToolsFromFrontmatter()`, supporting comma-separated strings or arrays.
- **`model: "inherit"`**: Uses the model from the main thread (case-sensitive; only lowercase "inherit" works).
- **`memory`**: When enabled, automatically injects `Write`, `Edit`, and `Read` tools (even if not in `tools`) and appends memory instructions to the end of the system prompt.
- **`isolation: "remote"`**: Only available internally at Anthropic (`USER_TYPE === 'ant'`); external builds only support `worktree`.
- **`background`**: Setting to `true` ensures the agent always runs in the background, with the main thread not waiting for results.

## Loading and Discovery Mechanism

`getAgentDefinitionsWithOverrides()` (memoized) executes the full discovery process:

```
1. Load Markdown Files
   ├── loadMarkdownFilesForSubdir('agents', cwd)
   │   ├── ~/.claude/agents/*.md  (User-level, source = 'userSettings')
   │   ├── .claude/agents/*.md    (Project-level, source = 'projectSettings')
   │   └── managed/policy sources (Policy-level, source = 'policySettings')
   │
   └── For each .md file:
       ├── Parse YAML frontmatter
       ├── Use body as system prompt
       ├── Validate required fields (name, description)
       ├── Silently skip .md files without frontmatter (might be reference docs)
       └── Record failedFiles on parsing error without blocking other agents

2. Load Plugin Agents in parallel
   └── loadPluginAgents() → memoized

3. Initialize Memory Snapshots (if AGENT_MEMORY_SNAPSHOT is enabled)
   └── initializeAgentMemorySnapshots()

4. Merge Built-in + Plugin + Custom
   └── getActiveAgentsFromList() → De-duplicate by agentType, latter overwrites former

5. Assign Colors
   └── setAgentColor(agentType, color) → Distinguish agents in the terminal UI
```

## Implementation of Tool Filtering

When an agent is derived, `AgentTool` filters the available tools based on the defined `tools` and `disallowedTools`:

```
All Tools
  ↓ Remove disallowedTools
  ↓ Filter by tools whitelist (if specified)
Available Tools
```

- **`tools` not specified**: Agent can use all tools (full capability by default).
- **`tools` specified**: Agent is restricted to the listed tools.
- **`disallowedTools`**: These tools are prohibited even if `tools` is not specified.
- **Auto-injection**: `Write`, `Edit`, and `Read` are added automatically when `memory` is enabled.

Example using the built-in Explore agent:

```typescript
// packages/builtin-tools/src/tools/AgentTool/built-in/exploreAgent.ts
disallowedTools: [
  "Agent", // Cannot recursively call Agent
  "ExitPlanMode", // Plan mode not needed
  "FileEdit", // Read-only
  "FileWrite", // Read-only
  "NotebookEdit", // Read-only
];
```

## System Prompt Injection Method

The system prompt for an agent is lazily generated via the `getSystemPrompt()` closure:

```typescript
// Markdown Agent
getSystemPrompt: () => {
  if (isAutoMemoryEnabled() && memory) {
    return systemPrompt + "\n\n" + loadAgentMemoryPrompt(agentType, memory);
  }
  return systemPrompt;
};
```

This means:
1.  **Markdown body = complete system prompt**: It replaces the default prompt rather than appending to it.
2.  **Memory instructions** are automatically appended when memory is enabled.
3.  **Lazy calculation via closure**: Memory status may change after the file is loaded.

For built-in agents, `getSystemPrompt` accepts a `toolUseContext` parameter, allowing dynamic adjustment of the prompt based on runtime state (e.g., whether an embedded search tool is used).

## Integration with AgentTool

When the main agent needs to derive a subagent:

```
AgentTool.call({ subagent_type: "reviewer", ... })
  ↓
1. Find agentType === "reviewer" in agentDefinitions.activeAgents
  ↓
2. Check requiredMcpServers (if the agent requires specific MCP servers)
  ↓
3. Filter the tool list (tools / disallowedTools)
  ↓
4. Resolve the model:
   - "inherit" → Use main thread model
   - Specific model name → Use directly
   - Unspecified → Use main thread model
  ↓
5. Resolve permission mode (permissionMode)
  ↓
6. Construct isolated environment (if isolation === "worktree")
  ↓
7. Inject system prompt (getSystemPrompt())
  ↓
8. Inject initialPrompt (if defined)
  ↓
9. Start subagent loop (forkSubagent / runAgent)
```

## Built-in Agent Reference

| Agent               | agentType           | Role                         | Tool Restrictions         | Model            |
| ------------------- | ------------------- | ---------------------------- | ------------------------- | ---------------- |
| **General Purpose** | `general-purpose`   | Default subagent             | All tools                 | Main thread model|
| **Explore**         | `Explore`           | Code search specialist       | Read-only (no Write/Edit) | Haiku (external) |
| **Plan**            | `Plan`              | Planning specialist          | Read-only + ExitPlanMode  | inherit          |
| **Verification**    | `verification`      | Result verification          | Controlled by feature flag| —                |
| **Code Guide**      | `claude-code-guide` | Claude Code user guide       | Read-only                 | —                |
| **Statusline Setup**| `statusline-setup`  | Terminal status bar config   | Limited                   | —                |

The SDK entry points (`sdk-ts`/`sdk-py`/`sdk-cli`) do not load the Code Guide agent. The environment variable `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS` can be used to completely disable built-in agents, providing a blank canvas for SDK users.

## Agent Memory: Persistent Agent State

When the `memory` field is enabled, the agent gains persistent memory across sessions:

- **`local`**: Valid for the current project and current user.
- **`project`**: Shared among all users in the current project.
- **`user`**: Shared across all projects.

Memory is injected via `loadAgentMemoryPrompt()` at the end of the system prompt, including instructions for reading and writing memory. The Agent Memory Snapshot mechanism synchronizes `user`-level memory across projects.
