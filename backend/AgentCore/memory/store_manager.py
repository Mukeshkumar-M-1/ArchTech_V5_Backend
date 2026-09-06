"""
Store Manager

Central coordinator for the specialized memory stores. It provides a unified interface
for the ContextBuilder to pull the aggregated state. It does not own data directly.
"""

import logging
from typing import Optional

from .working_store import WorkingMemoryStore
from .mission_store import MissionMemoryStore
from .scratchpad_store import ScratchpadStore

log = logging.getLogger(__name__)

class StoreManager:
    """Coordinates the different memory domains."""
    
    def __init__(self):
        self.working_store = WorkingMemoryStore()
        self.scratchpad_store = ScratchpadStore()
        self.mission_store: Optional[MissionMemoryStore] = None
        log.info("[StoreManager] Initialized Memory subsystem.")

    def attach_mission(self, mission_id: str) -> None:
        """Initialize mission memory when a new mission starts."""
        self.mission_store = MissionMemoryStore(mission_id)
        
    def get_snapshot(self) -> dict:
        """Takes a snapshot of all active memory to pass to ContextBuilder."""
        snapshot = {
            "working_memory": self.working_store.to_dict(),
            "scratchpad_keys": self.scratchpad_store.get_all_keys()
        }
        
        if self.mission_store:
            snapshot["mission_memory"] = self.mission_store.to_dict()
            
        return snapshot
