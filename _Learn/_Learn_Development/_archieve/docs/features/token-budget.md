# TOKEN_BUDGET — Token Budget Autonomous Persistence Mode

> Feature Flag: `FEATURE_TOKEN_BUDGET=1`
> Implementation Status: Fully operational.

## I. Feature Overview

`TOKEN_BUDGET` allows users to specify an output token budget target in their prompt (e.g., `+500k`, `spend 2M tokens`). Claude will then **automatically continue working** until the target is met, without requiring the user to repeatedly press Enter to continue the session.

This is ideal for long-running tasks such as large-scale refactors, batch modifications, or extensive code generation that require multiple tool call turns.

## II. User Interaction

### Syntax

| Format | Example | Description |
| :--- | :--- | :--- |
| **Shorthand (Start)** | `+500k` | Prefix at the start of the input. |
| **Shorthand (End)** | `refactor this module +2m` | Suffix at the end of the input. |
| **Full Syntax** | `spend 2M tokens` or `use 1B tokens` | Embedded as natural language. |

Units supported: `k` (thousand), `m` (million), `b` (billion). Case-insensitive.

### UI Feedback

- **Input Highlighting**: The budget syntax is highlighted in the input box (calculated by `findTokenBudgetPositions` in `PromptInput.tsx`).
- **Spinner Progress**: The bottom spinner displays real-time progress:
  - In-progress: `Target: 125,000 / 500,000 (25%) · ~2m 30s`
  - Completed: `Target: 510,000 used (500,000 min ✓)`
  - Includes an ETA based on the current token production rate.

## III. Implementation Architecture

### Data Flow

```
User enters "+500k"
     │
     ▼
┌─────────────────────────┐
│  parseTokenBudget()     │  src/utils/tokenBudget.ts
│  Regex parse → 500,000  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  REPL.tsx               │  Called on submission
│  snapshotOutputTokens   │  snapshotOutputTokensForTurn(500000)
│  ForTurn(500000)        │  Records turn start tokens + budget
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  query.ts Main Loop     │  Check at the end of each turn
│  checkTokenBudget()     │  Current output tokens vs budget
└────────┬────────────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
 continue    stop
 ( < 90%)    ( ≥ 90% or diminishing returns)
    │          │
    ▼          ▼
 Inject nudge Normal exit;
 message     send completion event
```

### Core Modules

#### 1. Parsing Layer — `src/utils/tokenBudget.ts`

Three regular expressions parse user input:
- `SHORTHAND_START_RE`: Matches `+500k` at the beginning.
- `SHORTHAND_END_RE`: Matches `+2m` at the end.
- `VERBOSE_RE`: Matches `spend 2M tokens`.

- `parseTokenBudget(text)`: Extracts the budget value as a `number`.
- `findTokenBudgetPositions(text)`: Returns match positions for highlighting.
- `getBudgetContinuationMessage(pct, turnTokens, budget)`: Generates the nudge message.

#### 2. State Layer — `src/bootstrap/state.ts`

Module-level singleton variables track the budget status for the current turn:
- `outputTokensAtTurnStart`: Total output tokens at the start of this turn.
- `currentTurnTokenBudget`: The budget target for this turn (`null` if none).
- `budgetContinuationCount`: Number of times the turn has been auto-continued.

Key functions:
- `getTotalOutputTokens()`: Aggregates output tokens across all models from `STATE.modelUsage`.
- `getTurnOutputTokens()`: `getTotalOutputTokens() - outputTokensAtTurnStart`.
- `snapshotOutputTokensForTurn(budget)`: Resets the turn start point and sets the new budget.

#### 3. Decision Layer — `src/query/tokenBudget.ts`

`checkTokenBudget(tracker, agentId, budget, globalTurnTokens)` decides whether to continue or stop:

**Continuation Conditions:**
- Not in a subagent (`agentId` is null).
- Budget exists and is > 0.
- Current tokens have not reached **90%** of the budget.
- No diminishing returns.

**Stop Conditions:**
- Reached 90% of the budget.
- Diminishing returns (the model is making no further progress).
- In subagent mode (skipped).

**Diminishing Returns Detection**: If `continuationCount >= 3` and the delta of the last two nudges is `< 500 tokens` each.

#### 4. Main Loop Integration — `src/query.ts`

Within the `query()` function:
1. Creates a `budgetTracker`.
2. Enters a `while` loop.
3. Calls `checkTokenBudget()` after each turn.
4. If the decision is `continue`:
   - Injects a meta user message (nudge).
   - Loops back to the start.
5. If the decision is `stop`:
   - Records a completion event (includes a `diminishingReturns` flag).
   - Returns normally.

#### 5. UI Layer

| File | Responsibility |
| :--- | :--- |
| `PromptInput.tsx:534` | Highlights budget syntax in the input field. |
| `Spinner.tsx:319-338` | Displays progress percentage and ETA in the spinner. |
| `REPL.tsx:2897` | Parses and snapshots the budget on submission. |
| `REPL.tsx:2138` | Clears the budget if the user cancels. |
| `REPL.tsx:2963` | Captures budget info for display when a turn ends. |

#### 6. System Prompts — `src/constants/prompts.ts:538-551`

Injects the `token_budget` section:
> "When the user specifies a token target (e.g., '+500k', 'spend 2M tokens', 'use 1B tokens'), your output token count will be shown each turn. Keep working until you approach the target — plan your work to fill it productively. The target is a hard minimum, not a suggestion. If you stop early, the system will automatically continue you."

Note: This prompt is **unconditionally cached** to avoid cache misses (~20K tokens) when toggling budgets.

#### 7. API Attachments — `src/utils/attachments.ts:3830-3845`

Each API call turn includes an `output_token_usage` attachment so the model can see its own progress.

## IV. Key Design Decisions

1.  **90% Threshold**: Stops at `COMPLETION_THRESHOLD = 0.9` to prevent the final nudge from overshooting the budget significantly.
2.  **Diminishing Returns Protection**: Terminate early if output is `< 500 tokens` per turn after 3 consecutive nudges.
3.  **Subagent Exemption**: Subtasks within `AgentTool` do not perform budget checks to avoid recursive triggering.
4.  **Unconditional Cache for Prompts**: The budget prompt is always injected, preventing 20K token cache misses on every budget change.
5.  **Cancel Logic**: Pressing Escape calls `snapshotOutputTokensForTurn(null)` to prevent residual budgets from triggering continuations.

## V. Usage Examples

```bash
# Enable the feature
FEATURE_TOKEN_BUDGET=1 bun run dev

# Usage in prompts
> +500k refactor all test files
> spend 2M tokens migrate this project from JS to TS
> write a complete CRUD module for me +1m
```

## VI. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/utils/tokenBudget.ts` | 73 | Regex parsing, position finding, and nudge message generation. |
| `src/query/tokenBudget.ts` | 93 | Budget tracker and continue/stop decision logic. |
| `src/bootstrap/state.ts` | 20 | Turn-level token snapshot state management. |
| `src/constants/prompts.ts` | 14 | System prompt injection. |
| `src/utils/attachments.ts` | 17 | API attachment appending. |
| `src/query.ts` | 48 | Main loop integration. |
| `src/screens/REPL.tsx` | 20 | REPL submission, completion, and cancellation handling. |
| `src/components/Spinner.tsx` | 20 | Progress bar UI. |
| `src/components/PromptInput/PromptInput.tsx` | 1 | Input highlighting logic. |
