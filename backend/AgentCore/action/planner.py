"""
Action Planner

Translates a high-level cognitive Intent (Decision) into a concrete, 
first-class ExecutionPlan.
"""

import logging
import uuid
from typing import List

from ..domain.decision import Decision, ActionDefinition
from ..domain.execution_plan import ExecutionPlan, ExecutionStep, StepStatus, RetryPolicy

log = logging.getLogger(__name__)

class ActionPlanner:
    def __init__(self):
        log.info("[ActionPlanner] Initialized.")

    def plan_actions(self, decision: Decision) -> ExecutionPlan:
        """
        Takes the chosen action/intent from the ReasoningEngine and expands it.
        For example, a high-level 'SEARCH' intent might become an ExecutionPlan 
        with multiple parallel or sequential ExecutionSteps.
        """
        log.info(f"[ActionPlanner] Expanding intent: '{decision.chosen_action.action_type}'")
        
        steps: List[ExecutionStep] = []
        
        # Rule-based expansion
        if decision.chosen_action.action_type == "SEARCH":
            query = decision.chosen_action.parameters.get("query", "")
            
            step1 = ExecutionStep(
                step_id=str(uuid.uuid4()),
                action=ActionDefinition("SEARCH_REPO", {"query": query}),
                retry_policy=RetryPolicy(max_retries=1)
            )
            step2 = ExecutionStep(
                step_id=str(uuid.uuid4()),
                action=ActionDefinition("SEARCH_FILES", {"pattern": f"*{query}*"}),
                dependencies=[step1.step_id] # Sequential dependency for demonstration
            )
            
            steps.extend([step1, step2])
        else:
            steps.append(ExecutionStep(
                step_id=str(uuid.uuid4()),
                action=decision.chosen_action
            ))
            
        return ExecutionPlan.create(generated_by="ActionPlanner", steps=steps)
