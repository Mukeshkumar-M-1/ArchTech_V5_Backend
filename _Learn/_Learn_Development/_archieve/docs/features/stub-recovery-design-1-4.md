# Stub Recovery Design — Phase 1-4

> Date: 2026-04-12
> Goal: Provide actionable design solutions for 4 stubbed or semi-stubbed command surfaces based on current code boundaries.
> Prioritization: Ranked by suggested implementation order (not by severity).

## Design Principles

- Prioritize items that can be implemented as independent loops with clear benefits and defined boundaries.
- Break large items into `MVP` and `Phase 2+` to avoid sinking into massive refactors.
- Reuse existing state management, transport layers, logging, and configuration capabilities rather than reinventing protocols.
- Base designs on the actual code in the current repository rather than idealized states from old documentation.

## 1. `claude daemon status` / `claude daemon stop`

### Current State
- The `start` path already has a complete supervisor and worker lifecycle implemented in `src/daemon/main.ts` and `src/daemon/workerRegistry.ts`.
- `status` and `stop` are currently just placeholder outputs in `src/daemon/main.ts`.
- The `/remote-control-server` has its own UI state within the command, but it only tracks the `daemonProcess` within the current process, making it unsuitable for cross-process CLI management.

### Goal
- Ensure `claude daemon status` and `claude daemon stop` work correctly across different CLI processes.
- Remove dependency on TUI memory state; do not require the managing process to be the one that started the daemon.

### MVP Plan
- Introduce a daemon state file: `~/.claude/daemon/remote-control.json`.
- On `start`, write the following:
  - Supervisor PID.
  - CWD.
  - `startedAt` timestamp.
  - Worker kinds.
  - Recent status.
- **`status`**:
  - Read the state file.
  - Use process detection capabilities to verify if the PID is alive.
  - Output `running`, `stopped`, or `stale`.
  - Automatically clean up the state file if it is `stale`.
- **`stop`**:
  - Read the PID.
  - Send `SIGTERM`.
  - Wait for exit.
  - Send `SIGKILL` if a timeout occurs.
  - Clean up the state file.

### Scope
- New: `src/daemon/state.ts`.
- Modify: `src/daemon/main.ts`.
- Lightweight modifications to `src/commands/remoteControlServer/remoteControlServer.tsx` to ensure the UI reads the same state file.

### Verification
1. Run `claude daemon start`.
2. In a new terminal, run `claude daemon status`.
3. Run `claude daemon stop`.
4. Run `claude daemon status` again and confirm it returns `stopped` or a clear `stale cleaned` message.

### Risks
- Signal models differ between Windows and Unix; `stop` requires a timeout fallback.
- Current design assumes a single supervisor and does not handle multi-instance concurrency.

---

## 2. `BG_SESSIONS`

### Current State
- Fast-paths are connected in `src/entrypoints/cli.tsx`.
- A real session registry exists in `src/utils/concurrentSessions.ts`.
- `exit` within a background session already calls `tmux detach-client` in `src/commands/exit/exit.tsx`.
- However, the CLI handlers in `src/cli/bg.ts` remain empty, and `taskSummary.ts` is still a stub.

### Goal
- Transform `ps`, `logs`, and `kill` into functional session management commands.
- Postpone full `attach` and `--bg` implementation beyond the first phase.

### Phase 2A: MVP
- **`ps`**:
  - Read live sessions from the registry.
  - Display PID, kind, `sessionId`, CWD, name, `startedAt`, and `bridgeSessionId`.
  - Show activity/status if available.
- **`logs`**:
  - Support searching by `sessionId`, `pid`, or `name`.
  - Reuse local transcript/log reading capabilities.
  - Support tailing log files if `logPath` exists in the registry.
- **`kill`**:
  - Resolve the target session.
  - Send exit signals.
  - Clean up stale registry entries.

### Phase 2B: Future Work
- Implement `attach`.
- Implement `--bg`.
- Implement status updates for `taskSummary`.

### Rationale
- The existing registry records `pid`, `sessionId`, `name`, and `logPath`.
- It lacks a reliable `tmux` attach target.
- `attach` and `--bg` require additional design for startup/attachment metadata beyond simply filling in handlers.

---

## 3. `TEMPLATES`

### Current State
- Command entry points are limited to fast-paths in `src/entrypoints/cli.tsx`.
- Handlers in `src/cli/handlers/templateJobs.ts` are empty.
- `markdownConfigLoader.ts` includes `templates` in the config directory.
- `query/stopHooks.ts` has placeholders for job classifier links, but `src/jobs/classifier.ts` remains a stub.

### Goal
- Create a functional template task system using `new`, `list`, and `reply`.
- Avoid complex automatic classification or execution in the initial phase.

### MVP Plan
- **Template Source**: `.claude/templates/*.md`.
- **Format**: Reuse existing Markdown + frontmatter parsing (no new DSL).
- **`list`**:
  - List all templates.
  - Display template names, descriptions, and paths.
- **`new <template> [args...]`**:
  - Parse the template.
  - Create a job directory: `~/.claude/jobs/<job-id>/`.
  - Write `template.md`, `input.txt`, and `state.json`.
  - Return the job ID and directory.
- **`reply <job-id> <text>`**:
  - Write replies to `replies.jsonl` or `input.txt`.
  - Update `state.json`.

### Phase 2
- Recover `src/jobs/classifier.ts`.
- Ensure job sessions with `CLAUDE_JOB_DIR` automatically update `state.json` upon turn completion.
- Determine the necessity of an automatic job runner.

### Rationale
- Evidence suggests these are "template job commands," not just a template list.
- Since an automatic job runner lacks a ready implementation, focus on a stable filesystem-based job lifecycle first.

---

## 4. `assistant [sessionId]`

### Current State
- The main `attach` flow exists in `src/main.tsx`.
- Foundational modules for the remote viewer exist in `src/remote/RemoteSessionManager.ts`, `src/hooks/useAssistantHistory.ts`, and `src/assistant/sessionHistory.ts`.
- Key stubs include `sessionDiscovery.ts`, `AssistantSessionChooser.ts`, `assistant.ts` command, and `src/assistant/index.ts`.

### Goal
- Focus on making the viewer attachment work for explicit `sessionId`s first.
- Gradually add discovery, the chooser, and installation logic. Avoid recovering the entire KAIROS system at once.

### Phase 4A: MVP
- Support only `claude assistant <sessionId>`.
- For `claude assistant` without parameters, return a clear message:
  - Explicit `sessionId` is required in the current version.
  - Discovery is not yet enabled.
- This allows immediate reuse of the existing `attach` branch without recovering the chooser or install wizard.

### Phase 4B: Discovery
- Recover `discoverAssistantSessions()`.
- Prioritize reusing existing sessions, bridge, and teleport APIs for data sourcing.
- Enable `claude assistant` without parameters to retrieve a list of candidate sessions.

### Phase 4C: Chooser
- Recover `AssistantSessionChooser`.
- Enable interactive selection when multiple sessions are present.

### Phase 4D: Installation
- Consider helper functions for the install wizard (guiding the user when no sessions exist).

### Rationale
- The `attach` rendering layer and remote message channels are mostly present.
- The missing pieces are "how to discover the target session" and "how to choose interactively."
- Pulling in the full KAIROS normal mode from `src/assistant/index.ts` would cause significant scope creep.

---

## Recommended Execution Order

1.  `claude daemon status` / `claude daemon stop`.
2.  `BG_SESSIONS`: Implement `ps`, `logs`, and `kill` MVP.
3.  `TEMPLATES`: Implement the job filesystem MVP.
4.  `assistant [sessionId]`: Implement explicit `sessionId` attachment, followed by discovery/chooser/install.

## Conclusion

Of the four items, `daemon status/stop` is the most suitable for immediate implementation. `BG_SESSIONS` and `TEMPLATES` should start with MVP handlers and filesystem loops. `assistant [sessionId]` should be recovered incrementally through an "attach → discovery → chooser → install" workflow.
