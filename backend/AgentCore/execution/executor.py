"""
ToolExecutor — Execute tools with validation, error handling, and structured feedback.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_ERROR_TRUNCATE = 10_000

@dataclass
class ToolExecutionResult:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool
    execution_time_ms: float
    context_updates: dict = field(default_factory=dict)


class ToolExecutor:
    """Execute tool calls with validation, error handling, permission checks, and hooks."""
    
    def __init__(self, permission_checker=None, model_map: dict[str, Any] | None = None):
        """Initialize the tool executor with optional permission checking and model map.

        Args:
            permission_checker: Optional PermissionChecker instance.
            model_map: Optional mapping of tool names to Pydantic models.
        """
        self._permission_checker = permission_checker
        self._model_map = model_map or self._default_model_map()
        log.info("[ToolExecutor] ToolExecutor initialized")

    # EXECUTE TOOL CALLS
    async def execute(
        self, tool: Any, tool_call_id: str, args: dict
    ) -> ToolExecutionResult:
        """Execute a single tool call with validation, permission checking, and error handling.

        Args:
            tool: The ToolDefinition or tool object to execute.
            tool_call_id: Unique identifier for this tool call.
            args: Dictionary of arguments to pass to the tool.

        Returns:
            ToolExecutionResult with the output and metadata.
        """
        start_time = time.monotonic()
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        log.info("[ToolExecutor] Execute tool_Name='%s', tool_id='%s'", tool_name, tool_call_id)

        # VALIDATE TOOL INPUT SCHEMA
        try:
            model_class = self._get_pydantic_model(tool.name)
            validated = model_class.model_validate(args)
            exec_args = validated.model_dump()
            log.info(f"[ToolExecutor] validate='{tool_name}' succeeded, {len(exec_args)} validated args")
        except Exception as validation_error:
            execution_time = (time.monotonic() - start_time) * 1000
            log.warning(f"[ToolExecutor] validate='{tool_name}' FAILED ({type(validation_error).__name__}): {str(validation_error)[:200]}")
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name=tool.name,
                content=self.format_zod_error(tool.name, validation_error),
                is_error=True,
                execution_time_ms=execution_time,
            )

        # VALIDATE TOOL PERMISSION
        if self._permission_checker and not self._permission_checker.can_use(tool.name):
            denied_msg = self._permission_checker.get_required_prompt_for(tool.name)
            execution_time = (time.monotonic() - start_time) * 1000
            log.warning(f"[ToolExecutor] permission DENIED for tool='{tool_name}' ({execution_time:.0f}ms)")
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name=tool.name,
                content=denied_msg or f"Permission denied for tool: {tool.name}",
                is_error=True,
                execution_time_ms=execution_time,
            )

        # EXECUTE TOOL CALLS
        try:
            log.info(f"[ToolExecutor] executing tool='{tool_name}' with {len(exec_args)} validated args")
            tool_result = tool.execute(**exec_args)
            if asyncio.iscoroutine(tool_result):
                tool_result = await tool_result

            execution_time = (time.monotonic() - start_time) * 1000
            content_len = len(str(tool_result)) if tool_result else 0
            log.info("[ToolExecutor] tool_name=[%s] tool_id=[%s] completed= %dms, output=%d chars", tool_name, tool_call_id, execution_time, content_len)
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name=tool.name,
                content=str(tool_result),
                is_error=False,
                execution_time_ms=execution_time,
            )
        except Exception as error:
            execution_time = (time.monotonic() - start_time) * 1000
            error_type = type(error).__name__
            error_msg = str(error)[:300]
            log.error(f"[ToolExecutor] tool='{tool_name}' CRASHED ({error_type}): {error_msg} ({execution_time:.0f}ms)")
            return ToolExecutionResult(
                tool_call_id=tool_call_id,
                tool_name=tool.name,
                content=self.format_error(tool.name, error),
                is_error=True,
                execution_time_ms=execution_time,
            )

    # BUILD INPUT SCHEMA FOR ALL MODELS
    @staticmethod
    def _default_model_map() -> dict[str, Any]:
        """Build model map dynamically from the registered tools.

        Returns:
            Mapping of tool names to their Pydantic input models.
        """
        from .registry import registry
        model_map = {}
        for tool in registry.get_all():
            if tool.input_model is not None:
                model_map[tool.name] = tool.input_model
        return model_map

    # GET PYDANTIC MODEL FOR A TOOL
    def _get_pydantic_model(self, tool_name: str) -> Any:
        """Get the Pydantic model class for a tool by name.

        Args:
            tool_name: Name of the tool to look up.

        Returns:
            The Pydantic model class for validation.

        Raises:
            ValueError: If no model is registered for the tool.
        """
        model_class = self._model_map.get(tool_name)
        if not model_class:
            # Fallback to default map for unknown tool names
            default_map = self._default_model_map()
            model_class = default_map.get(tool_name)
        if not model_class:
            raise ValueError(f"No model for tool: {tool_name}")
        return model_class

    # FORMAT TOOL ERROR FOR FEEDBACK
    @staticmethod
    def format_error(tool_name: str, error: Exception) -> str:
        """Format a tool error with truncation for LLM feedback.

        Args:
            tool_name: Name of the tool that failed.
            error: The exception that was raised.

        Returns:
            Formatted error string, truncated if excessively long.
        """
        error_type = type(error).__name__
        message = str(error)
        max_len = DEFAULT_ERROR_TRUNCATE
        if len(message) > max_len:
            half = max_len // 2
            message = f"Tool Name:{tool_name}\n\n Error:{message[:half]}\n\n... [{len(message) - max_len} characters truncated] ...\n\n{message[-half:]}"
        return f"{error_type}: {message}"

    # FORMAT INPUT VALIDATION ERROR
    @staticmethod
    def format_zod_error(tool_name: str, error: Exception) -> str:
        """Format validation errors for LLM feedback.

        Args:
            tool_name: Name of the tool that failed validation.
            error: The validation exception.

        Returns:
            Human-readable validation error string.
        """
        errors = []
        if hasattr(error, "errors"):
            for error_data in error.errors():
                location = ".".join(str(error_data_item) for error_data_item in error_data.get("loc", []))
                message = error_data.get("msg", str(error_data))
                if location:
                    errors.append(f"  - The required parameter `{location}` {message}")
                else:
                    errors.append(f"  - {message}")
        else:
            errors.append(f"  - {str(error)}")
        return (
            f"{tool_name} validation failed due to the following issues:\n"
            + "\n".join(errors)
        )


# CONVENIENCE: EXECUTE A SINGLE TOOL
async def execute_tool(
    tool: Any, tool_call_id: str, args: dict
) -> ToolExecutionResult:
    """Convenience function to execute a tool with a default executor.

    Args:
        tool: The tool to execute.
        tool_call_id: Unique identifier for this tool call.
        args: Arguments to pass to the tool.

    Returns:
        ToolExecutionResult with the output and metadata.
    """
    tool_executor = ToolExecutor()
    return await tool_executor.execute(tool, tool_call_id, args)
