# Agent Framework Final Production Roadmap (v1.2)

Based on the final architectural review, we are officially locking the structure into a six-stage lifecycle: M1 through M6.

## User Review Required

> [!IMPORTANT]
> Milestone 4.5 is officially locked in as the **Runtime Hardening** phase. As requested, before writing any system code for this phase, I have drafted the rigorous canonical contracts in the `runtime_specifications.md` artifact.
>
> Please review the specifications artifact. If you approve, I will begin implementing Milestone 4.5 based strictly on those contracts!

---

## Roadmap Progression

### M1: Runtime Foundation
### M2: Repository Intelligence
### M3: Reasoning Pipeline
### M4: Platform Integration (Complete)

### M4.5: Runtime Hardening (Current)
*Focuses exclusively on survivability, decoupling, and strict state management.*
- **RuntimeStateMachine**: The sole source of truth for execution states.
- **CheckpointManager**: Deep, event-based state snapshots.
- **ReplayEngine**: Deterministic debugging from the Journal.
- **Cancellation & Interrupt Managers**: Hierarchical signal propagation.
- **Dispatcher**: Sits between LoopController and ActionExecutor for queueing.
- **PolicyManager**: Replaces boolean checks with `ALLOW/DENY/ESCALATE/REWRITE`.
- **FailureClassifier**: Maps failures to explicit recovery strategies.
- **ExecutionPlan**: First-class domain object with dependencies and rollbacks.
- **Versioned Contracts**: Explicit versioning on all domain objects.

### M5: Orchestration
*Scales the hardened runtime into a distributed platform.*
- **IAgentRuntime**: The stable interface that supervisor agents will use to orchestrate workers.
- **QueueManager**
- **Multi-Agent & HITL**
- **Distributed Workers & Deep Resume**

### M6: Learning & Optimization (Future)
- **Memory consolidation**, **Strategy optimization**, **Prompt optimization**, **Self-evaluation**
