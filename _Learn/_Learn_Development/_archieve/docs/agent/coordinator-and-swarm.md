---
title: "Coordinator and Swarm Mode - Multi-Agent Advanced Orchestration"
description: "Analysis of Claude Code multi-Agent collaboration from a source code perspective: Coordinator Mode's System Prompt design, Worker life cycle, Task communication protocol, and Swarm cluster task allocation mechanism."
keywords: ["Coordinator mode", "Swarm mode", "Agent Swarm", "Multi-Agent collaboration", "Task orchestration"]
---

{/* The goal of this chapter: reveal the architectural design of Coordinator Mode and Agent Swarms from the source code perspective */}

## Architectural differences between the two collaboration modes

| Dimensions | Coordinator Mode | Agent Swarms |
|------|------------------|---------------|
| **Gating** | `feature('COORDINATOR_MODE')` + `CLAUDE_CODE_COORDINATOR_MODE=1` | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` Environment variables |
| **Topology** | Star: Coordinator in the center, Worker on the periphery | Star+P2P hybrid: Team Lead coordinates, Teammates can communicate directly |
| **Roles** | Clear division of labor: Coordinator orchestration, Worker execution | Team Lead coordination + Teammate autonomously claiming tasks |
| **Communication** | `SendMessage` directed communication + `<task-notification>` | Mailbox message system (message/broadcast) |
| **Applicable** | Complex tasks that require centralized decision-making | Tasks with a high degree of parallelism that require direct collaboration between Teammates |

The two are not mutually exclusive - in theory, Coordinator Mode can run on top of the Agent Teams architecture (concept layer overlay, non-nested teams), using the Coordinator as a special Team Lead, but this part of the integration (`getCoordinatorAgents` in `workerAgent.ts`) is currently implemented as a stub and has not yet been fully implemented.

## Coordinator Mode: Star orchestration architecture

### Activation mechanism

```typescript
// src/coordinator/coordinatorMode.ts:36
export function isCoordinatorMode(): boolean {
  if (feature('COORDINATOR_MODE')) {
    return isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE)
  }
  return false // External builds are always false
}
```

Coordinator Mode requires double gating: build-time `feature('COORDINATOR_MODE')` and run-time environment variables. `matchSessionMode()` automatically synchronizes the mode state when the session is restored - if the restored session is in coordinator mode, it flips the environment variable to ensure consistency.

### Coordinator’s toolset

Coordinator is stripped of all "hands-on" tools, retaining only orchestration capabilities:

| Tools | Purpose |
|------|------|
| **Agent** | Start a new Worker (`subagent_type: "worker"`) |
| **SendMessage** | Send subsequent instructions to existing Workers |
| **TaskStop** | Stop a Worker that is going in the wrong direction midway |
| **subscribe_pr_activity** | Subscribe to GitHub PR events (review comments, CI results) |

Coordinator **does not write code, does not read files, and does not execute commands**—its core responsibilities are: understanding requirements, assigning tasks, synthesizing results, and answering user questions directly without the need for tools.

### Worker’s tool permissions

The Worker's available tools are dynamically injected into the System Prompt by `getCoordinatorUserContext()` (`coordinatorMode.ts:80`):

```typescript
// In simplified mode: only Bash + Read + Edit
const workerTools = isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)
  ? [BASH_TOOL_NAME, FILE_READ_TOOL_NAME, FILE_EDIT_TOOL_NAME]
  : Array.from(ASYNC_AGENT_ALLOWED_TOOLS)
      .filter(name => !INTERNAL_WORKER_TOOLS.has(name))
```

`INTERNAL_WORKER_TOOLS` (TeamCreate, TeamDelete, SendMessage, SyntheticOutput) are explicitly excluded - Workers cannot be nested to create teams or send messages, preventing uncontrollable recursion.

### Scratchpad: shared knowledge base across workers

When `isScratchpadGateEnabled()` (internally checking the `tengu_scratch` feature gate) is enabled, Workers get a Scratchpad directory whose existence is known to the Coordinator through its system context:

```
Scratchpad directory:
  - Workers can read and write freely without permission approval
  - Cross-worker knowledge for persistence
  - The structure is determined by the Coordinator (no fixed format)
```

This is a key collaboration primitive - Worker A's research results can be written to Scratchpad, and Worker B can read them directly without going through the Coordinator.

### `<task-notification>` Communication protocol

When the Worker completes, the Coordinator receives a notification in XML format:

```xml
<task-notification>
  <task-id>agent-a1b</task-id> ← Worker’s agentId
  <status>completed|failed|killed</status>
  <summary>Agent "Investigate auth bug" completed</summary>
  <result>Found null pointer in src/auth/validate.ts:42...</result>
  <usage>
    <total_tokens>N</total_tokens>
    <tool_uses>N</tool_uses>
    <duration_ms>N</duration_ms>
  </usage>
</task-notification>
```

Notifications are delivered as `user-role messages`, which the Coordinator distinguishes from user messages through the `<task-notification>` tag. `<task-id>` is used for the `to` parameter of `SendMessage` to implement directed resume transmission.

### Core responsibilities of Coordinator: Synthesis

The Coordinator System Prompt (`coordinatorMode.ts:111-369`, ~line 260) explicitly requires that the Coordinator **not lazily delegate understanding**:

```
Anti-patterns (forbidden):
  "Based on your findings, fix the auth bug"
  → Put the responsibility of understanding on the Worker

Correct approach:
  "Fix the null pointer in src/auth/validate.ts:42.
   The user field on Session (src/auth/types.ts:15) is
   undefined when sessions expire but the token remains cached.
   Add a null check before user.id access."
  → Coordinator understands the problem himself and gives precise instructions
```

This is the core design constraint of Coordinator Mode: Coordinator must first understand and then assign.

## Agent Teams (Swarm): Swarm collaboration

Swarm mode is based on task system V2 (see [Task Management](../tools/task-management.mdx) for details). The core mechanism is **shared task list + competitive claim + Mailbox message system**:

### Team initialization

```
Team Lead creates a team (TeamCreateTool)
  ↓
set teamName → setLeaderTeamName()
  ↓
All Teammates automatically get the same taskListId
  ↓
When Teammate starts:
  1. CLAUDE_CODE_TASK_LIST_ID environment variable (explicit override)
  2. teamName of Teammate context (shared Lead’s task list)
  3. CLAUDE_CODE_TEAM_NAME environment variable
  4. teamName set by Lead
  5. getSessionId() (reveal the bottom line)
```

Multi-level prioritization ensures that the Team Lead and all Teammates are pointed to the same task list without additional coordination.

### Architecture components

The official Agent Teams architecture defines four core components:

| Components | Roles |
|------|------|
| **Team Lead** | The main Claude Code session that creates teams, assigns tasks, and synthesizes results |
| **Teammate** | Independent instances of Claude Code, each with its own context window |
| **Task List** | Shared task list, Teammate competes to claim and complete |
| **Mailbox** | Messaging system that supports direct communication between Teammates |

### Mailbox messaging system

Mailbox in the official architecture is the core primitive for communication between Teammates and supports two message modes (the `broadcast` mode is inferred from the source code and is not clearly broken down in the official documentation):

| Mode | Function | Scene |
|------|------|------|
| **message** | Directly sent to the specified Teammate | Pass specific instructions and request collaboration |
| **broadcast** | Broadcast to all Teammates | Global notification, status synchronization |

Mailbox key features:
- **Auto-delivery**: The message is automatically delivered to the conversation context of the target Teammate
- **Idle Notification** (TeammateIdle): When Teammate completes the current task and becomes idle, it will automatically notify Team Lead through Mailbox
- **Direct Communication**: Unlike Coordinator Mode, Teammates can communicate directly without going through Lead.

### Hook event

Agent Teams provides three key Hook events for injecting custom logic into the team lifecycle:

| Hook | Trigger timing | Typical uses |
|------|---------|---------|
| **TaskCreated** | When a new task is added to the task list | Automatic allocation, prioritization |
| **TaskCompleted** | When the task is marked as completed | Result notification, dependency unlocking |
| **TeammateIdle** | Teammate completes all tasks and becomes idle | Lead reallocation, dynamic expansion and contraction |

### Limitations

Limitations of the current Agent Teams implementation:
- **Nested teams not supported**: Teammate can no longer create sub-teams
- **One team per session**: A session can only belong to one team
- **Lead fixed**: Team Lead cannot be replaced after creation
- **Session recovery for in-process Teammate is not supported**: the state of in-process type Teammate is lost after the process is restarted

### Persistent storage

The team state is persisted through the file system to ensure recovery after process restarts:

```
~/.claude/teams/{team-name}/config.json ← Team configuration
~/.claude/tasks/{team-name}/ ← Shared task list (file lock protection)
```

### Task claim and competition

`claimTask()` is the core concurrency primitive of Agent Teams:

```
Teammate A calls TaskList → finds task #3 is pending
Teammate B also found that task #3 is pending
  ↓
Try both TaskUpdate(task #3, {status: "in_progress"})
  ↓
File locking guarantees atomicity:
  - The first writer gets the owner lock
  - The second writer receives an already_claimed error
  ↓
Get the task's teammate execution job
  ↓
After completion TaskUpdate(task #3, {status: "completed"})
  → Other tasks that depend on this task are automatically unlocked
  → tool_result prompt "Call TaskList to find your next task"
```

### Lifecycle management of Teammate

```
Teammate exits abnormally
  ↓
unassignTeammateTasks()
  → Scan the task list and find the unfinished tasks with owner === teammateName
  → reset to pending + owner=undefined
  ↓
Team Lead perception approach:
  1. Task status change (pending reset) - by sharing the task list
  2. Mailbox idle notification (TeammateIdle hook) - automatically notifies Lead when Teammate stops
  ↓
Team Lead reassigns tasks or creates a new Teammate
```

## Task type panorama

There are 7 task types (`src/tasks/types.ts`) that support multi-Agent collaboration:

| Task type | Running location | Status management | Applicable scenarios |
|----------|---------|---------|---------|
| **LocalAgentTask** | Local child process | `LocalAgentTaskState` | Standard child Agent task |
| **LocalShellTask** | local shell | `LocalShellTaskState` | background shell command |
| **InProcessTeammateTask** | In the same process | `InProcessTeammateTaskState` | Lightweight in-process teammate |
| **RemoteAgentTask** | Remote Server | `RemoteAgentTaskState` | Distributed Agent (CCR) |
| **DreamTask** | Silent in the background | `DreamTaskState` | Organize memory independently in the background |
| **LocalWorkflowTask** | Local | `LocalWorkflowTaskState` | Workflow orchestration |
| **MonitorMcpTask** | Local | `MonitorMcpTaskState` | MCP monitoring task |

The key difference between `InProcessTeammateTask` and `LocalAgentTask`: the former shares the memory space and infrastructure state of the process (such as MCP connection pool), but has independent conversation context and tool permissions; the latter is a fully isolated child process, with greater startup overhead but safer.

## Coordinator vs Agent Teams choice

| Scenario | Recommended mode | Reason |
|------|---------|------|
| "Reconstructing the authentication system requires multi-module coordination" | Coordinator | Centralized decision-making is required, and there are dependencies between workers |
| "Fix 10 independent lint warnings" | Agent Teams | Task independent, Teammate can be fully parallelized |
| "Study plan A and plan B, then choose one to implement" | Coordinator | Study in parallel first, then centralize decision-making |
| "Search all TODOs in the large warehouse and classify them" | Agent Teams | No dependencies, just take the tasks individually |