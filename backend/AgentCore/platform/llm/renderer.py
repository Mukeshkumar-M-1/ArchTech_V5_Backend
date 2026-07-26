"""
Prompt Renderer

Compiles the ExecutionContext and ReasoningState into a raw text string
or initial structured prompt before message building.
"""

import logging
from ...context.execution_context import ExecutionContext
from ...domain.reasoning_state import ReasoningState

log = logging.getLogger(__name__)

class PromptRenderer:
    def __init__(self):
        log.info("[PromptRenderer] Initialized.")

    def render(self, context: ExecutionContext, state: ReasoningState) -> str:
        log.info(f"[PromptRenderer] Rendering prompt for Task {context.task_id}")
        
        # Combine static context with mutable state
        prompt = f"""
        TASK: {context.directive}
        CURRENT HYPOTHESIS: {state.current_hypothesis}
        STRATEGY: {state.current_strategy}
        ATTEMPT: {state.attempt_number}
        
        Analyze the context and provide your next decision in strictly formatted JSON.
        """
        return prompt
