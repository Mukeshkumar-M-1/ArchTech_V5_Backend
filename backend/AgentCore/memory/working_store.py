"""
Working Memory Store

Ephemeral memory that tracks the current state of reasoning within a single task or thinking cycle.
It tracks open questions, assumptions, collected evidence, and blockers.
It resets or flushes when a task is completed.
"""

import logging
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

class WorkingMemoryStore:
    """Manages short-term context for the current reasoning cycle."""
    
    def __init__(self):
        self.open_questions: List[str] = []
        self.assumptions: List[str] = []
        self.evidence: List[Dict[str, str]] = []  # List of observation summaries
        self.blockers: List[str] = []
        log.info("[WorkingMemoryStore] Initialized ephemeral memory.")

    def add_question(self, question: str) -> None:
        if question not in self.open_questions:
            self.open_questions.append(question)
            
    def resolve_question(self, question: str) -> None:
        if question in self.open_questions:
            self.open_questions.remove(question)
            
    def add_assumption(self, assumption: str) -> None:
        if assumption not in self.assumptions:
            self.assumptions.append(assumption)
            
    def record_evidence(self, source: str, fact: str) -> None:
        self.evidence.append({"source": source, "fact": fact})
        
    def add_blocker(self, blocker: str) -> None:
        if blocker not in self.blockers:
            self.blockers.append(blocker)
            
    def clear(self) -> None:
        """Flushes memory when the current task completes."""
        self.open_questions.clear()
        self.assumptions.clear()
        self.evidence.clear()
        self.blockers.clear()
        log.info("[WorkingMemoryStore] Ephemeral memory flushed.")

    def to_dict(self) -> dict:
        return {
            "open_questions": self.open_questions,
            "assumptions": self.assumptions,
            "evidence": self.evidence,
            "blockers": self.blockers
        }
