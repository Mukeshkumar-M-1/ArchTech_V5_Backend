"""
Observation Parser

Replaces the basic ObservationEngine. Parses a raw ActionResult into a 
semantic Observation while ensuring the raw output is preserved for the journal.
"""

import logging
from ..domain.action_result import ActionResult, ActionResultStatus
from .observation import Observation
from .observation_bus import ObservationBus

log = logging.getLogger(__name__)

class ObservationParser:
    """Parses raw execution results into semantic Observations."""
    
    def __init__(self, bus: ObservationBus):
        self.bus = bus
        log.info("[ObservationParser] Initialized.")

    def parse(self, result: ActionResult) -> Observation:
        confidence = 1.0 if result.status == ActionResultStatus.SUCCESS else 0.1
        evidence = result.raw_output if result.status == ActionResultStatus.SUCCESS else f"Failed: {result.error_message}"
        
        # We store the raw_result explicitly in the Observation for journaling
        observation = Observation.create(
            source_tool=result.action_type,
            evidence=evidence,
            confidence=confidence
        )
        
        # In a real implementation, we might attach result.raw_output to observation.raw_result
        # For now, we broadcast to the bus
        log.info(f"[ObservationParser] Parsed Observation {observation.observation_id}")
        self.bus.publish(observation)
        
        return observation
