# FORK_SUBAGENT — Context-Inheriting Subagent

> Feature Flag: `FEATURE_FORK_SUBAGENT=1`
> Implementation Status: Fully functional.
> Reference Count: 4

## I. Feature Overview

`FORK_SUBAGENT` allows the `AgentTool` to generate "forked subagents" that inherit the full conversation context of the parent. The forked subagent sees the entire history, toolset, and system prompt of its parent and shares an API request prefix to maximize prompt cache hits.

### Core Advantages

- **Prompt Cache Maximization**: Multiple parallel forks share the same API request prefix; only the final directive text block differs.
- **Context Integrity**: The subagent inherits the full conversation history of the parent (including thinking configurations).
- **Permission Bubbling**: Permission prompts from the subagent are "bubbled up" to be displayed on the parent terminal.
- **Worktree Isolation**: Supports git worktree isolation, allowing the subagent to operate within an independent branch.

## II. User Interaction

### Triggering Method

When `FORK_SUBAGENT` is enabled, an `AgentTool` call that does not specify a `subagent_type` automatically follows the fork path:

```javascript
// Fork path (Inherits context)
Agent({ prompt: "Fix this bug" })  // No subagent_type

// General agent path (New context)
Agent({ subagent_type: "general-purpose", prompt: "..." })
```

### /fork Command

The `/fork` slash command is registered (currently a stub). When `FORK_SUBAGENT` is active, the `/branch` command loses its `fork` alias to avoid conflicts.

## III. Implementation Architecture

### 3.1 Gating and Mutex

File: `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts:32-39`

```ts
export function isForkSubagentEnabled(): boolean {
  if (feature('FORK_SUBAGENT')) {
    if (isCoordinatorMode()) return false   // Coordinator has its own delegation model
    if (getIsNonInteractiveSession()) return false  // Disabled in pipe/SDK modes
    return true
  }
  return false
}
```

### 3.2 `FORK_AGENT` Definition

```ts
export const FORK_AGENT = {
  agentType: 'fork',
  tools: ['*'],              // Wildcard: Uses the parent's full toolset
  maxTurns: 200,
  model: 'inherit',          // Inherits the parent's model
  permissionMode: 'bubble',  // Permissions bubble up to the parent terminal
  getSystemPrompt: () => '', // Not used: Directly passes the parent's rendered prompt
}
```

### 3.3 Core Call Flow

```
AgentTool.call({ prompt, name })
      │
      ▼
isForkSubagentEnabled() && !subagent_type?
      │
      ├── No → General agent path
      │
      └── Yes → Fork path
            │
            ▼
      Recursion protection checks
      ├── querySource === 'agent:builtin:fork' → Denied
      └── isInForkChild(messages) → Denied
            │
            ▼
      Obtain parent system prompt
      ├── toolUseContext.renderedSystemPrompt (Preferred)
      └── buildEffectiveSystemPrompt (Fallback)
            │
            ▼
      buildForkedMessages(prompt, assistantMessage)
      ├── Clone parent assistant message
      ├── Generate placeholder tool_result
      └── Append directive text block
            │
            ▼
      [Optional] buildWorktreeNotice()
            │
            ▼
      runAgent({
        useExactTools: true,
        override.systemPrompt: Parent,
        forkContextMessages: Parent messages,
        availableTools: Parent tools,
      })
```

### 3.4 Message Construction: `buildForkedMessages`

File: `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts:107-169`

Constructed message structure:

```
[
  ...history (filterIncompleteToolCalls),  // Parent's full history
  assistant(All tool_use blocks),           // Assistant message from the parent's current turn
  user(
    Placeholder tool_result × N +          // Identical placeholder text
    <fork-boilerplate> directive           // Unique to each fork
  )
]
```

**All forks use the same placeholder text**: `"Fork started — processing in background"`. This ensures that the API request prefixes for multiple parallel forks are identical, maximizing prompt cache hits.

### 3.5 Recursion Protection

Two layers of checks prevent nested forking:

1.  **`querySource` Check**: `toolUseContext.options.querySource === 'agent:builtin:fork'`. Set in `context.options`, this is resistant to automatic compaction (autocompact rewrites messages but does not alter options).
2.  **Message Scanning**: `isInForkChild()` scans message history for the `<fork-boilerplate>` tag.

### 3.6 Worktree Isolation Notification

When forking is combined with a worktree, a notification is appended to inform the subagent:

> "You have inherited the conversation context of the parent agent at `{parentCwd}`, but you are operating in an independent git worktree at `{worktreeCwd}`. Convert paths accordingly and re-read before editing."

### 3.7 Mandatory Asynchrony

When `isForkSubagentEnabled()` is true, all agent startups are forced to be asynchronous. The `run_in_background` parameter is removed from the schema. Interaction is handled uniformly via `<task-notification>` XML messages.

## IV. Prompt Cache Optimization

This is the core optimization goal of the fork design:

| Optimization Point | Implementation |
| :--- | :--- |
| **Identical System Prompt** | Pass `renderedSystemPrompt` directly to avoid re-rendering (GrowthBook states might differ). |
| **Identical Toolset** | `useExactTools: true` uses parent tools directly without `resolveAgentTools` filtering. |
| **Identical Thinking Config** | Inherits parent thinking configuration (non-fork agents disable thinking by default). |
| **Identical Placeholder Result**| All forks use the same `FORK_PLACEHOLDER_RESULT` text. |
| **ContentReplacementState Clone**| Clones the parent's replacement state by default to maintain consistent wire prefixes. |

## V. Subagent Instructions

`buildChildMessage()` generates directives wrapped in `<fork-boilerplate>`:

- You are a fork worker, not the main agent.
- Forbidden from spawning another sub-agent (execute directly).
- Avoid small talk or meta-commentary.
- Use tools directly.
- Commit changes after modifying files and report the commit hash.
- Reporting format: `Scope:`, `Result:`, `Key files:`, `Files changed:`, `Issues:`.

## VI. Key Design Decisions

1.  **Fork ≠ General Agent**: Forks inherit full context, while general agents start from scratch. The selection is based on the presence of `subagent_type`.
2.  **`renderedSystemPrompt` Passthrough**: Avoids re-calling `getSystemPrompt()` during forking. The parent freezes the prompt bytes at the start of the turn.
3.  **Shared Placeholder Results**: Multiple parallel forks use identical placeholders; only the directive differs.
4.  **Coordinator Mutex**: Forks are disabled in Coordinator mode due to incompatible delegation models.
5.  **Non-Interactive Disable**: Disabled in pipe and SDK modes to avoid invisible nested forks.

## VII. Usage

```bash
# Enable the feature
FEATURE_FORK_SUBAGENT=1 bun run dev

# Usage in REPL (following the fork path by omitting subagent_type)
# Agent({ prompt: "Research the structure of this module" })
# Agent({ prompt: "Implement this feature" })
```

## VIII. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `packages/builtin-tools/src/tools/AgentTool/forkSubagent.ts` | ~210 | Core definition, message construction, and recursion protection. |
| `packages/builtin-tools/src/tools/AgentTool/AgentTool.tsx` | — | Fork routing and mandatory asynchrony. |
| `packages/builtin-tools/src/tools/AgentTool/prompt.ts` | — | "When to Fork" prompt section. |
| `packages/builtin-tools/src/tools/AgentTool/runAgent.ts` | — | `useExactTools` path. |
| `packages/builtin-tools/src/tools/AgentTool/resumeAgent.ts` | — | Fork agent restoration. |
| `src/constants/xml.ts` | — | XML tag constants. |
| `src/utils/forkedAgent.ts` | — | `CacheSafeParams` and `ContentReplacementState` cloning. |
| `src/commands/fork/index.ts` | — | `/fork` command (stub). |
