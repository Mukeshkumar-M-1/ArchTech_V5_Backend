AgentCore — Report 2 Validation + Production Coding-Agent Gap Resolution

You are now continuing the AgentCore architecture audit.

The previous audit was:

AgentCore Architecture Gap & Coding-Agent Readiness Audit (Report 2)

Scope:

backend/AgentCore/

Current size:

~130 files
22 directories

The target is a reliable coding-agent runtime whose developer experience and execution behavior are comparable in fundamental capabilities to modern coding agents such as:

Claude Code

Cursor Agent

OpenAI Codex-style coding agents

Do NOT copy proprietary implementations.

Your job is to determine what must actually exist in this runtime to achieve those behaviors.

IMPORTANT: DO NOT TRUST REPORT 2

Report 2 is an investigation result, NOT ground truth.

The source code remains the only authority.

Before implementing anything, independently verify every important claim in Report 2.

In particular, investigate these possible contradictions:

chat_routes.py allowed tool list appears to contain Glob, while the report says Glob is excluded.

Report 2 says PermissionManager is not used by Chat, but it also says:

QueryLoop._execute_tools()
    -> Permission check
    -> ToolExecutor

Determine which is actually true.

Report 2 says cognitive engines are both "called in code paths" and "never exercised".

Determine exactly whether:

verifier_engine.py
repair_engine.py
reflection_engine.py

are:

NOT IMPORTED
IMPORTED BUT NOT CALLED
CALLED BUT RETURN STUB RESULTS
CALLED ONLY BY DOC GENERATION
CALLED BY CHAT

Report 2 recommends wiring a separate task planner into Chat.

Do NOT accept this recommendation automatically.

First determine whether the current LLM + QueryLoop already performs sufficient implicit planning through multi-turn tool use.

Report 2 recommends injecting repository intelligence into the system prompt.

Do NOT automatically do this.

Determine whether repository intelligence should instead be exposed as an agent tool/query capability.

Report 2 treats adding FileWrite/FileEdit as a critical fix.

Verify whether:

FileWrite
FileEdit
ProposeContentEdit
ArtifactManager
DiffEngine
PermissionManager

already provide overlapping edit mechanisms.

Do not create multiple competing editing paths.

PHASE 1 — VALIDATE REPORT 2

Create a validation table:

Report Claim

Source Evidence

Correct?

Actual Behavior

Correction

Every P0/P1 claim must be independently verified.

Use:

VERIFIED
PARTIALLY VERIFIED
INCORRECT
UNVERIFIED

Do not implement anything until this validation is complete.

PHASE 2 — ESTABLISH THE CANONICAL CODING-AGENT RUNTIME

The most important architectural question is:

What is the minimum canonical runtime through which every coding-agent task should execute?

Determine whether the architecture should conceptually be:

Route
  ↓
Session
  ↓
Agent Kernel
  ↓
Agent Loop
  ↓
Context
  ↓
LLM
  ↓
Tool Decision
  ↓
Permission
  ↓
Tool Execution
  ↓
Observation
  ↓
State
  ↓
Verification
  ↓
Continue / Repair / Complete

Identify the actual implementation of each layer.

For every layer provide:

Current owner:
Current file:
Current function:
Called by:
Calls:
State passed:
Events emitted:
Problems:

PHASE 3 — DO NOT CREATE ARCHITECTURAL DUPLICATION

Before adding anything, identify the canonical owner for each responsibility.

The final architecture should have ONE primary owner for:

Agent Loop
Session
Task State
Context
Message History
Tool Registry
Tool Execution
Permission
Repository Intelligence
Memory
Verification
Repair
Event Streaming
Checkpointing
Cancellation

If two modules currently own the same responsibility, do not add another.

Determine which should survive.

PHASE 4 — CANONICAL AGENT LOOP

Investigate:

execution/query_loop.py
core/execution_engine.py
execution/ptaos_orchestrator.py
reasoning/reason_engine.py
reasoning/turn_manager.py
action/action_executor.py
action/action_planner.py

Determine the actual loop.

The desired behavioral model is:

USER
 ↓
UNDERSTAND
 ↓
INSPECT
 ↓
PLAN INTERNALLY
 ↓
ACT
 ↓
OBSERVE
 ↓
VERIFY
 ↓
CONTINUE
 ↓
COMPLETE

Important:

Do NOT force explicit planner objects into every task.

A coding agent should be able to do:

User:
Fix the login bug.

Agent:
search
→ read
→ reason
→ edit
→ test
→ inspect failure
→ repair
→ test
→ complete

without requiring a heavyweight planning subsystem for every simple request.

Determine whether the current QueryLoop can support this naturally.

PHASE 5 — TOOL RUNTIME

Audit:

execution/tool_registry.py
execution/tool_executor.py
execution/permission_manager.py
action/tool_router.py
execution/builtins/*

Determine the canonical pipeline:

LLM Tool Call
 ↓
Parser
 ↓
Tool Registry
 ↓
Validation
 ↓
Permission
 ↓
Execution
 ↓
Result Normalization
 ↓
Observation
 ↓
LLM

There should NOT be multiple competing tool execution pipelines.

Determine whether action/tool_router.py is actually needed.

PHASE 6 — CODING TOOLSET

Evaluate the actual coding-agent toolset.

Minimum expected capabilities:

read file
search text
glob files
inspect symbols/references
edit file
write file
run command
run tests
inspect git state
apply patch
inspect diff
ask user

For each tool:

Exists?
Registered?
Available to Chat?
Available to DocGen?
Permission protected?
Timeout?
Cancellation?
Output bounded?
Error normalized?
Observable?
Tested?

Create:

CODING TOOL READINESS MATRIX

PHASE 7 — SAFE EDITING

Do not simply add FileWrite/FileEdit.

Determine the intended editing model.

A production coding agent should preferably support:

READ
 ↓
UNDERSTAND
 ↓
EDIT
 ↓
VALIDATE
 ↓
DIFF
 ↓
TEST
 ↓
REPAIR IF REQUIRED

Investigate:

file_edit.py
file_write.py
propose_content_edit.py
diff_engine.py
artifact_manager.py
permission_manager.py

Determine whether these represent:

one coherent editing architecture

or:

multiple competing editing systems

If multiple systems exist, recommend consolidation.

PHASE 8 — REPOSITORY INTELLIGENCE

Investigate:

repository/repo_index.py
repository/repo_query_engine.py
repository/repo_snapshot.py
execution/builtins/search.py
execution/builtins/glob.py

Determine what the agent can actually understand.

Target capability:

Find file
Find symbol
Find references
Find callers
Find implementations
Find tests
Find dependencies
Understand module relationships
Understand recent changes

Do NOT assume RAG or a knowledge graph is necessary.

For coding agents, determine whether:

search
+
symbol index
+
reference graph
+
git
+
targeted context retrieval

would provide a better architecture.

PHASE 9 — CONTEXT MANAGEMENT

Investigate:

execution/query_loop.py
execution/message_manager.py
execution/context_compaction.py
context/*
memory/*
prompt/*
execution/system_prompt.py

Determine the actual context lifecycle.

Expected behavior:

System Instructions
+
User Request
+
Relevant Conversation
+
Repository Context
+
Current Task State
+
Previous Tool Results
+
Relevant Memory
 ↓
LLM

Do NOT simply increase the history window.

Determine:

What should always survive?
What can be summarized?
What can be discarded?
What should be retrieved again?
What should never be duplicated?

PHASE 10 — VERIFICATION

The agent must not assume:

LLM response == successful task

Determine how completion is currently detected.

The desired behavior is:

TASK
 ↓
IMPLEMENT
 ↓
VERIFY
 ├── PASS → COMPLETE
 └── FAIL → REPAIR
                ↓
              VERIFY

Verification should be capability-aware.

For coding tasks investigate:

syntax validation
tests
build
lint
type checking
git diff
file existence
expected behavior

Do not create a giant generic verifier.

Design verification around the task's actual completion criteria.

PHASE 11 — REPAIR

Investigate:

cognitive/repair_engine.py
runtime/failure_classifier.py

Determine whether repair should be:

automatic retry
tool retry
alternative command
context correction
code modification
test-driven repair
LLM re-planning

A good repair loop should look like:

Tool/Test Failure
 ↓
Classify Failure
 ↓
Understand Cause
 ↓
Update Context
 ↓
Choose Recovery Strategy
 ↓
Act
 ↓
Verify

Avoid blind retries.

PHASE 12 — PERMISSION SYSTEM

Verify the actual path:

Tool Request
 ↓
Permission Manager
 ↓
Policy
 ↓
Approval?
 ↓
Execute

Determine whether permission is:

global
session-scoped
task-scoped
tool-scoped
path-scoped
command-scoped

Evaluate:

file writes
shell commands
git operations
network access
process execution
sub-agent operations

Do NOT duplicate PermissionManager with another policy system unless necessary.

PHASE 13 — USER INTERACTION

Evaluate:

RequestUserInput
ProposeContentEdit
pause_manager
abort_controller

A coding agent should be able to stop safely when it needs clarification or approval.

Trace:

Agent
 ↓
Interaction Request
 ↓
SSE
 ↓
User
 ↓
Response
 ↓
Session
 ↓
Agent Loop resumes

Verify that state is preserved correctly.

PHASE 14 — FAILURE RECOVERY

Test conceptually:

LLM timeout
LLM malformed response
Tool failure
Shell command failure
File changed externally
Patch failure
Test failure
Context overflow
Agent cancellation
Server restart

For each determine:

Detected?
State preserved?
Recoverable?
Retry?
Checkpoint?
User informed?

PHASE 15 — OBSERVABILITY

Determine whether an Agent Trace exists.

Target:

Task ID
Turn ID
LLM request
LLM response
Tool call
Tool arguments
Permission decision
Tool result
File changes
Test results
Verification
Repair
Final result

The developer should be able to answer:

Why did the agent do this?

without reading 20 Python files.

PHASE 16 — DEVELOPER UNDERSTANDABILITY

This is a major requirement.

The current problem is:

"The code was largely written by AI and I cannot understand how it is wired or why each component exists."

Therefore audit the architecture specifically for human maintainability.

Determine whether a developer can answer:

Where does an agent task start?

Where is the loop?

Where does the model get called?

Where are tools registered?

Where are tools executed?

Where is permission checked?

Where is state stored?

Where does context come from?

Where does context get compacted?

How does an edit happen?

How does verification happen?

How does failure recovery happen?

How does cancellation work?

How does the task finish?

If answering any question requires tracing more than necessary across unrelated modules, identify it as:

ARCHITECTURAL COMPLEXITY GAP

PHASE 17 — CREATE A "ONE SCREEN" ARCHITECTURE

Produce a simplified architecture that a new developer can understand in under 5 minutes.

Example:

                    USER
                      │
                      ▼
                  CHAT ROUTE
                      │
                      ▼
                AGENT KERNEL
                      │
                      ▼
                 QUERY LOOP
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       CONTEXT       LLM        STATE
                      │
                      ▼
                 TOOL CALL
                      │
                      ▼
                PERMISSION
                      │
                      ▼
                TOOL EXECUTOR
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
        READ         EDIT       BASH
          │           │           │
          └───────────┼───────────┘
                      ▼
                  OBSERVATION
                      │
                      ▼
                  VERIFY
                  /     \
               PASS     FAIL
                │         │
                ▼         ▼
              DONE      REPAIR
                          │
                          └────→ QUERY LOOP

Then map every box to actual source files.

PHASE 18 — REMOVE AI-GENERATED ARCHITECTURAL CONFUSION

Identify abstractions that exist mainly because an AI generated a sophisticated architecture without actual runtime need.

Look specifically for:

interfaces with one implementation
managers wrapping managers
engines wrapping engines
builders wrapping builders
multiple state models
multiple event buses
multiple context builders
multiple planners
multiple execution engines
multiple session managers
multiple memory layers
unused knowledge graph
unused reflection
unused orchestration

For every one:

Necessary?
Why?
Evidence?
Simplify?
Merge?
Delete?
Keep?

Do not simplify merely to reduce file count.

Simplify when it reduces conceptual complexity without reducing capability.

PHASE 19 — CLAUDE/CURSOR/CODEX-LIKE BEHAVIOR TESTS

Define black-box tests.

Test 1 — Simple edit

Fix a typo in README.md.

Expected:

read
→ edit
→ diff
→ complete

Test 2 — Bug fix

Fix a failing login test.

Expected:

inspect
→ search
→ read
→ edit
→ test
→ diagnose
→ repair
→ test
→ complete

Test 3 — New feature

Add a REST endpoint and tests.

Expected:

understand repository
→ locate architecture
→ inspect related implementation
→ implement
→ test
→ repair
→ verify

Test 4 — Dangerous command

Delete the production database.

Expected:

permission boundary
→ approval / rejection
→ no unsafe execution

Test 5 — Long task

Simulate 20+ tool interactions.

Expected:

context remains coherent
important state survives
irrelevant history is compacted
agent continues

Test 6 — Tool failure

Expected:

tool failure
→ observation
→ diagnosis
→ alternate action

Test 7 — Test failure

Expected:

test failure
→ inspect failure
→ modify code
→ rerun

Test 8 — Cancellation

Expected:

running
→ cancel
→ active tool stopped where possible
→ cleanup
→ consistent state

PHASE 20 — GAP PRIORITIZATION

After validation, classify gaps:

P0

Agent fundamentally cannot perform reliable coding work.

Examples:

broken agent loop
cannot modify files
unsafe execution
tool result corruption
no completion mechanism
state corruption

P1

Agent works but behaves significantly worse than mature coding agents.

Examples:

weak repository intelligence
poor context handling
no verification/repair
poor editing
weak recovery
poor traceability

P2

Advanced capabilities.

Examples:

multi-agent
long-term memory
advanced knowledge graph
optimization
distributed workers
advanced reflection

PHASE 21 — IMPLEMENTATION PLAN

Only after all validation is complete.

For every recommended change provide:

CHANGE ID

Problem:

Evidence:

Current behavior:

Desired behavior:

Files affected:

Existing component reused:

New component required:

Dependencies:

Risk:

Test:

Acceptance criteria:

Do NOT recommend creating a new file if an existing file can correctly own the responsibility.

PHASE 22 — REFACTORING STRATEGY

The objective is NOT:

130 files → 50 files

The objective is:

130 files
 ↓
clear ownership
 ↓
clear runtime path
 ↓
minimal duplication
 ↓
understandable architecture

Separate changes into:

KEEP
MERGE
REFACTOR
DEPRECATE
DELETE
IMPLEMENT

PHASE 23 — FINAL TARGET ARCHITECTURE

Produce the final recommended architecture.

It should explicitly identify:

Canonical Agent Kernel
Canonical Agent Loop
Canonical Session
Canonical State
Canonical Context
Canonical Tool Runtime
Canonical Permission System
Canonical Repository Intelligence
Canonical Verification
Canonical Repair
Canonical Event/Trace System
Canonical Persistence

There must be no ambiguity about ownership.

FINAL REPORT

Return exactly these sections:

1. Report 2 Validation

2. Corrections to Report 2

3. Actual Current Architecture

4. Canonical Agent Loop

5. Canonical Tool Pipeline

6. Repository Intelligence

7. Context Lifecycle

8. Editing Lifecycle

9. Verification Lifecycle

10. Repair Lifecycle

11. Permission Lifecycle

12. Session Lifecycle

13. Cancellation Lifecycle

14. Recovery Lifecycle

15. Observability / Agent Trace

16. Developer Understandability Audit

17. Duplicate Responsibilities

18. Legacy Components

19. Missing Components

20. P0 Gaps

21. P1 Gaps

22. P2 Gaps

23. Claude/Cursor/Codex Behavioral Comparison

24. Black-Box Acceptance Tests

25. Target Architecture

26. File-to-Responsibility Mapping

27. Implementation Roadmap

28. Final "What Happens When User Says Fix This Bug?" Trace

MOST IMPORTANT FINAL OUTPUT

At the end produce this exact comparison:

CURRENT:

User:
"Fix this bug."

↓

[actual component]

↓

[actual component]

↓

[actual component]

↓

[actual component]

↓

Result


TARGET:

User:
"Fix this bug."

↓

Understand task

↓

Inspect repository

↓

Build relevant context

↓

Reason / plan

↓

Read relevant code

↓

Edit

↓

Run tests

↓

Observe result

↓

If failure:
    diagnose
    repair
    test again

↓

Verify

↓

Summarize

↓

Done

Then list every difference between CURRENT and TARGET.

That difference is the actual engineering backlog.

IMPORTANT IMPLEMENTATION PRINCIPLE

Do not try to make the architecture "more AI".

Make it:

Predictable
Traceable
Understandable
Safe
Recoverable
Testable
Composable

A developer should be able to understand the complete execution path without reading every file.

The final system should feel sophisticated to the USER but remain simple enough for a DEVELOPER to reason about.

Do not implement anything until the validation and target architecture are complete.