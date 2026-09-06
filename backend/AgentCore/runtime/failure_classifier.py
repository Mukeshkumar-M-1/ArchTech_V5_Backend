"""
Failure Classifier

Separates failure analysis from recovery execution. Classifies raw errors 
or failures into explicit Recovery Strategies for the LoopController.
"""

import logging
from enum import Enum, auto

log = logging.getLogger(__name__)

class RecoveryStrategy(Enum):
    RETRY = auto()
    ESCALATE = auto()
    REBUILD_CONTEXT = auto()
    REPAIR_PARSER = auto()
    ABORT = auto()
    IGNORE = auto()

class FailureClassifier:
    def __init__(self):
        log.info("[FailureClassifier] Initialized.")

    def classify_error(self, error_type: str, error_msg: str) -> RecoveryStrategy:
        """
        Takes an error signature and maps it to a strategy.
        In a full implementation, this could use heuristics or small LLM calls.
        """
        error_msg = error_msg.lower()
        log.info(f"[FailureClassifier] Classifying error: {error_type} - {error_msg}")
        
        if "timeout" in error_msg:
            return RecoveryStrategy.RETRY
            
        if "policy violation" in error_msg or "security" in error_msg:
            return RecoveryStrategy.ESCALATE
            
        if "context overflow" in error_msg or "token limit" in error_msg or "context limit" in error_msg:
            return RecoveryStrategy.REBUILD_CONTEXT
            
        if "json" in error_msg or "parse" in error_msg:
            return RecoveryStrategy.REPAIR_PARSER
            
        return RecoveryStrategy.ABORT
