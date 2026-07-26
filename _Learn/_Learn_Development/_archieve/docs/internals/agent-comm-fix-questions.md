# Agent Communication Fix Questions Document

- Version: v1.0
- Generation Date: 2026-04-25
- Scope: ACP Agent / Bridge / Remote Control Server / REPL Hook Lifecycle
- Supporting Execution Document: `docs/internals/agent-comm-fix-jira-tasks.md`
- Purpose: Retain questions to be asked before decision-making, cross-validation prompts, and confirmed conclusions; do not write Jira execution steps here.

---

## 1. Confirmed Conclusions

- Only two delivery documents are maintained: this Questions document + the Jira Task document.
- The Jira Task document is the sole entry point for execution, containing Owner, priority, file scope, acceptance criteria, risks, and verification suggestions.
- Claude Cross-Validation Conclusions: Overall passed with no blocking findings; suggestions were made to add protocol regression gates, JIRA-001/008 dependencies, reference code locations, and threshold consistency, all of which have been merged into the Jira Task document.
- The project has entered the business code fix phase, necessitating the running of `bun run typecheck` and relevant regression tests.

---

## 2. Mandatory Questions Before Execution

1. Is the WebSocket message size limit for `session-ingress` fixed at 10MB, consistent with the ACP route?
2. Is the oversized packet close code unified to `1009`, and is the close reason fixed to `message too large`?
3. Does the plain text format for `resource_link` have any downstream dependencies, and can it replace the current markdown link expression?
4. Which is the actual settings key for ACP permission mode, and is the fallback for invalid values unified to `default`?
5. Must `_meta.permissionMode` always override `settings/defaultMode`?
6. In abort listener tests, can mock signals or counters stably prove no listener accumulation after 10k `next` calls?
7. Does the pending prompt queue cancellation semantics allow for lazy cleanup instead of immediate array deletion?
8. Is the cleanup scope for REPL hook suppression limited to the target segment, without inadvertently modifying other decompiled React Compiler structures?
9. Under which existing `__tests__` layout should the RCS WebSocket tests be placed, and are there existing route/mock infrastructures reusable?
10. Must the release gate include ensuring no regressions in `stopReason` decisions and `sessionUpdate` send order?

---

## 3. Review Questions for Claude or Reviewer

```text
Please act as an external reviewer and review docs/internals/agent-comm-fix-jira-tasks.md.

Please check:
1. Does it still meet the requirements of an "execution checklist divided by file" and a "Jira task document"?
2. Are there any missing files, acceptance criteria, risks, or pre-requisite dependencies?
3. Are there any issues such as duplication, misleading instructions, unreasonable priorities, or unverifiable tests?
4. Are there any findings that must block implementation?

Please output in English:
- Verdict
- Blocking Findings
- Non-blocking Findings
- Suggested Edits
- Final Recommendation

Do not modify the file; only output review feedback.
```

---

## 4. Addressed Review Suggestions

- The Release Checklist has been supplemented with a gate for no regression in protocol-layer behavior.
- The dependency relationship between JIRA-001 and JIRA-008 in the same file has been clarified.
- Reference code locations have been added to JIRA-001 through JIRA-008.
- JIRA-003 has added dequeue latency acceptance for the 1000 queued prompt scenario.
- JIRA-008 story points have been adjusted from 2 to 3.
- JIRA-010 has specified the 11MB payload alignment with the 10MB limit and the triggering of 1009 close.
- The recommended execution order has specified a P0 gate: complete all P0 changes and smoke verification before starting P1 refactoring.

---

## 5. Content Not Maintained in This Document

- Do not maintain the body of Jira tickets; modify them uniformly in `docs/internals/agent-comm-fix-jira-tasks.md`.
- Do not maintain business code implementation plans; read the corresponding file according to the specific ticket during implementation.
- Do not maintain historical intermediate drafts; the old execution checklist has been merged into the Jira Task document.
