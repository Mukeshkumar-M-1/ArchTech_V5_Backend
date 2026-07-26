---
title: "Sub-Agent Mechanism - Permissions, Processes, Synchronization/Asynchronous and Fork"
description: "Analysis of Claude Code sub-Agent from the source code perspective: AgentTool's execution link, permission mode, synchronous and asynchronous life cycle, task notification queue, AgentTool fork, slash command fork and the boundary of runForkedAgent."
keywords:
  [
    "Sub-Agent",
    "AgentTool",
    "Permission Mode",
    "Synchronous Sub-Agent",
    "Asynchronous Sub-Agent",
    "forkSubagent",
    "runForkedAgent",
  ]
---

{/_ The goal of this chapter: to dismantle and explain several easily confused execution links of the sub-Agent, and provide the source code entry. _/}

## Let’s first distinguish four concepts

What is often called "sub-Agent" in Claude Code actually has four types of execution paths:

| Type               | Who triggers                                                                           | Whether it goes through the Tool protocol          | How to get the results back                                                                                    | Typical entrance                                                           |
| ------------------ | -------------------------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Name the sub-Agent | The main model calls `Agent(...)` and provides `subagent_type`                         | Yes, belongs to one `tool_use`                     | `tool_result` of the current turn, or `<task-notification>` after the background is completed                  | `src/tools/AgentTool/AgentTool.tsx`                                        |
| AgentTool fork     | The main model calls `Agent(...)`, omitting `subagent_type`, and the fork gate is open | Yes, it is still the `Agent` tool                  | Return to `async_launched` first, and then return to the main model through task notification after completion | `src/tools/AgentTool/AgentTool.tsx`, `src/tools/AgentTool/forkSubagent.ts` |
| Slash command fork | The user executes the slash command / skill of `context: fork`                         | No, it is not issued by the model `Agent` tool_use | Normal mode synchronously returns the command output; assistant mode background backnote hides prompt          | `src/utils/processUserInput/processSlashCommand.tsx`                       |
| `runForkedAgent()` | The runtime internal service directly forks an execution branch                        | No, internal API                                   | The caller consumes the results internally                                                                     | `src/utils/forkedAgent.ts`                                                 |

One sentence to remember:

`AgentTool` fork is the tool semantics used by the model; `runForkedAgent()` is the implementation details used by the internal capabilities of the runtime; slash command fork is the execution mode of skill / command.

## AgentTool main process

The `Agent` tool that the model sees eventually goes into `AgentTool.call()`. The execution chain of a common named sub-Agent is as follows:

```text
assistant message
-> tool_use: Agent({ prompt, subagent_type?, run_in_background?, ... })
-> query.ts: runTools(...)
-> toolExecution.ts: await tool.call(...)
->AgentTool.call(...)
-> resolve selectedAgent / fork path / permission mode / tool pool
-> runAgent(...)
-> finalizeAgentTool(...)
-> mapToolResultToToolResultBlockParam(...)
-> user message with tool_result
-> query.ts starts next model turn with that tool_result
```

Key source code entry:

| Code                                          | Function                                                                          |
| --------------------------------------------- | --------------------------------------------------------------------------------- |
| `src/tools/AgentTool/AgentTool.tsx`           | `Agent` tool definition, routing, synchronous/asynchronous life cycle             |
| `src/tools/AgentTool/runAgent.ts`             | Query loop, system prompt, MCP, sidechain transcript of sub-Agent                 |
| `src/services/tools/toolExecution.ts`         | The outer tool executor, where `await tool.call(...)`                             |
| `src/query.ts`                                | Main agentic loop, collect tool results and enter the next round of model calling |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | Background local Agent task registration, status update, completion notification  |

## AgentTool input parameters

The input schema of the `Agent` tool is defined in `baseInputSchema()` and `fullInputSchema()` in `AgentTool.tsx`. Some fields will be hidden from the model visible schema by the feature gate, but the `call()` implementation will handle these optional fields as a unified `AgentToolInput` type.

### Basic parameters

| Parameters          | Type                | Required | Function                                                                                                              | Influence path                                                                                                                                                                     |
| ------------------- | ------------------- | -------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description`       | `string`            | Yes      | A short description of the task of 3-5 words, used for UI, task list, log, background notification and output summary | Does not participate in the actual prompt reasoning of the sub-Agent, but will affect task display and notification                                                                |
| `prompt`            | `string`            | Yes      | The complete task description to be performed by the child Agent                                                      | The ordinary agent will become the user message of the child Agent; the fork path will embed the fork directive; the remote path will serve as the remote initial message          |
| `subagent_type`     | `string`            | No       | Specify the named agent type                                                                                          | If there is a value, the named agent will be used; if it is omitted, the AgentTool fork will be used if the fork gate is enabled, otherwise it will fall back to `general-purpose` |
| `model`             | `'sonnet' \| 'opus' |
| `run_in_background` | `boolean`           | No       | Request background running                                                                                            | Run an asynchronous task when `true`; if the background task is disabled or the fork gate is enabled, this field will be hidden from the schema                                    |

### Multiple Agent / Teammate parameters

| Parameters  | Type            | Required | Function                                                                         | Influence path                                                                                                                                                                                                      |
| ----------- | --------------- | -------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`      | `string`        | No       | Name the spawned agent so that it can be directed by `SendMessage({ to: name })` | Trigger teammate spawn when it appears together with `team_name` or the current team context; `name -> agentId` will also be registered in the common background sub-Agent to facilitate subsequent message sending |
| `team_name` | `string`        | No       | Specify the team to join or use                                                  | Trigger `spawnTeammate()` together with `name`; when omitted, the current `appState.teamContext.teamName` can be inherited                                                                                          |
| `mode`      | permission mode | No       | Permission mode prompt for teammate spawn                                        | The current implementation only works with teammate's `plan_mode_required: spawnMode === 'plan'`; it is not an override of the normal local sub-Agent's `permissionMode`                                            |

`name + team_name` is an independent branch: it does not enter the normal `runAgent()` local sub-Agent path, but calls `spawnTeammate()`, returning `teammate_spawned`. If you continue to include `name` spawn teammate in teammate, it will be rejected because the team roster has a flat structure.

### Isolation and working directory parameters

| Parameters  | Type                                                  | Required | Function                                         | Influence path                                                                                                    |
| ----------- | ----------------------------------------------------- | -------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `isolation` | `'worktree'`, internal build also supports `'remote'` | No       | Override the isolation mode of agent definition  | `worktree` creates a temporary git worktree; `remote` delegates to CCR, returns directly to `remote_launched`     |
| `cwd`       | `string`                                              | No       | Specifies the running directory of the sub-Agent | Only exposed in `KAIROS` schema; will change the cwd of files and shell operations through `runWithCwdOverride()` |

The `isolation` input parameter has a higher priority than the `isolation` in the agent definition. The schema copywriting of `cwd` requires not to be used together with `isolation: "worktree"`; ​​in implementation, if both appear at the same time, `cwd` will take priority as the running directory, but worktree may still be created, so the caller should treat it as a mutually exclusive parameter.

### Parameter visibility and actual effects

| Parameters            | Possible invisible situations                                                 | Description                                                                                                                      |
| --------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `run_in_background`   | `DISABLE_BACKGROUND_TASKS` is in effect, or `isForkSubagentEnabled()` is true | When the fork gate is turned on, all `AgentTool` spawns will be forced asynchronous, so there is no need to select the model     |
| `cwd`                 | Non-`KAIROS` builds/schema                                                    | The schema will be omitted, but the implementation type still retains the field                                                  |
| `isolation: "remote"` | Not for internal builds                                                       | External builds only accept `worktree`                                                                                           |
| `model`               | coordinator mode or fork path                                                 | coordinator will clear model override; fork needs to inherit the parent model to maintain consistent request prefix and behavior |

### Priority of parameters and agent definition

| Configuration items       | Call parameters              | agent definition               | Final rules                                                                                                                                                                          |
| ------------------------- | ---------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| agent type                | `subagent_type`              | Default/active agents          | Explicit `subagent_type` takes precedence; when omitted, fork gate determines fork or `general-purpose`                                                                              |
| Model                     | `model`                      | `selectedAgent.model`          | Calling parameters in ordinary named agents take precedence; if there are no parameters, the definition will be used; if there are no parameters, the parent model will be inherited |
| Running in the background | `run_in_background`          | `selectedAgent.background`     | If any one is true, it will be asynchronous; there are also mandatory asynchronous conditions such as coordinator, assistant, fork gate, etc.                                        |
| Isolation                 | `isolation`                  | `selectedAgent.isolation`      | Call parameters take precedence                                                                                                                                                      |
| Permission mode           | No local override parameters | `selectedAgent.permissionMode` | Ordinary sub-Agents use definition's `permissionMode`, and the default is `acceptEdits`; fork uses `bubble`                                                                          |
| Tool collection           | No calling parameters        | `selectedAgent.tools`          | Ordinary sub-Agents are filtered by definition in `runAgent()`; fork uses parent exact tools                                                                                         |

## Agent Definition field

The calling parameters of `AgentTool` only describe "how to spawn this time". What really determines the default capabilities of an agent is the agent definition. Custom agents can come from the user/project directory, JSON configuration, plug-ins or built-in definitions, and the core fields will eventually be normalized to `AgentDefinition`.

### Commonly used frontmatter

| Field             | Type                             | Effect                                  | Runtime impact                                                                                        |
| ----------------- | -------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `name`            | `string`                         | agent type name                         | model matches it by `subagent_type`; plugin agents may be namespace prefixed                          |
| `description`     | `string`                         | Usage scenario description              | Enter the list of available agents to help with main model selection                                  |
| `tools`           | `string[]`                       | Allowed tool set                        | `runAgent()` is filtered by `resolveAgentTools()`; `['*']` represents the full set of available tools |
| `disallowedTools` | `string[]`                       | Disabled tools collection               | JSON agent supports this field for exclusion from allowed collection                                  |
| `prompt`          | `string`                         | agent system prompt body                | Commonly named sub-agent will use it to build its own system prompt                                   |
| `model`           | `string`                         | Default model                           | Can be overridden by `Agent({ model })`; `inherit` means inheriting the parent model                  |
| `effort`          | effort level or number           | inference effort level                  | passed to agent run configuration                                                                     |
| `permissionMode`  | permission mode                  | Default permission mode                 | Used when assembling the common sub-Agent tool pool; if omitted, the default is `acceptEdits`         |
| `background`      | `boolean`                        | Whether to always run in the background | When true, even if the calling parameter does not have `run_in_background`, it will go asynchronously |
| `isolation`       | `'worktree'` / `'remote'`        | Default isolation mode                  | Can be overridden by calling parameter `isolation`                                                    |
| `maxTurns`        | positive integer                 | Maximum agentic turns                   | Passed to `query()` to prevent infinite loops of child Agents                                         |
| `color`           | agent color                      | UI color                                | used for grouped UI, task panel, teammate display                                                     |
| `memory`          | `'user' \| 'project' \| 'local'` | Persistent memory scope                 | Append agent memory in the system prompt and read and write directories according to scope            |

Example:

```md
---
name: code-reviewer
description: Review a code change and find correctness risks
tools:
  - Read
  - Grep
  - Glob
model: sonnet
permissionMode: acceptEdits
background: true
maxTurns: 8
memory: project
---

You are a focused code reviewer. Prioritize bugs, regressions, and missing tests.
```

### MCP, Hooks, Skills

| Field                | Function                                        | Description                                                                                                                 |
| -------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `requiredMcpServers` | MCP server mode that must exist before starting | `AgentTool.call()` will wait for pending server, up to about 30 seconds; if no tool is available, an error will be reported |
| `mcpServers`         | agent-specific MCP server                       | `runAgent()` initialization, the life cycle follows the sub-Agent                                                           |
| `hooks`              | hooks registered during the agent life cycle    | `runAgent()` will register frontmatter hooks; session hooks are cleaned up when the agent stops                             |
| `skills`             | Preload skill name                              | `runAgent()` will parse and inject the corresponding skill; plug-in skill supports namespace or suffix matching             |
| `initialPrompt`      | The first user turn prefix content              | Can be used to inject additional instructions at startup                                                                    |

These fields belong to the agent definition, not the `Agent(...)` call parameters. The caller cannot temporarily pass in `tools`, `hooks` or `skills` in an `Agent` tool_use to override the agent definition.

### runAgent() extension point

`runAgent()` doesn't just throw prompt to the model. It will mount a set of agent-level extension points before and after entering the query loop:

| Extension points      | Timing                                         | Function                                                                                                          |
| --------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `SubagentStart` hooks | Sub-Agent query loop before starting           | Allow hooks to modify or supplement the startup context                                                           |
| frontmatter `hooks`   | Registered during agent session initialization | Only valid within the session of this sub-Agent and cleaned up after completion                                   |
| preload `skills`      | system prompt / skill parsing phase            | Inject the instructions and resources of the specified skill into the agent visible context                       |
| agent `memory`        | system prompt when building                    | Press `user` / `project` / `local` scope to read agent memory and append to agent prompt                          |
| sidechain transcript  | query loop runtime                             | records the independent message chain of the sub-Agent for recovery, debugging and `SendMessage` continuation use |

These extension points explain why different agent definitions for the same `runAgent()` will exhibit different tool boundaries, startup behavior, and long-term context.

## Routing rules

`AgentTool.call()` first determines which agent to run for this call:

```text
subagent_type has a value
-> Use named agent

subagent_type omitted && isForkSubagentEnabled() is true
-> Use fork agent

subagent_type omitted && fork gate closed
-> Fallback to general-purpose
```

Named agents come from definitions such as built-in agents, user configuration directories, plug-in agents, etc. The fork agent is a special agent built into the code, defined in `forkSubagent.ts`. It is not an ordinary professional role, but a "worker that inherits the parent context".

## Permission model

Sub-Agent permissions should be divided into three levels: whether the agent can be started, what tools the agent has, and how to handle permission requests when the tools are executed.

### Start permissions

`AgentTool` itself is a tool call, so it first passes through the normal tool permission system. Then `AgentTool.call()` will also perform agent-level filtering:

| Check                     | Instructions                                                                                                    |
| ------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `filterDeniedAgents()`    | Filter banned agent types based on permission rules                                                             |
| `requiredMcpServers`      | If the agent declares required MCP servers, it will wait for them to connect, and stop if it fails or times out |
| teammate limitations      | in-process teammate cannot continue to spawn teammate, nor can it spawn background agent                        |
| fork recursion protection | fork workers cannot fork again                                                                                  |

Named agents that are denied by permission rules will report errors directly instead of falling back to other agents. This prevents the model from bypassing user or configuration deny rules.

### Tool pool permissions

Ordinary named child agents do not directly inherit the parent agent's tool pool restrictions for the current round. It will reassemble the tool pool with its own permission mode:

```ts
const workerPermissionContext = {
  ...appState.toolPermissionContext,
  mode: selectedAgent.permissionMode ?? "acceptEdits",
};

const workerTools = assembleToolPool(
  workerPermissionContext,
  appState.mcp.tools,
);
```

There are several important implications here:

| Dimensions                | Behavior                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------ |
| Default permission mode   | If the agent definition does not write `permissionMode`, `acceptEdits` will be used by default         |
| Global allow / deny rules | Still from `appState.toolPermissionContext`                                                            |
| agent's own `tools` field | continue filtering through `resolveAgentTools()` within `runAgent()`                                   |
| MCP tool                  | From the connected MCP tool in the current AppState; the agent can also declare a dedicated MCP server |

The exception is the fork agent. In order to keep the prompt cache prefix of parent and child requests consistent, it will use the parent exact tools:

```text
useExactTools: true
availableTools: toolUseContext.options.tools
```

Therefore, the permission strategy of fork is not "reassemble the tool pool", but "inherit the parent tool definition and use the `bubble` permission mode to float the permission request to the parent terminal".

### Quick overview of permission mode

| Pattern                        | Meaning in sub-Agents                                                                                                               |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `acceptEdits`                  | Default mode. Safe paths are usually allowed to be read and edited, but dangerous operations still go through the permission system |
| `default` / Other normal modes | Ask or release according to the main authority system rules                                                                         |
| `bypassPermissions`            | Explicit dangerous mode, should only appear if the user has bypass permissions enabled                                              |
| `bubble`                       | Fork-specific idea: permission requests bubble up to the parent session for processing                                              |

## Synchronize sub-Agent

The synchronous sub-Agent is the default path: there is no explicit `run_in_background: true`, the agent definition does not have `background: true`, and it is not forced to be asynchronous by mechanisms such as coordinator / assistant mode / fork gate.

Synchronous waiting occurs in the normal tool call chain. The outer layer `toolExecution.ts` will execute:

```ts
const result = await tool.call(...)
```

If the tool is `AgentTool`, then `AgentTool.call()` will run the entire sub-Agent internally:

```text
AgentTool.call()
-> agentIterator = runAgent(...)[Symbol.asyncIterator]()
-> while true:
await agentIterator.next()
Collect assistant / user messages
Forward progress to UI/SDK
If result.done, jump out
-> finalizeAgentTool(agentMessages, ...)
-> return { data: { status: "completed", ...agentResult } }
```

After returning, `mapToolResultToToolResultBlockParam()` converts the `completed` result into the `tool_result` of the current turn. Then `query.ts` puts this tool result into the message list and enters the next round of model calling.

In other words, the synchronization sub-Agent does not inject results back through the unified queue. The main model waits on this `Agent` tool call and does not continue until it gets the final `tool_result`.
### Synchronization sub-Agent can be backgrounded 

The synchronization child agent is registered as a foreground task, so it can be backgrounded midway. The loop will wait for the next sub-Agent message and the background signal at the same time: 

```ts 
const raceResult = await Promise.race([ 
nextMessagePromise.then((result) => ({ type: "message", result })), 
backgroundPromise, 
]); 
``` 

If the background signal arrives first, the current foreground iterator will be cleaned up, and the new background `runAgent(..., isAsync: true)` will take over the remaining work. At this time, `AgentTool.call()` no longer waits for the final result, but returns `async_launched`, and the subsequent completed results will go to the task notification queue. 

## Asynchronous sub-Agent 

The triggering conditions for asynchronous sub-Agents include: 

| Conditions | Description | 
|--------------------------------|----------------------------------------------------------------| 
| `run_in_background: true` | The model explicitly requires background running | 
| agent definition `background: true` | The agent always runs in the background | 
| coordinator mode | workers are unified and asynchronous to facilitate orchestration | 
| fork subagent gate enabled | The current implementation will force all `AgentTool` spawns to use the asynchronous notification model | 
| assistant / kairos mode | Avoid synchronization subtasks blocking the input queue | 
| Proactive active | It is also possible to force asynchrony in active loops | 

Asynchronous paths do not wait for child agents to complete: 

```text 
AgentTool.call() 
-> registerAsyncAgent(...) 
-> void runAsyncAgentLifecycle(...) 
-> return { status: "async_launched", agentId, outputFile } 
``` 

The background lifecycle is completed in `runAsyncAgentLifecycle()`: 

```text 
runAsyncAgentLifecycle() 
-> for await message of runAgent(...) 
-> updateAsyncAgentProgress(...) 
-> finalizeAgentTool(...) 
-> completeAsyncAgent(...) 
-> enqueueAgentNotification(...) 
``` 

Asynchronous Agent uses standalone `AbortController`. Canceling the main thread with ordinary ESC will not automatically kill the background Agent; the background Agent needs to be explicitly terminated through task stop, bulk kill or task management commands.
## Completion notification and unified queue 

After the background Agent is completed, `enqueueAgentNotification()` will generate an XML form of `<task-notification>`: 

```xml 
<task-notification> 
<task-id>...</task-id> 
<tool-use-id>...</tool-use-id> 
<output-file>...</output-file> 
<status>completed</status> 
<summary>Agent "..." completed</summary> 
<result>...</result> 
<usage>...</usage> 
</task-notification> 
``` 

This message enters the unified command queue through `enqueuePendingNotification({ mode: 'task-notification' })`. 

### When does the queue consume? 

| Scenario | Consumption pattern | 
| ------------------ | --------------------------------------------------------------------------------------------------------------- | 
| REPL / TUI | `useQueueProcessor()` subscribes to a queue; when query is idle and no local JSX UI is blocking, call `processQueueIfReady()` | 
| CLI / SDK headless | `drainCommandQueue()` in `print.ts` continues to consume between turns; if there are still background tasks running, it will continue to wait and drain new notifications | 
| Inside the child Agent | `query.ts` will consume `task-notification` with the current `agentId`, and the main thread only consumes messages with `agentId === undefined` | 

`task-notification` will eventually enter the next round of model context as a user-role message or attachment. The model can therefore see the background results and decide whether to synthesize, proceed with action, or reply to the user. 

### What other messages go to the same queue? 

Unified queues are not just for background agents. Common sources include: 

| source | mode | purpose | 
|-------------------------------------------------- |---------------------------------- |--------------------------------------------------- | 
| The user continues to input before the current turn ends | `prompt` / `bash` | Queue to the next round of processing | 
| Background shell/monitor end or stuck reminder | `task-notification` | Notify model command status | 
| remote agent / ultraplan / ultrareview completed | `task-notification` | Hand over remote results to local model | 
| scheduled task / cron | `prompt` | Scheduled triggering of main model tasks | 
| Chrome / MCP channel push | `prompt` | External system actively injects messages | 
| Hook blocking error | `task-notification` | Wake up model processing stop hook error | 
| orphaned permission response | `orphaned-permission` | Handles the situation where the tool permission reply arrives later than the original request | 

The queue priority is `now > next > later`. `enqueue()` defaults to `next`, and `enqueuePendingNotification()` defaults to `later`, so that system notifications will not precede user input. 

## Continue communication and mission control 

After the background sub-Agent returns `async_launched`, the main model should not directly pretend to know the final answer. It has three subsequent operation surfaces: sending messages, reading output, and stopping tasks.
### SendMessage 

`SendMessage` is used to append messages to a running or previously started agent. It can find the local backend agent through two addresses: 

| Address | Source | Behavior | 
| ------------- | -------------------------------------------------- | ---------------------------------- | 
| `name` | `Agent({ name, ... })` registered to `agentNameRegistry` | First parse to agentId and then send | 
| raw `agentId` | returned in `async_launched` or `completed` tool result | directly locate the corresponding task or transcript | 

`summary` must be provided when sending a plain text message because the UI and permissions summary require a short description. `to: "*"` means broadcasting to teammate team; structured messages cannot be broadcast. 

There are three types of behaviors of `SendMessage` towards the local background agent: 

| Goal state | Behavior | Result | 
| -------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------- | 
| The task is still `running` | Call `queuePendingMessage(agentId, message, ...)` | The message enters the `pendingMessages` of the task and is delivered at the next tool round / loop boundary of the child Agent | 
| The task has stopped but is still in AppState | Call `resumeAgentBackground(...)` | Use this message to resume running the agent background, and still return through notification after completion | 
| task has been cleared from AppState | Still trying `resumeAgentBackground(...)` | If sidechain transcript is still there, resume from transcript; otherwise, return failure | 

This means that `SendMessage` cannot only be used while the agent is running. After a long time, as long as the caller still knows the `name` or `agentId`, and the corresponding transcript has not been cleared, it is possible to restore and continue the agent. Conversely, if the task status and transcript are gone, `SendMessage` cannot reconstruct the context out of thin air. 

Several points that are easily misunderstood: 

| Point | Description | 
|---------------------------------------- | ----------------------------------------------------------------------- | 
| Running agent will not immediately interrupt the current tool call | Messages will be queued into `pendingMessages` first, and then processed after the agent loop reaches the safe boundary | 
| The stopped agent will become a new background operation | `resumeAgentBackground()` returns the output file, and then returns the note with the completion notification | 
| `name` is only reliable while the registration is still there | name registry is a runtime state; raw `agentId` is more stable when restored over a long period of time | 
| cross-session send has additional restrictions | `bridge:` / `uds:` addresses only support plain text and may require explicit permissions or connection status |
### TaskOutput 

`TaskOutput` is an old-style tool for reading the output of background tasks. The current prompt clearly recommends using `Read` to read the `output_file` returned by the task. It is still available and the main behavior is as follows: 

| Parameters | Behavior | 
| -------------- | ---------------------------- | 
| `task_id` | The background task id to be read | 
| `block: false` | Non-blocking reading of current status and existing output | 
| `block: true` | Wait for the task to complete, default behavior | 
| `timeout` | Maximum blocking wait time | 

If `block: true` waits until the task is completed, `TaskOutput` will mark the task as `notified` to avoid sending completion notifications repeatedly. Because this tool has been deprecated, it is recommended that new code and model hints read `output_file` directly. 

### TaskStop 

`TaskStop` stops a running background task. It accepts `task_id` and is also compatible with the old `shell_id`. The verification rules are straightforward: the task must exist and the status is `running`, otherwise an error will be reported. 

After stopping, a unified `stopTask()` will be called, and the specific task type is mapped to its respective kill logic. For example, the local agent will abort its own `AbortController`, the shell task will stop the process, and the remote task will take the remote stop path. 

## Failure, Cancellation and Cleanup 

The abnormal paths of sub-Agents are mainly divided into synchronous and asynchronous. 

### Synchronization path 

When the synchronous sub-Agent throws `AbortError`, `AgentTool.call()` will continue to throw it to the outer tool framework, and the main turn will enter normal interrupt processing. Non-abort errors will be logged first; if assistant messages have been collected, `finalizeAgentTool()` will try to return partial results so that the main model can see the progress. If there is no assistant message at all, the error is rethrown. 

Synchronous finally will do this cleanup: 

| Cleanup | Function | 
| ---------------------------------- | -------------------------------------------------- | 
| Clear background hint UI | Avoid foreground hints remaining | 
| `stopForegroundSummarization()` | Stop the foreground summary timer | 
| `unregisterAgentForeground()` | When the sub-Agent is not backgrounded, it is removed from the foreground task registry | 
| SDK task notification | Send completion, failure or stopped events to the SDK / VS Code panel | 
| `clearInvokedSkillsForAgent()` | Clear agent scope skill status | 
| `clearDumpState()` | Clear dump/transcript debugging state | 
| `cleanupWorktreeIfNeeded()` | Clean or retain worktree when not backgrounded |
### Asynchronous path 

The asynchronous path is handled by `runAsyncAgentLifecycle()` to catch exceptions: 

| Situation | Status Updates | Notifications | 
| -------------------------- | -------------------------- | ---------------------------------------------------------------- | 
| Completed normally | `completeAsyncAgent(...)` | `enqueueAgentNotification(status: completed)` | 
| `AbortError` | `killAsyncAgent(...)` | `enqueueAgentNotification(status: killed)`, with partial result | 
| Other errors | `failAsyncAgent(...)` | `enqueueAgentNotification(status: failed)` with error | 

The code will first update the task status, and then do additional work such as handoff classifier or worktree cleanup, which may be slower. This order is very important: `TaskOutput(block=true)` waits for the task to enter terminal status and cannot be stuck by subsequent classifiers or git cleanup. 

Notifications also have an anti-repeater mechanism. `enqueueAgentNotification()` will first atomically check and set `task.notified`; if it has been notified, it will not be enqueued again. 

## AgentTool fork 

AgentTool fork is a special route for the `Agent` tool, not an ordinary named agent. 

###Gate 

fork is turned off by default. The `FORK_SUBAGENT` feature needs to be enabled during build/runtime, for example, explicitly set during development: 

```powershell 
$env:FEATURE_FORK_SUBAGENT='1'; bun run dev 
``` 

Even if the feature is turned on, the following scenarios will force it to turn off: 

| Scene | Reason | 
| ----------------------- | ----------------------------------------- | 
| coordinator mode | coordinator has its own delegation model | 
| non-interactive session | avoid invisible fork nesting in pipe / SDK scenarios | 

### Path 

```text 
master model 
-> Agent({ prompt }), no subagent_type 
->AgentTool.call() 
-> isForkSubagentEnabled() 
-> selectedAgent = FORK_AGENT 
-> buildForkedMessages(...) 
-> runAgent(... useExactTools: true, forkContextMessages: parent messages) 
->Register task / transcript / notification 
``` 

The goal of fork is to have multiple workers share the prompt cache prefix of the parent request. It will: 

| dimensions | fork behavior | 
| ----------------------- | -------------------------------------------------- | 
| system prompt | Use the system prompt that has been rendered by the parent | 
| Conversation history | Pass in parent complete `toolUseContext.messages` | 
| tools | use parent exact tools, no refiltering | 
| thinking config | Inherit parent configuration to avoid cache key changes | 
| placeholder tool_result | Multiple forks use the same placeholder text, only the last directive is different | 
| Permissions | `permissionMode: 'bubble'` | 

This is why the fork path and the normal agent path are different in tool pool, prompt construction, and model inheritance.
### Recursion protection 

The fork worker retains the `Agent` tool so that the tool definition bytes are consistent with the parent, but the code will refuse to fork again within the fork: 

| Protection | Description | 
|---------------------------------------- | ---------------------------------- | 
| `querySource === 'agent:builtin:fork'` | Directly identify that it is currently in the fork worker | 
| `<fork-boilerplate>` scan | Identify that the fork instruction already exists in the context | 

The fork worker should complete the task directly instead of continuing to delegate. 

## Slash command fork 

Slash command fork is the execution mode of skill / command. It is controlled by skill frontmatter: 

```md 
--- 
name: code-review 
context: fork 
allowed-tools: 
- Read 
- Grep 
-Glob 
--- 
``` 

When loading a skill, `frontmatter.context === 'fork'` will be parsed into command's `context: 'fork'`. When executing slash command: 

```text 
User input /code-review 
-> processSlashCommand(...) 
-> command.context === 'fork' 
-> executeForkedSlashCommand(...) 
-> prepareForkedCommandContext(...) 
-> runAgent(...) 
``` 

In normal interactive mode, `executeForkedSlashCommand()` will finish running the sub-Agent synchronously, display the progress UI, and then return the result to the main dialog as local command output. 

In assistant / kairos mode, it will fire-and-forget: After the background runner is completed, it will wrap the result into a hidden prompt and put it back into the command queue. This way multiple scheduled tasks will not serially block user input when starting.
## `runForkedAgent()` 

`runForkedAgent()` is an executor for internal services. It is not exposed to the model and does not generate `Agent` tool_result. 

Its inputs are runtime objects such as `cacheSafeParams`, `promptMessages`, `canUseTool`, etc. Run query loop directly: 

```text 
Internal services 
-> runForkedAgent({ promptMessages, cacheSafeParams, ... }) 
-> createSubagentContext(...) 
-> query(...) 
-> Return ForkedAgentResult 
``` 

Common callers: 

| Caller | Purpose | 
| ---------------------------------- | ---------------------------------- | 
| compact | conversation compression | 
| extractMemories / sessionMemory | Memory extraction and maintenance | 
| promptSuggestion / speculation | prompt suggestions and predictions | 
| sideQuestion | Ad hoc Q&A that does not disturb the main context | 
| agentSummary | background agent summary | 
| autoDream | Background memory integration | 

What it has in common with AgentTool fork is "forked execution", but the boundaries are completely different: 

| Dimensions | AgentTool fork | `runForkedAgent()` | 
| -------- | ----------------------------------------------- | ---------------------------- | 
| Caller | The model is called through the `Agent` tool | The runtime service is called directly | 
| Protocol layer | Through Tool schema / tool_use / tool_result | Not through Tool protocol | 
| Visibility | The main model will see `async_launched` first and a notification when completed | The result is handled by the internal caller | 
| Main goal | Parallel worker + prompt cache sharing | Internal auxiliary task reuse query loop | 

## Worktree Isolation 

The `Agent` tool supports `isolation: "worktree"`. When enabled, the sub-Agent runs in a temporary git worktree, which is suitable for implementation or experimental tasks. 

Life cycle: 

| Stage | Behavior | 
| --------------- | --------------------------------------------------------------- | 
| Create | Use agent id to derive slug and create independent worktree | 
| CWD Override | `runWithCwdOverride(worktreePath, fn)` makes the tool execute within the worktree | 
| fork + worktree | Additional injection path translation prompts to remind workers to re-read files | 
| Cleanup | If there are no changes, remove the worktree; if there are changes, keep it and return the path to the main model | 

If the worktree is hook-based, the code retains it because VCS changes cannot be reliably determined. 

## Result format 

`AgentTool.mapToolResultToToolResultBlockParam()` returns different tool results according to the status: 

| Status | Results | 
| ------------------ | --------------------------------------------------------------- | 
| `completed` | Sub-Agent output content, which can be accompanied by `agentId`, worktree information and usage | 
| `async_launched` | Background agent id, output file path, description of waiting for completion notification | 
| `teammate_spawned` | teammate id, name, team name | 
| `remote_launched` | remote task id, session URL, output file | 

The `completed` result of the synchronized sub-Agent directly becomes the `tool_result` of the current `Agent` tool call. The first tool result of the asynchronous sub-Agent is `async_launched`, and the final output is returned to the model through `<task-notification>`.
### Output fields 

| Status | Key Fields | Description | 
| ------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------ | 
| `completed` | `content`, `agentId`, `totalTokens`, `totalToolUseCount`, `totalDurationMs` | The final result of synchronizing sub-Agents; ordinary agents will come with `agentId` that can continue communication | 
| `async_launched` | `agentId`, `description`, `prompt`, `outputFile`, `canReadOutputFile` | The background agent has been launched; the final results arrive later via notifications | 
| `teammate_spawned` | `teammate_id`, `name`, `team_name` | teammate has been started, subsequent collaboration via mailbox / SendMessage | 
| `remote_launched` | `taskId`, `sessionUrl`, `outputFile`, `description` | remote CCR agent has been started, after completion, go to remote task notification | 

One-time built-in agents can omit the `agentId` / `SendMessage` hint and usage trailer to avoid inserting information that will not continue communication into the context. 

### outputSchema and tool_result 

The `outputSchema` of `AgentTool` describes the structured data returned by `call()`; `mapToolResultToToolResultBlockParam()` then maps these data into the `tool_result` text block actually seen by the model. When reading the code, you can read it in this order: 

```text 
AgentTool.call() 
-> return { data: { status, ...fields } } 
-> mapToolResultToToolResultBlockParam(data, toolUseID) 
-> ToolResultBlockParam 
-> query.ts put tool_result into the next round of messages 
```

Field highlights of the four types of results: 

| status | data field | model visible information | 
| ------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------ | 
| `completed` | `content`, `agentId`, usage, optional worktree result | The final output of the sub-Agent; if communication can continue, it will prompt that `SendMessage` is available | 
| `async_launched` | `agentId`, `description`, `prompt`, `outputFile`, `canReadOutputFile` | The background has been started; prompts to wait for notification or read output file | 
| `teammate_spawned` | `teammate_id`, `name`, `team_name` | teammate has joined the team; subsequent collaboration via mailbox / `SendMessage` | 
| `remote_launched` | `taskId`, `sessionUrl`, `outputFile`, `description` | remote task has been launched; local model is waiting for remote task notification | 

The `status` here is the main axis of result distribution. The failed, killed, and cleanup logic in catch / finally will not overwrite the returned synchronization `tool_result`; the background path will pass the final state to the main model through task state and notification.
## Life cycle state machine 

Treating the local sub-Agent as a task, the core status can be understood as follows: 

```text 
AgentTool.call() 
-> resolve route 
-> create optional worktree 
-> register foreground or register async task 
-> runAgent() 
-> completed / failed / killed 
-> tool_result or task-notification 
-> cleanup agent-scoped state 
``` 

The difference between synchronous and asynchronous is not whether `runAgent()` is called, but who waits for `runAgent()`: 

| Path | Who is waiting | When will the main model continue | 
| ------------------------------------------------ | ---------------------------------------------------------------- | -------------------------------------------------- | 
| Synchronize child Agent | `AgentTool.call()` itself `for await` child Agent message flow | After child Agent completes and returns `tool_result` | 
| Automatic backgroundization | The frontend waits first; after timeout, the frontend iterator exits, and the background lifecycle takes over | `AgentTool.call()` returns after `async_launched` | 
| Asynchronous sub-Agent | `runAsyncAgentLifecycle()` waits in the background | The main model continues immediately after receiving `async_launched` | 
| slash command fork normal interaction | `executeForkedSlashCommand()` etc. | after slash command is completed | 
| slash command fork assistant / kairos | fire-and-forget background runner, etc. | The main input process continues after startup, and is hidden after completion. Prompt backnote | 
| `runForkedAgent()` | Internal caller, etc. | Do not enter the main model tool_result protocol | 

So the shortest answer to "How does the synchronization sub-Agent wait for completion" is: the outer tool executor `await tool.call()`, and `AgentTool.call()` internally continues to consume the async iterator of `runAgent()` until the iterator `done` or an exception. 

## Comparison between waiting and re-injection methods 

There are three main mechanisms for returning sub-Agent results back to the main model: 

| Mechanism | Applicable path | Back-injection carrier | Whether to block the current turn | 
| ---------------------------------------- | -------------------------------------------------------- | ---------------------------------------- | ------------------ | 
| `tool_result` | Synchronize named sub-Agent | The tool result corresponding to the current `Agent` tool_use | Yes | 
| `<task-notification>` | Asynchronous/background local Agent, remote task, background shell, etc. | Unify task notification in command queue | No | 
| hidden prompt / command queue prompt | assistant / kairos's slash command fork, scheduled task, etc. | prompt message in queue | No | 

What is easily confusing here is that the background sub-Agent will not "rewrite" the original `tool_result` after it is completed. The original `Agent` tool call has returned `async_launched`; the final result is a new queue message, and the next round of models will decide how to integrate it after seeing it. 

## Progress, UI and Transcript 

The sub-Agent has three parallel "observable outputs": progress for the user, final results for the model, and transcript for system recovery. 

| Output | Synchronous path | Asynchronous path | Purpose | 
| -------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ | -------------------------------------------------- | 
| progress UI | `AgentTool.call()` forwards child Agent messages to the UI/SDK in real time when consuming them | `runAsyncAgentLifecycle()` updates task progress state | Let the user see what the child Agent is doing | 
| output file | The synchronization path will also be written to the side output to facilitate debugging and recovery | The main readable output of the background task, `async_launched` will return the path | The main model can be viewed with `Read(outputFile)` | 
| sidechain transcript | `runAgent()` records an independent message chain | It is also recorded and used for background recovery | `SendMessage`, resume, debug, and summary all depend on it | 
| task state | foreground task registry records synchronized running status | LocalAgentTask records running / completed / failed / killed | UI, `TaskOutput`, and notification anti-replication are all here | 

Synchronous progress is "displayed while running, and finally returns tool_result all at once". Asynchronous progress is "writing task state while running, and finally enqueuing task notification". The sidechain transcript is not equivalent to user-visible output; it is the message log used by the system to reconstruct the agent context. 

## Typical calling example 

### Synchronize named sub-Agent 

```json 
{ 
"description": "review parser bug", 
"prompt": "Review the parser changes and identify correctness risks.", 
"subagent_type": "code-reviewer" 
} 
``` 

Suitable for short tasks or tasks that require immediate results before continuing. The main model will wait until the child Agent outputs `completed`. 

### Backend named sub-Agent 

```json 
{ 
"description": "run regression suite", 
"prompt": "Run the regression tests and summarize failures.", 
"subagent_type": "general-purpose", 
"run_in_background": true 
} 
```
Perfect for long tasks. The main model first receives `async_launched`, which will contain `agentId` and `outputFile`. You can then wait for `<task-notification>`, or you can use `Read(outputFile)` to actively view the existing results. 

### Background Agent that can continue communication 

```json 
{ 
"description": "investigate flaky tests", 
"prompt": "Investigate flaky tests without editing files yet.", 
"subagent_type": "general-purpose", 
"name": "flaky-investigator", 
"run_in_background": true 
} 
``` 

You can use it later: 

```json 
{ 
"to": "flaky-investigator", 
"message": "Focus on the Windows-only failures and compare the last two runs.", 
"summary": "focus Windows failures" 
} 
``` 

If the time interval is long, it is preferable to use the raw `agentId` returned in `async_launched` or `completed`, because the `name` registry is a runtime state, and the sidechain transcript is more likely to be restored through `agentId`. 

### Worktree isolation implementation 

```json 
{ 
"description": "prototype parser fix", 
"prompt": "Implement a candidate fix in isolation and report the changed files.", 
"subagent_type": "general-purpose", 
"isolation": "worktree" 
} 
``` 

It is suitable for sub-Agents to modify the code without polluting the main workspace. After the main model gets the results, it needs to decide whether to merge, review or discard them based on the worktree path.
### AgentTool fork 

```json 
{ 
"description": "scan auth paths", 
"prompt": "Analyze the auth flow and report likely race conditions." 
} 
``` 

It is a fork only when the fork gate is enabled and `subagent_type` is omitted. The fork worker inherits the parent context and exact tools. The goal is parallel analysis and prompt cache reuse. It is not suitable for writing long-term stable professional roles. 

### Slash command fork 

```md 
--- 
name: audit-auth 
context: fork 
allowed-tools: 
- Read 
- Grep 
-Glob 
--- 

Audit the authentication flow and return only correctness risks. 
``` 

Result stream: 

```text 
User input /audit-auth 
-> processSlashCommand() 
-> executeForkedSlashCommand() 
-> runAgent() 
-> Normal interaction: command output goes directly back to the conversation 
-> assistant / kairos: After completion, the hidden prompt will join the queue and the next round of model consumption will 
``` 

## Troubleshooting Checklist
| Phenomenon | Priority Check | 
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | 
| The model cannot see the background results | Whether the task has enqueue notification; whether the queue is draining in the current mode; whether `task.notified` has been marked in advance by `TaskOutput(block=true)` | 
| `SendMessage` cannot find the target | Is `name` still in the registry; whether raw `agentId` can be used instead; whether sidechain transcript still exists | 
| The child Agent does not have a certain tool | Whether the `tools` of the agent definition are filtered out; whether the MCP server is connected; whether the fork path uses exact tools | 
| Sub-Agent permissions are different from expected | For ordinary agents, see `permissionMode`; teammate’s `mode` is not overridden by ordinary sub-Agent permissions; fork, see `bubble` | 
| fork is not triggered | whether the `FORK_SUBAGENT` feature is turned on; whether it is in coordinator or non-interactive; whether `subagent_type` is passed | 
| slash command has no fork | whether skill frontmatter writes `context: fork`; after loading, whether command.context is `fork` | 
| The worktree is not cleaned | Whether there are uncommitted changes; whether the hook-based worktree is hook-based; whether the cleanup is retained by the background task for post-notification processing | 
| `TaskOutput(block=true)` Wait | Whether the task really enters terminal status; if it is an async path, confirm whether the status update occurs before classifier / cleanup | 

##Which path to choose? 

| Requirements | Recommended paths | 
|-------------------------------------------------------- | -----------------------| 
| Requires specialized roles, limited context, clear toolset | Naming sub-Agents | 
| Requires long tasks but does not block the main model | Asynchronous sub-Agent | 
| Requires multiple workers to share full parent context and maximize prompt cache | AgentTool fork | 
| Need to execute a slash command/skill in isolation | slash command fork | 
| A lightweight forking inference is required inside the runtime | `runForkedAgent()` | 
| Need to isolate file changes | `isolation: "worktree"` | 

## Common misunderstandings 

| Misunderstanding | Correct understanding | 
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------- | 
| `mode` can override ordinary sub-Agent permissions | `mode` only affects the plan mode of teammate spawn; ordinary sub-Agent permissions come from the `permissionMode` of agent definition | 
| `SendMessage` can only be sent to the running agent | Queued when running, and will try to recover from the transcript background when stopped / evicted | 
| When the background agent is completed, the current tool_result will be directly changed | When the background agent is completed, it will go to the `<task-notification>` queue, and the next round of models will not see it | 
| fork is enabled by default | fork is disabled by default, requires `FORK_SUBAGENT` feature, and coordinator / non-interactive will be disabled | 
| fork is internal `runForkedAgent()` | AgentTool forks through Tool protocol; `runForkedAgent()` is internal runtime API | 
| `cwd` and `isolation: "worktree"` can be used together casually | Schema copywriting requires mutual exclusion; in implementation, `cwd` will give priority to overwriting the running directory, and the caller should avoid mixing | 
| Reading background output should give priority to `TaskOutput` | The current prompt suggests giving priority to `Read(output_file)`; `TaskOutput` retains compatibility and blocking waiting capabilities |
## Source code reading path 

If you want to verify a behavior from the source code, it is recommended to use different entrances according to the type of problem: 

| Questions | Reading Order | 
|--------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | 
| Why `Agent(...)` parameters take effect like this | schema of `AgentTool.tsx` -> `AgentTool.call()` parameter deconstruction -> routing rules | 
| Why do ordinary sub-Agents wait synchronously | `await tool.call()` of `toolExecution.ts` -> `AgentTool.call()` synchronization branch -> `runAgent()` | 
| Why the main model is notified when background completion | `registerAsyncAgent()` -> `runAsyncAgentLifecycle()` -> `enqueueAgentNotification()` -> queue processor |
 | Why `SendMessage` can restore the old agent | `SendMessageTool.ts` address resolution -> `queuePendingMessage()` / `resumeAgentBackground()` -> sidechain transcript |
 | why fork is not a normal agent | `isForkSubagentEnabled()` -> `FORK_AGENT` -> `buildForkedMessages()` -> `useExactTools` | 
| slash command fork why not use Tool protocol | skill load frontmatter -> `processSlashCommand()` -> `executeForkedSlashCommand()` | 
| Why there is no tool result in internal fork | `runForkedAgent()` -> `query()` -> The caller consumes `ForkedAgentResult` | 

## Maintenance Tips 

When updating child Agent behavior, these locations are first checked at the same time: 

| Documentation | Why it matters | 
| -------------------------------------------------- | -------------------------------------------------- | 
| `src/tools/AgentTool/AgentTool.tsx` | Routing, permissions, synchronization/asynchronous, and result mapping are all gathered here | 
| `src/tools/AgentTool/forkSubagent.ts` | Gate, FORK_AGENT, message structure of AgentTool fork | 
| `src/tools/AgentTool/runAgent.ts` | The real run loop of the sub-Agent | 
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | Background Agent status and notifications | 
| `src/utils/messageQueueManager.ts` | Unified command queue | 
| `src/utils/queueProcessor.ts` | REPL queue consumption rules | 
| `src/cli/print.ts` | headless / SDK queue consumption and background waiting | 
| `src/utils/processUserInput/processSlashCommand.tsx` | slash command fork | 
| `src/utils/forkedAgent.ts` | Internal `runForkedAgent()` | 
| `src/skills/loadSkillsDir.ts` | Analysis of `context: fork` in skill frontmatter |