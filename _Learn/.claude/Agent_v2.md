AgentCore v2 — Deep Architecture Gap & Coding-Agent Readiness Audit

You are a principal AI-agent runtime architect, distributed-systems engineer, and senior codebase reverse-engineering engineer.

You are auditing the existing:

"backend/AgentCore/"

The current implementation contains approximately 130 Python files across 22 directories.

The ultimate goal of this project is to build a production-grade LLM coding-agent runtime whose behavior and developer experience are comparable to modern coding agents such as:

- Claude Code
- Cursor Agent
- OpenAI Codex-style coding agents

Do NOT copy their proprietary implementation.

Instead, determine whether this AgentCore provides the same fundamental behavioral capabilities:

Understand task
      ↓
Inspect repository
      ↓
Build context
      ↓
Plan
      ↓
Use tools
      ↓
Read / search / edit / execute
      ↓
Observe results
      ↓
Reason about results
      ↓
Verify
      ↓
Repair failures
      ↓
Continue autonomously
      ↓
Complete task

---

PRIMARY OBJECTIVE

Do not immediately refactor the code.

Do not add new architecture simply because a directory exists.

Your first responsibility is to determine:

«What does AgentCore ACTUALLY do today?»

Then determine:

«What is missing for it to behave like a reliable autonomous coding agent?»

Then determine:

«Which existing components are duplicated, legacy, incorrectly wired, incomplete, or unnecessary?»

Finally produce:

«A concrete implementation roadmap ordered by dependency and priority.»

---

CRITICAL RULES

Rule 1 — Source code is the only authority

Do NOT trust:

- filenames
- directory names
- comments
- docstrings
- README claims
- architecture diagrams
- class names
- previous AI-generated explanations

Verify behavior from:

- imports
- function calls
- object construction
- inheritance
- interfaces
- actual control flow
- event publishers/subscribers
- state mutation
- tool registration
- tool execution
- tests
- API routes
- runtime traces if available

If something cannot be proven:

"UNVERIFIED"

---

Rule 2 — Do not modify code

During this audit:

- Do not refactor.
- Do not rename files.
- Do not delete files.
- Do not create replacement implementations.
- Do not change behavior.
- Do not "fix" architecture.

Only inspect, trace, classify, and report.

---

Rule 3 — Distinguish existence from wiring

A component is NOT considered implemented merely because a file exists.

Use these statuses:

IMPLEMENTED + WIRED
IMPLEMENTED + PARTIALLY WIRED
IMPLEMENTED + UNUSED
SKELETON
DUPLICATE
LEGACY
WRAPPER
UNCLEAR
MISSING

For example:

verifier_engine.py exists

does NOT mean:

verification capability = implemented

unless the actual agent execution path invokes it.

---

Rule 4 — Distinguish architecture from behavior

Evaluate the system primarily through behavior.

The question is not:

«"Do we have a context manager?"»

The question is:

«"Can the agent maintain useful context across multiple tool calls, context compaction, failures, and long-running tasks?"»

The question is not:

«"Do we have a planner?"»

The question is:

«"Can the agent autonomously break a complex coding task into useful executable steps?"»

---

CURRENT ARCHITECTURE

The current AgentCore contains:

AgentCore/
│
├── action/
├── agents/
├── cognitive/
├── context/
├── core/
├── domain/
├── execution/
│   └── builtins/
├── infrastructure/
├── journal/
├── knowledge/
├── memory/
├── observability/
├── orchestration/
├── platform/
├── prompt/
├── reasoning/
├── repository/
├── runtime/
├── shared/
└── _Testing_milestone/

Important existing components include:

execution/query_loop.py
execution/tool_executor.py
execution/tool_registry.py
execution/permission_manager.py
execution/context_compaction.py
execution/context_isolation.py
execution/session_manager.py
execution/task_state.py
execution/agent_spawner.py
execution/agent_mailbox.py

execution/builtins/
    bash.py
    file_read.py
    file_write.py
    file_edit.py
    glob.py
    search.py
    agent.py
    request_user_input.py
    propose_content_edit.py
    send_message.py
    tasks.py

orchestration/
    orchestrator.py
    mission_layer.py
    planner_engine.py
    task_planner.py
    dependency_graph.py
    scheduling_manager.py
    lease_manager.py
    runtime_adapter.py
    workflow.py
    worker_management.py

cognitive/
    verifier_engine.py
    repair_engine.py
    reflection_engine.py

repository/
    repo_index.py
    repo_query_engine.py
    repo_snapshot.py

runtime/
    state_machine.py
    checkpoint_manager.py
    replay_engine.py
    failure_classifier.py
    cancellation_manager.py
    interrupt_manager.py

memory/
    store_manager.py
    mission_store.py
    working_store.py
    scratchpad_store.py

platform/llm/
    interfaces.py
    adapter.py
    builder.py
    parser.py
    renderer.py

There are also potentially overlapping/legacy areas:

core/
execution/
action/
reasoning/
cognitive/
runtime/
orchestration/
context/
observability/
knowledge/

These overlaps must be investigated rather than assumed to be correct.

---

PHASE 1 — FIND THE REAL ENTRY POINT

Start from:

agents/routes.py

Determine:

HTTP request
    ↓
?
    ↓
?
    ↓
?
    ↓
Agent runtime
    ↓
?
    ↓
SSE response

Trace the exact implementation.

For every transition provide:

Source file:
Source class/function:
Target file:
Target class/function:
Call mechanism:
Data passed:
Reason:
Evidence:

Do not provide hypothetical architecture.

---

PHASE 2 — TRACE ONE COMPLETE REAL EXECUTION

Choose the most important real execution path, preferably document generation.

Trace:

User request
 ↓
Route
 ↓
Session
 ↓
Mission
 ↓
Task
 ↓
Planning
 ↓
Agent runtime
 ↓
Context
 ↓
LLM
 ↓
Tool call
 ↓
Tool execution
 ↓
Observation
 ↓
State update
 ↓
LLM again
 ↓
Verification
 ↓
Result
 ↓
SSE

If any stage does not actually exist, mark:

MISSING

If it exists but is not connected:

UNWIRED

---

PHASE 3 — IDENTIFY THE TRUE AGENT LOOP

This is the most important phase.

Find the actual implementation of:

Context
 ↓
LLM
 ↓
Model response
 ↓
Tool decision
 ↓
Tool execution
 ↓
Tool result
 ↓
Observation
 ↓
Context update
 ↓
LLM again

Determine whether this is implemented by:

execution/query_loop.py
core/execution_engine.py
execution/ptaos_orchestrator.py
reasoning/reason_engine.py
action/action_executor.py

or some combination.

Determine:

1. Who owns the loop?
2. Who starts the loop?
3. Who decides continuation?
4. Who interprets model output?
5. Who handles tool calls?
6. Who inserts tool results back into context?
7. Who detects final completion?
8. Who handles malformed model output?
9. Who handles LLM failure?
10. Who handles tool failure?
11. Who handles context overflow?
12. Who handles cancellation?
13. Who records the turn?
14. Who emits events?
15. Who terminates the task?

Produce the actual sequence diagram.

---

PHASE 4 — DETERMINE WHETHER PTaO IS ACTUALLY NECESSARY

Inspect:

execution/ptaos_orchestrator.py
reasoning/reason_engine.py
reasoning/turn_manager.py

Determine whether PTaO is:

A. Core agent loop
B. Planning layer
C. Reasoning abstraction
D. Wrapper
E. Legacy system
F. Duplicate of QueryLoop
G. Required orchestration protocol
H. Partially implemented

Provide source evidence.

Do NOT recommend keeping PTaO merely because it sounds architecturally sophisticated.

Determine whether a modern coding agent actually needs the abstraction as currently implemented.

---

PHASE 5 — CORE vs EXECUTION

Inspect:

core/
execution/

Especially:

core/execution_engine.py
execution/query_loop.py
execution/task_state.py
core/agent_state.py
core/agent_session_manager.py
execution/session_manager.py
core/execution_history.py
execution/context_compaction.py

Determine:

Which is active?
Which is legacy?
Which wraps the other?
Which duplicates functionality?
Which should own the responsibility?

Create:

CORE vs EXECUTION RESPONSIBILITY MATRIX

---

PHASE 6 — ACTION vs ORCHESTRATION vs EXECUTION

Inspect:

action/
orchestration/
execution/

Determine the exact distinction between:

Action Planner
Action Executor
Mission Planner
Task Planner
Mission Orchestrator
Runtime Adapter
PTaO Orchestrator
Query Loop
Tool Executor

Build:

USER GOAL
   ↓
MISSION
   ↓
TASK
   ↓
ACTION
   ↓
AGENT TURN
   ↓
TOOL

Determine which layer owns each responsibility.

Flag:

RESPONSIBILITY OVERLAP

where multiple modules perform essentially the same job.

---

PHASE 7 — TOOL SYSTEM AUDIT

Inspect:

execution/tool_registry.py
execution/tool_executor.py
execution/permission_manager.py
execution/builtins/*
action/tool_router.py

Trace:

LLM
 ↓
Tool Call
 ↓
Parser
 ↓
Registry
 ↓
Router
 ↓
Permission
 ↓
Executor
 ↓
Builtin Tool
 ↓
Tool Result
 ↓
Agent

Determine which of these actually exists.

Audit:

Tool discovery

Can the model know which tools exist?

Tool schemas

Are arguments strongly validated?

Tool routing

Why does "tool_router.py" exist if "tool_registry.py" exists?

Permission

Can dangerous operations require user approval?

Timeout

Can long-running tools be stopped?

Cancellation

Does cancellation propagate into the tool?

Output limits

Can huge command/file outputs be safely handled?

Errors

Are errors returned to the model as useful observations?

Traceability

Can we reconstruct every tool call?

---

PHASE 8 — CODING-AGENT TOOL COMPLETENESS

Determine whether the agent can perform these fundamental operations:

READ
SEARCH
GLOB
EDIT
WRITE
DELETE
MOVE/RENAME
BASH
GIT
TEST
BUILD
ASK USER
SPAWN AGENT

Classify each:

AVAILABLE
AVAILABLE BUT WEAK
AVAILABLE BUT UNSAFE
AVAILABLE BUT UNWIRED
MISSING

Also identify missing high-value coding-agent capabilities.

---

PHASE 9 — REPOSITORY INTELLIGENCE

Inspect:

repository/repo_index.py
repository/repo_query_engine.py
repository/repo_snapshot.py
execution/builtins/search.py
execution/builtins/glob.py

Determine whether the agent can answer:

Where is this feature implemented?

Who calls this function?

Where is this class instantiated?

What references this symbol?

What depends on this module?

Which tests cover this code?

What files are related to this feature?

What changed since the last checkpoint?

What is the repository architecture?

Determine whether the repository intelligence is:

keyword-only
symbol-aware
reference-aware
dependency-aware
AST-aware
snapshot-aware
git-aware

Identify the highest-impact gaps.

---

PHASE 10 — CONTEXT ARCHITECTURE

Inspect:

context/*
orchestration/context_builder.py
execution/context_compaction.py
execution/message_manager.py
execution/system_prompt.py
platform/llm/builder.py
prompt/*

This is a high-risk area because there appear to be multiple context/prompt systems.

Determine the exact distinction between:

Context Builder
Execution Context
Context Selector
Orchestration Context Builder
LLM Builder
Prompt Manager
Prompt Registry
Prompt Template
System Prompt
Message Manager
Context Compaction

Produce:

CONTEXT PIPELINE

User
 ↓
System
 ↓
Mission
 ↓
Repository
 ↓
Task
 ↓
History
 ↓
Tool Results
 ↓
Memory
 ↓
Compaction
 ↓
LLM

Determine whether the current implementation actually behaves this way.

---

PHASE 11 — CONTEXT COMPACTION QUALITY

Inspect:

execution/context_compaction.py
core/execution_history.py

Determine:

- when compaction occurs
- what triggers it
- what is preserved
- what is discarded
- whether tool results are summarized
- whether important repository facts survive
- whether task state survives
- whether user instructions survive
- whether previous edits remain known
- whether the agent can recover information after compaction

Determine whether long-running coding tasks are realistically supported.

---

PHASE 12 — FILE EDITING SYSTEM

Inspect:

execution/builtins/file_edit.py
execution/builtins/file_write.py
execution/builtins/propose_content_edit.py
platform/artifacts/diff_engine.py
platform/artifacts/artifact_manager.py

Determine whether editing follows:

READ
 ↓
UNDERSTAND
 ↓
PROPOSE PATCH
 ↓
VALIDATE
 ↓
APPLY
 ↓
DIFF
 ↓
TEST

Audit:

- targeted edits
- patch safety
- stale-file detection
- concurrent modification
- atomic writes
- syntax validation
- rollback
- diff generation
- edit history
- failed patch recovery

---

PHASE 13 — VERIFICATION / REPAIR LOOP

Inspect:

cognitive/verifier_engine.py
cognitive/repair_engine.py
cognitive/reflection_engine.py

Determine whether the actual system performs:

IMPLEMENT
 ↓
VERIFY
 ├── PASS → DONE
 └── FAIL
       ↓
    DIAGNOSE
       ↓
     REPAIR
       ↓
    VERIFY AGAIN

Determine whether verification includes:

tests
lint
type checking
build
runtime checks
custom validation

Determine whether repair is automatically connected to the execution loop.

---

PHASE 14 — STATE ARCHITECTURE

Inspect:

core/agent_state.py
execution/task_state.py
domain/reasoning_state.py
runtime/state_machine.py

Identify every state model.

For each:

Name:
Owner:
Created by:
Modified by:
Read by:
Persisted:
Lifecycle:
Transitions:

Detect duplicate state concepts.

Especially investigate:

AgentState
TaskState
ReasoningState
RuntimeState
MissionState
SessionState

---

PHASE 15 — SESSION / MEMORY

Inspect:

core/agent_session_manager.py
core/execution_history.py
execution/session_manager.py
execution/session_memory.py
memory/*

Determine the actual lifecycle:

Session Created
 ↓
Conversation
 ↓
Task
 ↓
Working Memory
 ↓
Tool Execution
 ↓
History
 ↓
Compaction
 ↓
Checkpoint
 ↓
Resume

Determine whether these memory systems are genuinely different:

Mission Memory
Working Memory
Scratchpad
Session Memory
Execution History

Identify unnecessary duplication.

---

PHASE 16 — OBSERVATION / KNOWLEDGE

Inspect:

event_bus.py
knowledge/observation_bus.py
knowledge/observation_engine.py
knowledge/observation_manager.py
knowledge/observation_parser.py
knowledge/evidence_manager.py
knowledge/knowledge_manager.py

Determine:

Tool Result
 ↓
Observation
 ↓
Evidence
 ↓
Knowledge

if that is actually implemented.

Also determine why both:

event_bus.py
knowledge/observation_bus.py

exist.

Identify duplicate event/observation mechanisms.

---

PHASE 17 — RUNTIME / RECOVERY

Inspect:

runtime/*
execution/abort_controller.py
execution/pause_manager.py
execution/agent_cleanup.py

Determine whether the agent can survive:

LLM failure
Tool failure
Network failure
Timeout
Process interruption
Cancellation
Context overflow
Worker failure
Partial edit

Determine whether:

checkpoint
→ crash
→ restart
→ replay
→ resume

actually works.

Do not assume "checkpoint_manager.py" means checkpoint recovery exists.

---

PHASE 18 — PAUSE / RESUME / CANCEL

Trace:

execution/abort_controller.py
execution/pause_manager.py
runtime/cancellation_manager.py
runtime/interrupt_manager.py

Determine whether:

RUNNING
 ↓
PAUSE
 ↓
RESUME

and:

RUNNING
 ↓
CANCEL
 ↓
CLEANUP

actually work across:

LLM
Tools
Sub-agents
Background tasks
SSE

Identify broken propagation paths.

---

PHASE 19 — MULTI-AGENT SYSTEM

Inspect:

execution/agent_spawner.py
execution/agent_mailbox.py
execution/context_isolation.py
execution/builtins/agent.py
execution/builtins/send_message.py
execution/builtins/tasks.py
orchestration/worker_management.py
orchestration/lease_manager.py

Determine whether multi-agent execution is actually functional.

Audit:

spawn
context isolation
permissions
communication
task assignment
result collection
failure
cancellation
resource limits
recursion protection

Determine whether this is:

real multi-agent runtime
prototype
partially wired
abstraction only

---

PHASE 20 — PERMISSION / SAFETY

Inspect:

execution/permission_manager.py
infrastructure/policy_manager.py
domain/runtime_policy.py
execution/builtins/bash.py

Determine:

Tool request
 ↓
Policy
 ↓
Permission
 ↓
User approval
 ↓
Execution

Determine whether dangerous operations are properly controlled.

Check:

shell
filesystem
git
network
processes
sub-agents

---

PHASE 21 — OBSERVABILITY / AGENT TRACE

Inspect:

journal/execution_journal.py
observability/agent_kernel.py
observability/blackboard.py
observability/budget_manager.py
infrastructure/telemetry_manager.py
execution/transcript_writer.py
execution/token_usage_tracker.py

Determine whether you can reconstruct:

User request
 ↓
Agent decision
 ↓
LLM request
 ↓
LLM response
 ↓
Tool call
 ↓
Tool result
 ↓
State change
 ↓
File change
 ↓
Verification
 ↓
Failure
 ↓
Repair
 ↓
Final result

The system should ideally provide an Agent Trace.

Determine whether it currently can.

---

PHASE 22 — STREAMING / USER EXPERIENCE

Inspect:

agents/routes.py
event_bus.py
observability/*
execution/transcript_writer.py

Determine what the user receives while the agent is running.

Can the UI show:

Thinking / planning
Reading file
Searching repository
Editing file
Running command
Test result
Waiting for approval
Repairing failure
Completed

Determine whether events are:

structured
ordered
reliable
replayable
correlated with a task/turn

---

PHASE 23 — AGENT KERNEL AUDIT

Inspect:

observability/agent_kernel.py

Determine the exact difference between:

ChatAgentKernel
GenerationAgentKernel

Answer:

Why are there two kernels?

What lifecycle does each own?

Do they duplicate runtime responsibilities?

Which one should be the canonical Agent Runtime?

Are both actively used?

---

PHASE 24 — BUDGET / RESOURCE GOVERNANCE

Inspect:

observability/budget_manager.py
infrastructure/telemetry_manager.py
execution/token_usage_tracker.py

Determine whether the runtime can enforce:

max turns
max tokens
max execution time
max tool calls
max sub-agents
max command duration
max cost

Determine whether limits are:

declared
enforced
observable
recoverable

---

PHASE 25 — LEGACY / DUPLICATION AUDIT

Explicitly investigate these:

core/
execution/

action/
orchestration/

context/context_builder.py
orchestration/context_builder.py

platform/llm/builder.py
prompt/prompt_manager.py
execution/system_prompt.py

core/agent_state.py
execution/task_state.py
domain/reasoning_state.py
runtime/state_machine.py

core/agent_session_manager.py
execution/session_manager.py

core/execution_history.py
execution/context_compaction.py

event_bus.py
knowledge/observation_bus.py

reasoning/
cognitive/

observability/agent_kernel.py
orchestration/runtime_adapter.py

For every overlap:

Component A:
Component B:

Relationship:
ACTIVE / DUPLICATE / LEGACY / WRAPPER / SPECIALIZED / UNCLEAR

Evidence:

Recommendation:

---

PHASE 26 — ARCHITECTURE DEPENDENCY DIRECTION

Determine whether dependency direction is healthy.

Ideal conceptual direction:

API
 ↓
Agent Runtime
 ↓
Orchestration
 ↓
Execution
 ↓
Tools
 ↓
Infrastructure

while domain models should remain relatively independent.

Find:

- circular dependencies
- upward dependencies
- infrastructure leaking into domain
- tools calling orchestration
- LLM provider code leaking into agent logic
- API logic leaking into execution
- runtime managers calling UI code

Produce:

DEPENDENCY VIOLATIONS

---

PHASE 27 — TEST VALIDATION

Inspect:

_Testing_milestone/

Do not assume passing tests mean the architecture is correct.

Map every major test to the capability it validates.

Create:

TEST COVERAGE BY CAPABILITY

For each capability:

Capability:
Implementation:
Integration Test:
Failure Test:
Concurrency Test:
Recovery Test:
Performance Test:
Governance Test:

Identify important runtime behaviors with no tests.

---

PHASE 28 — CODING-AGENT BEHAVIOR MATRIX

Evaluate the current system against these behaviors:

Capability

Exists

Wired

Reliable

Production Ready

Evidence

Autonomous agent loop











Multi-turn tool use











Repository exploration











Code search











Symbol/reference understanding











Context selection











Context compaction











File editing











Patch/diff











Shell execution











Git operations











Test execution











Automatic verification











Automatic repair











Failure recovery











Permission approval











Cancellation











Pause/resume











Session persistence











Checkpoint/resume











Agent trace











Streaming events











Sub-agents











Context isolation











Token/cost budgets











Long-running tasks











PHASE 29 — BEHAVIORAL GAP ANALYSIS

Compare the current system to the following target behavior.

Simple task

User:

Fix the typo in README.md.

Expected:

Search/read
 ↓
Edit
 ↓
Verify diff
 ↓
Done

Medium task

User:

Fix the login API bug and add a regression test.

Expected:

Inspect repository
 ↓
Find login implementation
 ↓
Understand call chain
 ↓
Inspect tests
 ↓
Plan
 ↓
Edit
 ↓
Add test
 ↓
Run test
 ↓
Failure?
 ↓
Repair
 ↓
Run again
 ↓
Done

Complex task

User:

Add OAuth authentication to the application.

Expected:

Understand requirements
 ↓
Explore repository
 ↓
Identify architecture
 ↓
Plan
 ↓
Implement incrementally
 ↓
Run tests
 ↓
Repair
 ↓
Verify
 ↓
Summarize changes

Determine where the current AgentCore fails to support these behaviors.

PHASE 30 — IDENTIFY THE MOST IMPORTANT MISSING CONCEPTS

Do not simply list missing files.

Identify missing runtime concepts.

Examples:

Agent Turn
Agent Trace
Tool Observation
Execution Contract
Repository Context
Approval Request
Verification Cycle
Recovery Point
Task Completion Criteria

For every missing concept explain:

Concept:
Why needed:
Current substitute:
Why substitute is insufficient:
Where it should belong:
Priority:

PHASE 31 — GAP PRIORITY

Classify gaps.

P0 — Fundamental

The system cannot reliably behave like a coding agent without this.

Examples:

broken agent loop
tool results not returned correctly
no reliable execution state
no completion detection
no verification
unsafe tool execution

P1 — Major

Required for strong coding-agent behavior.

Examples:

weak repository intelligence
weak context management
poor editing
weak recovery
poor permission UX
missing agent trace

P2 — Advanced

Useful after the core runtime is reliable.

Examples:

advanced multi-agent
long-term memory
advanced knowledge graph
optimization
advanced telemetry

PHASE 32 — TARGET ARCHITECTURE

After understanding the existing implementation, design a target architecture.

The target should conceptually resemble:

                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │   SESSION   │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │ AGENT KERNEL │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │ AGENT LOOP  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           CONTEXT       PLANNER       MEMORY
              │            │            │
              └────────────┼────────────┘
                           ▼
                          LLM
                           │
                           ▼
                      TOOL CALL
                           │
                           ▼
                    PERMISSION/POLICY
                           │
                           ▼
                       EXECUTOR
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
        SEARCH           EDIT            BASH
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                      OBSERVATION
                           │
                           ▼
                         STATE
                           │
                           ▼
                       VERIFY
                      /       \
                   PASS       FAIL
                    │           │
                    ▼           ▼
                  DONE        REPAIR
                                │
                                └──────► AGENT LOOP

Adapt this to the actual codebase.

Do not force the existing code into this architecture if the source code suggests a better design.

PHASE 33 — FINAL FILE CLASSIFICATION

Classify every AgentCore source file into exactly one:

CORE_RUNTIME
AGENT_CAPABILITY
DOMAIN_MODEL
INFRASTRUCTURE
SUPPORTING
LEGACY
DUPLICATE
UNUSED
TEST_ONLY
UNCLEAR

For each file provide:

File:
Classification:
Actual responsibility:
Called by:
Calls:
Why it exists:
Status:
Evidence:

FINAL REPORT FORMAT

Your final report MUST contain these sections in this order:

1. Executive Summary

2. Actual Entry Point

3. Actual End-to-End Execution Flow

4. Actual Agent Loop

5. Actual Call Graph

6. Actual Data Flow

7. Actual State Flow

8. Actual Event Flow

9. Tool Architecture

10. Repository Intelligence

11. Context Architecture

12. Memory Architecture

13. File Editing Architecture

14. Verification & Repair

15. Session Architecture

16. Runtime & Recovery

17. Permission & Governance

18. Multi-Agent Architecture

19. Agent Trace & Observability

20. Streaming / UX Architecture

21. Core vs Execution Analysis

22. Action vs Orchestration Analysis

23. Context / Prompt Duplication Analysis

24. State Duplication Analysis

25. Event / Observation Duplication Analysis

26. Legacy / Unused Components

27. Dependency Violations

28. Architecture Smells

29. Test Coverage Analysis

30. Coding-Agent Capability Matrix

31. Behavioral Gap Analysis

32. Missing Runtime Concepts

33. P0 Gaps

34. P1 Gaps

35. P2 Gaps

36. Target Architecture

37. File-to-Target Mapping

38. Recommended Implementation Roadmap

REQUIRED FORMAT FOR EVERY IMPORTANT GAP

Never say only:

"Context management needs improvement."

Instead:

GAP ID: CTX-001

Name:
Context selection is not sufficiently repository-aware.

Current:
[actual implementation]

Expected:
[desired coding-agent behavior]

Evidence:
[file + class + function]

Impact:
[what breaks]

Priority:
P0/P1/P2

Affected Files:
[...]

Recommended Direction:
[...]

Dependencies:
[...]

Do NOT implement yet.

FINAL ROADMAP REQUIREMENT

The roadmap must be dependency-aware.

Do NOT produce:

1. Add memory
2. Add multi-agent
3. Add RAG
4. Add tools
5. Add verification

Instead produce something like:

PHASE 0 — Understand and stabilize existing runtime

PHASE 1 — Establish canonical Agent Loop

PHASE 2 — Establish canonical Tool Runtime

PHASE 3 — Establish Repository Intelligence

PHASE 4 — Establish Context/Memory lifecycle

PHASE 5 — Establish Safe Editing + Permissions

PHASE 6 — Establish Verification + Repair

PHASE 7 — Establish Agent Trace + Streaming UX

PHASE 8 — Establish Recovery + Checkpointing

PHASE 9 — Establish Multi-Agent Runtime

PHASE 10 — Optimization

For every phase identify:

Goal
Existing components reused
Components to merge
Components to deprecate
New concepts required
Dependencies
Risks
Validation tests
Completion criteria

MOST IMPORTANT QUESTION

At the very end answer this explicitly:

If I gave this AgentCore to a developer and asked it to "fix a bug in an unfamiliar repository", what exact sequence of events would happen today?

Then answer:

What exact sequence should happen in the target Claude/Cursor/Codex-like runtime?

Produce a side-by-side comparison:

CURRENT
vs
TARGET

The difference between those two flows is the actual AgentCore development backlog.

Do not optimize for number of files.

Optimize for:

Behavior
Reliability
Explainability
Safety
Recoverability
Repository understanding
Autonomy
Developer experience

Do not implement changes until this audit is complete.