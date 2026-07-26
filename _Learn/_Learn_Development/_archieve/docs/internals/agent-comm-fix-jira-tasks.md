# Agent Communication Fix Jira Tasks

- Version: v1.0
- Generation Date: 2026-04-25
- Source: Consolidated and merged from per-file execution checklists and Claude cross-validation feedback.
- Scope: ACP Agent / Bridge / Remote Control Server / REPL Hook Lifecycle
- Usage: This is the sole execution task document; each `JIRA-*` section can be directly split into a Jira issue, with uniform fields for easy copying or secondary import.

---

## Plan Nature

This document is a target-state execution plan, not a temporary patch list. Each ticket must deliver explicit code end-states, test coverage, and regression boundaries; do not use local workarounds to mask problems.

---

## Execution Principles

1. **Security First, Internal Optimization Second**: Fix WS ingress size limits and input validation first to prevent risk escalation.
2. **Per-File Rollbackable**: Keep modifications within each file cohesive to facilitate rollbacks and bisects.
3. **Preserve Protocol Semantics, Fix Implementation Defects**: Do not change the main flow contract, except for unifying `resource_link` expression.
4. **Acceptance Output for Every File**: Must have either test cases or log/metric verification.
5. **Pre-release Verification**: Ensure no regressions in protocol-layer behavior (stability of `stopReason` decisions and `sessionUpdate` send order).

---

## Epic

### JIRA-EPIC-001: Enhance Agent Communication Link Stability and Boundary Security

- Issue Type: Epic
- Priority: P0
- Owner: Core Communication / Backend Gateway / QA
- Scope: ACP Agent, ACP Bridge, Remote Control Server, REPL Initialization Lifecycle
- Goal: Fix long-session resource leaks, complete WebSocket ingress boundaries, unify prompt conversion, converge type risks, and add critical regression tests.

#### Epic Acceptance Criteria

- `bun run typecheck` passes with 0 errors.
- P0 WebSocket oversized message rejection logic is implemented and test-covered.
- ACP bridge abort listener lifecycle has no accumulation.
- Prompt conversion implementation is single-sourced.
- `settings/defaultMode` correctly influences ACP permission mode, with `_meta.permissionMode` maintaining highest priority.
- REPL target hook suppress cleanup is complete, and timer cleanup is fully implemented.

---

## P0 Tickets

### JIRA-001: Implement Message Size Limit for Session Ingress WebSocket

- Issue Type: Bug
- Priority: P0
- Story Points: 3
- Owner: Backend / Gateway
- Files:
  - `packages/remote-control-server/src/routes/v1/session-ingress.ts`
- Follow-up: JIRA-008 (Type convergence and decode path cleanup for the same file)

#### Reference Code Location

- `packages/remote-control-server/src/routes/v1/session-ingress.ts:100-106`

#### Background

`session-ingress` currently lacks a WebSocket message size limit. ACP routes already have a similar limit, and the inconsistency between the two ingress boundaries could lead to large packets consuming memory or bypassing ingress protection.

#### Implementation Requirements

- Add `MAX_WS_MESSAGE_SIZE = 10 * 1024 * 1024`, aligning with the 10MB limit of ACP routes.
- Prioritize checking payload size after `onMessage` decode.
- Execute `ws.close(1009, "message too large")` when the limit is exceeded.
- Log `sessionId`, payload size, and limit.
- Unify decode dispatching for `string`, `ArrayBuffer`, and `Uint8Array`.
- Directly reject and log unsupported types, bypassing business handlers.

#### Acceptance Criteria

- 11MB payload results in a 1009 close.
- 1KB valid payload still enters the handler normally.
- Unsupported type payloads do not enter the handler.
- URL, auth, and session parsing logic remain unchanged.

#### Regression Scope

- Remote Control Server session ingress WebSocket.
- Normal session message forwarding.
- WebSocket close code behavior.

#### Risk Level

- Medium. Changes to ingress logic may affect special client payload types.

#### Mandatory Verification

- Add test cases for large packets, small packets, and bad type payloads for session-ingress WebSocket in `packages/remote-control-server/src/__tests__/routes.test.ts`.
- Run `bun run typecheck`.

---

### JIRA-002: Fix ACP Bridge Abort Listener Lifecycle Leak

- Issue Type: Bug
- Priority: P0
- Story Points: 3
- Owner: Core Communication
- Files:
  - `src/services/acp/bridge.ts`

#### Reference Code Location

- `src/services/acp/bridge.ts:576-585`

#### Background

The `Promise.race` abort branch in ACP bridge lacks complete cleanup after registering a listener. Long sessions or high-frequency `next` scenarios may lead to listener accumulation.

#### Implementation Requirements

- Refactor the abort race to use a cleanable listener pattern.
- Retain the handler reference after registering the listener.
- Must call `removeEventListener` when `sdkMessages.next()` returns first.
- Ensure cleanup in a `finally` block for abort, throw, and return paths.
- Do not change `stopReason` decision logic.
- Do not change `sessionUpdate` send order.

#### Acceptance Criteria

- Simulate 10k `next` calls without aborting; listener count does not increase.
- Abort scenarios still return `cancelled`.
- No regressions in original streaming/session update behavior.

#### Regression Scope

- ACP bridge streaming loop.
- User-initiated request cancellation.
- SDK generator exception paths.

#### Risk Level

- Medium. Changes to asynchronous control flow require coverage of cancellation and exception paths.

#### Mandatory Verification

- Add unit tests for listener cleanup.
- Run `bun run typecheck`.

---

## P1 Tickets

### JIRA-003: Optimize ACP Agent Pending Prompt Queue for O(1) Dequeue

- Issue Type: Task
- Priority: P1
- Story Points: 5
- Owner: Core Communication
- Files:
  - `src/services/acp/agent.ts`

#### Reference Code Location

- `src/services/acp/agent.ts:332-339`

#### Background

The current pending prompt queue uses `Map + sort` to retrieve the next item, which incurs unnecessary sorting costs as the queue size grows.

#### Implementation Requirements

- Change to a `queue: string[]` + `pendingMap: Map<string, PendingPrompt>` combination.
- Enqueue by executing `queue.push(id)` and `pendingMap.set(id, prompt)`.
- Dequeue by lazily skipping cancelled items from the front of the queue.
- Cancellation should only delete from `pendingMap`, avoiding array middle deletions.
- Maintain existing cancellation semantics and dequeue order.

#### Acceptance Criteria

- Dequeue order is correct in a 1000 pending prompt scenario.
- Cancelled prompts are not resolved.
- Dequeue no longer depends on full sorting.
- Dequeue latency for 1000 queued prompts is lower than the old implementation; tests should document the complexity risk of the old implementation and the O(1) dequeue path of the new implementation.
- Behavior is compatible with the old implementation.

#### Regression Scope

- ACP prompt queue.
- Concurrent prompt requests.
- Prompt cancel / resolve boundaries.

#### Risk Level

- Medium. Changes to queue structure may introduce cancellation boundary issues.

#### Mandatory Verification

- Add tests for queue order and cancellation.
- Perform performance assertions or logging for the 1000 prompt scenario.

---

## JIRA-004: Integrate Real Settings and Validate ACP Permission Mode

- Issue Type: Bug
- Priority: P1
- Story Points: 3
- Owner: Core Communication
- Files:
  - `src/services/acp/agent.ts`

#### Reference Code Location

- `src/services/acp/agent.ts:465-467`

#### Background

`getSetting()` is currently not integrated with project configuration, causing the default permission mode setting to fail.

#### Implementation Requirements

- Integrate with existing project settings/config retrieval logic.
- Accept only valid permission mode enum values.
- Fallback to `default` for invalid values.
- `_meta.permissionMode` continues to hold the highest priority.
- Do not change external protocol fields.

#### Acceptance Criteria

- `settings/defaultMode` correctly influences the default permission mode.
- `_meta.permissionMode` correctly overrides settings.
- Invalid settings values do not propagate to runtime.
- Type checks pass.

#### Regression Scope

- ACP agent session initialization.
- Permission mode synchronization.
- Client `_meta` override logic.

#### Risk Level

- Medium. Incorrect configuration priority affects permission behavior.

#### Mandatory Verification

- Add priority tests for `defaultMode` / `_meta.permissionMode`.
- Run `bun run typecheck`.

---

### JIRA-005: Single-Source ACP Prompt Conversion Logic

- Issue Type: Refactor
- Priority: P1
- Story Points: 5
- Owner: Core Communication
- Files:
  - `src/services/acp/agent.ts`
  - `src/services/acp/bridge.ts`
  - `src/services/acp/promptConversion.ts` (New)

#### Reference Code Location

- `src/services/acp/agent.ts:754-758`
- `src/services/acp/agent.ts:764-785`
- `src/services/acp/bridge.ts:522-537`

#### Background

Duplicate prompt conversion logic exists in ACP agent and bridge, and output strategies for blocks like `resource_link` are prone to divergence.

#### Implementation Requirements

- Create a shared conversion module `src/services/acp/promptConversion.ts`.
- Refactor `agent.ts` and `bridge.ts` to call shared conversion functions.
- Remove the actual implementation of `promptToQueryContent` from `bridge.ts`; if exports must be retained, only allow a wrapper that calls the shared function.
- Change `resource_link` output to stable plain text metadata, prohibiting markdown links.
- Maintain conversion semantics for other blocks.

#### Acceptance Criteria

- Only one actual prompt conversion implementation remains in the repository.
- Identical input blocks result in consistent output in agent/bridge.
- `resource_link` no longer outputs `[name](uri)` format.
- Tests cover conversion consistency.

#### Regression Scope

- ACP prompt input.
- Bridge query content.
- Resource link prompt expression.

#### Risk Level

- Medium. Changes to text format may affect downstream prompt snapshots or assertions.

#### Mandatory Verification

- Add unit tests for shared conversion.
- Search for duplicate conversion functions across the repository.
- Run `bun run typecheck`.

---

### JIRA-006: Clean Up REPL onInit Effect Dependencies and Add Timer Cleanup

- Issue Type: Task
- Priority: P1
- Story Points: 3
- Owner: Terminal UI
- Files:
  - `src/screens/REPL.tsx`

#### Reference Code Location

- `src/screens/REPL.tsx:654-662`
- `src/screens/REPL.tsx:4996-5005`

#### Background

The target initialization effect in REPL has hook dependency suppression, and the warm-up timer requires explicit cleanup to avoid dangling tasks during frequent mount/unmount.

#### Implementation Requirements

- Organize the `onInit` lifecycle using stable references or effect inlining.
- Remove `exhaustive-deps` suppression for target segments.
- Maintain existing unmount cleanup behavior.
- Record timeout ID in the warm-up effect.
- Execute `clearTimeout(timeoutId)` in cleanup.
- Retain `alive` check as concurrency protection.

#### Acceptance Criteria

- Target segments no longer require hooks lint suppression.
- High-frequency toggling of the search bar results in no dangling timer growth.
- No regressions in REPL initialization behavior.

#### Regression Scope

- REPL initialization.
- Search bar warm-up.
- Component unmount cleanup.

#### Risk Level

- Medium. Managing React effect dependencies may alter initialization timing.

#### Mandatory Verification

- Run lint/typecheck.
- Manually or via tests cover REPL mount/unmount.

---

### JIRA-007: Converge Any Types in ACP Route WebSocket Events

- Issue Type: Task
- Priority: P1
- Story Points: 2
- Owner: Backend / Gateway
- Files:
  - `packages/remote-control-server/src/routes/acp/index.ts`

#### Reference Code Location

- `packages/remote-control-server/src/routes/acp/index.ts:108-146`

#### Background

`any` types exist for WebSocket events and socket parameters in the ACP route, reducing compile-time protection.

#### Implementation Requirements

- Define minimal WebSocket event types: open/message/close/error.
- Replace `_evt: any`, `evt: any`, and `ws: any` with narrow types.
- Do not change payload decode and size check strategies.
- Do not change existing handler behavior.

#### Acceptance Criteria

- Compile-time errors are caught for incorrect event field access.
- Existing WebSocket behavior remains unchanged.
- `bun run typecheck` passes.

#### Regression Scope

- ACP WebSocket route.
- Message decode.
- Close/error handler.

#### Risk Level

- Low. Primarily type convergence.

#### Mandatory Verification

- Run `bun run typecheck`.
- Ensure existing tests pass.

---

### JIRA-008: Converge Session Ingress WebSocket Event Types and Decode Path

- Issue Type: Task
- Priority: P1
- Story Points: 3
- Owner: Backend / Gateway
- Files:
  - `packages/remote-control-server/src/routes/v1/session-ingress.ts`
- Pre-requisite: JIRA-001 merged

#### Reference Code Location

- `packages/remote-control-server/src/routes/v1/session-ingress.ts:100-106`

#### Background

After completing the P0 size guard, session ingress still requires further convergence of event types and decode paths to reduce implicit type risks.

#### Implementation Requirements

- Define or reuse minimal WebSocket message event types.
- Consolidate message decode branches into a small function.
- Maintain P0 size guard and close code semantics.
- Do not change auth/session parsing.

#### Acceptance Criteria

- Decode path is single and clear.
- Explicit rejection path for unsupported payload types.
- `bun run typecheck` passes.

#### Regression Scope

- Session ingress WebSocket message handling.
- P0 oversized packet rejection logic.

#### Risk Level

- Low to Medium. Same file as JIRA-001; avoid overlapping conflict.

#### Mandatory Verification

- Test alongside JIRA-001.
- Run `bun run typecheck`.

---

## QA Tickets

### JIRA-009: Supplement ACP Communication Regression Tests

- Issue Type: Test
- Priority: P1
- Story Points: 5
- Owner: QA / Core Communication
- Files:
  - `src/services/acp/agent.ts`
  - `src/services/acp/bridge.ts`
  - `src/services/acp/promptConversion.ts`
  - `src/services/acp/__tests__/agent.test.ts`
  - `src/services/acp/__tests__/bridge.test.ts`
  - `src/services/acp/__tests__/promptConversion.test.ts`

#### Scenarios Covered

- Long session with 10k turns, no abort listener accumulation.
- Prompt queue with 1000 concurrent items; correct cancellation/dequeue order.
- Correct priority for `settings/defaultMode` and `_meta.permissionMode`.
- Consistent `resource_link` conversion in agent and bridge.

#### Acceptance Criteria

- New tests pass stably locally.
- No dependency on real networks or external services.
- Test mocks follow repository conventions (mocking only side-effect paths).

#### Regression Scope

- ACP bridge.
- ACP agent.
- Prompt conversion.
- Permission mode resolution.

#### Risk Level

- Medium. Asynchronous tests may have stability issues; avoid time-sensitive assertions.

#### Mandatory Verification

- Run relevant `bun test`.
- Run `bun run typecheck`.

---

### JIRA-010: Supplement Remote Control Server WebSocket Ingress Regression Tests

- Issue Type: Test
- Priority: P1
- Story Points: 3
- Owner: QA / Backend
- Files:
  - `packages/remote-control-server/src/__tests__/routes.test.ts`
  - `packages/remote-control-server/src/routes/v1/session-ingress.ts`

#### Scenarios Covered

- 11MB session ingress payload results in a 1009 close (aligning with the 10MB limit).
- Valid small payloads enter handlers normally.
- Unsupported payload types are rejected.
- Logs or observable output include sessionId, payload size, and limit.

#### Acceptance Criteria

- 11MB payload results in a 1009 close (aligning with the 10MB limit).
- New tests pass stably.
- No real external services are started.
- Do not change existing route public contract.

#### Regression Scope

- RCS session ingress route.
- WebSocket message handling.
- Close code behavior.

#### Risk Level

- Medium. Tests need to adapt to existing WebSocket/mock infrastructure.

#### Mandatory Verification

- Run RCS package related tests.
- Run `bun run typecheck`.

---

## Recommended Execution Order

Execution pace remains consistent with the original plan: complete all P0 changes and smoke verification before starting P1 refactoring; test tickets can be executed in parallel but must not bypass the P0 gate.

1. JIRA-001: Seal ingress oversized packet risk.
2. JIRA-002: Fix long-session listener lifecycle.
3. JIRA-010: Add RCS ingress tests, locking in P0 behavior.
4. JIRA-003: Optimize pending prompt queue.
5. JIRA-004: Integrate settings/defaultMode.
6. JIRA-005: Single-source prompt conversion.
7. JIRA-009: Add ACP regression tests.
8. JIRA-006: Clean up REPL effect/timer.
9. JIRA-007: Converge ACP route types.
10. JIRA-008: Converge session ingress types and decode path.

---

## Release Checklist

- [ ] `bun run typecheck` passes with 0 errors
- [ ] P0 tickets merged and tested
- [ ] ACP regression tests pass
- [ ] RCS WebSocket ingress tests pass
- [ ] Single-sourced prompt conversion confirmed via code search
- [ ] Permission mode priority tests pass
- [ ] No regressions in protocol-layer behavior (stopReason decisions, sessionUpdate send order)
- [ ] REPL hook/timer changes pass lint/typecheck
- [ ] Final change notes include risks and uncovered items
