"""
Action Executor

The bridge between a dispatched ActionDefinition and the ToolRouter. It distinguishes between
system tool calls and purely cognitive actions.
"""

import logging
from ..domain.action_decision import ActionDefinition
from ..domain.action_result import ActionResult, ActionResultStatus
from .tool_router import ToolRouter

log = logging.getLogger(__name__)

class ActionExecutor:
    """Interprets and routes single Actions to tools or internal state handlers."""
    
    def __init__(self, tool_router: ToolRouter):
        self.tool_router = tool_router
        self.internal_actions = {"THINK", "REFLECT", "WAIT", "COMPLETE", "ASK_USER", "SEARCH", "REASON"}
        log.info("[ActionExecutor] Initialized.")

    def execute_action(self, action: ActionDefinition) -> ActionResult:
        log.info(f"[ActionExecutor] Processing Action: {action.action_type}")
        
        if action.action_type in self.internal_actions:
            log.info(f"[ActionExecutor] Action '{action.action_type}' handled internally.")
            return ActionResult(
                status=ActionResultStatus.SUCCESS,
                action_type=action.action_type,
                raw_output=f"Internal action '{action.action_type}' processed.",
                duration_ms=1.0
            )
        else:
            return self.tool_router.route(action.action_type, action.parameters)
