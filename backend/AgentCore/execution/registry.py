"""
ToolRegistry — Central registry of all available tools.

Mirrors CCB's tool system where every tool is a first-class object with:
- A name and description
- A Pydantic schema for validation
- An execute function
- A concurrency safety flag (for partitioning)

Tools are auto-discovered via @register decorator.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

log = logging.getLogger(__name__)



@dataclass
class ToolDefinition:
    """A single tool definition that can be called by the LLM."""

    name: str
    description: str
    input_schema: dict  # JSON Schema (from Pydantic model)
    execute: Callable
    input_model: Any = None  # Pydantic model class for validation
    is_concurrency_safe: bool = False
    prompt_fn: Callable | None = None  # Dynamic description builder
    metadata: dict = field(default_factory=dict)

    def get_description(self, context: dict | None = None) -> str:
        """Get the tool description, using dynamic prompt_fn if available.

        Args:
            context: Optional context dict for dynamic prompt generation.

        Returns:
            The tool description string.
        """
        if self.prompt_fn and context:
            return self.prompt_fn(context)
        return self.description

    @property
    def is_write_tool(self) -> bool:
        """True if this tool modifies files or executes commands.

        Returns:
            True if the tool is a write tool, False otherwise.
        """
        return not self.is_concurrency_safe


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        log.info("[registry] Initialized (empty)")

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition in the central registry.

        Args:
            tool: The ToolDefinition to register.
        """
        self._tools[tool.name] = tool
        # log.info(f"[registry] registered tool: '{tool.name}' (safe={tool.is_concurrency_safe})")

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name from the registry.

        Args:
            name: The tool name to look up.

        Returns:
            The ToolDefinition if found, None otherwise.
        """
        return self._tools.get(name)

    def get_all(self) -> list[ToolDefinition]:
        """Get all registered tools as a list.

        Returns:
            List of all ToolDefinition objects in the registry.
        """
        names = [tool_entry.name for tool_entry in self._tools.values()]
        log.info(f"[registry] get_all: {len(names)} tools: {names}")
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool name strings.
        """
        return list(self._tools.keys())

    def build_tool_definitions(self, context: dict | None = None) -> list[dict]:
        """Build tool definitions for the LLM API request.

        Each tool becomes a dict with name, description, and input_schema.

        Args:
            context: Optional context for dynamic prompt generation.

        Returns:
            List of tool definition dicts suitable for LLM API.
        """
        definitions = []
        for tool in self._tools.values():
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.get_description(context),
                        "parameters": tool.input_schema,
                    },
                }
            )
        log.info(f"[registry] build_tool_definitions: {len(definitions)} tools")
        return definitions

    def register_builtins(self, base_dir: Path) -> None:
        """Auto-register built-in tools from the builtins module.

        Scans the builtins module directory and registers any ToolDefinition
        objects found.

        Args:
            base_dir: Path to the base directory containing builtins.
        """
        from . import builtins as builtin_module
        count = 0
        for name in dir(builtin_module):
            obj = getattr(builtin_module, name)
            if isinstance(obj, ToolDefinition):
                self.register(obj)
                count += 1
        log.info(f"[registry] register_builtins: loaded {count} tools from {base_dir}/builtins")


# Global singleton registry
registry = ToolRegistry()


def register(tool_def: ToolDefinition) -> ToolDefinition:
    """Decorator to register a tool definition in the global registry.

    Args:
        tool_def: The ToolDefinition to register.

    Returns:
        The original tool definition, for decorator usage.
    """
    registry.register(tool_def)
    return tool_def


def get_tool_definition(context: dict | None = None) -> list[dict]:
    """Helper to build all tool definitions for an API request.

    Args:
        context: Optional context for dynamic prompt generation.

    Returns:
        List of tool definition dicts suitable for LLM API.
    """
    return registry.build_tool_definitions(context)
