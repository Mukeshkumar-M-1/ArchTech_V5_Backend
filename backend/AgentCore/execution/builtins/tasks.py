"""
Built-in task helpers — internal coordination for background agents.

This module is NOT a tool. It provides internal helpers (get_store, get_running_tasks)
used by agent_spawner, abort_controller, and agent_cleanup.
"""

from __future__ import annotations

_running_tasks: dict[str, object] = {}


def get_running_tasks() -> dict:
    """Get the global dict of running background tasks.

    Returns:
        Dict mapping agent_id to asyncio.Task.
    """
    return _running_tasks


def get_store() -> dict:
    """Alias for get_running_tasks — same global store.

    Returns:
        Dict mapping agent_id to asyncio.Task.
    """
    return _running_tasks
