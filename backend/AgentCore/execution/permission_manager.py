"""
Permission system — Tool authorization before execution.

Mirrors CCB's permissionMode:
- FULL_AUTO: No prompts, tools execute immediately
- REQUIRE_PROMPT: Each tool requires user confirmation
- SKIP: All tools denied (read-only mode)

Permissions are checked before each tool call via PreToolUse hooks.
Require prompt tools: Bash
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .tool_registry import ToolDefinition

log = logging.getLogger(__name__)


class PermissionMode(str, Enum):
    FULL_AUTO = "full_auto"       # No prompts, tools execute immediately
    REQUIRE_PROMPT = "require_prompt"  # Each tool requires user confirmation
    SKIP = "skip"                 # All tools denied (read-only mode)


class PermissionManager:
    """Tool permission manager with configurable rules."""

    # Tools that can execute without user confirmation
    AUTO_ALLOW = frozenset({
        "FileRead", "FileWrite", "FileEdit", "Glob", "Search",
        "Agent", "SendMessage", "Bash", "RequestUserInput", "ProposeContentEdit"
    })

    # Tools that require user confirmation
    REQUIRE_PROMPT = frozenset({
       
    })

    def __init__(self, mode: PermissionMode = PermissionMode.REQUIRE_PROMPT) -> None:
        """Initialize with a permission mode.

        Args:
            mode: The permission mode to enforce.
        """
        log.info("[PermissionManager] Initialized with mode=%s", mode.value)
        self._mode = mode

    @property
    def mode(self) -> PermissionMode:
        """Get the current permission mode.

        Returns:
            The current PermissionMode value.
        """
        return self._mode

    @mode.setter
    def mode(self, value: PermissionMode) -> None:
        """Set the permission mode.

        Args:
            value: The new PermissionMode value.
        """
        log.info("[PermissionManager] Mode changed: %s -> %s", self._mode.value, value.value)
        self._mode = value

    def can_use(self, tool_name: str) -> bool:
        """Check if a tool can be used in the current permission mode.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if the tool is allowed, False if denied.
        """
        log.info("[PermissionManager] can_use: tool=%s, mode=%s", tool_name, self._mode.value)
        if self._mode == PermissionMode.FULL_AUTO:
            return True
        elif self._mode == PermissionMode.SKIP:
            return False
        elif self._mode == PermissionMode.REQUIRE_PROMPT:
            # Auto-allowed tools pass; require-prompt tools need confirmation
            if tool_name in self.AUTO_ALLOW:
                return True
            if tool_name in self.REQUIRE_PROMPT:
                return False  # Requires user confirmation — return False to trigger prompt
            # Unknown tools: deny by default
            log.warning(f"[PermissionManager] Unknown tool '{tool_name}' — denying by default")
            return False
        return False

    def check(self, tool_name: str) -> bool:
        """Alias for can_use -- same behavior.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if the tool is allowed, False if denied.
        """
        return self.can_use(tool_name)

    def get_denied_tools(self) -> list[str]:
        """List all tools denied in the current mode.

        Returns:
            List of tool names that are denied in the current mode.
        """
        log.info("[PermissionManager] get_denied_tools: mode=%s", self._mode.value)

    def get_denied_tools(self) -> list[str]:
        """List all tools denied in the current mode.

        Returns:
            List of tool names that are denied in the current mode.
        """
        if self._mode == PermissionMode.FULL_AUTO:
            return []
        elif self._mode == PermissionMode.SKIP:
            return list(self.AUTO_ALLOW | self.REQUIRE_PROMPT)
        else:  # REQUIRE_PROMPT
            return list(self.REQUIRE_PROMPT)

    def get_required_prompt_for(self, tool_name: str) -> Optional[str]:
        """If tool requires confirmation, return the confirmation prompt text.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            Confirmation prompt string, or None if no confirmation needed.
        """
        log.info("[PermissionManager] get_required_prompt_for: tool=%s", tool_name)
        if self._mode != PermissionMode.REQUIRE_PROMPT:
            return None
        if tool_name in self.REQUIRE_PROMPT:
            return f"Allow running tool: {tool_name}?"
        return None
