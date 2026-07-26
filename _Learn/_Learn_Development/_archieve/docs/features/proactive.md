# PROACTIVE — Autonomous Mode

> Feature Flag: `FEATURE_PROACTIVE=1` (Shares functionality with `FEATURE_KAIROS=1`)
> Implementation Status: Core loop and `SleepTool` are implemented; some peripheral documentation is still being updated.
> Reference Count: 37

## I. Feature Overview

`PROACTIVE` implements a tick-driven autonomous agent. The CLI continues to work even when the user is not providing input: it wakes up at scheduled intervals to execute tasks and manages its own rhythm using the `SleepTool`. This is ideal for long-running background tasks (e.g., waiting for CI, monitoring file changes, periodic checks).

### Relationship with KAIROS

All code checks use `feature('PROACTIVE') || feature('KAIROS')`, meaning:
- Enabling `FEATURE_PROACTIVE=1` alone grants proactive capabilities.
- Enabling `FEATURE_KAIROS=1` alone automatically grants proactive capabilities.
- Enabling both results in the same effect (they are not redundant).

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status | Description |
| :--- | :--- | :--- | :--- |
| **Core Logic** | `src/proactive/index.ts` | **Implemented** | `activateProactive()`, `deactivateProactive()`, `pause/resume`, and `nextTickAt` scheduling state. |
| **SleepTool Prompt** | `src/tools/SleepTool/prompt.ts` | **Complete** | Tool prompt definition (Tool name: `Sleep`). |
| **Command Registration**| `src/commands.ts:62-65` | **Wired** | Dynamically loads `./commands/proactive.js`. |
| **Tool Registration** | `src/tools.ts:26-28` | **Wired** | Dynamic loading for `SleepTool`. |
| **REPL Integration** | `src/screens/REPL.tsx` | **Implemented** | Tick-driven heartbeats, `standby`/`sleeping` states, footer UI, and bridge automation metadata reporting. |
| **System Prompts** | `src/constants/prompts.ts:864-918`| **Complete** | Autonomous work behavioral directives (~55 lines of detailed prompt). |
| **Remote State Mirror** | `src/utils/sessionState.ts` | **Implemented** | Exposes `automation_state` metadata to remote-control/CCR. |

### 2.2 System Prompt Content

The autonomous work instructions injected by `getProactiveSection()` include:

| Section | Content |
| :--- | :--- |
| **Tick-Driven** | `<tick_tag>` prompts keep the agent alive, including the user's local time. |
| **Rhythm Control** | `SleepTool` controls wait intervals; prompt caches expire after 5 minutes. |
| **No-Op Rules** | **Must** call `Sleep` when there is nothing to do; forbidden from outputting "still waiting" text. |
| **Initial Wake-up** | Brief greeting; waits for direction (does not explore proactively). |
| **Subsequent Wake-ups**| Searches for useful work: investigation, verification, or checks (without spamming the user). |
| **Action Bias** | Read files, search code, and commit without needing to ask permission. |
| **Terminal Focus** | `terminalFocus` field adjusts the level of autonomy. |

### 2.3 Data Flow

```
activateProactive()
      │
      ▼
Tick Scheduler Starts
      │
      ├── Periodically generates <tick_tag> messages
      │   ├── Includes user's current local time
      │   └── Injected into the conversation stream (sessionStorage)
      │
      ▼
Model processes the tick
      │
      ├── Work available → Executes via tools → May Sleep again
      └── No work available → Must call SleepTool
      │
      ▼
SleepTool waits
      │
      ├── User inserts new work / Command in queue → Immediate wake-up
      ├── Proactive mode disabled → Immediate interruption
      └── Reports `automation_state = sleeping` to remote surfaces upon dormancy
      │
      ▼
Next tick arrives
```

## III. Current Behavior Supplements

- **`standby`**: Proactive mode is enabled, no turn is currently active, and the next tick has been scheduled.
- **`sleeping`**: The model has explicitly called `SleepTool` to enter a wait window.
- **Remote surfaces** (Remote-control/CCR) receive these states via `external_metadata.automation_state`, which is used for the Autopilot status display in the Web UI.
- **`SleepTool`** is no longer a pure timer; it wakes up early if new work appears in the shared command queue.

## IV. Key Design Decisions

1.  **Tick-Driven**: The model controls its own wake-up frequency via `SleepTool` rather than relying on external event pushing.
2.  **Mandatory Sleep for No-Ops**: Prevents "still waiting" filler messages from wasting turns and tokens.
3.  **Prompt Cache Considerations**: The `SleepTool` prompt mentions the 5-minute cache expiration, suggesting a balance for wait times.
4.  **Terminal Focus Awareness**: The model adjusts its autonomy based on whether the user is viewing the terminal.

## V. Usage

```bash
# Enable proactive mode directly
FEATURE_PROACTIVE=1 bun run dev

# Enable indirectly via KAIROS
FEATURE_KAIROS=1 bun run dev

# Combined usage
FEATURE_PROACTIVE=1 FEATURE_KAIROS=1 FEATURE_KAIROS_BRIEF=1 bun run dev
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `src/proactive/index.ts` | Core logic and `next-tick` state management. |
| `src/tools/SleepTool/prompt.ts` | `SleepTool` tool prompt. |
| `src/tools/SleepTool/SleepTool.ts` | Execution logic for dormancy/wake-up. |
| `src/constants/prompts.ts:864-918` | Autonomous work system prompts. |
| `src/screens/REPL.tsx` | REPL tick integration and automation state reporting. |
| `src/utils/sessionStorage.ts:4892-4912` | Tick message injection logic. |
| `src/utils/sessionState.ts` | Mirroring metadata for bridge/CCR. |
| `src/components/PromptInput/PromptInputFooterLeftSide.tsx` | Footer UI status display. |
