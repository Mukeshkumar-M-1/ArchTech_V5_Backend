# KAIROS — Persistent Assistant Mode

> Feature Flag: `FEATURE_KAIROS=1` (and its sub-features)
> Implementation Status: Core framework is complete; some sub-modules are stubs; proactive/sleep rhythm control is functional.
> Reference Count: 154 (the largest in the entire repository)

## I. Feature Overview

`KAIROS` transforms Claude Code from a simple request-response tool into a "Persistent Assistant." When enabled, the CLI runs continuously in the background and supports:

- **Persistent Bridge Sessions**: Cross-terminal session reuse via Anthropic OAuth connection to `claude.ai`.
- **Background Task Execution**: Continues working after the user leaves the terminal (in conjunction with the `PROACTIVE` feature).
- **Mobile Push Notifications**: Alerts the user via push notifications when tasks are complete or input is required (with `KAIROS_PUSH_NOTIFICATION`).
- **Daily Memory Logs**: Automatically records and reviews work progress (with `KAIROS_DREAM`).
- **External Channel Message Integration**: Slack, Discord, or Telegram messages forwarded to the CLI (with `KAIROS_CHANNELS`).
- **Structured Brief Output**: Outputs structured messages via `BriefTool` (with `KAIROS_BRIEF`).

### Sub-Feature Dependencies

```
KAIROS (Master Switch)
├── KAIROS_BRIEF (BriefTool, structured output)
├── KAIROS_CHANNELS (External channel messages)
├── KAIROS_PUSH_NOTIFICATION (Mobile push)
├── KAIROS_GITHUB_WEBHOOKS (GitHub PR webhooks)
└── KAIROS_DREAM (Memory distillation)
```

> [!IMPORTANT]
> `PROACTIVE` is tightly coupled with `KAIROS`. Code checks often use `feature('PROACTIVE') || feature('KAIROS')`, meaning the CLI automatically gains proactive capabilities when `KAIROS` is enabled.

## II. System Prompts

`KAIROS` injects two major sections into the system prompt:

### 2.1 Brief Section (`getBriefSection`)

File: `src/constants/prompts.ts:847-858`

Injected when `feature('KAIROS') || feature('KAIROS_BRIEF')` is true. Contains instructions for the structured message output of the Brief tool (`SendUserMessage`). Note that the `/brief` toggle and `--brief` flag only control display filtering and do not alter the model's behavior.

### 2.2 Proactive/Autonomous Work Section (`getProactiveSection`)

File: `src/constants/prompts.ts:864-918`

Injected when `feature('PROACTIVE') || feature('KAIROS')` is true and `isProactiveActive()` is true. Core behavioral directives include:

- **Tick-Driven**: Remains active via `<tick_tag>` prompts, each containing the user's current local time.
- **Rhythm Control**: Uses the `SleepTool` to manage wait intervals (as prompt caches expire after 5 minutes).
- **Mandatory Sleep for No-Ops**: Forbidden from outputting "still waiting" filler text (to avoid wasting tokens and turns).
- **Action Bias**: Read files, search code, modify files, and commit—all without needing explicit user permission.
- **Terminal Focus Awareness**: A `terminalFocus` field indicates whether the user is viewing the terminal.
    - **Unfocused**: Encourages high levels of autonomous action.
    - **Focused**: Encourages more collaborative behavior and presenting choices to the user.

## III. Implementation Architecture

### 3.1 Core Modules

| Module | File | Status | Responsibility |
| :--- | :--- | :--- | :--- |
| **Assistant Entry** | `src/assistant/index.ts` | **Stub** | `isAssistantMode()`, `initializeAssistantTeam()`. |
| **Session Discovery** | `src/assistant/sessionDiscovery.ts` | **Stub** | Discover available bridge sessions. |
| **Session History** | `src/assistant/sessionHistory.ts` | **Stub** | Persistent session history. |
| **Gate Control** | `src/assistant/gate.ts` | **Stub** | GrowthBook gating checks. |
| **Session Selector** | `src/assistant/AssistantSessionChooser.ts` | **Stub** | UI for selecting sessions. |
| **BriefTool** | `src/tools/BriefTool/` | **Stub** | Structured message output tool. |
| **Channel Notification**| `src/services/mcp/channelNotification.ts` | **Stub** | External channel message integration. |
| **Dream Task** | `src/components/tasks/src/tasks/DreamTask/` | **Stub** | Memory distillation task. |
| **Memory Directory** | `src/memdir/memdir.ts` | **Stub** | Memory directory management. |

### 3.2 SleepTool (Shared with Proactive)

File: `src/tools/SleepTool/prompt.ts`

The `SleepTool` is the core of rhythm control for `KAIROS`/`Proactive`. The tool description teaches the model the concept of "dormancy":
- **Tool Name**: `Sleep`
- **Function**: Wait for a specified duration before responding to the next tick prompt; can be woken early if new work appears in the queue or if proactive mode is disabled.
- **Heartbeat Mechanism**: Works with `<tick_tag>` to implement heartbeat-style autonomous work.
- **State Reporting**: Remote control interfaces see either `standby` or `sleeping` via `automation_state`.

### 3.3 Bridge Integration

`KAIROS` connects to `claude.ai` servers via Bridge Mode (`src/bridge/`):

```
claude.ai web/app
      │
      ▼ (HTTPS long-poll)
┌──────────────────────┐
│  Bridge API Client   │  src/bridge/bridgeApi.ts
│  (register/poll/     │
│   acknowledge)       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Session Runner      │  src/bridge/sessionRunner.ts
│  (Create/Restore REPL)│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  REPL + Proactive    │  Tick-driven autonomous work
│  Tick Loop           │
└──────────────────────┘
```

### 3.4 Data Flow

```
User sends message from claude.ai
         │
         ▼
Bridge pollForWork() receives WorkResponse
         │
         ▼
acknowledgeWork() confirms receipt
         │
         ▼
sessionRunner creates or restores a REPL session
         │
         ▼
User message is injected into the REPL conversation
         │
         ▼
Model processes → Tool call → BriefTool structured output
         │
         ▼
Results sent back to claude.ai via Bridge API
```

## IV. Key Design Decisions

1.  **Tick-Driven vs. Event-Driven**: The model controls its own wake-up frequency via `SleepTool` rather than external event pushing. This simplifies the architecture but increases API call overhead.
2.  **KAIROS ⊃ PROACTIVE**: All proactive checks include `KAIROS`, so enabling both flags is unnecessary.
3.  **Brief Display/Behavior Separation**: The `/brief` toggle only filters the UI; the model can always use `BriefTool`.
4.  **Terminal Focus Awareness**: The model automatically adjusts its level of autonomy based on whether the user is focused on the terminal.
5.  **GrowthBook Gating**: Certain features (e.g., push notifications) require server-side GrowthBook switches even if the feature flag is enabled locally.

## V. Usage

```bash
# Minimal Enablement (Persistent Assistant + Brief)
FEATURE_KAIROS=1 FEATURE_KAIROS_BRIEF=1 bun run dev

# Full Feature Enablement
FEATURE_KAIROS=1 \
FEATURE_KAIROS_BRIEF=1 \
FEATURE_KAIROS_CHANNELS=1 \
FEATURE_KAIROS_PUSH_NOTIFICATION=1 \
FEATURE_KAIROS_GITHUB_WEBHOOKS=1 \
FEATURE_PROACTIVE=1 \
bun run dev

# Combined with Token Budget
FEATURE_KAIROS=1 FEATURE_TOKEN_BUDGET=1 bun run dev
```

## VI. External Dependencies

- **Anthropic OAuth**: Requires logging in with a `claude.ai` subscription (not an API key).
- **GrowthBook**: Server-side feature gating (e.g., `tengu_ccr_bridge`).
- **Bridge API**: Uses `/v1/environments/bridge` series of endpoints.

## VII. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/assistant/index.ts` | 9 | Assistant module entry (stub). |
| `src/assistant/gate.ts` | — | GrowthBook gating (stub). |
| `src/assistant/sessionDiscovery.ts` | — | Session discovery (stub). |
| `src/assistant/sessionHistory.ts` | — | Session history persistence (stub). |
| `src/assistant/AssistantSessionChooser.ts` | — | Session selection UI (stub). |
| `src/tools/BriefTool/` | — | `BriefTool` implementation (stub). |
| `src/tools/SleepTool/prompt.ts` | ~30 | `SleepTool` tool prompt. |
| `src/tools/SleepTool/SleepTool.ts` | ~200 | Dormancy/Wake-up and automation metadata. |
| `src/services/mcp/channelNotification.ts`| 5 | External channel message integration (stub). |
| `src/memdir/memdir.ts` | — | Memory directory management (stub). |
| `src/constants/prompts.ts:557,847-918` | 72 | System prompt injection logic. |
| `src/components/tasks/src/tasks/DreamTask/`| 3 | Memory distillation task (stub). |
| `src/proactive/index.ts` | — | Proactive core (shared with KAIROS). |
| `src/utils/sessionState.ts` | — | Exposing automation state to bridge/CCR. |
