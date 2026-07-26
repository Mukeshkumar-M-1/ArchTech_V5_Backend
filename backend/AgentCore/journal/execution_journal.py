"""
Execution Journal

The universal 'Git log for reasoning'. 
Records every Decision, Observation, Reflection, and Repair in an append-only history.
Provides complete debuggability.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

log = logging.getLogger(__name__)

class ExecutionJournal:
    """Append-only record of the entire reasoning and execution timeline."""
    
    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self._entries: List[Dict[str, Any]] = []
        log.info(f"[ExecutionJournal] Initialized for mission {mission_id}")

    def record_decision(self, decision: Any) -> None:
        self._append("DECISION", decision.__dict__)
        
    def record_observation(self, observation: Any) -> None:
        # Expected to be subscribed to the ObservationBus
        self._append("OBSERVATION", observation.__dict__)
        
    def record_reflection(self, reflection: Any) -> None:
        self._append("REFLECTION", reflection.__dict__)
        
    def record_repair(self, repair_plan: Any) -> None:
        self._append("REPAIR", repair_plan.__dict__)

    def _append(self, entry_type: str, payload: dict) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "payload": payload
        }
        self._entries.append(entry)
        log.info(f"[ExecutionJournal] Recorded {entry_type}")

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the immutable history log."""
        return self._entries.copy()
