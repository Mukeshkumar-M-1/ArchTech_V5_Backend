# Task 004: assistant [sessionId] — Phased Restoration

> Source: [stub-recovery-design-1-4.md](../features/stub-recovery-design-1-4.md) Item 4
> Priority: P3
> Effort: Medium for Phase 4A, very large for full completion of 4A-4D
> Status: Phase 4A DONE, 4B-4D TODO

## Goal

Do not restore the entire KAIROS assistant system at once. First, make "viewer attach with explicit sessionId" available, then gradually supplement discovery / chooser / install.

## Background

- The main attach flow already exists (`src/main.tsx:4708`).
- Basic modules required for the remote viewer already exist:
  - `src/remote/RemoteSessionManager.ts`
  - `src/hooks/useAssistantHistory.ts`
  - `src/assistant/sessionHistory.ts`
- True stubs are primarily:
  - `src/assistant/sessionDiscovery.ts`
  - `src/assistant/AssistantSessionChooser.tsx`
  - `src/commands/assistant/assistant.tsx:7`
  - `src/assistant/index.ts`

## Phased Implementation

### Phase 4A: MVP — Explicit sessionId attach

**Modified Files:**

| File | Change |
|------|------|
| `src/main.tsx` | Ensure the attach branch is available |
| `src/commands/assistant/index.ts` | Implement explicit sessionId parameter entry |

**Behavior:**
- `claude assistant <sessionId>` — Enter remote viewer.
- `claude assistant` (no parameters) — Return a clear prompt: current version requires an explicit sessionId, discovery not yet enabled.

**Verification:**
- [ ] `claude assistant <sessionId>` enters the remote viewer.
- [ ] History lazy loading works correctly.
- [ ] No-parameter mode provides a clear prompt.

### Phase 4B: session discovery

**Modified Files:**

| File | Change |
|------|------|
| `src/assistant/sessionDiscovery.ts` | Restore `discoverAssistantSessions()` |

**Behavior:**
- Prioritize reusing existing sessions / bridge / teleport APIs for data sources, without adding new protocols.
- `claude assistant` without parameters can obtain a candidate session list.

**Verification:**
- [ ] No-parameter call lists available sessions.
- [ ] Data sources reuse existing channels.

### Phase 4C: session chooser

**Modified Files:**

| File | Change |
|------|------|
| `src/assistant/AssistantSessionChooser.ts` | Restore interactive chooser |

**Behavior:**
- Interactive selection available when multiple sessions exist.

**Verification:**
- [ ] Chooser pops up when multiple sessions exist.
- [ ] Correctly attaches after selection.

### Phase 4D: install wizard

**Modified Files:**

| File | Change |
|------|------|
| `src/commands/assistant/assistant.ts` | Restore install wizard helper functions |

**Behavior:**
- Guide users on what to do when no sessions exist.

**Verification:**
- [ ] Guide users to create/connect when no sessions are available.

## Why split

- The attach rendering layer and remote message channels are mostly present.
- What's truly missing is "how to discover the target session" and "how to choose interactively."
- Bringing in the full set of KAIROS normal modes from `src/assistant/index.ts` would cause the scope to lose control.

## Risks

- This is the largest scope among the four items.
- Bringing in the full KAIROS normal mode could expand from "viewer attach" into "full assistant mode restoration."

## Dependencies

- Reusable session registry pattern from Task 002.
