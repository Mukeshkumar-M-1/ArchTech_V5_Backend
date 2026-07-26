"""
SessionManager - Manages persistence, pause/resume, and crash recovery.

In Milestone 1, this provides basic save/load functionality for AgentState.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .agent_state import AgentStateStore, AgentState

log = logging.getLogger(__name__)

class SessionManager:
    """Manages the persistence lifecycle of an Agent session."""
    
    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"[SessionManager] Initialized with directory: {self.session_dir}")

    def save_session(self, session_id: str, agent_state_store: AgentStateStore) -> None:
        """Save the current agent state to disk."""
        session_file = (self.session_dir / f"{session_id}.json").resolve()
        self.session_dir.mkdir(parents=True, exist_ok=True)

        current_agent_store = agent_state_store.get_state()
        updated_agent_state_data = {
            "current_state": current_agent_store.current_state,
            "active_skill": current_agent_store.active_skill,
            "current_mission_id": current_agent_store.current_mission_id,
            "current_task_id": current_agent_store.current_task_id,
            "retry_count": current_agent_store.retry_count,
            "loop_count": current_agent_store.loop_count,
            "tokens_used": current_agent_store.tokens_used,
            "version_count":current_agent_store.version_count,
            "version_data":current_agent_store.version_data,
        }
        
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(updated_agent_state_data, f, indent=2)
            log.info(f"[SessionManager] Saved session [{session_id}] to [{session_file}]")
        except Exception as exception:
            log.error(f"[SessionManager] Failed to save session '{session_id}': {exception}", exc_info=True)

    def load_session(self, session_id: str) -> Optional[AgentStateStore]:
        """Load an agent state from disk."""
        session_file = (self.session_dir / f"{session_id}.json").resolve()
        
        if not session_file.is_file():
            log.info(f"[SessionManager] Session file not found: {session_file}")
            return None
            
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
                
            agent_state_store = AgentStateStore()
            current_agent_store = agent_state_store.get_state()
            current_agent_store.current_state = session_data.get("current_state", "IDLE")
            current_agent_store.active_skill = session_data.get("active_skill")
            current_agent_store.current_mission_id = session_data.get("current_mission_id")
            current_agent_store.current_task_id = session_data.get("current_task_id")
            current_agent_store.retry_count = session_data.get("retry_count", 0)
            current_agent_store.loop_count = session_data.get("loop_count", 0)
            current_agent_store.tokens_used = session_data.get("tokens_used", 0)
            current_agent_store.version_count= session_data.get("version_count", 0)
            current_agent_store.version_data = session_data.get("version_data", [])
            
            log.info(f"[SessionManager] Successfully loaded session '{session_id}'")
            return agent_state_store
        except Exception as exception:
            log.error(f"[SessionManager] Failed to load session '{session_id}': {exception}", exc_info=True)
            return None
