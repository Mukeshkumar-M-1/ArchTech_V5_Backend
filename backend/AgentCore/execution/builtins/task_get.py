"""
TaskGet tool — Retrieve a task by ID.
Mirrors CCB TaskGetTool/prompt.ts.

Phase 1: Reads from TaskStore (handles both TaskState and dict entries).
"""
from __future__ import annotations

import logging
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import TaskGetInput

log = logging.getLogger(__name__)


def _execute(taskId: str, **kwargs) -> str:
    """Return full details of a single task by its ID.

    Args:
        taskId: The task identifier to look up.
        **kwargs: Additional parameters.

    Returns:
        Formatted task details, or error message if not found.
    """
    log.info("[TaskGet] Getting task: %s", taskId)
    from .tasks import get_store

    store = get_store()
    task = store.get(taskId)
    if not task:
        return f"Error: Task not found: {taskId}"

    # Handle both dict and TaskState objects
    if isinstance(task, dict):
        task_id = task.get("id", taskId)
        subject = task.get("subject", "")
        description = task.get("description", "")
        status = task.get("status", "unknown")
        blocks = task.get("blocks", [])
        blocked_by = task.get("blockedBy", [])
        owner = task.get("owner", "")
        active_form = task.get("activeForm", "")
        extra = ""
    else:
        task_id = getattr(task, "id", taskId)
        subject = getattr(task, "description", "")
        description = subject
        status = getattr(task, "status", "unknown")
        blocks = []
        blocked_by = []
        owner = getattr(task, "owner", "")
        active_form = ""
        extra = f"\nAge: {(time.time() - task.created_at):.0f}s | Retained: {task.retain_flag}"
        if hasattr(task, "ttl_seconds"):
            extra += f" | TTL: {task.ttl_seconds}s"

    return (
        f"Task: {task_id}\n"
        f"Subject: {subject}\n"
        f"Description: {description}\n"
        f"Status: {status}\n"
        f"Blocks: {blocks}\n"
        f"BlockedBy: {blocked_by}\n"
        f"Owner: {owner}\n"
        f"ActiveForm: {active_form}"
        f"{extra}"
    )


TaskGet = ToolDefinition(
    name="TaskGet",
    description=(
        "Use this tool to retrieve a task by its ID from the task list.\n\n"
        "## When to Use:\n"
        "- When you need the full description and context before starting work on a task\n"
        "- To understand task dependencies (what it blocks, what blocks it)\n"
        "- After being assigned a task, to get complete requirements\n\n"
        "## Output\n"
        "Returns full task details:\n"
        "- **subject**: Task title\n"
        "- **description**: Detailed requirements and context\n"
        "- **status**: 'pending', 'in_progress', or 'completed'\n"
        "- **blocks**: Tasks waiting on this one to complete\n"
        "- **blockedBy**: Tasks that must complete before this one can start\n\n"
        "## Tips\n"
        "- After fetching a task, verify its blockedBy list is empty before beginning work.\n"
        "- Use TaskList to see all tasks in summary form."
    ),
    input_schema=TaskGetInput.model_json_schema(),
    input_model=TaskGetInput,
    execute=_execute,
    is_concurrency_safe=True,  # read-only
)
