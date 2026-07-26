# Background Agent Selector — Unified Bottom Background Agent Switcher

> Feature Flag: None (Enabled by default)
> Implementation Status: Fully functional
> Dependencies: Reuse of existing `viewingAgentTaskId` / `enterTeammateView` / `exitTeammateView` mechanisms

## I. Feature Overview

The Background Agent Selector is a persistent status bar rendered below the PromptInput, listing all currently **backgrounded local_agent tasks** (including fork agents derived via `/fork` and sub-agents spawned by Task/AgentTools with `run_in_background: true`). Users can use the ↑/↓ arrow keys to switch focus between the `main` session and various agents. Pressing Enter replaces the REPL's main view with a real-time transcript of the selected agent; pressing Enter again while `main` is selected returns the user to the main conversation.

The entire mechanism fully reuses the official teammate transcript viewing infrastructure without introducing new view layers or data flows, only adding a new footer pill type.

### Core Features

- **Unified Entry Point**: `/fork` agents, sub-agents spawned by tasks, and all agents with `run_in_background: true` are displayed in the same bar.
- **In-place Switching**: When the prompt is empty, pressing ↓ overflows into the bottom selector. Use ↑/↓ to select a row, and Enter to switch the main view.
- **Real-time Status**: Each row displays the agent type, description, runtime duration, and token usage. Running agents are indicated by a green dot.
- **Keep-alive View**: Once an agent is finished, it is retained for a grace period (defined by `evictAfter`), allowing the user to review it.
- **Zero Interface Intrusion**: The selector is not rendered at all when there are zero tasks, taking up no screen height.
- **Coexistence with Legacy Dialog**: The `BackgroundTasksDialog` (opened with Shift+↓) retains its original behavior; the selector serves as an additional display and quick-switching tool.

## II. User Interaction

### Triggering

When there are any background agents, the selector automatically appears below the `bypass permissions on` line:

```
  claude-code | Opus 4.7 (1M context) | ctx:4%
  ▶▶ bypass permissions on (shift+tab to cycle)

  ○ main                                    ↑/↓ to select · Enter to view
  ● Explore  Research src/hooks              23s · ↓ 10.9k tokens
  ○ Explore  Research src/components         22s · ↓  9.5k tokens
  ○ Explore  Research src/utils              21s · ↓ 13.6k tokens
```

### Keyboard Routing

| Position / State | Key | Behavior |
| :--- | :--- | :--- |
| PromptInput not empty | ↑/↓ | Cursor movement / History navigation (unchanged). |
| PromptInput empty + at bottom of history | ↓ | Focus moves down to the selector, highlighting `● main`. |
| Selector focused (`footerSelection === 'bg_agent'`) | ↓ | Highlight moves down: -1 → 0 → ... → N-1. |
| Selector focused | ↑ | Highlight moves up; at `main`, ↑ returns focus to PromptInput. |
| Selector focused | Enter | `-1` → `exitTeammateView`; `>=0` → `enterTeammateView(agentId)`. Focus remains on the pill. |
| Selector focused | Esc | `footer:clearSelection`, focus returns to PromptInput. |

### Visual Rules

- `● main` / `● <agent>`: Indicates the row currently being **viewed** (pointed to by `viewingAgentTaskId`) or **focused by the cursor** (when the pill is focused, the cursor takes precedence).
- Running agents: The dot is rendered in the `success` color (green), aligning with the state semantics of `BackgroundTasksDialog`.
- The top-right hint changes based on state:
  - Pill focused: `↑/↓ to select · Enter to view`
  - Selected running agent: `shift+↓ to manage · x to stop`
  - Selected terminal agent: `shift+↓ to manage · x to clear`
  - No agent selected: `shift+↓ to manage background agents`

## III. Implementation Architecture

### 3.1 Data Layer: `useBackgroundAgentTasks`

File: `src/hooks/useBackgroundAgentTasks.ts`

Wraps and filters `useAppState(s => s.tasks)`:

```ts
export function useBackgroundAgentTasks(): LocalAgentTaskState[] {
  const tasks = useAppState(s => s.tasks)
  return useMemo(() => {
    const now = Date.now()
    return Object.values(tasks)
      .filter(isLocalAgentTask)
      .filter(t => t.agentType !== 'main-session')
      .filter(t => t.isBackgrounded !== false)
      .filter(t => t.evictAfter === undefined || t.evictAfter > now)
      .sort((a, b) => a.startTime - b.startTime)
  }, [tasks])
}
```

Both `/fork` and `AgentTool` with `run_in_background: true` use `registerAsyncAgent → runAsyncAgentLifecycle` internally, ultimately writing to the same `appState.tasks` Map. This hook is the sole source of truth, consumed by both the Selector and the `bgAgentList` in PromptInput.

### 3.2 State Layer: New Fields

File: `src/state/AppStateStore.ts`

```ts
export type FooterItem =
  | 'tasks' | 'tmux' | 'bagel' | 'teams' | 'bridge' | 'companion'
  | 'bg_agent'   // ← Added

export type AppState = DeepImmutable<{
  // ...
  selectedBgAgentIndex: number  // -1 = main, 0..N-1 = selected agent
}>
```

- `'bg_agent'` is added as a `FooterItem` to the footer pill system, utilizing existing `footer:up` / `footer:down` / `footer:openSelected` keybinding routing.
- `selectedBgAgentIndex` records the cursor position within the selector, independent of `viewingAgentTaskId` (which tracks "what is currently being viewed"). It cannot be derived from `viewingAgentTaskId` because the cursor remains on the pill for continued navigation after Enter is pressed, even as the viewed target changes.

### 3.3 Keyboard Routing: PromptInput Footer Pill Branch

File: `src/components/PromptInput/PromptInput.tsx`

1.  **`bg_agent` added to `footerItems[0]`**: Ensures that when the prompt overflows via ↓ (`handleHistoryDown` → `selectFooterItem(footerItems[0])`), focus enters the selector directly rather than other pills like `tasks`.
2.  **`footer:up` branch**: If `bgAgentSelected` and `selectedBgAgentIndex > -1`, it decrements; at -1, it calls `selectFooterItem(null)` to exit the pill.
3.  **`footer:down` branch**: Decrements if `selectedBgAgentIndex < bgAgentList.length - 1`, clamped at the end.
4.  **`footer:openSelected` branch**: `index === -1` → `exitTeammateView`; otherwise `enterTeammateView(bgAgentList[i].agentId)`. **Does not clear pill focus**, leaving the cursor on the selector for continued navigation.
5.  **`selectFooterItem('bg_agent')`**: Resets `selectedBgAgentIndex = -1` (focusing on `main`) upon entering the pill.

### 3.4 Rendering Layer: `BackgroundAgentSelector`

File: `src/components/tasks/BackgroundAgentSelector.tsx`

A display-only component that does not subscribe to keyboard events:

```tsx
const tasks = useBackgroundAgentTasks()
const viewingId = useAppState(s => s.viewingAgentTaskId)
const footerSelection = useAppState(s => s.footerSelection)
const selectedBgIndex = useAppState(s => s.selectedBgAgentIndex)

if (tasks.length === 0) return null

const pillFocused = footerSelection === 'bg_agent'
const highlightedId = pillFocused
  ? (selectedBgIndex === -1 ? null : tasks[selectedBgIndex]?.agentId ?? null)
  : (viewingId ?? null)
```

**Highlight Derivation Rule**: When the pill is focused, follow `selectedBgAgentIndex`; otherwise, mirror `viewingAgentTaskId`. This ensures that the selector correctly reflects changes when a user switches views via the Shift+↓ Dialog or other `enterTeammateView` methods.

### 3.5 Main View Switching: Reusing `viewingAgentTaskId`

The main part of `REPL.tsx` still reuses the existing viewing logic:

```ts
const viewedTask = viewingAgentTaskId ? tasks[viewingAgentTaskId] : undefined
const viewedAgentTask = ... (isLocalAgentTask(viewedTask) ? viewedTask : undefined)
const displayedMessages = viewedAgentTask ? displayedAgentMessages : messages
```

When `enterTeammateView(agentId)` sets `viewingAgentTaskId` to the ID of a `local_agent`:

- `viewedAgentTask` resolves to that agent.
- `displayedMessages` switches to the agent's messages.
- The entire set of components (message list, spinner, unseen divider, etc.) automatically re-renders using the agent's transcript.
- The main conversation flow is "paused" (not destroyed; it remains in place when returning to `main`).

`enterTeammateView` is also responsible for: setting `retain: true` to prevent eviction, clearing `evictAfter`, and triggering a disk bootstrap to load the full transcript from `agent-<id>.jsonl` into `task.messages`.

#### Fork Agent Prompt Normalization

The transcript for a `/fork` agent differs from a normal sub-agent: it inherits the context of the main agent, and its true initial message state looks like:

```text
...parent messages
assistant([...tool_use])
user([tool_result..., text("<fork-boilerplate>...Your directive: <prompt>")])
...fork live messages
```

The prompt text here is mixed with multiple blocks in the user message (e.g., `tool_result`, `text`). The message rendering pipeline prioritizes this user message as tool-result plumbing, making the user's prompt within the `<fork-boilerplate>` inconsistently visible. To ensure the user's fork prompt is always visible when switching to a fork agent, `REPL.tsx` performs display-layer normalization for the fork view:

1.  Only enabled when `viewedAgentTask.agentType === 'fork'`; does not affect normal Explore/Task sub-agents.
2.  Identifies the carrier message containing `<fork-boilerplate>` from the raw messages.
3.  Strips the boilerplate text block from the carrier message but retains `tool_result` blocks to avoid breaking the connection with the parent assistant's `tool_use`.
4.  Forcefully inserts an independent `createUserMessage({ content: viewedAgentTask.prompt })` as the visible user prompt.
5.  Prioritizes insertion after the boilerplate carrier; if the sidechain bootstrap hasn't read the carrier yet, it is inserted after the last inherited `assistant tool_use` to ensure the prompt follows the main context rather than appearing at the top of the view.

This normalization only affects the `displayedAgentMessages` used for UI display; it does not write back to `task.messages` or change the fork transcript sent to the model.

### 3.6 Lifecycle

Reuses existing official mechanisms:

- **Running**: The `isBackgroundTask()` predicate is true; listed in the selector.
- **Completed / Failed / Killed**: `completeAgentTask` / `failAgentTask` / `killAsyncAgent` set the `status` to terminal.
- **Exit after Visit**: `exitTeammateView` calls `release(task)`—clears `retain`, clears `messages`, and sets `evictAfter = now + PANEL_GRACE_MS (30s)` for terminal states.
- **evictAfter Expiration**: Naturally excluded during `useBackgroundAgentTasks` filtering; the selector row disappears.
- **Manual Clear**: `stopOrDismissAgent(taskId)` sets `evictAfter = 0`, causing immediate removal.

## IV. Design Decisions

1.  **Single Data Source**: `useBackgroundAgentTasks` is the sole filtering point, reused by PromptInput to avoid scattered filtering logic.
2.  **Focus Retention on Pill**: Entering a view does not release focus from the pill, allowing for continuous navigation with ↑/↓, mirroring the official experience.
3.  **`bg_agent` placed in `footerItems[0]`**: Ensures ↓ overflow enters the selector directly.
4.  **Selector does not subscribe to keyboard**: All key routing is centralized in PromptInput's `footer:*` branches to avoid conflicts between `useInput` in the selector and PromptInput.
5.  **`selectedBgAgentIndex` stored in AppState**: The selector and PromptInput are in different subtrees, necessitating a global field for coordination; this value cannot be derived from `viewingAgentTaskId`.
6.  **Coexistence with `BackgroundTasksDialog`**: Shift+↓ behavior remains unchanged; the selector is a complementary quick-entry point. The Dialog still manages task types not shown in the selector, such as shell, workflow, and monitor_mcp.
7.  **Display-layer Fallback for Fork Prompt**: The fork prompt does not rely on its own boilerplate rendering; it is synthesized as an independent user message within `displayedAgentMessages`. Normal sub-agents do not use this branch to avoid duplicate prompts.

## V. Key API Reuse

| Existing Capability | How Selector Uses It |
| :--- | :--- |
| `AppState.tasks` | Single source of truth; no need for file watchers or JSONL output subscriptions. |
| `registerAsyncAgent` | Shared by `/fork` and `AgentTool`; selector is agnostic of the source. |
| `enterTeammateView(id)` | Called on Enter; handles retention and disk bootstrap. |
| `exitTeammateView` | Called on Enter when `main` is selected. |
| `release(task)` + `PANEL_GRACE_MS` | 30s keep-alive automatically applies to the selector. |
| `useElapsedTime` | Displays duration for each row; interval stops automatically for non-running tasks. |
| `formatTokens` (`utils/format.ts`) | 1k abbreviation for token counts. |
| `footer:up` / `footer:down` / `footer:openSelected` keybinding | Reuses Footer context for keyboard routing. |

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `src/hooks/useBackgroundAgentTasks.ts` | Data filtering hook (backgrounded local_agent + `evictAfter` filtering + `startTime` sorting). |
| `src/components/tasks/BackgroundAgentSelector.tsx` | Bottom selector UI, display-only. |
| `src/components/PromptInput/PromptInput.tsx` | Added `'bg_agent'` footer pill and corresponding `footer:up/down/openSelected` branches. |
| `src/state/AppStateStore.ts` | Added `'bg_agent'` to `FooterItem` and added the `selectedBgAgentIndex` field. |
| `src/main.tsx` | Initializes `selectedBgAgentIndex: -1` in `getDefaultAppState`. |
| `src/screens/REPL.tsx` | Mounts `<BackgroundAgentSelector />` after PromptInput + SessionBackgroundHint; handles main agent view switching and fork transcript prompt normalization. |
| `src/components/messages/AssistantToolUseMessage.tsx` | Added `defaultCollapsed?: boolean` prop for future tool block collapsing in detail views. |
| `src/components/messages/UserTextMessage.tsx` | Identifies `<fork-boilerplate>` for the dedicated fork renderer. |
| `src/components/messages/UserForkBoilerplateMessage.tsx` | Collapses fork boilerplate text into a pure user prompt; serves as a compatibility path for in-place rendering. |

## VII. Known Limitations

- `Date.now()` within `useMemo` in `useBackgroundAgentTasks` is frozen when triggered by `[tasks]`. If no new task change events occur for a long time, terminal agents whose grace period has expired might not disappear immediately until the next task change. This is typically unnoticeable in normal usage (where messages are continuously generated) and does not currently warrant an additional interval.
- The selector currently does not handle types like Shell Task, Workflow, or Monitor MCP; these are still managed via `BackgroundTasksDialog` (Shift+↓).
- The `defaultCollapsed` prop in `AssistantToolUseMessage` currently has no callers passing a value; it is reserved as an extension point for "default collapsing of tool blocks in agent detail views."
