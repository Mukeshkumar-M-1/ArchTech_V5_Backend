"""
TodoWrite tool — Structured task list management.
Mirrors CCB TodoWriteTool/prompt.ts (V1 — in-memory, flat list).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from AgentCore.shared.types import TodoWriteInput
from AgentCore.execution.registry import ToolDefinition

log = logging.getLogger(__name__)

# Session-scoped state (mirrors CCB's AppState.todos)
_todo_state: dict[str, list[dict]] = {}
_todo_lock: asyncio.Lock = asyncio.Lock()


def _execute(todos: list[dict], **kwargs) -> str:
    """Validate and store a structured task list for the current session.

    Args:
        todos: List of todo dicts with content, status, and activeForm.
        **kwargs: Additional parameters including session_id.

    Returns:
        Summary string of the updated todo list.
    """
    log.info("[TodoWrite] Processing %d todos", len(todos))
    session_id = kwargs.get("session_id", "default")

    # Validate each todo using proper validation, not assert
    valid_statuses = {"pending", "in_progress", "completed"}
    for i, todo_item in enumerate(todos):
        if "content" not in todo_item:
            return f"Error: Todo at index {i} is missing 'content'"
        if "status" not in todo_item:
            return f"Error: Todo at index {i} is missing 'status'"
        if "activeForm" not in todo_item:
            return f"Error: Todo at index {i} is missing 'activeForm'"
        if todo_item["status"] not in valid_statuses:
            return f"Error: Todo at index {i} has invalid status '{todo_item['status']}'. Valid: {sorted(valid_statuses)}"

    # Enforce single in_progress
    in_progress = [todo_item for todo_item in todos if todo_item["status"] == "in_progress"]
    if len(in_progress) > 1:
        return f"Error: Exactly one task must be in_progress. Found {len(in_progress)}."

    # Update state under lock
    async def _update_state():
        async with _todo_lock:
            _todo_state[session_id] = todos

    try:
        _loop = asyncio.get_running_loop()
        _loop.create_task(_update_state())
    except RuntimeError:
        import asyncio as _asyncio
        _asyncio.new_event_loop().run_until_complete(_update_state())

    # Build response
    lines = []
    for i, todo_item in enumerate(todos, 1):
        icon = {"pending": "⬜", "in_progress": "🔵", "completed": "✅"}[todo_item["status"]]
        lines.append(f"{icon} [{todo_item['status']}] {todo_item['content']}")
    return "Updated todo list:\n" + "\n".join(lines)


TodoWrite = ToolDefinition(
    name="TodoWrite",
    description=(
        "Use this tool to create and manage a structured task list for your current coding session. "
        "This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.\n"
        "It also helps the user understand the progress of the task and overall progress of their requests.\n\n"
        "## When to Use This Tool\n"
        "Use this tool proactively in these scenarios:\n\n"
        "1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions\n"
        "2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations\n"
        "3. User explicitly requests todo list - When the user directly asks you to use the todo list\n"
        "4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)\n"
        "5. After receiving new instructions - Immediately capture user requirements as todos\n"
        "6. When you start working on a task - Mark it as in_progress BEFORE beginning work. "
        "Ideally you should only have one todo as in_progress at a time\n"
        "7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation\n\n"
        "## When NOT to Use This Tool\n\n"
        "Skip using this tool when:\n"
        "1. There is only a single, straightforward task\n"
        "2. The task is trivial and tracking it provides no organizational benefit\n"
        "3. The task can be completed in less than 3 trivial steps\n"
        "4. The task is purely conversational or informational\n\n"
        "NOTE that you should not use this tool if there is only one trivial task to do. "
        "In this case you are better off just doing the task directly.\n\n"
        "## Examples of When to Use the Todo List\n\n"
        "<example>\n"
        "User: I want to add a dark mode toggle to the application settings. "
        "Make sure you run the tests and build when you're done!\n"
        "Assistant: *Creates todo list with the following items:*\n"
        "1. Creating dark mode toggle component in Settings page\n"
        "2. Adding dark mode state management (context/store)\n"
        "3. Implementing CSS-in-JS styles for dark theme\n"
        "4. Updating existing components to support theme switching\n"
        "5. Running tests and build process, addressing any failures or errors that occur\n"
        "*Begins working on the first task*\n\n"
        "<reasoning>\n"
        "The assistant used the todo list because:\n"
        "1. Adding dark mode is a multi-step feature requiring UI, state management, and styling changes\n"
        "2. The user explicitly requested tests and build be run afterward\n"
        "3. The assistant inferred that tests and build need to pass by adding "
        "\"Ensure tests and build succeed\" as the final task\n"
        "</reasoning>\n"
        "</example>\n\n"
        "<example>\n"
        "User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project\n"
        "Assistant: *Uses grep or search tools to locate all instances of getCwd in the codebase*\n"
        "I've found 15 instances of 'getCwd' across 8 different files.\n"
        "*Creates todo list with specific items for each file that needs updating*\n\n"
        "<reasoning>\n"
        "The assistant used the todo list because:\n"
        "1. First, the assistant searched to understand the scope of the task\n"
        "2. Upon finding multiple occurrences across different files, it determined this was a complex task with multiple steps\n"
        "3. The todo list helps ensure every instance is updated systematically\n"
        "4. This approach prevents missing any occurrences and maintains code consistency\n"
        "</reasoning>\n"
        "</example>\n\n"
        "## Task States and Management\n\n"
        "1. **Task States**: Use these states to track progress:\n"
        "   - pending: Task not yet started\n"
        "   - in_progress: Currently working on (limit to ONE task at a time)\n"
        "   - completed: Task finished successfully\n\n"
        "   **IMPORTANT**: Task descriptions must have two forms:\n"
        "   - content: The imperative form describing what needs to be done "
        "(e.g., \"Run tests\", \"Build the project\")\n"
        "   - activeForm: The present continuous form shown during execution "
        "(e.g., \"Running tests\", \"Building the project\")\n\n"
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
        "     - content: \"Fix authentication bug\"\n"
        "     - activeForm: \"Fixing authentication bug\"\n\n"
        "When in doubt, use this tool. Being proactive with task management demonstrates attentiveness "
        "and ensures you complete all requirements successfully."
    ),
    input_schema=TodoWriteInput.model_json_schema(),
    input_model=TodoWriteInput,
    execute=_execute,
    is_concurrency_safe=True,
)
