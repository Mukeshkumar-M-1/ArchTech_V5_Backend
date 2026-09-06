"""
Observation Engine

Converts an ActionResult into a structured, immutable Observation.
Extracts the relevant evidence and calculates initial confidence based on 
the Action's success status and raw output.
"""

import logging
from typing import Optional

from ..domain.action_result import ActionResult, ActionResultStatus
from .observation_manager import ObservationManager
from .observation_bus import ObservationBus

log = logging.getLogger(__name__)

class ObservationEngine:
    """Parses raw execution results into semantic Observations."""
    
    def __init__(self, bus: ObservationBus):
        self.bus = bus
        log.info("[ObservationEngine] Initialized and connected to ObservationBus.")

    def process_result(self, result: ActionResult, expected_observation: str) -> ObservationManager:
        """
        In a real implementation, this might invoke a small LLM call to summarize
        large raw_outputs or check if they match the expected_observation.
        For Milestone 3, we build the deterministic frame.
        """
        confidence = 1.0 if result.status == ActionResultStatus.SUCCESS else 0.1
        
        evidence = result.raw_output
        if result.status == ActionResultStatus.FAILURE:
            evidence = f"Action failed: {result.error_message}"
            
        observation = ObservationManager.create(
            source_tool=result.action_type,
            evidence=evidence,
            confidence=confidence
        )
        
        log.info(f"[ObservationEngine] Generated Observation {observation.observation_id} (Status: {result.status.name})")
        
        # Publish directly to the bus, so Memory/Journal/Knowledge pick it up
        self.bus.publish(observation)
        
        return observation
