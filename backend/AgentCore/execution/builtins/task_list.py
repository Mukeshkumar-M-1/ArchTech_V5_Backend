"""
TaskList tool — List all tasks.
Mirrors CCB TaskListTool/prompt.ts.

Phase 1: Reads from TaskStore (handles both TaskState and dict entries).
"""
from __future__ import annotations

import logging
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import TaskListInput

log = logging.getLogger(__name__)


def _execute(**kwargs) -> str:
    """Return summary of all tasks sorted by ID.

    Returns:
        Formatted task list string, or empty message if no tasks exist.
    """
    log.info("[TaskList] Listing all tasks")
    from .tasks import get_store

    store = get_store()
    if not store:
        return "No tasks in the list."

    def _sort_key(item):
        raw_id = item.get("id", "0")
        try:
            return int(str(raw_id).split("_")[1])
        except (IndexError, ValueError):
            return 999999

    tasks = sorted(store.values(), key=_sort_key)
    if not tasks:
        return "No tasks in the list."

    lines = []
    for task_entry in tasks:
        if isinstance(task_entry, dict):
            task_id = task_entry.get("id", "unknown")
            status = task_entry.get("status", "unknown")
            subject = task_entry.get("subject", task_id)
            owner = task_entry.get("owner", "")
            blocked_by = task_entry.get("blockedBy", [])
        else:
            task_id = getattr(task_entry, "id", "unknown")
            status = getattr(task_entry, "status", "unknown")
            subject = getattr(task_entry, "subject", task_id)
            owner = getattr(task_entry, "owner", "")
            blocked_by = []
        lines.append(f"Task {task_id}: [{status}] {subject} (owner: {owner}, blockedBy: {blocked_by})")
    return "Task List:\n" + "\n".join(lines)


TaskList = ToolDefinition(
    name="TaskList",
    description=(
        "List all tasks in the task list.\n\n"
        "When to Use:\n"
        "- To see what tasks are available to work on (pending, no owner, not blocked)\n"
        "- To check overall progress on the project\n"
        "- To find tasks that are ready to be picked up\n"
        "- To claim the next task\n"
        "- Prefer working on tasks in ID order (lowest ID first) when multiple are available\n\n"
        "## Output\n"
        "Returns a summary of each task:\n"
        "- **id**: Task identifier (use with TaskGet, TaskUpdate)\n"
        "- **subject**: Brief description of the task\n"
        "- **status**: 'pending', 'in_progress', or 'completed'\n"
        "- **owner**: Agent ID if assigned, empty if available\n"
        "- **blockedBy**: List of open task IDs that must be resolved first\n\n"
        "Use TaskGet with a specific task ID to view full details."
    ),
    input_schema=TaskListInput.model_json_schema(),
    input_model=TaskListInput,
    execute=_execute,
    is_concurrency_safe=True,  # read-only
)
