# ULTRAPLAN — Enhanced Planning

> Feature Flag: `FEATURE_ULTRAPLAN=1`
> Implementation Status: Keyword detection, command processing, and CCR remote sessions are complete.
> Reference Count: 10

## I. Feature Overview

`ULTRAPLAN` automatically enters an enhanced planning mode when the "ultraplan" keyword is detected in user input. Compared to the standard plan mode, `ULTRAPLAN` provides deeper planning capabilities and supports both local and remote (CCR) execution.

### Triggers

| Method | Behavior |
| :--- | :--- |
| **Input with "ultraplan"** | Automatically redirects to the `/ultraplan` command. |
| **`/ultraplan` Command** | Executes the command directly. |
| **Rainbow Highlighting** | The "ultraplan" keyword in the input box is animated with rainbow colors. |

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Lines | Status |
| :--- | :--- | :--- | :--- |
| **Command Handler** | `src/commands/ultraplan.tsx` | 525 | **Complete** |
| **CCR Session** | `src/utils/ultraplan/ccrSession.ts` | 349 | **Complete** |
| **Keyword Detection**| `src/utils/ultraplan/keyword.ts` | 127 | **Complete** |
| **Embedded Prompt** | `src/utils/ultraplan/prompt.txt` | 1 | **Complete** |
| **REPL Dialogs** | `src/screens/REPL.tsx` | — | **Wired** |
| **Keyword Highlighting**| `src/components/PromptInput/PromptInput.tsx` | — | **Wired** |

### 2.2 Keyword Detection

File: `src/utils/ultraplan/keyword.ts` (127 lines)

`findUltraplanTriggerPositions(text)` includes intelligent filtering to avoid false positives:
- Excludes "ultraplan" within quotes.
- Excludes "ultraplan" within paths (e.g., `/path/to/ultraplan/`).
- Only detects the keyword outside of slash command contexts.
- `replaceUltraplanKeyword(text)` handles the removal of the keyword from the final prompt.

### 2.3 CCR Remote Session

File: `src/utils/ultraplan/ccrSession.ts` (349 lines)

The `ExitPlanModeScanner` class implements a complete event state machine:
- `pollForApprovedExitPlanMode()`: 3-second polling interval.
- Timeout handling and retries.
- Support for both remote (teleport) and local execution.

### 2.4 Data Flow

```
User enters "ultraplan to refactor this module"
         │
         ▼
processUserInput detects "ultraplan"
         │
         ▼
Redirects to /ultraplan command
         │
         ├── Local execution → EnterPlanMode
         │
         └── Remote execution → teleportToRemote → CCR Session
                 │
                 ▼
          ExitPlanModeScanner polls
                 │
                 ▼
          User approves remotely → Results received locally
```

## III. Missing Implementations

| Module | Description |
| :--- | :--- |
| `UltraplanChoiceDialog` / `UltraplanLaunchDialog` | Dialog components in `src/screens/REPL.tsx` for choosing between local and remote execution. |
| `src/commands/ultraplan/` | Empty directory, likely intended for unmerged subcommand structures. |

## IV. Key Design Decisions

1.  **Intelligent Keyword Filtering**: Excludes quotes and paths to prevent misfires.
2.  **Local/Remote Dual Modes**: Seamlessly supports both local plan mode and CCR remote sessions.
3.  **Rainbow Highlighting Feedback**: Uses a rainbow animation for the "ultraplan" keyword in the input box to signal special functionality.
4.  **`processUserInput` Integration**: Intercepts input early in the processing pipeline for seamless redirection.

## V. Usage

```bash
# Enable the feature
FEATURE_ULTRAPLAN=1 bun run dev

# Usage in REPL
> ultraplan refactor the authentication module
> /ultraplan
```

## VI. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/commands/ultraplan.tsx` | 525 | Slash command handler. |
| `src/utils/ultraplan/ccrSession.ts` | 349 | Management of CCR remote sessions. |
| `src/utils/ultraplan/keyword.ts` | 127 | Keyword detection and replacement. |
| `src/utils/ultraplan/prompt.txt` | 1 | Embedded system prompt. |
| `src/utils/processUserInput/processUserInput.ts:468` | — | Keyword redirection logic. |
| `src/components/PromptInput/PromptInput.tsx` | — | Rainbow highlighting implementation. |
