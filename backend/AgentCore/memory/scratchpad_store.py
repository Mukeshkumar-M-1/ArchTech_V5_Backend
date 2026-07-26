"""
Scratchpad Store

Provides a temporary, unstructured notepad where the agent can store JSON, text, 
or code blocks that it wants to reference later without updating formal knowledge graphs.
"""

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

class ScratchpadStore:
    """Manages temporary scratchpad notes for the agent."""
    
    def __init__(self):
        self._notes: Dict[str, str] = {}
        log.info("[ScratchpadStore] Initialized.")

    def write(self, key: str, content: str) -> None:
        """Write a note to the scratchpad."""
        self._notes[key] = content
        
    def read(self, key: str) -> Optional[str]:
        """Read a note from the scratchpad."""
        return self._notes.get(key)
        
    def delete(self, key: str) -> None:
        """Delete a note."""
        if key in self._notes:
            del self._notes[key]
            
    def get_all_keys(self) -> list[str]:
        """List all active notes in the scratchpad."""
        return list(self._notes.keys())
        
    def to_dict(self) -> dict:
        return self._notes.copy()
