# Code Review Progress
## 2026-05-03 — The first round of CRUD business logic layer Code Review 

### Scope of review 
Reviewed 4 core CRUD modules: task management (tasks.ts), settings management (settings.ts), plug-in management (installedPluginsManager.ts), and team collaboration mailbox (teammateMailbox.ts). 

### Change content 
1. **New `src/utils/__tests__/tasks.test.ts`** — 37 tests covering complete CRUD operations: create/read/update/delete tasks, high water mark to prevent ID reuse, file lock concurrency safety, blockTask bidirectional relationship, claimTask race protection (including agent_busy check), resetTaskList, notification signal mechanism, concurrent creation of unique ID verification. 

### Code Review Discovery 
- tasks.ts has a reasonable structure, and file locks + high water marks ensure concurrency safety. 
- settings.ts dependency chain is too deep (MDM/remote management/file system), 63 existing tests have good coverage 
- installedPluginsManager.ts V1→V2 has clear migration logic and good memory/disk status separation design 
- teammateMailbox.ts 25 existing tests cover pure functions, and the protocol message detection function is complete

## 2026-05-05 — The first round of user thinking Design Review 

### Scope of review 
Examine the CLI interaction experience from a user perspective: Onboarding process, Trust Dialog, error messages, Help Menu. Focus on user-friendliness issues at the non-code level. 

### Unfriendly issues found 
1. **The error message lacks actionable tips**: When the budget exceeds the limit/max turns are exhausted, it only informs the user that "an error occurred" and does not guide the user how to continue. 
2. **Onboarding security notes are cold**: The title of "Security notes" is too technical and users can easily skip it. 
3. **Trust Dialog has lengthy copy**: The language of the security check dialog box is official, and the core information is submerged. 

### Change content 
1. **`src/cli/print.ts`** — Add Tip lines for 3 error subtypes (budget/turns/structured-output) to inform users of specific solutions 
2. **`src/QueryEngine.ts`** — Add `--max-budget-usd` guidance to budget overrun error message 
3. **`src/components/Onboarding.tsx`** — The title of the safety steps is changed to "Before you start, keep in mind", and the entry copy is more colloquial 
4. **`src/components/TrustDialog/TrustDialog.tsx`** — Simplified into two sentences of core information to reduce cognitive load 
5. **`src/cli/__tests__/userFacingErrorMessages.test.ts`** — 7 test verification message contents contain key boot information 

## 2026-05-05 — Second round of permissions and help system Design Review 

### Scope of review 
Examine permission interaction prompts (prompt line at the bottom of Bash/File permission dialog box), Help page guidance, and permission option label length from a user perspective. 

### Unfriendly issues found 
1. **The bottom prompt of the permission dialog box has ambiguous semantics**: "Esc to cancel" is not as clear as "Esc to reject", and "Tab to amend" the user does not know what to do 
2. **Help General page lacks novice guidance**: There is only one sentence + all shortcut keys, and new users don’t know where to start. 
3. **.claude/ folder permission option label is too long** (60+ characters), truncated by narrow terminal 

### Change content 
1. **`src/components/HelpV2/General.tsx`** — Add a 3-step "Getting started" guide to replace the original single paragraph description 
2. **`src/components/permissions/BashPermissionRequest/BashPermissionRequest.tsx`** — Bottom "cancel"→"reject", "amend"→"add feedback" 
3. **`src/components/permissions/FilePermissionDialog/FilePermissionDialog.tsx`** — synchronize bottom prompt words 
4. **`src/components/permissions/FilePermissionDialog/permissionOptions.tsx`** — .claude/ options label reduced from 60 characters to 49 characters 
5. **`src/components/HelpV2/__tests__/General.test.ts`** — 10 tests covering permission prompt copy and help page guidance content
## 2026-05-05 — The third round of model selection and session recovery Design Review 

### Scope of review 
Examine the ModelPicker selector, the error prompt of the /resume session recovery command, and the cost command display from a user perspective. 

### Unfriendly issues found 
1. **ModelPicker subtitle information overload**: Model switching instructions and --model parameter prompts are mixed in one sentence, which may easily confuse new users. 
2. **Resume error message lacks operation guidance**: "Session X was not found" and does not tell the user how to list all sessions. 

### Change content 
1. **`src/components/ModelPicker.tsx`** — The subtitle is changed from technical description to operation tips ("← → adjust effort, Space switch 1M context"), controlled within 120 characters 
2. **`src/commands/resume/resume.tsx`** — Add "Run /resume to browse" operation guide to error prompt 
3. **`src/commands/resume/__tests__/resume.test.ts`** — 6 tests covering model selector, session recovery, cost message copy 

## 2026-05-05 — The fourth round of compression and context management Design Review 

### Scope of review 
Examine the /compact command experience, automatic compression prompts, context window exhaustion errors, and CompactSummary component display from a user perspective. 

### Unfriendly issues found 
1. **"Not enough messages to compact" Lack of guidance**: Users don’t know what to do next 
2. **The operation of "Press esc twice" prompted by "Conversation too long" is not intuitive**: esc twice is a fuzzy operation for users. 
3. **The "Compact summary" title is not informative to users**: Users do not know what happened during automatic compression. 

### Change content 
1. **`src/services/compact/compact.ts`** — "Not enough messages" adds "Send a few more messages first" guidance; "Conversation too long" recommends `/compact` or `/clear` instead 
2. **`src/components/CompactSummary.tsx`** — The automatic compression title is changed from "Compact summary" to "Conversation summarized to free up context", and the shortcut key tip is changed from "expand" to "view summary" 
3. **`src/components/__tests__/compactMessages.test.ts`** — 7 tests covering compression error messages and presentation copy