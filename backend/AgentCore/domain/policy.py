"""
Runtime Policy Domain Object

Defines global constraints and budgets for the agent's execution loop.
Consulted by the LoopController and tactical engines to prevent runaway loops or budget overruns.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class RuntimePolicy:
    """Immutable policy constraints for execution."""
    max_tokens: int = 50000
    max_turns: int = 50
    max_repairs_per_task: int = 3
    timeout_seconds: int = 3600
    
    # Extended Phase 4.4 Policies
    max_cost_usd: float = 5.00
    max_tool_duration_ms: float = 30000.0  # 30 seconds max per tool
    network_access_allowed: bool = False
    
    allowed_actions: frozenset[str] = frozenset([
        "READ", "SEARCH", "WRITE", "PATCH", "THINK", 
        "REFLECT", "WAIT", "SUMMARIZE", "VERIFY", "COMPLETE", "ASK_USER"
    ])

    @classmethod
    def create_default(cls) -> 'RuntimePolicy':
        log.info("[RuntimePolicy] Created default runtime policy.")
        return cls()
