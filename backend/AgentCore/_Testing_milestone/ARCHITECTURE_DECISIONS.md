# Architecture Decisions Record (ADR)

This document records the foundational architectural decisions for the AgentCore framework (Frozen at Version 1.0).

## 1. 5 Top-Level Subsystems
- **Decision**: The framework is strictly divided into `Runtime`, `Intelligence`, `Knowledge`, `Platform`, and `Infrastructure`.
- **Reasoning**: Prevents `AgentKernel` from becoming a monolithic "God class" full of orchestration logic. Ensures strict separation of concerns (e.g., Runtime cannot directly update Knowledge without going through the proper bus).

## 2. LoopController vs WorkflowRunner
- **Decision**: `LoopController` owns the `while` loop, retries, and budgets. `WorkflowRunner` owns the higher-level state (Start, Pause, Stop).
- **Reasoning**: Isolates tactical loop complexity from strategic workflow states.

## 3. ActionPlanner separation from ReasoningEngine
- **Decision**: `ReasoningEngine` outputs intent; `ActionPlanner` expands that intent into a multi-step execution plan.
- **Reasoning**: Decouples "What should I do?" from "How exactly do I do it using tools?", enabling batching and optimization later.

## 4. Preservation of RawResult
- **Decision**: Execution tools emit a `RawResult`. The `ObservationParser` translates this into an `Observation`, but both are logged.
- **Reasoning**: Raw stdout/stderr is too noisy for memory but critical for debugging, telemetry, and replay.

## 5. Artifact Diffing Before Commit
- **Decision**: The pipeline flows as `Validator -> Formatter -> DiffEngine -> ArtifactManager -> Commit`.
- **Reasoning**: Ensures that the agent (or a human) can preview and approve a precise diff before mutating the actual codebase.

## 6. Separation of RepositoryIndex and KnowledgeGraph
- **Decision**: `RepositoryIndex` is deterministic AST/file mappings. `KnowledgeGraph` is subjective, semantic relationships discovered over time.
- **Reasoning**: Mixing deterministic repo state with probabilistic LLM assumptions degrades context reliability.

## 7. Distinct Reflection and Verifier Roles
- **Decision**: `ReflectionEngine` dynamically branches the workflow (Continue, Verify, Replan). `Verifier` strictly checks task completion against evidence.
- **Reasoning**: Reflection is a continuous, tactical course-correction. Verification is a rigid, boolean check of finality.

## 8. Stable Interfaces
- **Decision**: Subsystems must interact via interfaces (e.g., `ILLMAdapter`, `IReasoningEngine`).
- **Reasoning**: Concrete implementations (like the LLM provider or Sandbox engine) will evolve rapidly. The framework wiring must remain immune to these shifts.
