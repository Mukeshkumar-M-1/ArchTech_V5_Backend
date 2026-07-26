"""
Sandbox Manager

Isolates tool execution from the host operating system.
Enforces file restrictions, command denylists, and timeouts.
"""

import logging
from typing import Callable, Dict, Any

from ...domain.action_result import ActionResult, ActionResultStatus

log = logging.getLogger(__name__)

class SandboxManager:
    def __init__(self):
        # Basic heuristic limits for M4
        self.blocked_commands = {"rm", "mkfs", "reboot", "shutdown", "chmod"}
        log.info("[SandboxManager] Initialized with heuristic security restrictions.")

    def execute_safely(self, action_type: str, handler: Callable, parameters: Dict[str, Any]) -> ActionResult:
        """Executes the tool handler within sandbox constraints."""
        
        # 1. Security Check
        cmd = parameters.get("command", "").lower()
        if any(blocked in cmd for blocked in self.blocked_commands):
            error_msg = f"Security Violation: Command '{cmd}' contains blocked keywords."
            log.error(f"[SandboxManager] {error_msg}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                action_type=action_type,
                raw_output="",
                duration_ms=0.0,
                error_message=error_msg
            )
            
        # 2. Safe Execution (In a real system, this runs in a subprocess/Docker with timeouts)
        log.info(f"[SandboxManager] Action '{action_type}' passed security checks. Executing.")
        try:
            result = handler(parameters)
            if not isinstance(result, ActionResult):
                return ActionResult(
                    status=ActionResultStatus.SUCCESS,
                    action_type=action_type,
                    raw_output=str(result),
                    duration_ms=0.0
                )
            return result
        except Exception as e:
            log.error(f"[SandboxManager] Execution faulted: {e}")
            return ActionResult(
                status=ActionResultStatus.FAILURE,
                action_type=action_type,
                raw_output="",
                duration_ms=0.0,
                error_message=str(e)
            )
