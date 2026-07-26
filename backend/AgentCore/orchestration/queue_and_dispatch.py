"""
Queue & Dispatch

Handles pending tasks, lease assignments, dispatching to runtimes, and tracking ownership.
"""

import logging
import time
import asyncio
from typing import Dict, List, Optional, Deque
from collections import deque
import uuid

from AgentCore.orchestration.contracts import TaskContract, Assignment, IAgentRuntime
from AgentCore.runtime.failure_classifier import FailureClassifier, RecoveryStrategy

log = logging.getLogger(__name__)

class TaskQueue:
    """The source of pending, ready-to-execute work."""
    def __init__(self):
        self.agent_task_queue: Deque[TaskContract] = deque()
        
    def enqueue(self, task: TaskContract):
        self.agent_task_queue.append(task)
        log.info(f"[TaskQueue] Enqueued TaskNode [{task.task_id}] (Total: {len(self.agent_task_queue)})")
        
    def dequeue(self) -> Optional[TaskContract]:
        if self.agent_task_queue:
            log.info(f"[TaskQueue] TaskNode Dequeued success, (Total: {len(self.agent_task_queue)})")
            return self.agent_task_queue.popleft()
        return None
        
    def size(self) -> int:
        return len(self.agent_task_queue)


class LeaseManager:
    """Grants time-bound leases for tasks to specific workers."""
    def __init__(self):
        self._leases: Dict[str, Assignment] = {} # Key: task_id
        
    def create_lease(self, worker_id: str, task_id: str, duration_sec: float) -> Assignment:
        assignment = Assignment(
            worker_id=worker_id,
            task_id=task_id,
            lease_expiration_timestamp=time.time() + duration_sec
        )
        self._leases[task_id] = assignment
        log.info(f"[LeaseManager] Lease created: Task {task_id} -> Worker {worker_id} for {duration_sec}s")
        return assignment
        
    def release_lease(self, task_id: str):
        if task_id in self._leases:
            del self._leases[task_id]
            log.info(f"[LeaseManager] Released lease for Task {task_id}")
            
    def get_lease(self, task_id: str) -> Optional[Assignment]:
        return self._leases.get(task_id)


class AssignmentTracker:
    """Preserves task-to-worker history for telemetry and debugging."""
    def __init__(self):
        # Key: task_id, Value: List of historical assignments
        self._history: Dict[str, List[Assignment]] = {}
        
    def record_assignment(self, assignment: Assignment):
        if assignment.task_id not in self._history:
            self._history[assignment.task_id] = []
        self._history[assignment.task_id].append(assignment)
        log.debug(f"[AssignmentTracker] Recorded assignment {assignment.assignment_id}")


class Dispatcher:
    """Invokes the worker runtime after a lease is granted."""
    def __init__(self, runtime_adapter: Dict[str, IAgentRuntime]):
        self.agent_runtime_adapter = runtime_adapter # Key: worker_id
        
    async def dispatch(self, assignment: Assignment, task: TaskContract) -> asyncio.Task:
        current_worker_agent = self.agent_runtime_adapter.get(assignment.worker_id)
        if not current_worker_agent:
            raise ValueError(f"Worker {assignment.worker_id} not found for dispatch!")
            
        log.info(f"[Dispatcher] Dispatching Task {task.task_id} to Worker {assignment.worker_id}")
        # Return an asyncio.Task so the orchestrator doesn't block on execution
        return asyncio.create_task(current_worker_agent.execute(task))


class RetryManager:
    """Intercepts classified failures, applies backoff, and requeues."""
    def __init__(self, queue: TaskQueue, classifier: FailureClassifier):
        self.queue = queue
        self.classifier = classifier
        self.max_retries = 3
        
    def handle_failure(self, task: TaskContract, error_msg: str, attempt_num: int):
        strategy = self.classifier.classify_error("Exception", error_msg)
        
        log.warning(f"[RetryManager] Task {task.task_id} failed on attempt {attempt_num}. Strategy: {strategy.name}")
        
        if strategy == RecoveryStrategy.ABORT or strategy == RecoveryStrategy.ESCALATE:
            log.error(f"[RetryManager] Aborting Task {task.task_id} permanently due to policy.")
            # Would notify MissionStateUpdater here
            return
            
        if attempt_num >= self.max_retries:
            log.error(f"[RetryManager] Task {task.task_id} exhausted retries ({self.max_retries}).")
            return
            
        log.info(f"[RetryManager] Requeuing Task {task.task_id} for attempt {attempt_num + 1}")
        # In a real system, we'd add async sleep for exponential backoff here
        self.queue.enqueue(task)
