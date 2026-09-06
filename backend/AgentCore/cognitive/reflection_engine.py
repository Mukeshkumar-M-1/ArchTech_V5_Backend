"""
Reflection Engine

Evaluates the recent Observations and the ReasoningState to determine the
next overarching branch of the execution loop (e.g., Continue, Verify, Replan).
"""

import logging
from enum import Enum
from dataclasses import dataclass

from ..domain.reasoning_state import ReasoningState
from ..knowledge.observation_manager import ObservationManager

log = logging.getLogger(__name__)

class ReflectionDecision(Enum):
    CONTINUE = "CONTINUE"
    VERIFY = "VERIFY"
    REPLAN = "REPLAN"
    ASK_USER = "ASK_USER"
    COMPLETE = "COMPLETE"

class ReflectionEngine:
    """Event-driven evaluator determining the loop's branching strategy."""
    
    def __init__(self):
        log.info("[ReflectionEngine] Initialized.")

    def reflect(self, observation: ObservationManager, state: ReasoningState) -> ReflectionDecision:
        """
        In a real implementation, evaluates 'Expected Observation' vs 'Actual Observation'.
        Also applies ReflectionPolicy (e.g., 'If low confidence 3 times, AskUser').
        """
        log.info(f"[ReflectionEngine] Reflecting on Observation {observation.observation_id}")
        
        # Simulated reflection logic:
        # If confidence is extremely low, ask user
        if observation.confidence < 0.2:
            log.warning("[ReflectionEngine] Confidence critically low. Triggering ASK_USER.")
            return ReflectionDecision.ASK_USER
            
        # If the observation evidence indicates completion
        if "COMPLETE" in observation.source_tool or "complete" in observation.evidence.lower():
            log.info("[ReflectionEngine] Task marked complete. Triggering VERIFY.")
            return ReflectionDecision.VERIFY
            
        # Default: Continue loop
        log.info("[ReflectionEngine] Progress looks good. Triggering CONTINUE.")
        return ReflectionDecision.CONTINUE
