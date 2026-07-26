# CONTEXT_COLLAPSE — Context Collapse

> Feature Flag: `FEATURE_CONTEXT_COLLAPSE=1`
> Sub-Feature: `FEATURE_HISTORY_SNIP=1`
> Implementation Status: Core logic is stubbed; wiring is complete.
> Reference Count: `CONTEXT_COLLAPSE` (20) + `HISTORY_SNIP` (16) = 36

## I. Feature Overview

`CONTEXT_COLLAPSE` allows the model to introspect its context window usage and intelligently compress old messages. As a conversation approaches the context limit, old messages are automatically folded into compressed summaries, preserving key information while freeing up token space.

### Sub-Features

| Feature | Function |
| :--- | :--- |
| `CONTEXT_COLLAPSE` | Context collapse engine (background LLM calls to compress old messages). |
| `HISTORY_SNIP` | SnipTool — Mark messages for folding or pruning. |

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status |
| :--- | :--- | :--- |
| **Collapse Core** | `src/services/contextCollapse/index.ts` | **Stub** — Interfaces are complete (`ContextCollapseStats`, `CollapseResult`, `DrainResult`), but functions are no-ops. |
| **Collapse Operations**| `src/services/contextCollapse/operations.ts` | **Stub** — `projectView` is an identity function. |
| **Collapse Persistence**| `src/services/contextCollapse/persist.ts` | **Stub** — `restoreFromEntries` is a no-op. |
| **CtxInspectTool** | `packages/builtin-tools/src/tools/CtxInspectTool/CtxInspectTool.ts` | **Complete** — Context introspection tool. |
| **SnipTool Prompt** | `src/tools/SnipTool/prompt.ts` | **Stub** — Empty tool name. |
| **SnipTool Implementation**| `src/tools/SnipTool/SnipTool.ts` | **Missing** |
| **force-snip Command** | `src/commands/force-snip.js` | **Missing** |
| **Collapse Read Search**| `src/utils/collapseReadSearch.ts` | **Complete** — Handles Snip as a silent absorption operation. |
| **QueryEngine Integration**| `src/QueryEngine.ts` | **Wired** — Imports and uses snip projections. |
| **Token Warning UI** | `src/components/TokenWarning.tsx` | **Wired** — Collapse progress labels. |

### 2.2 Core Interfaces (Defined, Pending Implementation)

```ts
// contextCollapse/index.ts
interface ContextCollapseStats {
  // Context usage statistics
}
interface CollapseResult {
  // Results of the collapse operation
}
interface DrainResult {
  // Emergency release results
}

// Key functions (all stubbed):
isContextCollapseEnabled()          // → false
applyCollapsesIfNeeded(messages)    // Passthrough
recoverFromOverflow(messages)       // Passthrough (413 recovery)
initContextCollapse()               // No-op
```

### 2.3 Expected Data Flow

```
Conversation grows continuously
      │
      ▼
Context approaches the limit (detected by query.ts)
      │
      ├── Overflow detection (query.ts:440, 616, 802)
      │
      ▼
applyCollapsesIfNeeded(messages) [TO BE IMPLEMENTED]
      │
      ├── Background LLM call to compress old messages
      ├── Preserve key info (decisions, file paths, errors)
      └── Replace old messages with compressed summaries
      │
      ├── 413 Recovery (query.ts:1093, 1179)
      │   └── recoverFromOverflow() emergency collapse
      │
      ▼
projectView() filters the view of collapsed messages
      │
      ▼
Model continues working (within the compressed context)
```

### 2.4 HISTORY_SNIP Sub-Feature

SnipTool provides manual folding capabilities:

- `/force-snip` command — Manually forces a collapse.
- SnipTool — Marks specific messages for folding or pruning.
- `collapseReadSearch.ts` is fully implemented, treating Snip as a silent absorption operation.

### 2.5 Integration Points

| File | Location | Description |
| :--- | :--- | :--- |
| `src/query.ts` | 18, 440, 616, 802, 1093, 1179 | Overflow detection, 413 recovery, applying collapses. |
| `src/QueryEngine.ts` | 124, 127, 1301 | Snip projection usage. |
| `src/utils/analyzeContext.ts`| 1122 | Skip display of preserved buffers. |
| `src/utils/sessionRestore.ts`| 127, 494 | Restoring collapse state. |
| `src/services/compact/autoCompact.ts` | 179, 215 | Accounting for collapses during auto-compaction. |

## III. Missing Implementations

| Priority | Module | Effort | Description |
| :--- | :--- | :--- | :--- |
| 1 | `services/contextCollapse/index.ts` | Large | Collapse state machine, LLM calls, message compression. |
| 2 | `services/contextCollapse/operations.ts`| Medium | `projectView()` message filtering. |
| 3 | `services/contextCollapse/persist.ts` | Small | `restoreFromEntries()` disk persistence. |
| 4 | `tools/CtxInspectTool/` | Done | Context introspection tool implemented. |
| 5 | `tools/SnipTool/SnipTool.ts` | Medium | Snip tool implementation. |
| 6 | `commands/force-snip.js` | Small | `/force-snip` command. |

## IV. Key Design Decisions

1.  **Background LLM Compression**: Collapsing is not simple truncation; it uses an LLM to generate compressed summaries that preserve critical information.
2.  **413 Recovery**: When the API returns a 413 error (Request Too Large), emergency collapsing is the primary recovery mechanism.
3.  **Collaboration with `autoCompact`**: Collapsing and automatic compaction (`compact`) are distinct mechanisms; collapsing operates at the message level, while compaction operates at the conversation level.
4.  **Persistence**: Collapse state is persisted to disk and reloaded upon session restoration.

## V. Usage

```bash
# Enable context collapse
FEATURE_CONTEXT_COLLAPSE=1 bun run dev

# Enable the snip sub-feature
FEATURE_CONTEXT_COLLAPSE=1 FEATURE_HISTORY_SNIP=1 bun run dev
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `src/services/contextCollapse/index.ts` | Collapse core (stub; interfaces defined). |
| `src/services/contextCollapse/operations.ts` | Projection operations (stub). |
| `src/services/contextCollapse/persist.ts` | Persistence (stub). |
| `src/utils/collapseReadSearch.ts` | Snip absorption operations (complete). |
| `src/query.ts` | Integration of overflow detection and 413 recovery. |
| `src/QueryEngine.ts` | Snip projection usage. |
| `src/components/TokenWarning.tsx` | Collapse progress UI. |
