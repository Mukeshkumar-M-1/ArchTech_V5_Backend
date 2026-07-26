"""
Execution Plan Domain Object

Elevates execution sequences from flat action lists into a structured, 
versioned graph. Supports step dependencies and explicit rollback/compensation actions.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum, auto

from .decision import ActionDefinition

log = logging.getLogger(__name__)

class StepStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    ROLLED_BACK = auto()

@dataclass
class RetryPolicy:
    max_retries: int = 0
    delay_ms: float = 0.0

@dataclass
class ExecutionStep:
    step_id: str
    action: ActionDefinition
    dependencies: List[str] = field(default_factory=list)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    compensation_action: Optional[ActionDefinition] = None
    status: StepStatus = StepStatus.PENDING

@dataclass
class ExecutionPlan:
    plan_id: str
    generated_by: str
    version: str = "v1"
    estimated_cost: float = 0.0
    estimated_tokens: int = 0
    expected_evidence: str = ""
    rollback_plan_id: Optional[str] = None
    steps: List[ExecutionStep] = field(default_factory=list)

    @classmethod
    def create(cls, generated_by: str, steps: List[ExecutionStep]) -> 'ExecutionPlan':
        plan_id = str(uuid.uuid4())
        log.info(f"[ExecutionPlan] Created plan {plan_id} with {len(steps)} steps.")
        return cls(plan_id=plan_id, generated_by=generated_by, steps=steps)
