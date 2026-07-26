"""
AgentStateStore - Manages the current execution state, retry counts, and token budgets.

Separates temporary working memory from the persistent runtime state of the agent.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

log = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Represents the current state of the agent."""
    current_state: str = "IDLE"  # e.g., EXPLORE, PLAN, EXECUTE, VERIFY, REFLECT
    active_skill: Optional[str] = None
    current_mission_id: Optional[str] = None
    current_task_id: Optional[str] = None

    # Budgets and Limits
    retry_count: int = 0
    loop_count: int = 0
    max_loops: int = 500
    tokens_used: int = 0

    # Generated Data
    version_data: Dict[str, List[Any]] = field(default_factory=dict)
    version_count: int = 0



class AgentStateStore:
    """Central store for managing and querying the AgentState."""

    def __init__(self):
        self.agent_state = AgentState()
        log.info("[AgentStateStore] Initialized with default state.")

    def get_state(self) -> AgentState:
        """Get a copy of the current state."""
        # Returning the reference for now, but could return a deepcopy if immutability is desired
        return self.agent_state

    def update_state(self, new_state_name: str) -> None:
        """Update the high-level state (e.g., PLAN -> EXECUTE)."""
        log.info(f"[AgentStateStore] Transitioning state: [{self.agent_state.current_state}] -> [{new_state_name}]")
        self.agent_state.current_state = new_state_name

    def set_active_skill(self, skill_name: str) -> None:
        """Set the currently active skill/prompt profile."""
        log.info(f"[AgentStateStore] Setting active skill to: {skill_name}")
        self.agent_state.active_skill = skill_name

    def set_active_task(self, task_id: str) -> None:
        """Set the currently active task ID."""
        self.agent_state.current_task_id = task_id
        self.agent_state.retry_count = 0  # Reset retries for new task
        self.agent_state.loop_count = 0   # Reset loop budget for new task

    def increment_loop(self) -> bool:
        """Increment the loop counter. Returns False if budget exceeded."""
        self.agent_state.loop_count += 1
        if self.agent_state.loop_count > self.agent_state.max_loops:
            log.warning(f"[AgentStateStore] Max loops exceeded ({self.agent_state.max_loops})!")
            return False
        return True
    
    def get_version_count(self) -> int:
        "Get a current version count data"
        return self.agent_state.version_count
    
    def set_version_count(self, agent_version_count) -> None:
        "Set version count data"
        self.agent_state.version_count = agent_version_count
        
    def update_version_count(self) -> None:
        "Update version count data"
        self.agent_state.version_count += 1

    def update_version_data(self, agent_version_data: Dict[str, Any]) -> None:
        "Update version data"
        self.agent_state.version_data = agent_version_data
     

