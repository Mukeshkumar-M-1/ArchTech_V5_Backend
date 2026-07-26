"""
Orchestration: Planning and Task Scheduling

Provides the strategic layer ABOVE the tactical reasoning loop.
MissionManager -> PlanningEngine -> TaskScheduler -> WorkflowRunner
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)

@dataclass
class Task:
    task_id: str
    directive: str
    expected_evidence: str
    exit_conditions: str

@dataclass
class Plan:
    version: int
    tasks: List[Task]


class PlanningEngine:
    """Generates immutable versioned plans based on current knowledge."""
    
    def __init__(self):
        self.current_version = 0
        log.info("[PlanningEngine] Initialized.")

    def create_plan(self, mission_directive: str) -> Plan:
        self.current_version += 1
        log.info(f"[PlanningEngine] Generating Plan v{self.current_version} for directive: '{mission_directive}'")
        
        # Simulate planning
        t1 = Task(
            task_id=f"t{self.current_version}_1",
            directive="Understand the WorkflowRunner implementation.",
            expected_evidence="WorkflowRunner class definition and its lifecycle methods.",
            exit_conditions="WorkflowRunner methods identified in the KnowledgeGraph."
        )
        return Plan(version=self.current_version, tasks=[t1])


class TaskScheduler:
    """Feeds Tasks from the Plan into the WorkflowRunner."""
    
    def __init__(self):
        self.plan: Optional[Plan] = None
        self.completed_task_ids = set()
        log.info("[TaskScheduler] Initialized.")

    def load_plan(self, plan: Plan) -> None:
        self.plan = plan
        log.info(f"[TaskScheduler] Loaded Plan v{plan.version}")

    def get_next_task(self) -> Optional[Task]:
        if not self.plan:
            return None
        for task in self.plan.tasks:
            if task.task_id not in self.completed_task_ids:
                log.info(f"[TaskScheduler] Scheduled next task: '{task.task_id}'")
                return task
        log.info("[TaskScheduler] No more pending tasks.")
        return None

    def mark_completed(self, task_id: str) -> None:
        self.completed_task_ids.add(task_id)
        log.info(f"[TaskScheduler] Marked task '{task_id}' as COMPLETED.")


class MissionManager:
    """Top-level strategic orchestrator."""
    
    def __init__(self, planner: PlanningEngine, scheduler: TaskScheduler):
        self.planner = planner
        self.scheduler = scheduler
        log.info("[MissionManager] Initialized.")

    def start_mission(self, directive: str) -> None:
        log.info(f"[MissionManager] Starting Mission: '{directive}'")
        plan = self.planner.create_plan(directive)
        self.scheduler.load_plan(plan)
