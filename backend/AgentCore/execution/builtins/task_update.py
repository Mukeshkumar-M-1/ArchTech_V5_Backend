"""
TaskUpdate tool — Update existing tasks.
Mirrors CCB TaskUpdateTool/prompt.ts.

Phase 1: Uses TaskStore.transition() for valid status transitions.
"""
from __future__ import annotations

import logging
from typing import Optional
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import TaskUpdateInput
from AgentCore.execution.task_state import TaskStatus, can_transition, _VALID_TRANSITIONS
from .tasks import get_store

log = logging.getLogger(__name__)


_STATUS_MAP = {
    "in_progress": TaskStatus.RUNNING,
    "completed": TaskStatus.COMPLETED,
    "failed": TaskStatus.FAILED,
    "deleted": TaskStatus.COMPLETED,  # deleted maps to completed
}


def _execute(
    taskId: str,
    subject: Optional[str] = None,
    description: Optional[str] = None,
    activeForm: Optional[str] = None,
    status: Optional[str] = None,
    addBlocks: Optional[list] = None,
    addBlockedBy: Optional[list] = None,
    owner: Optional[str] = None,
    metadata: Optional[dict] = None,
    **kwargs,
) -> str:
    """Update an existing task by ID, enforcing valid state transitions.

    Args:
        taskId: The task identifier to update.
        subject: Optional new task title.
        description: Optional new description.
        activeForm: Optional present-continuous title.
        status: Optional new status (pending, in_progress, completed, deleted).
        addBlocks: Optional list of task IDs this task now blocks.
        addBlockedBy: Optional list of task IDs that block this task.
        owner: Optional new owner (agent name).
        metadata: Optional metadata dict to merge.
        **kwargs: Additional parameters.

    Returns:
        Confirmation with updated field list, or error message.
    """
    log.info("[TaskUpdate] Updating task %s: subject=%s, status=%s", taskId, subject, status)
    store = get_store()

    task = store.get(taskId)
    if not task:
        return f"Error: Task not found: {taskId}"

    updated_fields = []

    # Phase 1: enforce valid status transitions via TaskState if available
    if status is not None:
        task_state = store.get_task(taskId)
        if task_state:
            target = _STATUS_MAP.get(status.lower(), TaskStatus.RUNNING)
            if not can_transition(task_state.status, target):
                allowed = [s.value for s in _VALID_TRANSITIONS.get(task_state.status, [])]
                return (
                    f"Error: Cannot transition task {taskId} to '{status}'. "
                    f"Current status: {task_state.status.value}. "
                    f"Allowed transitions: {allowed}"
                )
            task_state.transition(target)
        task["status"] = status
        updated_fields.append("status")

    if subject is not None:
        task["subject"] = subject
        updated_fields.append("subject")
    if description is not None:
        task["description"] = description
        updated_fields.append("description")
    if activeForm is not None:
        task["activeForm"] = activeForm
        updated_fields.append("activeForm")
    if owner is not None:
        task["owner"] = owner
        updated_fields.append("owner")
    if metadata is not None:
        if task["metadata"] is None:
            task["metadata"] = {}
        task["metadata"].update({k: v for k, v in metadata.items() if v is not None})
        updated_fields.append("metadata")
    if addBlocks is not None:
        task["blocks"].extend(addBlocks)
        updated_fields.append("addBlocks")
    if addBlockedBy is not None:
        task["blockedBy"].extend(addBlockedBy)
        updated_fields.append("addBlockedBy")

    return f"Updated task {taskId}: {', '.join(updated_fields)}"


TaskUpdate = ToolDefinition(
    name="TaskUpdate",
    description=(
        "Use this tool to update a task in the task list.\n\n"
        "## When to Use:\n"
        "**Mark tasks as resolved:**\n"
        "- When you have completed the work described in a task\n"
        "- When a task is no longer needed or has been superseded\n"
        "- Always mark your assigned tasks as resolved when you finish them\n"
        "- After resolving, call TaskList to find your next task\n"
        "- ONLY mark a task as completed when you have FULLY accomplished it\n"
        "- If you encounter errors, blockers, or cannot finish, keep the task as in_progress\n"
        "- When blocked, create a new task describing what needs to be resolved\n"
        "- Never mark completed if: tests failing, implementation partial, "
        "unresolved errors, missing files\n\n"
        "**Delete tasks:**\n"
        "- When a task is no longer relevant or was created in error\n"
        "- Setting status to 'deleted' permanently removes the task\n\n"
        "**Update task details:**\n"
        "- When requirements change or become clearer\n"
        "- When establishing dependencies between tasks\n\n"
        "## Fields You Can Update\n"
        "- **status**: pending, in_progress, completed, deleted\n"
        "- **subject**: New title (imperative form)\n"
        "- **description**: New description\n"
        "- **activeForm**: Present continuous for spinner\n"
        "- **owner**: Change task owner (agent name)\n"
        "- **metadata**: Merge metadata keys (null deletes key)\n"
        "- **addBlocks**: Mark tasks that cannot start until this completes\n"
        "- **addBlockedBy**: Mark tasks that must complete before this can start\n\n"
        "## Status Workflow\n"
        "pending → in_progress → completed | deleted\n\n"
        "## Staleness\n"
        "Make sure to read a task's latest state using TaskGet before updating it.\n\n"
        "## Examples\n"
        "json: {\"taskId\": \"1\", \"status\": \"in_progress\"}\n"
        "json: {\"taskId\": \"1\", \"status\": \"completed\"}\n"
        "json: {\"taskId\": \"1\", \"status\": \"deleted\"}\n"
        "json: {\"taskId\": \"1\", \"owner\": \"my-name\"}\n"
        "json: {\"taskId\": \"2\", \"addBlockedBy\": [\"1\"]}"
    ),
    input_schema=TaskUpdateInput.model_json_schema(),
    input_model=TaskUpdateInput,
    execute=_execute,
    is_concurrency_safe=False,
)
