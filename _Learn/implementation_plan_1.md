# AI Agent Framework Architectural Blueprint

This document outlines the definitive implementation plan to evolve the backend from a document-generation system into a general-purpose, event-driven AI Agent Framework. The architecture is heavily inspired by state-of-the-art systems like Claude Code and Codex.

## Goal Description

Build a highly modular, event-driven Agent Framework centered around an `AgentKernel` and a detached `ExecutionEngine`. The system will support dynamic task scheduling, persistent state, deterministic repository graphs, and advanced reasoning loops (Plan → Execute → Observe → Reflect → Repair).

## User Review Required

> [!IMPORTANT]
> This blueprint incorporates all 15 architectural additions from your latest review, structured into a 4-Milestone roadmap. Please confirm that this final blueprint matches your vision. If approved, we will begin executing **Milestone 1**.

---

## The Architecture Layer Diagram

```text
                        AgentKernel
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
 MissionManager        SessionManager      EventBus
        │                    │                    │
        └──────────────┬─────┴─────────────┬──────┘
                       ▼
                 AgentStateStore
                       │
                       ▼
               TaskScheduler
                       │
                       ▼
                StateMachine
                       │
                       ▼
               ExecutionEngine  <-- (Replaces QueryLoop)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 PromptManager   ContextBuilder   ToolPolicy
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                    LLM Call
                       │
                  ToolExecutor
                       │
                  EventBus Event
                       ▼
      ┌───────────┬─────────────┬─────────────┐
      ▼           ▼             ▼             ▼
 Observer    MemoryManager  KnowledgeGraph  ArtifactManager
      │           │             │             │
      └───────────┼─────────────┴─────────────┘
                  ▼
           ReflectionEngine
                  │
                  ▼
             Verification
                  │
          ┌───────┴────────┐
          ▼                ▼
     RepairEngine     Task Complete
          │                │
          └────────────────┘
```

---

## Implementation Roadmap (4 Milestones)

We will execute this transformation iteratively. We will not build the entire system at once. 

### Milestone 1 – Runtime Foundation
**Goal**: Execute a single task robustly using a decoupled engine.

- **`AgentKernel`**: The central lifecycle manager. It does not know about LLM turns.
- **`EventBus`**: The pub/sub system for asynchronous event routing (`ToolFinished` -> `Observer`).
- **`AgentStateStore`**: Manages the current execution state, retry counts, and token budgets.
- **`ExecutionEngine`**: The critical boundary. Encapsulates the old `QueryLoop`. The Kernel simply asks it to "Execute Task", and the engine handles the internal `Turn -> Tool -> Turn` LLM mechanics.
- **`SessionManager`**: Basic persistence for crash recovery.
- **Integration**: Wire the existing `ToolExecutor` into the `ExecutionEngine`.

### Milestone 2 – Repository Intelligence
**Goal**: Understand codebases efficiently without wasting LLM context.

- **`KnowledgeGraph` / `RepositoryIndex`**: Deterministic parsers for AST, imports, symbols, and dependencies.
- **`MemoryManager`**: Centralizes different memory types (Working, Mission, Scratchpad).
- **`ContextBuilder` & `ContextSelector`**: Intelligently selects context (Recent, Semantic, Evidence) instead of blindly appending text.
- **`PromptManager`**: Versioned, hierarchical prompts instead of hardcoded strings.

### Milestone 3 – Autonomous Reasoning
**Goal**: Enable self-directed planning, execution, reflection, and recovery.

- **`MissionManager`**: Owns the high-level goal hierarchy (Mission → Goal → SubGoal → Task → Step).
- **`TaskScheduler` & `StateMachine`**: Manages prioritizing tasks and enforcing state transitions (`EXPLORE` → `PLAN` → `EXECUTE`).
- **`ReflectionEngine`**: Asks "Are we stuck?" based on `EventBus` observations.
- **`Verifier` & `RepairEngine`**: Validates task output against evidence, triggering a repair loop if it fails.

### Milestone 4 – Platform Capabilities
**Goal**: Evolve into a reusable, production-grade engineering platform.

- **`Skill Runtime`**: Specialized modules (Architecture, Code, Verification) with own prompts and validation.
- **`ToolPolicyManager`**: State-based rules (e.g., `PLAN` state blocks `FileWrite`).
- **`RuntimePolicyManager`**: Enforces budgets (Tokens, Time, Max Turns, Max Repairs).
- **`ArtifactManager`**: Dedicated system for safely creating and patching files (Markdown, Code, Logs).
- **`Parallelism`**: Scheduler support for parallel task execution.

---

## Next Steps

Upon your approval of this roadmap, I will immediately begin work on **Milestone 1**. This will involve scaffolding the `AgentKernel`, `EventBus`, `AgentStateStore`, and refactoring the legacy `QueryLoop` into a clean `ExecutionEngine` abstraction.
