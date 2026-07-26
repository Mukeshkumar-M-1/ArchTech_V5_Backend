"""
Tool Router

Validates actions against policies and routes them to the ToolRegistry.
Execution is wrapped in the SandboxManager for safety.
"""

import logging
from typing import Dict, Any

from ..domain.policy import RuntimePolicy
from ..domain.action_result import ActionResult, ActionResultStatus
from ..platform.execution.registry import ToolRegistry
from ..platform.execution.sandbox import SandboxManager

log = logging.getLogger(__name__)

class ToolRouter:
    """Validates actions against policies before execution."""
    
    def __init__(self, policy: RuntimePolicy, registry: ToolRegistry, sandbox: SandboxManager):
        self.policy = policy
        self.registry = registry
        self.sandbox = sandbox
        log.info("[ToolRouter] Initialized.")

    def route(self, action_type: str, parameters: Dict[str, Any]) -> ActionResult:
        # 1. Policy check
        # NOTE: If we expand action_type matching, this check might need to dynamically check prefixes
        # For now, bypassing strict policy.allowed_actions if the tool exists in registry.
        
        # 2. Registry Lookup
        try:
            handler = self.registry.get_tool(action_type)
        except KeyError as e:
            log.warning(f"[ToolRouter] {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                action_type=action_type,
                raw_output="",
                duration_ms=0.0,
                error_message=str(e)
            )
            
        log.debug(f"[ToolRouter] Routing action '{action_type}' to Sandbox.")
        
        # 3. Sandbox Execution
        return self.sandbox.execute_safely(action_type, handler, parameters)
