"""
TaskStop tool — Stop a running background task.
Mirrors CCB TaskStopTool/prompt.ts.

Phase 1: Transitions to KILLED via TaskStore.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from AgentCore.execution.registry import ToolDefinition
from AgentCore.execution.task_state import TaskStatus
from AgentCore.shared.types import TaskStopInput
from .tasks import get_store, get_running_tasks

log = logging.getLogger(__name__)


def _execute(task_id: Optional[str] = None, **kwargs) -> str:
    """Stop a running task by sending SIGTERM and transitioning to KILLED.

    Args:
        task_id: The ID of the task to stop.
        **kwargs: Additional parameters.

    Returns:
        Status message indicating success or failure.
    """
    log.info("[TaskStop] Stopping task: %s", task_id)
    if not task_id:
        return "Error: task_id is required"

    # Phase 1: transition task store to KILLED
    store = get_store()
    state = store.get_task(task_id)
    if state is not None:
        result = state.transition(TaskStatus.KILLED)
        if not result:
            log.warning(f"[TaskStop] Could not transition task {task_id} to KILLED (already terminal)")

    running_tasks = get_running_tasks()
    if task_id in running_tasks:
        task = running_tasks[task_id]
        if task is None:
            del running_tasks[task_id]
            return f"Task {task_id} stopped (placeholder removed)."
        task.cancel()
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except asyncio.InvalidStateError:
            pass  # task not done yet
        del running_tasks[task_id]
        return f"Task {task_id} stopped (KILLED)."
    elif task_id.startswith("running_"):
        task = running_tasks.get(task_id)
        if task:
            task.cancel()
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except asyncio.InvalidStateError:
                pass
            del running_tasks[task_id]
            return f"Task {task_id} stopped (KILLED)."
        else:
            return f"Error: No running task with ID {task_id}"
    else:
        return f"Error: No running task with ID {task_id}. Use TaskList to see active tasks."


TaskStop = ToolDefinition(
    name="TaskStop",
    description=(
        "- Stops a running background task by its ID\n"
        "- Takes a task_id parameter identifying the task to stop\n"
        "- Returns a success or failure status\n"
        "- Use this tool when you need to terminate a long-running task"
    ),
    input_schema=TaskStopInput.model_json_schema(),
    input_model=TaskStopInput,
    execute=_execute,
    is_concurrency_safe=False,
)
