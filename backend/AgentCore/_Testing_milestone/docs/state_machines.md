# AgentCore State Machine Diagrams

## 1. AgentKernel Lifecycle

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> INITIALIZING: start()
    INITIALIZING --> RUNNING
    RUNNING --> PAUSED: pause()
    PAUSED --> RUNNING: resume()
    RUNNING --> COMPLETE: all sections done
    RUNNING --> CANCELLED: cancel()
    RUNNING --> FAILED: unrecoverable error
    COMPLETE --> IDLE: cleanup()
    CANCELLED --> IDLE: cleanup()
    FAILED --> IDLE: cleanup()
```

## 2. TaskNode Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: Scheduler.enqueue()
    PENDING --> SCHEDULED: Scheduler.dequeue()
    SCHEDULED --> RUNNING: Task starts
    RUNNING --> COMPLETED: verification.passed
    RUNNING --> FAILED: verification.failed
    COMPLETED --> [*]: Task done
    FAILED --> REQUEUED: task.retry_count < max_retries
    REQUEUED --> SCHEDULED: MissionController.adapt()
    SCHEDULED --> RUNNING: Task retries
    FAILED --> DEGRADED: task.retry_count >= max_retries
    DEGRADED --> [*]: Mark as partial
```

## 3. GoalManager State Machine

```mermaid
stateDiagram-v2
    [*] --> GlobalGoal

    GlobalGoal --> PhaseGoal: initialize()
    PhaseGoal --> SectionGoal: advance_to_section(section)

    SectionGoal --> TurnGoal: advance_to_turn()
    TurnGoal --> TurnGoal: mark_turn_complete()

    TurnGoal --> SectionGoal: all turns done, mark_section_complete()
    TurnGoal --> SectionGoal: mark_section_failed()

    SectionGoal --> SectionGoal: advance_to_section(next)

    SectionGoal --> PhaseGoal: all sections done, complete()
    PhaseGoal --> GlobalGoal: mission_complete()
    GlobalGoal --> [*]: cleanup()
```

## 4. SessionLifecycle State

```mermaid
stateDiagram-v2
    [*] --> NOT_EXISTS: No session yet
    NOT_EXISTS --> CREATING: SessionLifecycle.create_generation()
    CREATING --> ACTIVE: write session JSON
    ACTIVE --> COMPLETE: SessionLifecycle.update_progress(100)
    ACTIVE --> CANCELLED: cancel()
    ACTIVE --> ERROR: unexpected failure
    CANCELLED --> [*]: cleanup()
    COMPLETE --> [*]: cleanup()
    ERROR --> [*]: cleanup()
```

## 5. QueryGuard State

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> RUNNING: try_start(session_id)
    RUNNING --> IDLE: end()
    RUNNING --> RUNNING: (still running, blocked)
```

## 6. Blackboard State

```mermaid
stateDiagram-v2
    [*] --> EMPTY
    EMPTY --> MISSION_CREATED: MissionController.parse()
    MISSION_CREATED --> TASK_SCHEDULED: Scheduler.enqueue()
    TASK_SCHEDULED --> RUNNING: QueryLoop runs
    RUNNING --> VERIFIED: verification.run()
    VERIFIED --> COMPLETED: passed
    VERIFIED --> REFLECTING: failed
    REFLECTING --> ADAPTED: MissionController.adapt()
    ADAPTED --> TASK_SCHEDULED: Scheduler.requeue()
    COMPLETED --> [*]: Mission complete
```

## 7. TaskState (Built-in Tool Tasks)

```mermaid
stateDiagram-v2
    [*] --> PENDING: TaskCreate
    PENDING --> RUNNING: start()
    RUNNING --> COMPLETED: finish()
    RUNNING --> FAILED: error
    RUNNING --> KILLED: TaskStop
    COMPLETED --> [*]: cleanup
    FAILED --> [*]: cleanup
    KILLED --> [*]: cleanup
```
