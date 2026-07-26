"""
Repair Planner

Triggered when the Verifier fails or a tool critically faults.
It generates a structured RepairPlan without executing any tools itself.
"""

import logging
from dataclasses import dataclass
from typing import List

log = logging.getLogger(__name__)

@dataclass
class RepairPlan:
    reason: str
    missing: str
    retry_strategy: str
    confidence: float
    alternatives: List[str]

class RepairPlanner:
    """Generates structured recovery strategies upon failure."""
    
    def __init__(self):
        log.info("[RepairPlanner] Initialized.")

    def plan_repair(self, failure_reason: str, missing_evidence: str) -> RepairPlan:
        log.warning(f"[RepairPlanner] Generating RepairPlan for failure: '{failure_reason}'")
        
        # Simulate LLM generating a repair strategy
        plan = RepairPlan(
            reason=failure_reason,
            missing=missing_evidence,
            retry_strategy="Fallback to searching global symbol index.",
            confidence=0.8,
            alternatives=["Ask user for missing context."]
        )
        
        return plan
