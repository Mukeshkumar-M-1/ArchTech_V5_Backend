---
title: "Hooks Lifecycle Hooks - Execution Engine and Interception Protocol"
description: "Analyzing the Claude Code Hooks system from a source code perspective: 27 hook events, 6 hook types, sync/async execution protocols, JSON output schema, 'if' condition matching, and how hooks inject context and intercept tool calls."
keywords: ["Hooks", "Lifecycle Hooks", "Interceptors", "PreToolUse", "Hook Protocol"]
---

{/* Goal: Reveal the hook execution engine, matching mechanism, return value protocol, and lifecycle management from a source code perspective */}

## 27 Hook Events

Claude Code defines 27 hook events (`HOOK_EVENTS` array in `src/entrypoints/sdk/coreTypes.ts`), covering the complete Agent lifecycle:

| Phase | Event | Trigger Point | Match Field |
| :--- | :--- | :--- | :--- |
| **Session** | `SessionStart` | Session starts | `source` |
| | `SessionEnd` | Session ends | `reason` |
| | `Setup` | Initialization complete | `trigger` |
| **User Interaction** | `UserPromptSubmit` | User submits a message | — |
| | `Stop` | Agent stops responding | — |
| | `StopFailure` | Agent failed to stop | `error` |
| **Tool Execution** | `PreToolUse` | Before tool call | `tool_name` |
| | `PostToolUse` | After tool call (success) | `tool_name` |
| | `PostToolUseFailure` | After tool call (failure) | `tool_name` |
| **Permissions** | `PermissionRequest` | Permission request | `tool_name` |
| | `PermissionDenied` | Permission denied | `tool_name` |
| **Sub-Agent** | `SubagentStart` | Sub-agent starts | `agent_type` |
| | `SubagentStop` | Sub-agent stops | `agent_type` |
| **Compression** | `PreCompact` | Before context compression | `trigger` |
| | `PostCompact` | After context compression | `trigger` |
| **Collaboration** | `TeammateIdle` | Teammate idle | — |
| | `TaskCreated` | Task created | — |
| | `TaskCompleted` | Task completed | — |
| **MCP** | `Elicitation` | MCP server requests user input | `mcp_server_name` |
| | `ElicitationResult` | Elicitation result returned | `mcp_server_name` |
| **Notification** | `Notification` | System notification event | `notification_type` |
| **Environment** | `ConfigChange` | Configuration change | `source` |
| | `CwdChanged` | Working directory change | — |
| | `FileChanged` | File change | `file_path` |
| | `InstructionsLoaded` | Instructions loaded | `load_reason` |
| | `WorktreeCreate` / `WorktreeRemove` | Worktree operation | — |

## 6 Hook Types

Hooks configuration supports 6 execution methods. Type definitions are spread across three files:

- **Persistable Types** (`command`, `prompt`, `agent`, `http`) — Defined via Zod schema in `src/schemas/hooks.ts` using `z.discriminatedUnion('type', [...])`.
- **callback Type** — Defined as a TypeScript interface in `src/types/hooks.ts`, used for internal JS functions registered via the SDK.
- **function Type** — Defined in `src/utils/hooks/sessionHooks.ts`, used for function hooks registered dynamically at runtime.

| Type | Execution Method | Use Case |
| :--- | :--- | :--- |
| `command` | Shell command (bash/PowerShell) | General scripts, CI checks |
| `prompt` | Injected into AI context | Code style reminders |
| `agent` | Launches a sub-agent to execute | Complex analysis tasks |
| `http` | HTTP request | Remote services, webhooks |
| `callback` | Internal JS function | System built-in hooks |
| `function` | Runtime-registered function hook | Internal use by agents or skills |

## Execution Engine: execCommandHook

`execCommandHook()` (located in `src/utils/hooks.ts`) is the core execution engine for command-type hooks:

```
execCommandHook(hook, hookEvent, hookName, jsonInput, signal)
  ├── Shell selection: hook.shell ?? DEFAULT_HOOK_SHELL
  │   ├── bash: spawn(cmd, [], { shell: gitBashPath | true })
  │   └── powershell: spawn(pwsh, ['-NoProfile', '-NonInteractive', '-Command', cmd])
  ├── Variable substitution
  │   ├── ${CLAUDE_PLUGIN_ROOT} → pluginRoot path
  │   ├── ${CLAUDE_PLUGIN_DATA} → plugin data directory
  │   └── ${user_config.X} → user configuration value
  ├── Environment variable injection
  │   ├── CLAUDE_PROJECT_DIR
  │   ├── CLAUDE_ENV_FILE (SessionStart/Setup/CwdChanged/FileChanged)
  │   └── CLAUDE_PLUGIN_OPTION_* (plugin options)
  ├── stdin write: jsonInput + '\n'
  ├── Timeout: hook.timeout * 1000 ?? 600000ms (10 minutes)
  └── Async detection: checks if the first line of stdout is {"async":true}
```

### Detection Protocol for Async Hooks

If the first line of a hook process's `stdout` is `{"async":true}`, the system treats it as a background task (detected by `isAsyncHookJSONOutput` + calling `executeInBackground`):

```typescript
const firstLine = firstLineOf(stdout).trim()
if (isAsyncHookJSONOutput(parsed)) {
  executeInBackground({
    processId: `async_hook_${child.pid}`,
    asyncResponse: parsed,
    ...
  })
}
```

Background hooks are registered via `registerPendingAsyncHook()` in the `AsyncHookRegistry` and notify the main thread via `enqueuePendingNotification()` upon completion.

### asyncRewake: Hook Wake-up Model

Hooks in `asyncRewake` mode bypass the `AsyncHookRegistry`. When a hook exits with code 2, it injects a message via `enqueuePendingNotification()` in `task-notification` mode. This wakes up an idle model (via `useQueueProcessor`) or injects a `queued_command` attachment if the model is busy.

## JSON Schema for Hook Output

The output of a synchronous hook follows a strict Zod schema (`syncHookResponseSchema` defined in `src/types/hooks.ts`, and `hookJSONOutputSchema` defined in `src/schemas/hooks.ts`):

```json
{
  "continue": false,                    // Whether to continue execution
  "suppressOutput": true,               // Hide stdout
  "stopReason": "Security check failed", // Reason if continue=false
  "decision": "approve" | "block",      // Global decision
  "reason": "Reason explanation",       // Reason for the decision
  "systemMessage": "Warning content",   // System message injected into context
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask",
    "permissionDecisionReason": "Matched security rule",
    "updatedInput": { ... },            // Modified tool input
    "additionalContext": "Extra context" // Context injected into conversation
  }
}
```

### hookSpecificOutput by Event

| Event | Exclusive Fields | Purpose |
| :--- | :--- | :--- |
| `PreToolUse` | `permissionDecision`, `permissionDecisionReason`, `updatedInput`, `additionalContext` | Intercept/modify tool input |
| `PostToolUse` | `additionalContext`, `updatedMCPToolOutput` | Modify MCP tool output |
| `PostToolUseFailure` | `additionalContext` | Inject context after failure |
| `UserPromptSubmit` | `additionalContext` | Inject additional context |
| `SessionStart` | `additionalContext`, `initialUserMessage`, `watchPaths` | Set initial message and file monitoring |
| `PermissionRequest` | `decision` (includes `allow`/`deny` subfields) | Hook decision for permission request |
| `PermissionDenied` | `retry` | Indicate whether to retry |
| `SubagentStart` | `additionalContext` | Inject context at sub-agent start |
| `Elicitation` | `action`, `content` | Control user input dialogs |
| `ElicitationResult` | `action`, `content` | Handle elicitation results |
| `Notification` | `additionalContext` | Inject context for notification events |
| `Setup` | `additionalContext` | Inject context at initialization |
| `CwdChanged` | `watchPaths` | Update watch paths after directory change |
| `FileChanged` | `watchPaths` | Update watch paths after file change |
| `WorktreeCreate` | `worktreePath` | Worktree creation notification |

## Hook Matching Mechanism: getMatchingHooks

`getMatchingHooks()` (in `src/utils/hooks.ts`) is responsible for finding matching hooks from all sources:

### Multi-source Merging

```
getHooksConfig()
  ├── getHooksConfigFromSnapshot()    ← Hooks in settings.json (user/project/local)
  ├── getRegisteredHooks()            ← callback hooks registered via SDK
  ├── getSessionHooks()               ← session hooks pre-registered by Agents/Skills
  └── getSessionFunctionHooks()       ← runtime function hooks
```

### Matching Rules

The `matcher` field supports three modes (via the `matchesPattern()` function in `src/utils/hooks.ts`):

```
"Write"              → Exact match
"Write|Edit"         → Multi-value match separated by pipes
"^Bash(git.*)"       → Regex match
"*" or ""            → Wildcard (matches all)
```

### if Condition Filtering

Hooks can specify an `if` condition to trigger only on specific inputs. `prepareIfConditionMatcher()` (in `src/utils/hooks.ts`) pre-compiles the matcher:

```json
{
  "hooks": [{
    "command": "check-git-branch.sh",
    "if": "Bash(git push*)"
  }]
}
```

The `if` condition is parsed using `permissionRuleValueFromString`, following the same syntax as permission rules (tool name + parameter pattern). For the Bash tool, it also uses tree-sitter for AST-level command parsing.

### Hook De-duplication

The same hook command may be repeated across different configuration levels (user/project/local). The system de-duplicates them using a Map with a four-part composite key: `${pluginRoot}\0${shell}\0${command}\0${ifCondition}` (built by the `hookDedupKey()` function), keeping the **last merged level**.

## Workspace Trust Check

**All hooks require workspace trust** (checked via the `shouldSkipHookDueToTrust()` function in `src/utils/hooks.ts`). This is a defense-in-depth measure—preventing a malicious repository's `.claude/settings.json` from executing arbitrary commands without being trusted.

```typescript
// In interactive mode, all hooks require trust
const hasTrust = checkHasTrustDialogAccepted()
return !hasTrust
```

In non-interactive SDK sessions, trust is implicit (checked via `getIsNonInteractiveSession()`).

## Mapping Four Hook Capabilities to Source Code

### 1. Intercepting Operations (PreToolUse)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny"
  }
}
```

`processHookJSONOutput()` maps `permissionDecision` to `result.permissionBehavior = 'deny'` and sets a `blockingError`, preventing the tool from executing.

### 2. Modifying Behavior (updatedInput / updatedMCPToolOutput)

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "updatedInput": { "command": "npm test -- --bail" }
  }
}
```

`updatedInput` replaces the original tool input; `updatedMCPToolOutput` (for `PostToolUse` events) replaces the return value of an MCP tool—useful for filtering sensitive data.

### 3. Injecting Context (additionalContext / systemMessage)

- `additionalContext` → Injected as a user message via `createAttachmentMessage({ type: 'hook_additional_context' })`.
- `systemMessage` → Injected as a system warning displayed directly to the user.

### 4. Controlling Flow (continue / stopReason)

```json
{ "continue": false, "stopReason": "Build failed, stopping execution" }
```

`continue: false` sets `preventContinuation = true`, preventing the Agent from proceeding with further operations.

## Lifecycle of Session Hooks

Pre-hooks for Agents and Skills are registered via `registerFrontmatterHooks()` (called in `packages/builtin-tools/src/tools/AgentTool/runAgent.ts`, defined in `src/utils/hooks/registerFrontmatterHooks.ts`), bound to the agent's session ID. They are cleared when the Agent ends via `clearSessionHooks()` (defined in `src/utils/hooks/sessionHooks.ts`).

```typescript
// runAgent.ts — Register pre-hooks for an agent
registerFrontmatterHooks(rootSetAppState, agentId, agentDefinition.hooks, ...)

// runAgent.ts — Cleanup in finally block
clearSessionHooks(rootSetAppState, agentId)
```

This ensures that hooks from Agent A do not leak into the execution of Agent B.
