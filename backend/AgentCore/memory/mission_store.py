"""
Mission Memory Store

Persistent memory tracking long-term discoveries, key architectural decisions, 
and context spanning multiple tasks within a single mission.
"""

import logging
from typing import List, Dict, Set

log = logging.getLogger(__name__)

class MissionMemoryStore:
    """Manages persistent context spanning the entire mission lifecycle."""
    
    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.key_discoveries: List[str] = []
        self.architectural_rules: List[str] = []
        self.completed_tasks: Set[str] = set()
        log.info(f"[MissionMemoryStore] Initialized for mission {mission_id}")

    def add_discovery(self, discovery: str) -> None:
        self.key_discoveries.append(discovery)
        
    def add_architectural_rule(self, rule: str) -> None:
        self.architectural_rules.append(rule)
        
    def record_completed_task(self, task_id: str) -> None:
        self.completed_tasks.add(task_id)

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "key_discoveries": self.key_discoveries,
            "architectural_rules": self.architectural_rules,
            "completed_tasks": list(self.completed_tasks)
        }
