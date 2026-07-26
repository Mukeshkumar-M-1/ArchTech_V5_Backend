"""
Turn Manager

Highly scoped orchestrator. It manages exactly ONE iteration of the loop:
Reason -> Act -> Observe. It does NOT handle retries, while loops, or reflection.
"""

import logging

from ..context.execution_context import ExecutionContext
from ..domain.reasoning_state import ReasoningState
from .engine import ReasoningEngine
from ..action.executor import ActionExecutor
from ..knowledge.observation_engine import ObservationEngine
from ..knowledge.observation import Observation

log = logging.getLogger(__name__)

class TurnManager:
    """Executes a single tactical turn."""
    
    def __init__(
        self,
        reasoning_engine: ReasoningEngine,
        action_executor: ActionExecutor,
        observation_engine: ObservationEngine
    ):
        self.reasoning = reasoning_engine
        self.executor = action_executor
        self.observer = observation_engine
        log.info("[TurnManager] Initialized.")

    def execute_turn(self, context: ExecutionContext, state: ReasoningState,
                     observation_history=None) -> Observation:
        """Runs the sequence: Reason -> Act -> Observe."""
        log.info(f"\n--- Starting Turn (Attempt {state.attempt_number}) ---")
        if observation_history is None:
            observation_history = []

        # 1. Reason
        decision = self.reasoning.decide(context, state, observation_history)
        
        # 2. Act
        action_result = self.executor.execute_action(decision.chosen_action)
        
        # 3. Observe
        # The ObservationEngine parses the ActionResult and publishes to the ObservationBus
        observation = self.observer.process_result(
            result=action_result,
            expected_observation=decision.expected_observation
        )
        
        log.info("--- Turn Completed ---\n")
        return observation
