# Auto Dream — Automated Memory Consolidation

## Overview

Auto Dream is the background memory consolidation mechanism in Claude Code. It automatically reviews, organizes, and prunes persistent memory files between sessions to ensure that future sessions can quickly obtain accurate context.

The memory system is stored in the file system (defaulting to `~/.claude/projects/<project-slug>/memory/`) and consists of a `MEMORY.md` index file and several topical files (e.g., `user_language.md`, `project_overview.md`). As sessions accumulate, memory can become outdated, redundant, or contradictory—Dream is responsible for cleaning up this buildup.

## Architecture

### Core Modules

| Module | Path | Responsibility |
| :--- | :--- | :--- |
| Scheduler | `src/services/autoDream/autoDream.ts` | Time/Session/Lock triple gating; triggers the forked agent. |
| Configuration | `src/services/autoDream/config.ts` | Reads the `isAutoDreamEnabled()` toggle. |
| Prompts | `src/services/autoDream/consolidationPrompt.ts` | Constructs the 4-phase consolidation prompt. |
| Lock File | `src/services/autoDream/consolidationLock.ts` | PID lock + mtime as `lastConsolidatedAt`. |
| Task UI | `src/tasks/DreamTask/DreamTask.ts` | Background task registration; visible via footer pill + Shift+Down. |
| Manual Entry | `src/skills/bundled/dream.ts` | `/dream` command, available unconditionally. |

### Memory Path Resolution

Priority (`src/memdir/paths.ts`):

1.  `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` environment variable (full path override).
2.  `autoMemoryDirectory` setting (`settings.json`, supports `~/` expansion).
3.  Default: `<memoryBase>/projects/<sanitized-git-root>/memory/`

Where `memoryBase` is `CLAUDE_CODE_REMOTE_MEMORY_DIR` or `~/.claude`.

## Trigger Mechanism

### Automatic Trigger (Auto Dream)

At the end of each conversation turn, `executeAutoDream()` sequentially checks triple gating:

```
┌─────────────────────────────────────────────────────┐
│  Gate 1: Global Switch                               │
│  isAutoMemoryEnabled() && isAutoDreamEnabled()       │
│  Excludes: KAIROS mode / Remote mode                  │
├─────────────────────────────────────────────────────┤
│  Gate 2: Time Gating                                 │
│  hoursSince(lastConsolidatedAt) >= minHours          │
│  Default: 24 hours                                   │
├─────────────────────────────────────────────────────┤
│  Gate 3: Session Gating                              │
│  sessionsTouchedSince(lastConsolidatedAt) >= minSessions │
│  Default: 5 sessions (excluding the current one)      │
├─────────────────────────────────────────────────────┤
│  Lock: PID Lock File                                 │
│  .consolidate-lock (mtime = lastConsolidatedAt)      │
│  Dead process detection + 1-hour expiration          │
└─────────────────────────────────────────────────────┘
```

If all gates pass, the consolidation task runs as a **forked agent** (restricted sub-agent):

- Bash tools are restricted to read-only commands (`ls`, `grep`, `cat`, etc.).
- Can only read and write files within the memory directory.
- Users can view progress or terminate the task in the Shift+Down background task panel.

### Manual Trigger (`/dream` command)

Triggered at any time via the `/dream` command, with no gating restrictions:

- Runs in the main loop (not a forked agent) with full tool permissions.
- Users can observe the operation process in real-time.
- Automatically updates the lock file mtime before execution.

### Configuration Toggles

| Toggle | Location | Function |
| :--- | :--- | :--- |
| `autoDreamEnabled` | `settings.json` | `true`/`false` explicit toggle. |
| `autoMemoryEnabled` | `settings.json` | Master switch; if off, all memory features are disabled. |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Environment variable | `1`/`true` disables all memory features. |
| `tengu_onyx_plover` | GrowthBook | Official remote config; controls `enabled`/`minHours`/`minSessions`. |

Default values (without GrowthBook connection):

```typescript
minHours: 24      // At least 24 hours since the last consolidation.
minSessions: 5    // At least 5 new sessions.
```

## Consolidation Flow (4 Phases)

The Dream agent's execution prompt includes 4 phases:

### Phase 1 — Orient

- `ls` the memory directory to see existing files.
- Read the `MEMORY.md` index.
- Browse existing topical files to avoid duplicate creation.

### Phase 2 — Gather Signals

Collect new information based on priority:

1.  **Log Files** (`logs/YYYY/MM/YYYY-MM-DD.md`, append-only logs under KAIROS mode).
2.  **Outdated Memory** — Facts that contradict the current state of the codebase.
3.  **Session Records** — Narrow keyword grep of JSONL files (no full reading).

### Phase 3 — Consolidate

- Merge new signals into existing topical files instead of creating near-duplicates.
- Convert relative dates ("yesterday", "last week") to absolute dates.
- Delete overturned facts.

### Phase 4 — Prune and Index

- Keep `MEMORY.md` under 200 lines and 25KB.
- One line per index entry, not exceeding 150 characters.
- Remove outdated, incorrect, or superseded pointers.

## Memory Types

The memory system uses 4 types (`src/memdir/memoryTypes.ts`):

| Type | Purpose | Example |
| :--- | :--- | :--- |
| `user` | User roles, preferences, knowledge | User is a senior backend engineer, prefers Chinese. |
| `feedback` | Guidance on working methods | Do not mock database tests; use bundled PRs for reviews. |
| `project` | Project context (not inferable from code) | Merge freeze begins March 5th; auth rewrite is for compliance. |
| `reference` | Pointers to external systems | Linear INGEST project tracking pipeline bugs. |

**What is NOT saved**: Code patterns, architecture, and file paths (inferable from code); Git history (`git log` is the authority); debugging plans (already in code).

## Lock File Mechanism

The `.consolidate-lock` file is located within the memory directory:

- **File Content**: PID of the holder.
- **mtime**: Timestamp of `lastConsolidatedAt`.
- **Expiration**: 1 hour (to prevent PID reuse).
- **Race Condition Handling**: If two processes write simultaneously, the second one verifies the PID and exits if it fails.
- **Rollback**: If the forked agent fails or is terminated by the user, mtime rolls back to its value before acquisition.

## Use Cases

### Case 1: Automatic Consolidation in Daily Development

A developer uses Claude Code to handle various tasks over multiple days. Auto Dream triggers automatically after 5+ sessions have accumulated and 24 hours have passed since the last consolidation, merging user preferences and project decisions scattered across sessions.

### Case 2: Manual Memory Consolidation

A user notices that Claude repeatedly makes the same mistake or forgets previous decisions. Entering `/dream` immediately triggers consolidation, bypassing the automatic trigger cycle.

### Case 3: Fast Context for New Sessions

At the start of a new session, `MEMORY.md` is loaded into the context. Memory files organized by Dream have a clear structure and accurate information, allowing Claude to quickly understand the user and project.

### Case 4: Log Distillation in KAIROS Mode

In KAIROS (persistent assistant mode), the agent writes to date-based log files in an append-only fashion. Dream is responsible for distilling these logs into topical files and the `MEMORY.md` index.

## Relationship with Other Systems

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Interaction  │────▶│ Memory Write  │────▶│ MEMORY.md     │
│ (Main Agent) │     │ (Immediate)  │     │ + Topic Files │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                               │
       ┌───────────────────────────────────────┘
       ▼
┌──────────────┐     ┌──────────────┐
│ Auto Dream   │────▶│ Consolidate  │
│ (Background) │     │ / Prune      │
└──────────────┘     └──────────────┘
       ▲
┌──────────────┐
│ /dream cmd   │
│ (Manual)     │
└──────────────┘
```

- **extractMemories** (`src/services/extractMemories/`): Extracts new memories from the conversation and writes them at the end of each turn. Dream is responsible for consolidation, not extraction.
- **CLAUDE.md**: Project-level instruction file, loaded into context but not part of the memory system.
- **Team Memory** (`TEAMMEM` feature): Team-shared memory directory, using the same Dream mechanism as personal memory.
