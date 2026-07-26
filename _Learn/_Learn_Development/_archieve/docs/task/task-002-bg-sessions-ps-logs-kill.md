# Task 002: BG_SESSIONS — ps / logs / kill

> Source: [stub-recovery-design-1-4.md](../features/stub-recovery-design-1-4.md) Item 2
> Priority: P1
> Effort: Medium
> Status: DONE
> Phase: Phase 2A (MVP)

## Goal

Turn `ps` / `logs` / `kill` into truly useful session management commands. Do not complete `attach` / `--bg` in the first phase.

## Background

- fast-path is already connected (`src/entrypoints/cli.tsx:218`).
- session registry has a real implementation (`src/utils/concurrentSessions.ts`).
- `exit` within a bg session already performs `tmux detach-client` (`src/commands/exit/exit.tsx:20`).
- CLI handlers are still entirely empty (`src/cli/bg.ts`).
- task summary is still a stub (`src/utils/taskSummary.ts`).

## Implementation Plan

### Modified Files

| File | Change |
|------|------|
| `src/cli/bg.ts` | Implement `ps` / `logs` / `kill` handlers |
| `src/utils/concurrentSessions.ts` | Extend for subsequent use by attach/--bg |
| `src/utils/taskSummary.ts` | Supplement basic implementation |

### Reused Modules

- `src/utils/sessionStorage.ts` — session storage
- `src/utils/udsClient.ts` — UDS communication

### ps Command

- Read live sessions from the registry.
- Display: pid, kind, sessionId, cwd, name, startedAt, bridgeSessionId.
- If activity/status exists, display them as well.

### logs Command

- Support searching by `sessionId` / `pid` / `name`.
- Prioritize reusing local transcript/log reading capabilities.
- If `logPath` exists in the registry, support tailing the file.

### kill Command

- Resolve the target session.
- Send the exit signal.
- Clean up the stale registry.

## Verification Steps

- [ ] `ps` can list current live sessions.
- [ ] `logs <sessionId|pid|name>` can output the corresponding log.
- [ ] `kill <sessionId|pid|name>` can end the target session and clean up the registry.
- [ ] Clear prompts are provided for each command when no live sessions exist.

## Phase 2B (Subsequent)

- [ ] Implement `attach`.
- [ ] Implement `--bg`.
- [ ] Implement mid-point status updates for `taskSummary`.

### Why split

- The existing registry records `pid / sessionId / name / logPath`.
- However, there is no reliable tmux attach target.
- `attach` and `--bg` require start/attachment metadata design, not just simple handler completion.

## Risks

- Phase 2 of `attach` / `--bg` requires tmux metadata design.
- tmux paths on Windows require a clear fallback strategy.

## Dependencies

- Task 001 (daemon state management reusable pattern, but not a hard dependency).
