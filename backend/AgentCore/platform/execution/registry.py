"""
Tool Registry

Dynamically loads and tracks registered capabilities (tools).
Allows the agent framework to be extended with new tools without modifying the core.
"""

import logging
from typing import Dict, Any, Callable

log = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        log.info("[ToolRegistry] Initialized.")

    def register_tool(self, name: str, handler: Callable) -> None:
        if name in self._tools:
            log.warning(f"[ToolRegistry] Overwriting existing tool: {name}")
        self._tools[name] = handler
        log.info(f"[ToolRegistry] Registered tool: {name}")

    def get_tool(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]
        
    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
