"""
Shared task storage — all task tools import this module to access the same state.
Also tracks running async subagent tasks for TaskOutput and TaskStop.

Phase 1: Replaced bare dict with TaskStore (lifecycle-managed).
Phase 3: Resolves from AgentContext (contextvars) if isolated.
"""

import asyncio
import logging

from AgentCore.execution.task_state import TaskStore, TaskStatus

log = logging.getLogger(__name__)

_task_store: TaskStore = TaskStore()
_next_id = 1
_running_tasks: dict[str, asyncio.Task] = {}  # agent_id → asyncio.Task
_task_counter = 0


def get_store() -> TaskStore:
    """Get the active task store, resolving from context if isolated.

    Phase 3: resolve from context if isolated, else module-level.

    Returns:
        The TaskStore for the current context or the module-level store.
    """
    from AgentCore.execution.context_isolation import get_context
    ctx = get_context()
    if ctx is not None and ctx.task_store is not None:
        log.info("[TaskStore] Resolving from context (isolated)")
        return ctx.task_store
    return _task_store


def get_next_id() -> str:
    """Get the next sequential task ID.

    Returns:
        A string task ID like "task_001", "task_002", etc.
    """
    global _next_id
    task_id = f"task_{_next_id:03d}"
    _next_id += 1
    log.info("[TaskStore] Generated task_id=%s", task_id)
    return task_id


def get_running_tasks() -> dict[str, asyncio.Task]:
    """Get the dictionary of running async tasks.

    Returns:
        Dict mapping task keys to asyncio.Task objects.
    """
    return _running_tasks


def register_task(agent_id: str, task: asyncio.Task) -> None:
    """Register a running async task so TaskOutput/TaskStop can find it."""
    """Register a running async task so TaskOutput/TaskStop can find it."""
    global _task_counter
    _task_counter += 1
    running_key = f"running_{_task_counter:03d}"
    _running_tasks[running_key] = task


def remove_task(running_key: str) -> None:
    _running_tasks.pop(running_key, None)


def get_terminal_task_count() -> int:
    """Return count of terminal tasks still in the store (not yet evicted).

    Returns:
        Number of terminal (completed/failed/killed) tasks.
    """
    count = 0
    for v in _task_store.values():
        if hasattr(v, "status") and v.status in (
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED
        ):
            count += 1
    return count
