# Agent Framework Final Production Roadmap (v1.0)

This is the finalized, frozen architectural roadmap. We have structurally decomposed the massive `AgentKernel` into five top-level subsystems to prevent orchestration bloat. We've also integrated multi-step Action Planning, Evaluator roles, and an expanded Milestone 5 feature set.

## User Review Required

> [!IMPORTANT]
> The architecture has been refined into Version 1.0! The 5 major subsystems are established. The `ActionPlanner` now supports multi-step batching. The `Artifact Pipeline` correctly computes diffs *before* commits. If you give the green light, we will lock this architecture in and immediately begin implementing **Milestone 4**.

---

## The 5 Top-Level Subsystems

To keep the `AgentKernel` as a thin composition root, all components are explicitly grouped:

### 1. Runtime (The Orchestrators)
- **WorkflowRunner**: Lifecycle owner.
- **LoopController**: Owns budgets, triggers, and the `while` loop.
- **TurnManager**: Manages exactly one Turn sequence.
- **TaskScheduler**: Queues and dispatches tasks.
- **QueueManager**: Handles concurrency, preemption, and pausing.

### 2. Intelligence (The Cognitive Brain)
- **ReasoningEngine**: Emits predictions and intent.
- **ActionPlanner**: Translates intent into **multi-step action plans** (e.g., Read A, Read B, Search C).
- **ReflectionEngine**: Triggered dynamically (not periodic) to adjust strategy.
- **Evaluator** *(NEW)*: Judges the *quality* of an observation independently of task completion (e.g., "Tool succeeded, but data is stale").
- **Verifier & RepairPlanner**: Enforces task exit conditions.

### 3. Knowledge (Memory & Environment)
- **RepositoryIndex**: Deterministic AST and codebase mapping.
- **KnowledgeGraph**: The relationship store.
- **MemoryManager**: Ephemeral and Mission memory coordination.
- **EvidenceExtractor**: Extracts atomic facts from semantic observations.
- **ContextBuilder**: Merges memory, graph, and repo state for the LLM.

### 4. Platform (Execution & External Bridge)
- **ToolRegistry & Sandbox**: Loads and safely isolates tools.
- **Artifact Pipeline**: `ArtifactRequest -> Validator -> Formatter -> DiffEngine -> ArtifactManager -> Commit`. (Diffs exist *before* writing).
- **LLMAdapter**: Exposes both `invoke()` and `stream()` methods.
- **StreamingParser**: Handles JSON chunking.

### 5. Infrastructure (Cross-Cutting Concerns)
- **EventBus**: Global pub/sub.
- **ExecutionJournal**: Preserves both `Observation` and the `RawResult` as an immutable Git-like log.
- **Telemetry & CostTracker**: Observability for tokens, latencies, and dollars.
- **SessionManager**: Handles deep-resume hierarchies.
- **RuntimePolicy**: Modular constraints (Resource, Network, Cost, Time).

---

## Milestone 4: Runtime & Tool Platform

**Goal**: Implement the Platform and Infrastructure subsystems so the agent can safely interact with the host OS, external APIs, and live LLMs.

### Tasks
- Build the **LLM Adapter Pipeline** to connect the Reasoning Engine to a live model.
- Implement the **ActionPlanner** to expand Intents into multiple executable Actions.
- Implement the **ToolRegistry** and **SandboxManager**.
- Build the **Artifact Pipeline** ensuring diffs are computed before file commits.
- Implement the **ObservationParser** ensuring `RawResult` is preserved.

## Milestone 5: Production Agent Features

**Goal**: Elevate the agent to a long-running, resilient, multi-agent orchestration platform.

### Features
- **Deep Session Resume**: Checkpointing to save and restore workflow state at any layer.
- **QueueManager & Concurrency**: Support parallel execution and dependency resolution.
- **Evaluator Harness**: Benchmarking and evaluating agent reasoning quality.
- **Replay Mode**: Re-run a workflow from the ExecutionJournal.
- **Human-in-the-Loop (HITL)**: Advanced approval workflows beyond a simple prompt.
- **Plugin SDK & Distributed Workers**: Remote tool execution and agent extension.
