# COORDINATOR_MODE — Multi-Agent Orchestration

> Feature Flag: `FEATURE_COORDINATOR_MODE=1` + Environment Variable `CLAUDE_CODE_COORDINATOR_MODE=1`
> Implementation Status: Coordinator is fully functional; worker agents use the generic `AgentTool` worker.
> Reference Count: 32

## I. Feature Overview

`COORDINATOR_MODE` transforms the CLI into an "Orchestrator" role. The Orchestrator does not directly manipulate files; instead, it dispatches tasks to multiple worker agents in parallel using the `AgentTool`. This mode is ideal for breaking down large tasks, parallel research, or separating implementation from verification.

### Core Constraints

- **Orchestrator tools are limited to**: `Agent` (dispatching workers), `SendMessage` (continuing workers), and `TaskStop` (stopping workers).
- **Worker agents** can use all standard tools (Bash, Read, Edit, etc.), MCP tools, and Skill tools.
- Every message from the Orchestrator is intended for the user; worker results arrive in the form of `<task-notification>` XML.

## II. User Interaction

### Enabling Coordinator Mode

```bash
FEATURE_COORDINATOR_MODE=1 CLAUDE_CODE_COORDINATOR_MODE=1 bun run dev
```

Both the feature flag and the environment variable must be set. The `CLAUDE_CODE_COORDINATOR_MODE` can be automatically toggled during session restoration (`matchSessionMode`).

### Typical Workflow

```
User: "Fix the null pointer in the auth module."

Orchestrator:
  1. Dispatches two workers in parallel:
     - Agent({ description: "Investigate auth bug", prompt: "..." })
     - Agent({ description: "Research auth tests", prompt: "..." })

  2. Receives <task-notification>:
     - Worker A: "Found null pointer at validate.ts:42."
     - Worker B: "Test coverage analysis..."

  3. Synthesizes findings and continues Worker A:
     - SendMessage({ to: "agent-a1b", message: "Fix validate.ts:42..." })

  4. Receives fix results and dispatches verification:
     - Agent({ description: "Verify fix", prompt: "..." })
```

## III. Implementation Architecture

### 3.1 Mode Detection

File: `src/coordinator/coordinatorMode.ts:36-41`

```ts
export function isCoordinatorMode(): boolean {
  return feature('COORDINATOR_MODE') &&
    isEnvTruthy(process.env.CLAUDE_CODE_COORDINATOR_MODE)
}
```

### 3.2 Session Mode Recovery

`matchSessionMode(sessionMode)` checks the stored mode when restoring an old session. If the current environment variable is inconsistent with the stored mode, it automatically flips the environment variable. This prevents restoring an orchestration session in standard mode (or vice versa).

### 3.3 Worker Toolset

`getCoordinatorUserContext()` informs the Orchestrator of the tools available to workers:

- **Standard Mode**: `ASYNC_AGENT_ALLOWED_TOOLS` excludes internal tools (`TeamCreate`, `TeamDelete`, `SendMessage`, `SyntheticOutput`).
- **Simple Mode** (`CLAUDE_CODE_SIMPLE=1`): Limited to Bash, Read, and Edit.
- **MCP Tools**: Lists the names of connected MCP servers.
- **Scratchpad**: If the GrowthBook `tengu_scratch` flag is enabled, a shared scratchpad directory is provided for cross-worker use.

### 3.4 System Prompt

File: `src/coordinator/coordinatorMode.ts:111-369`

The Orchestrator system prompt (`getCoordinatorSystemPrompt()`) is approximately 370 lines and includes:

| Section | Content |
| :--- | :--- |
| **1. Your Role** | Definition of Orchestrator responsibilities. |
| **2. Your Tools** | Instructions for using `Agent`, `SendMessage`, and `TaskStop`. |
| **3. Workers** | Worker capabilities and limitations. |
| **4. Task Workflow** | Research → Synthesis → Implementation → Verification flow. |
| **5. Writing Worker Prompts** | Guide for writing self-contained prompts with good/bad examples. |
| **6. Example Session** | A complete example conversation. |

### 3.5 Worker Agent

File: `src/coordinator/workerAgent.ts`

Currently a stub. Workers actually utilize the generic `AgentTool` with the `worker` `subagent_type`.

### 3.6 Data Flow

```
User Message
      │
      ▼
Orchestrator REPL (Restricted Toolset)
      │
      ├──→ Agent({ subagent_type: "worker", prompt: "..." })
      │         │
      │         ▼
      │    Worker Agent (Full Toolset)
      │    ├── Execute tasks (Bash/Read/Edit/...)
      │    └── Return <task-notification>
      │
      ├──→ SendMessage({ to: "agent-id", message: "..." })
      │         │
      │         ▼
      │    Continue an existing Worker
      │
      └──→ TaskStop({ task_id: "agent-id" })
                │
                ▼
           Stop a running Worker
```

## IV. Key Design Decisions

1.  **Dual-Switch Design**: Feature flags control code availability, while environment variables control actual activation. This allows inclusion at build time without mandatory default enablement.
2.  **Restricted Orchestrator**: Limiting the Orchestrator to dispatch-related tools ensures focus on orchestration rather than execution.
3.  **Self-Contained Prompts**: Workers cannot see the Orchestrator's conversation history; each worker's prompt must be fully self-contained.
4.  **Parallelism First**: The system prompt emphasizes "Parallelism is your superpower," encouraging the dispatch of independent tasks in parallel.
5.  **Synthesis Over Forwarding**: Orchestrators must synthesize worker findings into specific implementation instructions rather than lazy delegation (e.g., avoiding "based on your findings").
6.  **Optional Shared Scratchpad**: A shared directory (gated by GrowthBook) allows workers to persist and share knowledge.

## V. Usage

```bash
# Basic activation
FEATURE_COORDINATOR_MODE=1 CLAUDE_CODE_COORDINATOR_MODE=1 bun run dev

# Combined with Fork Subagent
FEATURE_COORDINATOR_MODE=1 FEATURE_FORK_SUBAGENT=1 \
CLAUDE_CODE_COORDINATOR_MODE=1 bun run dev

# Simple Mode (Workers limited to Bash/Read/Edit)
FEATURE_COORDINATOR_MODE=1 CLAUDE_CODE_COORDINATOR_MODE=1 \
CLAUDE_CODE_SIMPLE=1 bun run dev
```

## VI. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/coordinator/coordinatorMode.ts` | 370 | Mode detection, system prompts, and user context. |
| `src/coordinator/workerAgent.ts` | — | Worker agent definition (stub). |
| `src/constants/tools.ts` | — | `ASYNC_AGENT_ALLOWED_TOOLS` tool whitelist. |
