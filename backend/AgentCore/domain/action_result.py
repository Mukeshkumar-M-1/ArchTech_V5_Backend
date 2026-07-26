"""
Action Result Domain Object

Represents the raw execution output from the ActionExecutor or ToolRouter.
Provides a standard boundary before outputs are parsed into Observations.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List

log = logging.getLogger(__name__)

class ActionResultStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"

@dataclass
class ActionResult:
    """Standardized output wrapper for any executed action."""
    status: ActionResultStatus
    action_type: str
    raw_output: str
    duration_ms: float
    artifacts_created: List[str] = field(default_factory=list)
    error_message: str = ""
    
    def __post_init__(self):
        if self.status == ActionResultStatus.SUCCESS:
            log.info(f"[ActionResult] Action {self.action_type} succeeded in {self.duration_ms:.2f}ms.")
        else:
            log.warning(f"[ActionResult] Action {self.action_type} ended with status {self.status.name}. Error: {self.error_message}")
