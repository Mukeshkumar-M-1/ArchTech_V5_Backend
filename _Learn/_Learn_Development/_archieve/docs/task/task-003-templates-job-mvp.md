# Task 003: TEMPLATES — job Filesystem MVP

> Source: [stub-recovery-design-1-4.md](../features/stub-recovery-design-1-4.md) Item 3
> Priority: P2
> Effort: Medium
> Status: DONE
> Phase: MVP

## Goal

Make `new` / `list` / `reply` into a usable template task system. Do not touch complex automatic classification or automatic execution in the first phase.

## Background

- Command entry is only through fast-path (`src/entrypoints/cli.tsx:272`).
- Handlers are empty (`src/cli/handlers/templateJobs.ts`).
- `markdownConfigLoader` has already included `templates` in the configuration directory (`src/utils/markdownConfigLoader.ts:35`).
- `query/stopHooks` has reserved the job classifier chain (`src/query/stopHooks.ts:103`).
- `jobs/classifier.ts` is still a stub (`src/jobs/classifier.ts`).

## Implementation Plan

### New Files

| File | Description |
|------|------|
| `src/jobs/state.ts` | job state management |
| `src/jobs/templates.ts` | Template parsing and listing |

### Modified Files

| File | Change |
|------|------|
| `src/cli/handlers/templateJobs.ts` | Implement `new` / `list` / `reply` handlers |

### Template Source

`.claude/templates/*.md`

### Template Format

Reuse existing markdown + frontmatter parsing; no separate DSL design.

### list Command

- List all templates.
- Display: Template name, description, path.

### new Command

- Parse the template.
- Create a job directory under `~/.claude/jobs/<job-id>/`.
- Write `template.md`, `input.txt`, `state.json`.
- Return the job id and directory path.

### reply Command

- Write the reply to `replies.jsonl` or `input.txt`.
- Update `state.json`.

## Verification Steps

- [ ] `list` can list all templates under `.claude/templates`.
- [ ] `new <template> [args...]` can create the job directory and state file.
- [ ] `reply <job-id> <text>` can update job content and state.
- [ ] The minimum field set for frontmatter schema is defined.

## Phase 2 (Subsequent)

- [ ] Restore `src/jobs/classifier.ts`.
- [ ] Enable job sessions with `CLAUDE_JOB_DIR` to automatically update `state.json` after turn completion.
- [ ] Decide whether to supplement an automatic job runner.

### Why split

- Current implementation covers "template job commands," not just a template list.
- The automatic job running chain lacks sufficient existing implementation.
- Implementing the filesystem job lifecycle first is more stable.

## Risks

- The frontmatter schema needs a minimum field set defined first.
- Scope will expand significantly once extended to "automatic job running."

## Dependencies

No hard dependencies; can be implemented independently.
