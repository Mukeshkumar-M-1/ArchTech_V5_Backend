"""
Policy Manager

Evaluates action requests against modular policies (e.g., Resource, Security)
and yields complex decisions (ALLOW, DENY, ESCALATE, REWRITE) rather than simple booleans.
"""

import logging
from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)

class PolicyDecision(Enum):
    ALLOW = auto()
    DENY = auto()
    ESCALATE = auto()
    WAIT = auto()
    REWRITE = auto()

@dataclass
class PolicyEvaluation:
    decision: PolicyDecision
    reason: str
    rewritten_action: Optional[str] = None
    rewritten_parameters: Optional[Dict[str, Any]] = None

class PolicyManager:
    def __init__(self):
        # Stub configuration for M4.5
        self.banned_terms = {"rm", "drop table", "shutdown"}
        log.info("[PolicyManager] Initialized with heuristic policies.")

    def evaluate(self, action_type: str, parameters: Dict[str, Any]) -> PolicyEvaluation:
        log.info(f"[PolicyManager] Evaluating action: {action_type}")
        
        # 1. Evaluate Security Policy
        cmd = parameters.get("command", "").lower()
        if any(term in cmd for term in self.banned_terms):
            if "rm" in cmd:
                # Example of REWRITE: Move to /tmp instead of deleting
                return PolicyEvaluation(
                    decision=PolicyDecision.REWRITE,
                    reason="Destructive 'rm' commands are banned. Rewriting to a safe move.",
                    rewritten_action="BASH",
                    rewritten_parameters={"command": cmd.replace("rm", "mv") + " /tmp/trash"}
                )
            return PolicyEvaluation(
                decision=PolicyDecision.DENY,
                reason=f"Action contains banned term."
            )
            
        # Default
        return PolicyEvaluation(
            decision=PolicyDecision.ALLOW,
            reason="All policies passed."
        )
