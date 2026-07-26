# AI Agent Framework Architectural Blueprint (Revised)

This document outlines the definitive implementation plan to evolve the backend from a document-generation system into a general-purpose, event-driven AI Agent Framework. The architecture is heavily inspired by state-of-the-art systems like Claude Code and Codex.

## Goal Description

Build a highly modular, event-driven Agent Framework centered around an `AgentKernel` and a detached `ExecutionEngine`. The system will support dynamic task scheduling, persistent state, deterministic repository graphs, and advanced reasoning loops.

## User Review Required

> [!IMPORTANT]
> The roadmap has been heavily revised. **Milestone 2** has been completely restructured to focus on building the raw intelligence infrastructure (Deterministic AST Parsing, Memory Stores, Context Assembly, Prompt Management) *before* Milestone 3 introduces any autonomous reasoning. Please review this updated roadmap. Once approved, we will begin executing Milestone 2.

---

## Implementation Roadmap (4 Milestones)

### Milestone 1 – Runtime Foundation (✅ COMPLETED)
- `AgentKernel`, `EventBus`, `AgentStateStore`, `ExecutionEngine`, `SessionManager`

### Milestone 2 – Repository Intelligence & Memory Infrastructure
**Goal**: Build a deterministic understanding of the codebase and establish the foundational memory and context stores required for reasoning. (No LLM planning yet).

**Phase 2.1: Repository Intelligence**
- **Deliverables**: `RepositorySnapshot`, `SnapshotManager`, `RepositoryIndex`, `RepositoryQueryEngine`
- *Details*: Purely deterministic analysis. Parses ASTs, Import Graphs, Call Graphs, and Symbol Tables. Answers queries (e.g., "Find callers of X") without touching the LLM.

**Phase 2.2: Memory Layer**
- **Deliverables**: `MemoryManager`, `WorkingMemoryStore`, `MissionMemoryStore`, `ScratchpadStore`
- *Details*: The `MemoryManager` acts as a coordinator for specialized memory stores. Each store has a distinct lifecycle.

**Phase 2.3: Context Assembly**
- **Deliverables**: `ContextBuilder`, `ContextSelector`
- *Details*: The sole producer of `ExecutionContext`. Responsible for token budgeting and history reduction. Isolates the `ExecutionEngine` from prompt assembly.

**Phase 2.4: Prompt Runtime**
- **Deliverables**: `PromptManager`, `PromptRegistry`, `PromptRenderer`, `PromptVersion`
- *Details*: Manages versioned, hierarchical prompts instead of hardcoded strings.

**Phase 2.5: Knowledge Layer (V1)**
- **Deliverables**: `Observation`, `KnowledgeGraph`, `KnowledgeUpdater`
- *Details*: Simple JSON/NetworkX representation of semantic relationships (e.g., "Controller -> Uses -> Verifier"). Purely consumes `Observations` generated from execution.

### Milestone 3 – Autonomous Reasoning
**Goal**: Enable self-directed planning, execution, reflection, and recovery.

- **`MissionManager`**: Owns the high-level goal hierarchy (Mission → Goal → Task).
- **`PlanningEngine` & `TaskScheduler`**: Produces versioned `Plans` and prioritizes tasks.
- **`ReasoningEngine`**: Dedicated to evaluating state and producing a `Decision` (Hypothesis -> Action).
- **`ReflectionEngine`**: Asks "Are we stuck?" based on `EventBus` observations.
- **`Verifier` & `RepairEngine`**: Validates task output against evidence.

### Milestone 4 – Platform Capabilities
**Goal**: Evolve into a reusable, production-grade engineering platform.

- **`CapabilityRegistry` & `Skill Runtime`**: Specialized modules with their own schemas.
- **`ToolPolicyManager` & `RuntimePolicyManager`**: Enforces strict budgets and security rules.
- **`ArtifactManager`**: Dedicated system for safely creating and patching files.
- **`IExecutionJournal`**: Universal timeline of reasoning and events ("Git log for reasoning").

---

## Next Steps

Upon your approval of this revised roadmap, we will immediately begin work on **Milestone 2**, starting strictly with **Phase 2.1 (Repository Intelligence)**.
