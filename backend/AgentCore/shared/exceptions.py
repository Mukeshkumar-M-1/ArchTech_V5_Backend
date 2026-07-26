"""Custom exception hierarchy for AgentCore.

Provides a structured exception hierarchy that replaces bare
Exception handling throughout the codebase. Every tool execution,
query loop operation, and document generation step uses these
exceptions for consistent error handling.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class AgentCoreError(Exception):
    """Base exception for all AgentCore errors."""

    def __init__(self, message: str = "AgentCore error occurred", **kwargs) -> None:
        """Initialize with a descriptive message and optional context.

        Args:
            message: Human-readable error description.
            **kwargs: Additional context to include in the error.
        """
        super().__init__(message)
        self.context = kwargs
        log.info("AgentCoreError created: %s, context=%s", message, kwargs)


class ToolExecutionError(AgentCoreError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, error: Exception, **kwargs) -> None:
        """Initialize with tool context.

        Args:
            tool_name: Name of the tool that failed.
            error: The underlying exception that caused the failure.
            **kwargs: Additional context (e.g., tool_call_id, args).
        """
        message = f"Tool execution failed for '{tool_name}': {error}"
        super().__init__(message, tool_name=tool_name, original_error=str(error), **kwargs)
        log.error("ToolExecutionError: tool=%s, error=%s", tool_name, error)


class ToolPermissionError(ToolExecutionError):
    """Raised when a tool is not authorized for use."""

    def __init__(self, tool_name: str, permission_mode: str = "", **kwargs) -> None:
        """Initialize with permission context.

        Args:
            tool_name: Name of the unauthorized tool.
            permission_mode: The permission mode that denied access.
            **kwargs: Additional context.
        """
        message = f"Tool '{tool_name}' denied in permission mode '{permission_mode}'"
        super().__init__(tool_name, RuntimeError(message), mode=permission_mode, **kwargs)
        log.warning("ToolPermissionError: tool=%s, mode=%s", tool_name, permission_mode)


class QueryLoopError(AgentCoreError):
    """Raised when the query loop encounters an error."""

    def __init__(self, message: str = "Query loop error", **kwargs) -> None:
        """Initialize with query loop context.

        Args:
            message: Descriptive error message.
            **kwargs: Additional context (e.g., turn_number, model_name).
        """
        super().__init__(message, **kwargs)
        log.info("QueryLoopError: %s", message)


class QueryTimeoutError(QueryLoopError):
    """Raised when the query loop exceeds its time limit."""

    def __init__(self, timeout_seconds: float, turn_number: int = 0, **kwargs) -> None:
        """Initialize with timeout context.

        Args:
            timeout_seconds: The timeout that was exceeded.
            turn_number: The turn number when the timeout occurred.
            **kwargs: Additional context.
        """
        message = f"Query loop timed out after {timeout_seconds}s at turn {turn_number}"
        super().__init__(message, timeout=timeout_seconds, turn=turn_number, **kwargs)
        log.error("QueryTimeoutError: timeout=%ss, turn=%d", timeout_seconds, turn_number)


class AbortRequestedError(QueryLoopError):
    """Raised when the query loop is aborted by the controller."""

    def __init__(self, reason: str = "", **kwargs) -> None:
        """Initialize with abort context.

        Args:
            reason: Reason for the abort.
            **kwargs: Additional context.
        """
        message = f"Query loop aborted: {reason}"
        super().__init__(message, reason=reason, **kwargs)
        log.info("AbortRequestedError: %s", reason)


class SectionGenerationError(AgentCoreError):
    """Raised when a document section generation fails."""

    def __init__(self, section_number: str, error: Exception = None, **kwargs) -> None:
        """Initialize with section context.

        Args:
            section_number: The section number that failed.
            error: The underlying exception if any.
            **kwargs: Additional context.
        """
        message = f"Section {section_number} generation failed: {error or 'unknown error'}"
        super().__init__(message, section=section_number, original_error=str(error) if error else None, **kwargs)
        log.error("SectionGenerationError: section=%s, error=%s", section_number, error)


class KnowledgeIndexError(AgentCoreError):
    """Raised when knowledge index building fails."""

    def __init__(self, project_id: str = "", missing_files: list = None, **kwargs) -> None:
        """Initialize with knowledge index context.

        Args:
            project_id: The project that failed.
            missing_files: List of files that were expected but missing.
            **kwargs: Additional context.
        """
        message = f"Knowledge index build failed for project '{project_id}'"
        if missing_files:
            message += f": missing {len(missing_files)} files"
        super().__init__(message, project_id=project_id, missing_files=missing_files or [], **kwargs)
        log.error("KnowledgeIndexError: project=%s, missing=%s", project_id, missing_files)
