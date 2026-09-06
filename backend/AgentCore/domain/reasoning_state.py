"""
Reasoning State Domain Object

Tracks the evolving cognitive state of the agent across multiple turns.
Unlike ExecutionContext which contains static environment data, ReasoningState
is highly mutable and changes as hypotheses are confirmed or rejected.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

class ReasoningState:
    """Mutable tracker of the agent's current cognitive state."""
    
    def __init__(self, current_goal: str, initial_strategy: str = "Search First"):
        self.current_goal: str = current_goal
        self.current_strategy: str = initial_strategy
        self.current_hypothesis: Optional[str] = None
        self.confidence: float = 1.0
        self.attempt_number: int = 1
        self.observation_history: list = []
        
        log.info(f"[ReasoningState] Initialized. Goal: '{self.current_goal}', Strategy: '{self.current_strategy}'")

    def update_hypothesis(self, hypothesis: str, confidence: float) -> None:
        """Update the working theory and confidence based on recent observations."""
        self.current_hypothesis = hypothesis
        self.confidence = confidence
        log.info(f"[ReasoningState] Updated Hypothesis: '{hypothesis}' (Confidence: {confidence:.2f})")

    def change_strategy(self, new_strategy: str) -> None:
        """Called by the ReflectionEngine when the current approach fails."""
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        log.info(f"[ReasoningState] Strategy changed from '{old_strategy}' to '{new_strategy}'")

    def increment_attempt(self) -> None:
        self.attempt_number += 1
        log.info(f"[ReasoningState] Attempt number incremented to {self.attempt_number}")
