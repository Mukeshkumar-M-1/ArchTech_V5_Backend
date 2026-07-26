# AI Agent Framework Architectural Blueprint (Milestone 3 Final)

This document outlines the definitive implementation plan for **Milestone 3: Autonomous Reasoning**. Based on the final architectural review, we have elevated Planning out of the tactical loop, introduced strict Runtime Policies, and evolved Reflection into a multi-branch decision node.

## Goal Description

Build the cognitive architecture of the agent. This layer consumes the deterministic `ExecutionContext` (built in Milestone 2) and executes a structured, highly-observable loop of reasoning, action, reflection, and verification.

## User Review Required

> [!IMPORTANT]
> The architecture has been updated to reflect your final feedback. `MissionManager` and `TaskScheduler` now sit strictly above the `WorkflowRunner`. `ActionResult` has been added. `ReflectionEngine` now branches dynamically. `RuntimePolicy` has been introduced. Please give the final approval to begin implementation!

---

## The Reasoning Pipeline (Milestone 3)

The architecture is built around this exact flow:

```
MissionManager
      │
PlanningEngine
      │
TaskScheduler
      │
WorkflowRunner
      │
LoopController (Consults RuntimePolicy)
      │
TurnManager
      │
ReasoningEngine & ReasoningState
      │
Decision
      │
ActionExecutor
      │
ToolRouter
      │
ToolExecutor
      │
ActionResult
      │
ObservationEngine
      │
ObservationBus
 ┌────┼────────────┬─────────────┐
 ▼    ▼            ▼             ▼
Memory Knowledge Journal Telemetry
      │
KnowledgeUpdater
      │
ReflectionEngine
      │
ReflectionDecision
 ┌────┼───────────────┬──────────────┐
 ▼    ▼               ▼              ▼
Continue Verify Replan AskUser Complete
      │
Verifier (only if Verify)
      │
RepairPlanner (only if failed)
      │
LoopController
      │
TaskScheduler
```

### Strategic Layer (Above the Loop)

1. **`MissionManager`**: Initializes goals.
2. **`PlanningEngine`**: Generates strictly versioned `Plan v1`, `Plan v2`.
3. **`TaskScheduler`**: The overarching owner of task selection and completion. It feeds the `Task` into the `WorkflowRunner`.

### Tactical Loop (Inside the Runner)

1. **`WorkflowRunner`**
   - **Role**: Pure lifecycle manager for a single Task (`Start`, `Stop`, `Pause`, `Resume`).

2. **`RuntimePolicy`**
   - **Role**: Global constraints (Token Budget, Turn Budget, Max Repairs). Consulted by the LoopController and all tactical engines.

3. **`LoopController`**
   - **Role**: The true brain of the loop. Owns the `while` statement, retry logic, and triggers.

4. **`TurnManager`**
   - **Role**: Highly scoped. Orchestrates exactly one sequence: `Reason -> Action -> Observe`.

5. **`ReasoningEngine` & `ReasoningState`**
   - **Role**: Evaluates the immutable `ExecutionContext` alongside a mutable `ReasoningState` (tracking `Current Hypothesis`, `Confidence`, `Strategy`).

6. **`Decision` (Domain Object)**
   - **Role**: Contains `Hypothesis`, `Confidence`, `Chosen Action`, `Expected Evidence`, `Expected Observation`, and `Exit Condition`.

7. **`ActionExecutor`**
   - **Role**: Parses intent (`READ`, `SEARCH`, `THINK`, `COMPLETE`). Only routes to `ToolRouter` if a system tool is required.

8. **`ActionResult`**
   - **Role**: Standardized output object (`Success`, `Failure`, `Artifacts`, `Tool Output`) before parsing into an Observation.

9. **`ObservationEngine` & `ObservationBus`**
   - **Role**: Converts `ActionResult` into immutable `Observations`. Emitted to the `ObservationBus`, where `Memory`, `KnowledgeUpdater`, and `Journal` subscribe.

10. **`ReflectionEngine` & `ReflectionDecision`**
    - **Role**: Evaluates progress (e.g., did `Expected Observation` match reality?). Decides among 5 branches: **Continue**, **Verify**, **Replan**, **AskUser**, or **Complete**.

11. **`Verifier` & `RepairPlanner`**
    - **Role**: Triggered *only* if Reflection chooses 'Verify'. `Verifier` checks Task Exit Conditions against collected Evidence/Artifacts. If failed, `RepairPlanner` generates a structured `RepairPlan` and passes it back to the `LoopController`.

12. **`ExecutionJournal`**
    - **Role**: The universal "Git log for reasoning". Records every `Decision`, `Observation`, `Reflection`, and `Repair` in append-only history.

---

## Next Steps
Upon your final "Go", I will create the `task.md` checklist and begin writing the code for Milestone 3!
