"""
Result Layer

Processes execution results, resolves leases, updates mission graphs, and aggregates events.
"""

import logging
from AgentCore.orchestration.contracts import RuntimeResult, RuntimeLifecycleStatus, AgentStatus
from AgentCore.orchestration.lease_manager import LeaseManager, AssignmentTracker
from AgentCore.orchestration.mission_layer import TaskGraph, MissionStateManager
from AgentCore.orchestration.worker_management import WorkerDirectory

log = logging.getLogger(__name__)

class MissionStateUpdater:
    """Updates MissionStateManager and unblocks dependents in the TaskGraph."""
    def __init__(self, task_graph: TaskGraph, mission_state_manager: MissionStateManager):
        self.task_graph = task_graph
        self.mission_state_manager = mission_state_manager
        
    def handle_task_success(self, task_id: str):
        self.task_graph.complete_task(task_id)
        self.mission_state_manager.completed_tasks += 1
        self.mission_state_manager.pending_tasks -= 1
        log.info(f"[MissionStateUpdater] TaskNode [{task_id}] marked as success.")
        
    def handle_task_failure(self, task_id: str):
        self.mission_state_manager.failed_tasks += 1
        self.mission_state_manager.pending_tasks -= 1
        log.error(f"[MissionStateUpdater] TaskNode [{task_id}] marked as permanently failed.")

class ResultProcessor:
    """Receives RuntimeResult, releases the lease via LeaseManager, and parses success/failure."""
    def __init__(
        self, 
        lease_manager: LeaseManager, 
        mission_state_updater: MissionStateUpdater,
        worker_directory: WorkerDirectory
    ):
        self.lease_manager = lease_manager
        self.state_updater = mission_state_updater
        self.directory = worker_directory
        
    def process_result(self, result: RuntimeResult):
        log.info(f"[ResultProcessor] Processing result for Task {result.task_id} (Status: {result.status.name})")
        
        # 1. Look up lease to find the worker
        lease = self.lease_manager.get_lease(result.task_id)
        if lease:
            worker_id = lease.worker_id
            log.info(f"[ResultProcessor] Result was from Worker {worker_id}")
            
            # Free the worker back to IDLE
            hb = self.directory.get_heartbeat(worker_id)
            if hb and hb.status == AgentStatus.BUSY:
                hb.status = AgentStatus.IDLE
                
            # 2. Release the lease
            self.lease_manager.release_lease(result.task_id)
        else:
            log.warning(f"[ResultProcessor] No active lease found for Task {result.task_id}!")

        # 3. Process outcome
        if result.status == RuntimeLifecycleStatus.COMPLETED:
            self.state_updater.handle_task_success(result.task_id)
        elif result.status == RuntimeLifecycleStatus.FAILED:
            # Here we would normally invoke the RetryManager. 
            # For simplicity, if it reaches here, we assume it's a permanent failure.
            self.state_updater.handle_task_failure(result.task_id)

class EventAggregator:
    """Rolls up granular runtime events into orchestration-level TaskCompleted events."""
    # This acts as a bridge between the EventBus and the Orchestrator.
    # In a full integration, it subscribes to the EventBus of all active RuntimeAdapters,
    # aggregates their Decision/Observation telemetry, and buffers it for the ExecutionJournal.
    
    def __init__(self):
        self.event_buffer = []
        
    def ingest_runtime_event(self, event: dict):
        self.event_buffer.append(event)
        
    def flush_to_telemetry(self):
        count = len(self.event_buffer)
        self.event_buffer.clear()
        log.info(f"[EventAggregator] Flushed {count} runtime events to Telemetry/Journal")
