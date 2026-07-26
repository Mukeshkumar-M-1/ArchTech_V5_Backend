"""
Milestone 5 — Orchestration Layer Boundary Tests

Validates every M5 architectural layer in isolation, mirroring the
test_milestone_4.py pattern.  No project templates, no LLM calls,
no async heartbeats — just pure contract, scheduling, dispatch, and
mission-layer interface checks.
"""

import logging
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.orchestration.contracts import (
    AgentDescriptor,
    AgentHeartbeat,
    AgentStatus,
    Assignment,
    RuntimeResult,
    RuntimeLifecycleStatus,
    TaskContract,
)
from AgentCore.orchestration.worker_management import (
    AgentCatalog,
    WorkerDirectory,
    HeartbeatMonitor,
    WorkerLifecycle,
    FailureDetector,
)
from AgentCore.orchestration.queue_and_dispatch import (
    TaskQueue,
    LeaseManager,
    AssignmentTracker,
    Dispatcher,
    RetryManager,
)
from AgentCore.orchestration.scheduling import (
    CapabilityResolver,
    LeastBusyPolicy,
    Scheduler,
)
from AgentCore.orchestration.mission_layer import (
    TaskGraph,
    TaskNode,
    MissionStateManager,
    ReadyTaskSelector,
)
from AgentCore.orchestration.result_layer import (
    ResultProcessor,
    MissionStateUpdater,
    EventAggregator,
)

logging.basicConfig(
    level=logging.INFO,
    format="\n\n %(asctime)s [%(name)s.%(funcName)s]\n [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log8.log",
            encoding="utf-8",
            mode="a",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_descriptor(agent_id: str, capabilities: frozenset[str] = None) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        agent_profile="General_Purpose",
        agent_capabilities=capabilities or frozenset(["bash", "python"]),
        agent_resource_limits={},
        agent_supported_contract_versions=frozenset(["v1"]),
    )


def _sample_task(task_id: str, goal: str = "Do the thing") -> TaskContract:
    return TaskContract(
        task_id=task_id,
        goal=goal,
        execution_context={},
    )


# ---------------------------------------------------------------------------
# Test harness (synchronous — no async/LLM deps)
# ---------------------------------------------------------------------------

def main():
    print("\n=== Initializing Milestone 5 Orchestration Boundaries ===")

    # -----------------------------------------------------------------------
    # 1. Contracts
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.1: Core Contracts ===")

    # 1a. TaskContract is frozen (immutable)
    print("\n[Test 1] TaskContract Immutability")
    task_a = _sample_task("task-001", "Write a bash script")
    try:
        task_a.goal = "Overridden!"  # type: ignore[assignment]
    except Exception as e:
        print(f"  TaskContract is correctly frozen: {type(e).__name__}")
    else:
        print(f"  Goal (expected immutable): {task_a.goal}")

    # 1b. RuntimeResult carries full evidence
    print("\n[Test 2] RuntimeResult Rich Output")
    result_a = RuntimeResult(
        task_id="task-001",
        status=RuntimeLifecycleStatus.COMPLETED,
        produced_evidence="print('hello')",
        produced_artifacts=["script.py"],
        journal_reference="exec_m5_001",
        cost_usd=0.012,
        metrics={"llm_calls": 3, "tool_calls": 5},
        checkpoint_id="chk_001",
    )
    print(f"  Status: {result_a.status.name} | Artifacts: {result_a.produced_artifacts} | Cost: ${result_a.cost_usd:.3f}")

    # 1c. Assignment with lease expiration
    print("\n[Test 3] Assignment Lease Binding")
    assignment = Assignment(
        worker_id="worker_001",
        task_id="task-001",
        lease_expiration_timestamp=time.time() + 60.0,
        priority=2,
        attempt_number=1,
    )
    print(f"  Assignment: {assignment.assignment_id} | Worker: {assignment.worker_id} | Task: {assignment.task_id} | Lease: {assignment.lease_expiration_timestamp:.1f}")

    # -----------------------------------------------------------------------
    # 2. Worker Management
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.3: Worker Management ===")

    catalog = AgentCatalog()
    directory = WorkerDirectory()
    lifecycle = WorkerLifecycle(directory)
    failure_detector = FailureDetector(directory, timeout_seconds=0.5)

    # 2a. Register workers
    print("\n[Test 4] AgentCatalog Registration")
    desc_bash = _sample_descriptor("worker_bash", frozenset(["bash"]))
    desc_python = _sample_descriptor("worker_python", frozenset(["python"]))
    desc_general = _sample_descriptor("worker_general", frozenset(["bash", "python"]))

    catalog.register_profile(desc_bash)
    catalog.register_profile(desc_python)
    catalog.register_profile(desc_general)

    all_profiles = catalog.list_all()
    print(f"  Catalog size: {len(all_profiles)}")

    # 2b. Heartbeat monitoring
    print("\n[Test 5] WorkerDirectory Heartbeat")
    hb = AgentHeartbeat(
        agent_id="worker_bash",
        status=AgentStatus.IDLE,
        cpu_usage_pct=12.5,
        memory_usage_mb=256.0,
        queue_depth=0,
        health_score=1.0,
    )
    directory.update_heartbeat(hb)

    cached = directory.get_heartbeat("worker_bash")
    print(f"  Cached heartbeat — CPU: {cached.cpu_usage_pct}%, Health: {cached.health_score}")

    # 2c. Lifecycle transitions
    print("\n[Test 6] WorkerLifecycle Transitions")
    lifecycle.set_status("worker_bash", AgentStatus.BUSY)
    cached = directory.get_heartbeat("worker_bash")
    print(f"  After BUSY transition: {cached.status.name}")

    lifecycle.drain_worker("worker_bash")
    cached = directory.get_heartbeat("worker_bash")
    print(f"  After DRAIN transition: {cached.status.name}")

    # 2d. Failure detection
    print("\n[Test 7] FailureDetector Stale Heartbeat")
    stale_hb = AgentHeartbeat(
        agent_id="worker_general",
        status=AgentStatus.READY,
        cpu_usage_pct=0.0,
        memory_usage_mb=0.0,
        queue_depth=0,
        health_score=1.0,
        last_seen_timestamp=time.time() - 10.0,  # 10s stale
    )
    directory.update_heartbeat(stale_hb)
    print(f"  Stale heartbeat registered. Health score: {stale_hb.health_score} | Last seen: {stale_hb.last_seen_timestamp}")

    # -----------------------------------------------------------------------
    # 3. Queue & Dispatch
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.4: Queue & Dispatch ===")

    queue = TaskQueue()
    lease_mgr = LeaseManager()
    assign_tracker = AssignmentTracker()

    # 3a. Enqueue / dequeue
    print("\n[Test 8] TaskQueue FIFO")
    t1 = _sample_task("tq-001", "Task A")
    t2 = _sample_task("tq-002", "Task B")
    t3 = _sample_task("tq-003", "Task C")
    queue.enqueue(t1)
    queue.enqueue(t2)
    queue.enqueue(t3)
    print(f"  Queue size after enqueue: {queue.size()}")

    d1 = queue.dequeue()
    d2 = queue.dequeue()
    print(f"  Dequeued: {d1.task_id}, {d2.task_id} | Remaining: {queue.size()}")

    # 3b. Lease creation and release
    print("\n[Test 9] LeaseManager Create & Release")
    lease = lease_mgr.create_lease("worker_bash", "tq-001", 60.0)
    print(f"  Lease created — Worker: {lease.worker_id}, Task: {lease.task_id}, TTL: 60s")

    cached_lease = lease_mgr.get_lease("tq-001")
    print(f"  Lease lookup confirms: {cached_lease.worker_id} -> {cached_lease.task_id}")

    lease_mgr.release_lease("tq-001")
    print(f"  Lease released. Lookup returns: {lease_mgr.get_lease('tq-001')}")

    # 3c. Assignment tracking history
    print("\n[Test 10] AssignmentTracker History")
    assign_tracker.record_assignment(lease)
    history = assign_tracker._history.get("tq-001", [])
    print(f"  Assignment history for 'tq-001': {len(history)} records")

    # 3d. RetryManager requeue (timeout triggers RETRY strategy)
    print("\n[Test 11] RetryManager Requeue")
    from AgentCore.runtime.failure_classifier import FailureClassifier

    queue2 = TaskQueue()
    classifier = FailureClassifier()
    retry_mgr2 = RetryManager(queue2, classifier)
    retry_task = _sample_task("retry-001", "Must retry")
    retry_mgr2.handle_failure(retry_task, "Request timeout after 30s waiting for response", attempt_num=1)
    print(f"  Queue size after retry requeue: {queue2.size()}")
    retrived = queue2.dequeue()
    print(f"  Retrieved from retry: {retrived.task_id}")

    # -----------------------------------------------------------------------
    # 4. Scheduling Layer
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.5: Scheduling ===")

    # Re-populate catalog and directory for scheduler tests
    sched_catalog = AgentCatalog()
    sched_catalog.register_profile(_sample_descriptor("scheduler-01", frozenset(["bash", "python"])))
    sched_catalog.register_profile(_sample_descriptor("scheduler-02", frozenset(["bash"])))

    sched_dir = WorkerDirectory()
    sched_dir.update_heartbeat(AgentHeartbeat(
        agent_id="scheduler-01", status=AgentStatus.IDLE,
        cpu_usage_pct=10.0, memory_usage_mb=128.0, queue_depth=0, health_score=1.0,
    ))
    sched_dir.update_heartbeat(AgentHeartbeat(
        agent_id="scheduler-02", status=AgentStatus.IDLE,
        cpu_usage_pct=80.0, memory_usage_mb=512.0, queue_depth=5, health_score=0.5,
    ))

    # 4a. CapabilityResolver
    print("\n[Test 12] CapabilityResolver Filtering")
    resolver = CapabilityResolver(sched_catalog)

    eligible_bash = resolver.get_eligible_workers(frozenset(["bash"]))
    eligible_python = resolver.get_eligible_workers(frozenset(["python"]))
    print(f"  Workers matching ['bash']: {len(eligible_bash)} — {[w.agent_id for w in eligible_bash]}")
    print(f"  Workers matching ['python']: {len(eligible_python)} — {[w.agent_id for w in eligible_python]}")

    # 4b. LeastBusyPolicy scoring
    print("\n[Test 13] LeastBusyPolicy Scoring")
    policy = LeastBusyPolicy()
    score_01 = policy.score_worker("scheduler-01", sched_dir)
    score_02 = policy.score_worker("scheduler-02", sched_dir)
    print(f"  scheduler-01 score (10% CPU, 0 queue): {score_01:.1f}")
    print(f"  scheduler-02 score (80% CPU, 5 queue): {score_02:.1f}")
    print(f"  Better worker: {'scheduler-01' if score_01 > score_02 else 'scheduler-02'}")

    # -----------------------------------------------------------------------
    # 5. Mission Layer
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.6: Mission Layer ===")

    # 5a. TaskGraph dependency chain
    print("\n[Test 14] TaskGraph DAG Construction")
    graph = TaskGraph()
    graph.add_task(_sample_task("dep-001", "First"))
    graph.add_task(_sample_task("dep-002", "Second"), dependencies=["dep-001"])
    graph.add_task(_sample_task("dep-003", "Third"), dependencies=["dep-001", "dep-002"])

    node_001 = graph.task_node["dep-001"]
    node_003 = graph.task_node["dep-003"]
    print(f"  dep-001 — dependents: {node_001.dependents}")
    print(f"  dep-003 — dependencies: {node_003.dependencies}")

    # 5b. Dependency resolution via complete_task
    print("\n[Test 15] TaskGraph Dependency Propagation")
    initial_dep_003_deps = len(node_003.dependencies)
    graph.complete_task("dep-001")
    graph.complete_task("dep-002")
    print(f"  dep-003 dependencies before completion chain: {initial_dep_003_deps}")
    print(f"  dep-003 dependencies after both parents completed: {len(node_003.dependencies)}")
    print(f"  dep-003 is_ready: {node_003.is_ready}")

    # 5c. ReadyTaskSelector
    print("\n[Test 16] ReadyTaskSelector")
    selector_queue = TaskQueue()
    selector_graph = TaskGraph()
    selector_graph.add_task(_sample_task("sel-001", "Ready now"))
    selector_graph.add_task(_sample_task("sel-002", "Blocked"), dependencies=["sel-001"])
    selector = ReadyTaskSelector(selector_graph, selector_queue)
    selector.build_ready_tasknode()
    print(f"  Ready tasks enqueued (sel-001 only): {selector_queue.size()}")
    picked = selector_queue.dequeue()
    print(f"  Dequeued: {picked.task_id}")

    # 5d. MissionStateManager
    print("\n[Test 17] MissionStateManager")
    state_mgr = MissionStateManager()
    state_mgr.initialize_from_graph(graph)
    print(f"  Total tasks: {state_mgr.total_tasks}")
    print(f"  Pending tasks: {state_mgr.pending_tasks}")

    graph.complete_task("dep-001")
    state_mgr.completed_tasks += 1
    state_mgr.pending_tasks -= 1
    print(f"  After 1 completion — Completed: {state_mgr.completed_tasks}, Pending: {state_mgr.pending_tasks}")

    # -----------------------------------------------------------------------
    # 6. Result Layer
    # -----------------------------------------------------------------------
    print("\n=== Phase 5.7: Result Layer ===")

    res_graph = TaskGraph()
    res_graph.add_task(_sample_task("res-001", "Test success"))
    res_graph.add_task(_sample_task("res-002", "Test failure"))

    res_state_mgr = MissionStateManager()
    res_state_mgr.initialize_from_graph(res_graph)

    res_updater = MissionStateUpdater(task_graph=res_graph, mission_state_manager=res_state_mgr)
    res_lease_mgr = LeaseManager()
    res_dir = WorkerDirectory()
    res_processor = ResultProcessor(
        lease_manager=res_lease_mgr,
        mission_state_updater=res_updater,
        worker_directory=res_dir,
    )
    event_agg = EventAggregator()

    # 6a. Process successful result
    print("\n[Test 18] ResultProcessor — Success Path")
    success_result = RuntimeResult(
        task_id="res-001",
        status=RuntimeLifecycleStatus.COMPLETED,
        produced_evidence="Success evidence",
        produced_artifacts=["output.md"],
        cost_usd=0.025,
    )
    res_processor.process_result(success_result)
    print(f"  Completed: {res_state_mgr.completed_tasks} | Failed: {res_state_mgr.failed_tasks}")

    # 6b. Process failed result
    print("\n[Test 19] ResultProcessor — Failure Path")
    fail_result = RuntimeResult(
        task_id="res-002",
        status=RuntimeLifecycleStatus.FAILED,
        failure_reason="LLM rate-limited",
    )
    res_processor.process_result(fail_result)
    print(f"  Completed: {res_state_mgr.completed_tasks} | Failed: {res_state_mgr.failed_tasks}")

    # 6c. EventAggregator buffering and flush
    print("\n[Test 20] EventAggregator Buffering")
    event_agg.ingest_runtime_event({"type": "Decision", "action": "write_file"})
    event_agg.ingest_runtime_event({"type": "Observation", "content": "File written"})
    event_agg.ingest_runtime_event({"type": "Checkpoint", "id": "chk_xyz"})
    print(f"  Events buffered: {len(event_agg.event_buffer)}")
    event_agg.flush_to_telemetry()
    print(f"  Events after flush: {len(event_agg.event_buffer)}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n=== Milestone 5 Boundary Tests Complete ===")
    print("Layers validated: Contracts | Worker Mgmt | Queue & Dispatch | Scheduling | Mission Layer | Result Layer")


if __name__ == "__main__":
    main()
