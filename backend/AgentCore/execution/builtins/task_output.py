"""
TaskOutput tool — Get output from a running/completed task.
Mirrors CCB TaskOutputTool/prompt.ts.
"""
from __future__ import annotations

import asyncio
import logging
import time
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import TaskOutputInput
from .tasks import get_store, get_running_tasks

log = logging.getLogger(__name__)


async def _execute(task_id: str, block: bool = True, timeout: int = 30000, **kwargs) -> str:
    """Retrieve output from a background task or agent.

    If the task is still running and block=True, waits up to timeout milliseconds.

    Args:
        task_id: The task identifier.
        block: Whether to wait for completion (default True).
        timeout: Maximum wait time in milliseconds when block=True.
        **kwargs: Additional parameters.

    Returns:
        Formatted task output string with status and content.
    """
    log.info("[TaskOutput] Getting output for task %s, block=%s, timeout=%d", task_id, block, timeout)
    store = get_store()
    running_tasks = get_running_tasks()

    # Check if it's a regular task (TaskCreate)
    task_data = store.get(task_id)
    if task_data and task_data.get("status") == "completed":
        return (
            f"Task: {task_id}\n"
            f"Status: completed\n"
            f"Output: {task_data.get('subject', '')}"
        )

    # Check for a running async task -- look for exact task_id match first
    async_task = running_tasks.get(task_id)
    if async_task:
        if async_task.done():
            status = "completed" if async_task.exception() is None else "failed"
            try:
                content = str(async_task.result())
            except Exception:
                content = "(task completed with error)"
            running_tasks.pop(task_id, None)
            return (
                f"Task: {task_id}\n"
                f"Type: async agent\n"
                f"Status: {status}\n"
                f"Output: {content}"
            )
        elif not block:
            return (
                f"Task: {task_id}\n"
                f"Type: async agent\n"
                f"Status: running\n"
                f"Output: (waiting for completion, block=false)"
            )
        elif block:
            try:
                await asyncio.wait_for(async_task, timeout=timeout / 1000)
                try:
                    content = str(async_task.result())
                except Exception:
                    content = "(task completed with error)"
                return (
                    f"Task: {task_id}\n"
                    f"Type: async agent\n"
                    f"Status: completed\n"
                    f"Output: {content}"
                )
            except asyncio.TimeoutError:
                return (
                    f"Task: {task_id}\n"
                    f"Type: async agent\n"
                    f"Status: timed out after {timeout}ms\n"
                    f"Output: (timeout reached)"
                )

    return (
        f"Task: {task_id}\n"
        f"Status: not found\n"
        f"Output: No running or completed task with this ID. "
        f"Use TaskList to see available tasks."
    )


TaskOutput = ToolDefinition(
    name="TaskOutput",
    description=(
        "DEPRECATED: Background tasks return their output file path in the tool result, "
        "and you receive a notification with the same path when the task completes.\n"
        "- For bash tasks: prefer using the Read tool on that output file path -- it contains stdout/stderr.\n"
        "- For local_agent tasks: use the Agent tool result directly. Do NOT Read the .output file.\n"
        "- For remote_agent tasks: prefer using the Read tool on the output file path -- it contains the streamed remote session output (same as bash).\n"
        "- Retrieves output from a running or completed task (background shell, agent, or remote session)\n"
        "- Takes a task_id parameter identifying the task\n"
        "- Returns the task output along with status information\n"
        "- Use block=true (default) to wait for task completion\n"
        "- Use block=false for non-blocking check of current status\n"
        "- Task IDs can be found using the /tasks command\n"
        "- Works with all task types: background shells, async agents, and remote sessions"
    ),
    input_schema=TaskOutputInput.model_json_schema(),
    input_model=TaskOutputInput,
    execute=_execute,
    is_concurrency_safe=True,
)
