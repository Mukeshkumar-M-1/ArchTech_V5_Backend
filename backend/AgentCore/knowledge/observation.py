"""
Observation Data Model

Observations are immutable records of tool executions and the evidence they produced.
They act as the foundational facts that the KnowledgeGraph is built upon.
"""

from dataclasses import dataclass
from datetime import datetime
import uuid

@dataclass(frozen=True)
class Observation:
    observation_id: str
    source_tool: str
    evidence: str
    confidence: float
    timestamp: float
    
    @classmethod
    def create(cls, source_tool: str, evidence: str, confidence: float = 1.0) -> 'Observation':
        return cls(
            observation_id=str(uuid.uuid4()),
            source_tool=source_tool,
            evidence=evidence,
            confidence=confidence,
            timestamp=datetime.now().timestamp()
        )
