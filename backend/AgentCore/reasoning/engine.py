"""
Reasoning Engine

Evaluates the ExecutionContext (immutable environment data) and the ReasoningState
(mutable tactical data) to generate the next tactical Decision.
"""

import logging

from ..context.execution_context import ExecutionContext
from ..domain.reasoning_state import ReasoningState
from ..domain.decision import Decision, ActionDefinition
from ..domain.policy import RuntimePolicy

log = logging.getLogger(__name__)

class ReasoningEngine:
    """Tactical engine generating Decisions."""

    def __init__(self, policy: RuntimePolicy):
        self.policy = policy
        log.info("[ReasoningEngine] Initialized.")

    def decide(self, context: ExecutionContext, state: ReasoningState,
               observation_history=None) -> Decision:
        """
        In a real implementation, this constructs a prompt using PromptManager,
        invokes the LLM, parses the JSON response, and maps it to a Decision object.
        For Milestone 3 architecture setup, we return a simulated Decision.
        """
        log.info(f"[ReasoningEngine] Evaluating context for Task '{context.task_id}', Attempt {state.attempt_number}")

        if observation_history is None:
            observation_history = []

        # Detect repeated actions: if SEARCH appeared 3+ times, switch to COMPLETE.
        search_count = sum(1 for o in observation_history if o.get("action_type") == "SEARCH")

        if search_count >= 3:
            # Enough evidence gathered - conclude and mark task complete.
            chosen_action = ActionDefinition(
                action_type="COMPLETE",
                parameters={"summary": (
                    f"WorkflowRunner orchestrates the LoopController, which runs a turn loop "
                    f"driven by the ReasoningEngine and ActionExecutor. Found across "
                    f"{search_count} turns."
                )}
            )
            decision = Decision(
                hypothesis="The WorkflowRunner orchestrates the LoopController, ReasoningEngine, and ActionExecutor in a try/catch lifecycle.",
                confidence=0.92,
                chosen_action=chosen_action,
                reason="Evidence gathered across multiple turns. Concluding analysis.",
                expected_evidence="Lifecycle status: COMPLETED.",
                expected_observation="None.",
                exit_condition="Lifecycle fully mapped.",
                alternatives=["None - sufficient evidence gathered."]
            )
        else:
            # Simulate LLM deciding to SEARCH
            chosen_action = ActionDefinition(
                action_type="SEARCH",
                parameters={"query": "find_symbol('WorkflowRunner')"}
            )

            decision = Decision(
                hypothesis="The WorkflowRunner orchestrates the LoopController.",
                confidence=0.85,
                chosen_action=chosen_action,
                reason="I need to see the implementation of WorkflowRunner.",
                expected_evidence="Class definition for WorkflowRunner.",
                expected_observation="Source code containing WorkflowRunner methods.",
                exit_condition="Task complete when all lifecycle methods are identified.",
                alternatives=["READ entire file", "ASK_USER"]
            )

        # In a real run, the state updates based on LLM output
        state.update_hypothesis(decision.hypothesis, decision.confidence)

        return decision
