---
title: "Project Memory System - File-Level Cross-Conversation Memory Architecture"
description: "In-depth analysis of Claude Code memory system: file-based persistent storage, MEMORY.md index structure, four-type classification method, Sonnet intelligent recall, Session Memory compression integration."
keywords:
  [
    "project memory",
    "MEMORY.md",
    "AI memory",
    "cross-conversation",
    "automatic memory",
    "memdir",
  ]
---

{/_ The goal of this chapter: Analyze the storage architecture, recall mechanism and injection link of the memory system from the source code level _/}

## Storage architecture of memory system

Source code path: `src/memdir/paths.ts`, `src/memdir/memdir.ts`

Claude Code's memory system is **pure file** - no database, no vector storage, only Markdown files and directory structures.

### Directory layout

```
~/.claude/projects/<sanitized-git-root>/memory/
├── MEMORY.md ← Entry Index (loaded per conversation)
├── user_role.md ← User memory
├── feedback_testing.md ← Feedback memory
├── project_mobile_release.md ← Project memory
├── reference_linear_ingest.md ← Reference memory
└── logs/ ← KAIROS mode: daily logs
└── 2026/
└── 04/
└── 2026-04-01.md
```

Path resolution link (`getAutoMemPath()`):

1. `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` environment variable (Cowork SDK full path coverage)
2. `autoMemoryDirectory` settings (only `policySettings`/`localSettings`/`userSettings` - **intentionally exclude** `projectSettings` to prevent malicious warehouses from pointing the memory path to `~/.ssh`)
3. Default: `<memoryBase>/projects/<sanitized-git-root>/memory/`

All worktrees in the same Git repository share a memory directory (find the real `.git` root through `findCanonicalGitRoot()`).

### MEMORY.md Index

`MEMORY.md` is the entry index of memory, and each conversation is fully loaded into the context:

```typescript
// memdir.ts:34-38
export const ENTRYPOINT_NAME = "MEMORY.md";
export const MAX_ENTRYPOINT_LINES = 200;
export const MAX_ENTRYPOINT_BYTES = 25_000;
```

The index is **double capped**: 200 rows AND 25KB. Exceeding any one will be truncated by `truncateEntrypointContent()` and a warning will be appended. Design reason: p97's index file can be covered with 200 lines, but some index entries are extremely long (197KB/200 lines observed for p100), and the byte limit catches this long line exception.

Index entry format:

```markdown
- [Title](file.md) — one-line hook
```

One line per entry, within ~150 characters. `MEMORY.md` itself has no frontmatter - it's just a linked list, not the memory contents.

## Four types of classification

Source code path: `src/memdir/memoryTypes.ts`

Memories are constrained as a **closed four-type system**, with each type having explicit `<when_to_save>`, `<how_to_use>` and `<body_structure>` specifications:

| Type          | Storage Content                                 | Typical Triggers                                                         |
| ------------- | ----------------------------------------------- | ------------------------------------------------------------------------ |
| **user**      | User role, preferences, technical background    | "I am a data scientist", "I have written Go for ten years"               |
| **feedback**  | User correction and confirmation of AI behavior | "Don't mock the database", "Single PR is better"                         |
| **project**   | Non-code-derivable project context              | "Merge freeze starts Thursday", "auth rewrite is compliance requirement" |
| **reference** | External system pointers                        | "pipeline bugs in Linear INGEST project"                                 |

Key design constraint: **Only store information that cannot be deduced from the current project status**. Code structure, file paths, and git history can all be obtained in real time without needing to remember.

### Dual-channel capture of feedback type

The `when_to_save` directive of the `feedback` type is particularly emphasized:

> Record from failure AND success: if you only save corrections, you will avoid past mistakes but drift away from approaches the user has already validated, and may grow overly cautious.

This means that the AI saves not only when the user says "don't do that" but also when the user says "yeah, that's it". The latter is harder to catch, but equally important - it prevents the AI's behavior from drifting over time.

### Frontmatter format of each memory

```markdown
---
name: { { memory name } }
description:
  { { one-line description — used to determine relevance in the future } }
type: { { user, feedback, project, reference } }
---

{{memory content — feedback/project type suggestion contains **Why:** and **How to apply:** lines}}
```

The `description` field is key: it is not a summary for humans to read, but a search keyword for the AI recall system to make relevance judgments.

## Intelligent recall mechanism

Source code path: `src/memdir/findRelevantMemories.ts`, `src/memdir/memoryScan.ts`

Not every memory is appropriate for every conversation. The system uses a lightweight Sonnet side query to filter the most relevant memories.

### Recall process

```
User messages → findRelevantMemories(query, memoryDir)
├── scanMemoryFiles() — scan the frontmatter of all memory files
├── selectRelevantMemories() — Sonnet side query, select ≤5 items from the list
└── Return [{path, mtimeMs}, ...]
```

The core is the `selectRelevantMemories()` function, which calls `sideQuery()` (a separate lightweight API call):

```typescript
  // findRelevantMemories.ts:98-121
  const result = await sideQuery({
    model: getDefaultSonnetModel(), // Use Sonnet for filtering (non-main model)
    system: SELECT_MEMORIES_SYSTEM_PROMPT,
    messages: [{
    role: 'user',
    content: `Query: ${query}\n\nAvailable memories:\n${manifest}${toolsSection}`
    }],
    max_tokens: 256,
    output_format: { type: 'json_schema', schema: { ... } },
  })
```

### Recent Tool De-duplication

When AI is using a tool, recalling that tool's documentation is noise (the work context already has the conversation). `recentTools` parameter allows the recall system to skip these memories:

```typescript
// findRelevantMemories.ts:92-95
const toolsSection =
  recentTools.length > 0
    ? `\n\nRecently used tools: ${recentTools.join(", ")}`
    : "";
```

System Prompt explicitly states: "If a list of recently used tools has been provided, do not select the usage reference or API documentation for that tool. 
**Still select** warnings, gotchas, or known issues about these tools — this is exactly the most critical information to use."

### Already Surfaced De-duplication

`alreadySurfaced` parameter filters out file paths that have already been displayed in previous rounds, allowing Sonnet's 5-slot budget to be spent on new candidates instead of repeatedly recalling the same file.

## Memory Injection System Prompt Link

Source code path: `src/memdir/memdir.ts` → `src/context.ts`

`loadMemoryPrompt()` is the entry point for memory injection, called once per session (cached via `systemPromptSection('memory', ...)`):

```typescript
// memdir.ts:419-507
export async function loadMemoryPrompt(): Promise<string | null> {
  // Priority order: KAIROS log mode → TEAMMEM combined mode → pure auto memory
  if (feature('KAIROS') && autoEnabled && getKairosActive()) {
    return buildAssistantDailyLogPrompt(skipIndex)
  }
  if (feature('TEAMMEM') && teamMemPaths!.isTeamMemoryEnabled()) {
    return teamMemPrompts!.buildCombinedMemoryPrompt(...)
  }
  if (autoEnabled) {
    return buildMemoryLines('auto memory', autoDir, ...).join('\n')
  }
  return null
}
```

Injection timing: When `getSystemContext()` is called in `context.ts`, the memory prompt is assembled as a section of the system prompt. The content of `MEMORY.md` is injected as a **user context message** (not system prompt), which allows leveraging the prefix sharing of the Prompt Cache.

## KAIROS Mode: Daily Logs

Source code path: `src/memdir/memdir.ts` (`buildAssistantDailyLogPrompt`)

Long-running assistant sessions use different memory strategies:

- **Standard mode**: AI maintains `MEMORY.md` as a real-time index + independent memory files
- **KAIROS mode**: AI only appends logs to date files (`logs/YYYY/MM/YYYY-MM-DD.md`), no reorganization

```typescript
// Daily log path pattern (non-literal path — because Prompt is cached)
const logPathPattern = join(memoryDir, "logs", "YYYY", "MM", "YYYY-MM-DD.md");
```

An independent nightly `/dream` skill is responsible for distilling the logs into theme files + `MEMORY.md` index.

## Memory Drift Defense

Source code path: `src/memdir/memoryTypes.ts` (`TRUSTING_RECALL_SECTION`)

Memories may become stale. The system includes a dedicated section in the Prompt called "Before recommending from memory":

```
A memory that names a specific function, file, or flag is a claim
that it existed *when the memory was written*. It may have been
renamed, removed, or never merged. Before recommending it:

- If the memory names a file path: check the file exists.
- If the memory names a function or flag: grep for it.
```

This section title was validated through A/B testing: "Before recommending from memory" (action-oriented) performed better than "Trusting what you recall" (abstract description) (3/3 vs 0/3).

### Strict Semantics for Ignoring Memory

```
If the user says to *ignore* or *not use* memory:
proceed as if MEMORY.md were empty.
Do not apply remembered facts, cite, compare against,
or mention memory content.
```

This addresses a common anti-pattern where the AI, upon being told to "ignore memory about X", still references "unlike what memory says about Y" — this is "acknowledging then overriding" rather than "ignoring".

## Session Memory and Compression Linkage

Source code path: `src/services/compact/sessionMemoryCompact.ts`

The memory system has deep integration with context compression. When both `tengu_session_memory` and `tengu_sm_compact` feature flags are enabled, compression prioritizes Session Memory over traditional summarization:

```typescript
// sessionMemoryCompact.ts:57-61
const DEFAULT_SM_COMPACT_CONFIG = {
  minTokens: 10_000, // At least 10K tokens after compression
  minTextBlockMessages: 5, // At least 5 text messages
  maxTokens: 40_000, // At most 40K tokens
};
```

SM-compact does not call the compression API (it has no summary model), but directly uses the existing Session Memory as the summary — faster, cheaper, and without information loss.
