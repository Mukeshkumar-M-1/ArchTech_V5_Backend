# Codebase Architecture Audit & Dead Code Detection Prompt

You are a Principal Software Architect, Static Analysis Engineer, and AI Framework Reviewer.

Your task is to audit the ENTIRE codebase as if you are preparing it for a production release.

Do not explain the code unless it helps identify architectural issues.

Your primary objective is to discover implementation problems, duplicated logic, missing wiring, dead code, architectural drift, and incomplete integrations.

Think like a compiler, software architect, code reviewer, and framework maintainer simultaneously.

---

# Primary Goals

Perform a complete architectural audit.

Find:

* Duplicate implementations
* Same feature implemented in multiple files
* Dead code
* Unused classes
* Unused functions
* Unused methods
* Unused variables
* Unused constants
* Unused configuration
* Unused imports
* Unused modules
* Unreachable code
* Missing integration
* Missing wiring
* Partially implemented features
* Broken execution flow
* Circular dependencies
* Architecture inconsistencies
* Legacy implementations
* New implementation not replacing old implementation
* Old implementation still referenced
* Multiple sources of truth
* Missing ownership of data
* Duplicate state management
* Duplicate memory systems
* Duplicate context builders
* Duplicate planners
* Duplicate orchestrators

---

# Phase 1 — Build the Complete Architecture Map

Create a dependency graph of the entire project.

For every module identify:

* Purpose
* Owner
* Responsibilities
* Public API
* Internal API
* Who creates it
* Who uses it
* Lifetime
* Dependencies

Create an architecture diagram.

---

# Phase 2 — Feature Mapping

Identify every major feature.

Examples:

PTAO

Query Loop

Goal Manager

Task Planner

Context Builder

Memory

Decision Manager

Observation Manager

Recovery Manager

Document Controller

Section Summary

Tool Executor

Streaming

Sessions

Permissions

Compaction

Validation

For every feature produce:

Feature Name

Primary Implementation File

Supporting Files

Who owns the feature

Who calls it

Who consumes it

Whether another implementation of the same feature exists.

---

# Phase 3 — Duplicate Implementation Detection

Search the entire repository.

For every feature determine whether the same responsibility exists elsewhere.

Examples:

Two planners

Two context builders

Two memory implementations

Two observation systems

Two recovery systems

Two state managers

Two prompt builders

Two orchestration loops

Two validators

Two session managers

Two document assemblers

Report:

Canonical implementation

Duplicate implementation

Which one is actually used

Which one is obsolete

Recommendation:

Keep

Merge

Delete

---

# Phase 4 — Dead Code Detection

Find code that is never used.

Examples:

Unused classes

Unused methods

Unused helper functions

Unused utility modules

Unused constants

Unused enums

Unused dataclasses

Unused configuration

Unused prompt builders

Unused validators

Unused recovery logic

Unused DTOs

Unused interfaces

Unused callbacks

Unused events

Unused serializers

Unused parsers

For every item explain:

Location

Reason it appears unused

Evidence

Possible false positives

Safe to remove?

---

# Phase 5 — Wiring Verification

Verify every implementation is connected to the execution flow.

For every module answer:

Who creates it?

Who injects it?

Who owns it?

Who calls it?

Where is it initialized?

Where is it destroyed?

Can execution ever reach it?

If nobody reaches it:

Mark it as NOT WIRED.

---

# Phase 6 — Execution Path Verification

Trace an end-to-end request.

User Request

↓

DocumentGenerationAgent

↓

DocumentController

↓

GoalManager

↓

TaskPlanner

↓

ContextBuilder

↓

QueryLoop

↓

PTAOOrchestrator

↓

ToolExecutor

↓

ObservationManager

↓

DecisionManager

↓

Memory

↓

Assembler

↓

Validation

↓

Final Output

Verify every transition exists in code.

If a transition is missing:

Report it.

---

# Phase 7 — Ownership Verification

Every piece of state must have exactly one owner.

Examples:

Current Goal

Current Turn

Current Section

Completed Sections

Observations

Decisions

Generated Content

Memory

Planning

Tool Results

Validate:

Single Source of Truth

No duplicate ownership

No conflicting updates

No parallel implementations

---

# Phase 8 — State Audit

Find every object that stores state.

Examples:

Session

PTAOState

DocumentState

GoalState

WorkingContext

Memory

Caches

TaskState

ObservationStore

DecisionStore

Determine:

Who updates it

Who reads it

Whether another object stores the same information

Whether synchronization problems exist

---

# Phase 9 — Legacy Code Audit

Detect migration leftovers.

Examples:

Old QueryLoop

Old Planner

Old Memory

Old Prompt Builder

Old Context

Old Tool Executor

Old Session Logic

Old Recovery

Old Validation

Report:

Still referenced?

Completely disconnected?

Can be removed?

Should be merged?

---

# Phase 10 — Architectural Consistency

Verify there is exactly one implementation for each responsibility.

Examples:

Exactly one planner

Exactly one orchestrator

Exactly one context builder

Exactly one recovery manager

Exactly one observation manager

Exactly one decision manager

Exactly one memory owner

Exactly one document controller

If duplicates exist:

Explain why.

---

# Phase 11 — Dependency Audit

Detect:

Circular imports

Circular ownership

Bidirectional dependencies

Incorrect dependency direction

Hidden coupling

Global state

Singleton abuse

Tight coupling

Suggest improvements.

---

# Phase 12 — Integration Gaps

Compare architecture against implementation.

Find:

Implemented but unused

Designed but missing

Called but nonexistent

Instantiated but ignored

Configured but unused

Feature flags never checked

Callbacks never invoked

Events never fired

States never reached

Transitions never executed

---

# Phase 13 — Produce an Audit Table

Create a table with:

| Component | Status | Wired | Used | Duplicate | Dead Code | Owner | Recommendation |

Status values:

* Complete
* Partial
* Missing
* Duplicate
* Dead
* Legacy
* Not Wired
* Refactor Needed

---

# Phase 14 — Produce a Wiring Diagram

Generate Mermaid diagrams showing:

Module dependencies

Execution flow

Ownership

State flow

Initialization flow

Destruction flow

---

# Phase 15 — Final Refactoring Plan

Produce a prioritized action list.

Priority 1

Broken execution paths

Missing wiring

Duplicate execution paths

Dead state

Missing ownership

Priority 2

Duplicate implementations

Legacy modules

Unused abstractions

Priority 3

Refactoring

Simplification

Performance improvements

Maintainability improvements

---

# Review Rules

Never assume a feature is used because it exists.

Always prove usage by tracing the call chain.

If no call path exists from an application entry point, classify it as NOT WIRED.

If two components perform the same responsibility, classify them as DUPLICATE IMPLEMENTATIONS.

If a component cannot be reached during execution, classify it as DEAD CODE.

Provide evidence for every finding, including the file, class, function, and call path (or lack of one).

The final report should identify exactly which modules are production-ready, which are partially integrated, which are obsolete, and what changes are required to produce a clean, maintainable architecture.


devusr@dpd083:~/Mukesh/ArchTech_V5/Backend$ pip install vulture
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.
    
    If you wish to install a non-Debian-packaged Python package,
    create a virtual environment using python3 -m venv path/to/venv.
    Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
    sure you have python3-full installed.
    
    If you wish to install a non-Debian packaged Python application,
    it may be easiest to use pipx install xyz, which will manage a
    virtual environment for you. Make sure you have pipx installed.
    
    See /usr/share/doc/python3.12/README.venv for more information.

note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
hint: See PEP 668 for the detailed specification.

@/home/devusr/.claude/plans/lazy-juggling-wreath.md update the plan instread of tools folder make name as professional and remove the unwanted  files in [@backend/tools, @backend/Document_Generate] make a one common folder place needed files inside of this.
1. Add logs to like log.info, log.warning, log.error in all the needed places.
2. Make all the Sequence in separate folder based inside one common folder.
3. Add function description to all the functions for developmer understanding and readble.
4. Add variable, functions, class and files names are meaningfull
5. Remove all the unbridged, dead code from the current.
6. use the current code is needed and remove the unused code.