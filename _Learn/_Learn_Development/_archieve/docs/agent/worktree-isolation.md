---
title: "Worktree Isolation - Git Worktree implements file-level isolation"
description: "Revealing Claude Code's git worktree isolation mechanism: how sub-agents obtain independent workspaces, worktree creation/destruction life cycle, path naming rules and security protection."
keywords: ["Worktree", "git worktree", "File isolation", "Multi-Agent isolation", "Parallel security"]
---

{/* The goal of this chapter: reveal the worktree’s creation/destruction life cycle, path naming rules, hook mechanism and security protection when exiting */}

## Why file-level isolation is needed

When multiple Agents work in parallel, sharing the same working directory will lead to three types of conflicts:

1. **Writing conflict**: Two Agents edit `config.ts` at the same time, and the one written later overwrites the one written before.
2. **State interference**: Agent A’s test relies on a certain environmental state, and Agent B’s modification destroys it.
3. **Indistinguishable**: Semi-completed modifications are mixed together, and it is impossible to tell which ones belong to which Agent.

Git worktree is a native git solution - create multiple independent working directories in the same repository, each on its own branch.

## Directory structure and naming rules

Worktree files are stored uniformly in `.claude/worktrees/` in the root directory of the warehouse:

```
<repo-root>/
├── .claude/
│ └── worktrees/
│ ├── fix-auth-bug/ # worktree working directory
│ │ ├── .git # Link file pointing to the main repository
│ │ └── src/... # Independent file system view
│ └── add-dark-mode/ # Another worktree
│ └── ...
├── src/ # Main working directory (not affected)
└── .git/ # Main repository
```

The branch naming rule is `worktree/<slug>`, where the slug is verified by `validateWorktreeSlug()`: each `/` separated segment only allows letters, numbers, `.`, `_`, `-`, with a total length of ≤64 characters. Automatically generated using plan slug when not specified.

## Creation process: EnterWorktreeTool

Execution link of `EnterWorktreeTool` (`packages/builtin-tools/src/tools/EnterWorktreeTool/EnterWorktreeTool.ts`):

```
EnterWorktreeTool.call({ name? })
  ↓
1. Check whether it is already in the worktree (anti-nesting)
  ↓
2. Resolve to the main repository root directory (findCanonicalGitRoot)
   If it is currently in the worktree, chdir to the main warehouse
  ↓
3. Generate slug (user-provided or plan slug)
  ↓
4. createWorktreeForSession(sessionId, slug)
   ├── Is there a WorktreeCreate hook?
   │ └── Execute the hook and return the path specified by the hook (supports non-git VCS)
   └── No hook → git native path:
       a. getOrCreateWorktree(repoRoot, slug)
          ├── Quick recovery: check if the worktree directory already exists
          │ └── Read HEAD SHA of .git pointer file (no child process)
          └── New:
              i. mkdir .claude/worktrees/(recursive)
              ii. fetch origin/<default-branch> (skip if cached)
              iii. git worktree add -b worktree/<slug> <path> <base>
              iv. performPostCreationSetup() (sparse checkout, etc.)
  ↓
5. Update process status:
   - process.chdir(worktreePath)
   - setCwd(worktreePath)
   - setOriginalCwd(worktreePath)
   - saveWorktreeState(session) → persist to project configuration
   - clearSystemPromptSections() → Recalculate cwd information in system prompts
   - clearMemoryFileCaches() → Reload CLAUDE.md in worktree
  ↓
6. Return worktreePath and worktreeBranch
```

### Hook-first architecture

`createWorktreeForSession()` first checks `hasWorktreeCreateHook()` - if the user configures `WorktreeCreate` hook in settings.json, the system does not call git at all, but executes the hook command and uses the returned path as the worktree path. This allows non-git version control systems (such as Pijul, Mercurial) to be connected via hooks.

### Quick recovery path

`getOrCreateWorktree()` has a key optimization: if the target path already exists, directly read the `.git` pointer file to obtain the HEAD SHA (pure file I/O, no subprocess), skipping the entire `fetch` + `worktree add` process. In a large warehouse `fetch` takes 6-8 seconds, this optimization reduces the latency in recovery scenarios to close to 0.

## Exit process: ExitWorktreeTool

`ExitWorktreeTool` (`packages/builtin-tools/src/tools/ExitWorktreeTool/ExitWorktreeTool.ts`) supports two exit strategies:

### keep: keep worktree

```
keepWorktree()
  ↓
1. chdir back to originalCwd
2. Clear currentWorktreeSession
3. Update project configuration (activeWorktreeSession = undefined)
4. The worktree directory and branches remain on disk
```

The user can continue working via `cd <worktreePath>` or merge manually later.

### remove: delete worktree

There are strict **security protection**:

```
validateInput() — first line of defense
  ↓
1. Check whether in the session created by EnterWorktree
   (Manually created worktrees will not be deleted)
  ↓
2. countWorktreeChanges(worktreePath, originalHeadCommit)
   ├── git status --porcelain → Count the number of uncommitted files
   ├── git rev-list --count <originalHead>..HEAD → Count the number of new submissions
   └── Return null (when git fails) → fail-closed (refuse to delete)
  ↓
3. Any uncommitted files or new submissions?
   → reject, requires discard_changes: true confirmation
```

```
call() — actual execution
  ↓
1. Recount changes (there may be new modifications between validateInput and call)
2. If there is a tmux session → killTmuxSession()
3. cleanupWorktree()
   ├── hook-based → execute WorktreeRemove hook
   └── git-based → git worktree remove --force + git branch -D
4. restoreSessionToOriginalCwd()
   - setCwd(originalCwd)
   - setOriginalCwd(originalCwd)
   - Only restore if projectRoot is a worktree (to prevent accidental touch)
   - Update hooks config snapshot
   - Clear system prompts and memory cache
```

### fail-closed design

`countWorktreeChanges()` returns `null` ("unknown, unsafe to assume") in the following cases:
- `git status` or `git rev-list` exit non-zero (lock file, corrupted index)
- `originalHeadCommit` is undefined (hook-based worktree does not set a baseline commit)

`validateInput` refuses to delete when `null` is returned - preferring to let the user handle it manually rather than risk losing work.

## Linkage with Agent tools

The `isolation` parameter of the Agent tool (`AgentTool`) determines whether the child Agent runs in the worktree. Note that the Agent tool uses the **specific** `createAgentWorktree()` (`src/utils/worktree.ts`) instead of the `createWorktreeForSession()` used for user sessions. There are key differences between the two:

| Dimensions | `createWorktreeForSession` (user session) | `createAgentWorktree` (child Agent) |
|------|---------------------------------------------|----------------------------------|
| Caller | EnterWorktreeTool | AgentTool |
| Session Management | Set `currentWorktreeSession` | **Do not set** `currentWorktreeSession` |
| Restore existing worktree | Reuse directly | Reuse and bump mtime (to prevent accidental deletion by periodic cleaning) |

The processing at the end of the child Agent is automatically completed by `cleanupWorktreeIfNeeded()` - it does not go to `ExitWorktreeTool` (because the Agent worktree has no session state, `validateInput` of `ExitWorktreeTool` will reject):
- **Changed** → Keep worktree and return `worktreePath` for subsequent merging by the main agent
- **No changes** → Automatically delete
- **Hook-based** → always reserved

## Session state persistence

The `WorktreeSession` object is persisted to disk through `saveCurrentProjectConfig()` and contains:

```typescript
{
  originalCwd: string, // working directory before entering worktree
  worktreePath: string, // The absolute path of worktree
  worktreeName: string, // slug
  worktreeBranch?: string, // branch name (such as worktree/fix-auth)
  originalBranch?: string, // enter the previous branch
  originalHeadCommit?: string, // HEAD commit before entry (used for change statistics)
  sessionId: string, // Create the session ID of this worktree
  tmuxSessionName?: string, // associated tmux session
  hookBased?: boolean, // Whether created by hook
  creationDurationMs?: number, // Creation time (for analysis)
  usedSparsePaths?: boolean, // Whether sparse checkout is used
}
```

This allows the worktree context to be correctly restored on session resume (`--resume`) - even if the process is restarted, `getCurrentWorktreeSession()` reads the state from the project configuration.

## Sparse Checkout optimization

For large monorepo, worktree supports `sparsePaths` configuration - only checkout specific directories instead of the entire repository. This reduces worktree creation time from tens of seconds to a few seconds in a repository of 210K files.

Configuration is located in `getInitialSettings().worktree?.sparsePaths` and is applied in `performPostCreationSetup()`.