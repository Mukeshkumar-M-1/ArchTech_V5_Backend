"""
Dispatcher

Sits between the LoopController and ActionExecutor. Responsible for queueing, 
batching, and parallel dispatch of ExecutionSteps.
"""

import logging
from typing import List

from ..domain.execution_plan import ExecutionPlan, ExecutionStep, StepStatus
from ..domain.action_result import ActionResult, ActionResultStatus
from ..action.action_executor import ActionExecutor

log = logging.getLogger(__name__)

class Dispatcher:
    def __init__(self, action_executor: ActionExecutor):
        self.executor = action_executor
        log.info("[Dispatcher] Initialized.")

    def dispatch_plan(self, plan: ExecutionPlan) -> List[ActionResult]:
        """
        Executes an ExecutionPlan.
        For M4.5, this is a simple sequential dispatcher. 
        M5 will implement DAG evaluation for dependencies and parallel execution.
        """
        log.info(f"[Dispatcher] Dispatching ExecutionPlan {plan.plan_id} with {len(plan.steps)} steps.")
        results = []
        
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
                
            step.status = StepStatus.RUNNING
            log.info(f"[Dispatcher] Executing step {step.step_id} ({step.action.action_type})")
            
            # Note: A real dispatcher would handle step.retry_policy here
            result = self.executor.execute_action(step.action)  
            results.append(result)
            
            if result.status == ActionResultStatus.SUCCESS:
                step.status = StepStatus.COMPLETED
            else:
                step.status = StepStatus.FAILED
                log.warning(f"[Dispatcher] Step {step.step_id} failed. Halting plan.")
                break
                
        return results
