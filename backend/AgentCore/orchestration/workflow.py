"""
Orchestration: Workflow Runner & Loop Controller

The WorkflowRunner is the simple lifecycle manager (start, pause).
The LoopController holds the main `while` statement and delegates out to 
the TurnManager, ReflectionEngine, Verifier, and RepairPlanner.
"""

import logging
from enum import Enum

from ..context.execution_context import ExecutionContext
from ..domain.reasoning_state import ReasoningState
from ..domain.policy import RuntimePolicy
from ..reasoning.turn_manager import TurnManager
from ..cognitive.reflection import ReflectionEngine, ReflectionDecision
from ..cognitive.verifier import Verifier
from ..cognitive.repair import RepairPlanner

log = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LoopController:
    """The brain of the loop managing turns, budgets, reflection, and verification."""
    
    def __init__(
        self, 
        policy: RuntimePolicy, 
        turn_manager: TurnManager, 
        reflection: ReflectionEngine,
        verifier: Verifier,
        repair: RepairPlanner
    ):
        self.policy = policy
        self.turn = turn_manager
        self.reflection = reflection
        self.verifier = verifier
        self.repair = repair
        log.info("[LoopController] Initialized.")

    def execute_task_loop(self, context: ExecutionContext, state: ReasoningState) -> WorkflowStatus:
        """The main iterative loop for a given task."""
        log.info(f"[LoopController] Entering execution loop for task '{context.task_id}'.")

        while state.attempt_number <= self.policy.max_turns:
            # 1. Execute one tactical turn (Reason -> Act -> Observe)
            #    Pass observation history so the ReasoningEngine can detect repeated actions.
            observation = self.turn.execute_turn(context, state, state.observation_history)

            # 2. Accumulate observation for the reasoning engine
            state.observation_history.append({
                "action_type": observation.source_tool,
                "confidence": observation.confidence,
                "evidence": observation.evidence,
            })

            # 3. Reflect on the outcome
            decision = self.reflection.reflect(observation, state)
            
            # 3. Branching Logic based on Reflection Decision
            if decision == ReflectionDecision.CONTINUE:
                state.increment_attempt()
                continue
                
            elif decision == ReflectionDecision.VERIFY:
                result = self.verifier.verify(context.task_id, "evidence_placeholder", None)
                if result.passed:
                    log.info("[LoopController] Verification PASSED. Exiting loop with SUCCESS.")
                    return WorkflowStatus.COMPLETED
                else:
                    log.warning("[LoopController] Verification FAILED. Entering Repair.")
                    repair_plan = self.repair.plan_repair(result.reason, result.missing_evidence)
                    # Loop back with new repair context in state
                    state.increment_attempt()
                    continue
                    
            elif decision == ReflectionDecision.REPLAN:
                log.info("[LoopController] Task requires strategic replanning. Exiting loop.")
                return WorkflowStatus.FAILED
                
            elif decision == ReflectionDecision.ASK_USER:
                log.info("[LoopController] Halting to ask user for input.")
                return WorkflowStatus.PAUSED
                
        log.error("[LoopController] Turn budget exceeded! Task failed.")
        return WorkflowStatus.FAILED


class WorkflowRunner:
    """High-level lifecycle manager for task execution."""
    
    def __init__(self, loop_controller: LoopController):
        self.loop_controller = loop_controller
        self.status = WorkflowStatus.STOPPED
        log.info("[WorkflowRunner] Initialized.")

    def run_task(self, context: ExecutionContext, initial_state: ReasoningState) -> WorkflowStatus:
        self.status = WorkflowStatus.RUNNING
        log.info(f"[WorkflowRunner] Starting lifecycle for task '{context.task_id}'")
        
        try:
            self.status = self.loop_controller.execute_task_loop(context, initial_state)
        except Exception as e:
            log.error(f"[WorkflowRunner] Critical pipeline fault: {e}")
            self.status = WorkflowStatus.FAILED
            
        log.info(f"[WorkflowRunner] Lifecycle ended with status: {self.status.name}")
        return self.status
