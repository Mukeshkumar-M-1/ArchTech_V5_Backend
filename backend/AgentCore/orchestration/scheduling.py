"""
Scheduling

Owns task allocation, capability matching, and scheduler logic.
"""

import logging
from typing import List, Optional, Protocol
from AgentCore.orchestration.contracts import TaskContract, AgentStatus, AgentDescriptor
from AgentCore.orchestration.worker_management import AgentCatalog, WorkerDirectory
from AgentCore.orchestration.queue_and_dispatch import TaskQueue, LeaseManager, Dispatcher, AssignmentTracker

log = logging.getLogger(__name__)

class CapabilityResolver:
    """Answers 'Who can execute X?' to narrow eligible workers."""
    
    def __init__(self, agent_catalog: AgentCatalog):
        self.agent_catalog = agent_catalog
        
    def get_eligible_workers(self, required_capabilities: frozenset[str]) -> List[AgentDescriptor]:
        eligible_worker_agent = []
        for agent_worker in self.agent_catalog.list_all():
            if required_capabilities.issubset(agent_worker.agent_capabilities):
                eligible_worker_agent.append(agent_worker)
        log.info(f"[CapabilityResolver] Found {len(eligible_worker_agent)} workers matching {required_capabilities}")
        return eligible_worker_agent


class ISchedulingPolicy(Protocol):
    """Protocol for scoring eligible workers."""
    def score_worker(self, agent_id: str, worker_directory: WorkerDirectory) -> float: ...


class LeastBusyPolicy(ISchedulingPolicy):
    def score_worker(self, agent_id: str, worker_directory: WorkerDirectory) -> float:
        agent_heart_beat = worker_directory.get_heartbeat(agent_id=agent_id)
        if not agent_heart_beat:
            return -1.0 # Invalid
            
        if agent_heart_beat.status != AgentStatus.IDLE:
            return -1.0 # Only select IDLE workers for now
            
        # Lower queue depth and CPU is better
        return 100.0 - (agent_heart_beat.cpu_usage_pct + (agent_heart_beat.queue_depth * 10))


class Scheduler:
    """The matching algorithm selecting the best worker from the eligible pool."""
    
    def __init__(
        self, 
        capability_resolver: CapabilityResolver, 
        worker_directory: WorkerDirectory,
        scheduling_policy: LeastBusyPolicy,
        lease_manager: LeaseManager,
        dispatcher: Dispatcher,
        assignment_tracker: AssignmentTracker
    ):
        self.capability_resolver = capability_resolver
        self.worker_directory = worker_directory
        self.scheduling_policy = scheduling_policy
        self.lease_manager = lease_manager
        self.dispatcher = dispatcher
        self.assignment_tracker = assignment_tracker
        
    async def run_scheduling_cycle(self, task_queue: TaskQueue) -> list:
        """Pulls tasks from task_queue and dispatches them. Returns list of spawned_task asyncio.Tasks."""
        agent_spawned_tasks = []
        
        # Simple greedy scheduling loop
        while task_queue.size() > 0:
            # Peek at the task
            agent_task = task_queue.agent_task_queue[0]
            
            # Build task required capabilities
            task_required_capability = agent_task.execution_context.get("required_capabilities", [])

            # Build eligible workers
            eligible_worker_agents = self.capability_resolver.get_eligible_workers(frozenset(task_required_capability))
            if not eligible_worker_agents:
                log.warning(f"[Scheduler] No eligible workers for Task {agent_task.task_id}. Re-evaluating later.")
                break
                
            # Build agent score worker
            new_agent_worker = None
            new_agent_score = -1.0
            
            for agent_worker in eligible_worker_agents:
                current_agent_score = self.scheduling_policy.score_worker(agent_id=agent_worker.agent_id, worker_directory=self.worker_directory)
                if current_agent_score > new_agent_score:
                    new_agent_score = current_agent_score
                    new_agent_worker = agent_worker
                    
            if not new_agent_worker:
                log.info(f"[Scheduler] No workers available (all busy) for Task {agent_task.task_id}.")
                break # Wait for workers to free up
                
            # Build Task queue
            assign_agent_task = task_queue.dequeue()
            
            # Build agent working duration
            if assign_agent_task.deadline_ms > 0:
                lease_duration = assign_agent_task.deadline_ms / 1000.0
            else:
                lease_duration = 1000.0
            
            # Build agent lease assignment
            agent_assignment = self.lease_manager.create_lease(worker_id=new_agent_worker.agent_id, task_id=assign_agent_task.task_id, duration_sec=lease_duration)
            
            # Recode lease assignment
            self.assignment_tracker.record_assignment(assignment=agent_assignment)
            log.info(f"[Scheduler] Scheduled Task {assign_agent_task.task_id} -> \n Worker : [{new_agent_worker.agent_id}] (Score: [{new_agent_score:.1f}])")
            
            spawned_task = await self.dispatcher.dispatch(agent_assignment, assign_agent_task)
            agent_spawned_tasks.append(spawned_task)
            
            # Update Agent status to busy
            agent_heart_beat = self.worker_directory.get_heartbeat(new_agent_worker.agent_id)
            if agent_heart_beat:
                agent_heart_beat.status = AgentStatus.BUSY
                
        return agent_spawned_tasks
