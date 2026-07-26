"""
TaskCreate tool — Create structured tasks.
Mirrors CCB TaskCreateTool/prompt.ts.

Phase 1: Uses TaskStore.create_task() for lifecycle management.
"""
from __future__ import annotations

import logging
from typing import Optional
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import TaskCreateInput
from AgentCore.execution.task_state import TaskStatus
from .tasks import get_store, get_next_id

log = logging.getLogger(__name__)


def _execute(subject: str, description: str, activeForm: Optional[str] = None, metadata: Optional[dict] = None, **kwargs) -> str:
    """Create a new structured task with lifecycle tracking.

    Args:
        subject: Brief, actionable title.
        description: Detailed task description.
        activeForm: Present-continuous form of the subject.
        metadata: Optional dict of additional task metadata.
        **kwargs: Additional parameters.

    Returns:
        Confirmation string with the task ID and subject.
    """
    log.info("[TaskCreate] Creating task: subject=%s, description_len=%d", subject, len(description))
    store = get_store()
    task_id = get_next_id()

    # Phase 1: create via TaskStore for lifecycle tracking
    store.create_task(task_id, description=description or subject)

    task = {
        "id": task_id,
        "subject": subject,
        "description": description,
        "activeForm": activeForm or subject,
        "status": TaskStatus.PENDING.value,
        "owner": "",
        "blocks": [],
        "blockedBy": [],
        "metadata": metadata or {},
    }

    # Update the same key with the dict — this overwrites the TaskState
    # We keep the TaskState for lifecycle, and merge dict fields for API compatibility
    # Read TaskState fields from the store entry for task_list/get
    store[task_id] = task

    return f"Created task: {task_id} — {subject}"


TaskCreate = ToolDefinition(
    name="TaskCreate",
    description=(
        "Use this tool to create a structured task list for your current coding session. This helps "
        "you track progress, organize complex tasks, and demonstrate thoroughness to the user.\n\n"
        "## When to Use:\n"
        "- Complex multi-step tasks - When a task requires 3 or more distinct steps or actions\n"
        "- Non-trivial and complex tasks - Tasks that require careful planning or multiple operations\n"
        "- User explicitly requests todo list - When the user directly asks you to use the todo list\n"
        "- User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)\n"
        "- After receiving new instructions - Immediately capture user requirements as tasks\n"
        "- When you start working on a task - Mark it as in_progress BEFORE beginning work\n"
        "- After completing a task - Mark it as completed and add new follow-up tasks discovered during implementation\n\n"
        "## When NOT to Use:\n"
        "- Single straightforward task\n"
        "- Trivial task with no organizational benefit\n"
        "- Task can be completed in less than 3 trivial steps\n"
        "- Purely conversational or informational\n\n"
        "## Task States and Management:\n"
        "1. **Task States**: Use these states to track progress:\n"
        "   - pending: Task not yet started\n"
        "   - in_progress: Currently working on (limit to ONE task at a time)\n"
        "   - completed: Task finished successfully\n"
        "\n"
        "   **IMPORTANT**: Task descriptions must have two forms:\n"
        "   - subject: A brief, actionable title in imperative form "
        "(e.g., \"Fix authentication bug in login flow\")\n"
        "   - activeForm: The present continuous form shown during execution "
        "(e.g., \"Fixing authentication bug\")\n\n"
        "2. **Task Management**:\n"
        "   - Update task status in real-time as you work\n"
        "   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)\n"
        "   - Exactly ONE task must be in_progress at any time (not less, not more)\n"
        "   - Complete current tasks before starting new ones\n"
        "   - Remove tasks that are no longer relevant from the list entirely\n\n"
        "3. **Task Completion Requirements**:\n"
        "   - ONLY mark a task as completed when you have FULLY accomplished it\n"
        "   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress\n"
        "   - When blocked, create a new task describing what needs to be resolved\n"
        "   - Never mark a task as completed if:\n"
        "     - Tests are failing\n"
        "     - Implementation is partial\n"
        "     - You encountered unresolved errors\n"
        "     - You couldn't find necessary files or dependencies\n\n"
        "4. **Task Breakdown**:\n"
        "   - Create specific, actionable items\n"
        "   - Break complex tasks into smaller, manageable steps\n"
        "   - Use clear, descriptive task names\n"
        "   - Always provide both forms:\n"
        "     - subject: \"Fix authentication bug\"\n"
        "     - activeForm: \"Fixing authentication bug\"\n\n"
        "When in doubt, use this tool. Being proactive with task management demonstrates attentiveness "
        "and ensures you complete all requirements successfully."
    ),
    input_schema=TaskCreateInput.model_json_schema(),
    input_model=TaskCreateInput,
    execute=_execute,
    is_concurrency_safe=False,
)
