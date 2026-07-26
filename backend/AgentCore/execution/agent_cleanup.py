"""
Agent Cleanup — Comprehensive resource cleanup on every agent exit path.

Mirrors CCB's runAgent.ts finally block (lines 844-889):
- Cancels running asyncio tasks
- Aborts controller hierarchy
- Closes transcript writers
- Clears message managers
- Logs token usage summaries
- Removes from hierarchy registry
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


class AgentCleaner:
    """Multi-step cleanup for agent lifecycle."""

    @staticmethod
    async def cleanup(agent_id: str, context=None) -> None:
        """Phase 4: comprehensive cleanup of agent resources.

        Args:
            agent_id: The agent's unique identifier.
            context: AgentContext if available, None otherwise.
        """
        log.info(f"[AgentCleanup] Cleaning up agent {agent_id}")

        # Step 1: Close transcript writer (Phase 5)
        if context and context.transcript_writer is not None:
            try:
                context.transcript_writer.close()
                log.info(f"[AgentCleanup] Closed transcript for {agent_id}")
            except Exception as e:
                log.warning(f"[AgentCleanup] Failed to close transcript for {agent_id}: {e}")

        # Step 2: Abort controller cleanup (Phase 2)
        if context and context.abort_controller is not None:
            try:
                from .abort_controller import get_hierarchy
                hierarchy = get_hierarchy()
                hierarchy.cleanup(agent_id)
                log.info(f"[AgentCleanup] Cleaned hierarchy for {agent_id}")
            except Exception as e:
                log.warning(f"[AgentCleanup] Hierarchy cleanup failed for {agent_id}: {e}")

        # Step 3: Clear message manager
        if context and context.message_manager is not None:
            try:
                context.message_manager.clear_context()
                log.info(f"[AgentCleanup] Cleared messages for {agent_id}")
            except Exception as e:
                log.warning(f"[AgentCleanup] Message clear failed for {agent_id}: {e}")

        # Step 4: Log token usage summary (Phase 9)
        if context and context.token_tracker is not None:
            try:
                snapshot = context.token_tracker.get_total()
                total = snapshot.get("total", 0)
                log.info(
                    f"[AgentCleanup] Token usage for {agent_id}: "
                    f"input={snapshot.get('input', 0)}, "
                    f"output={snapshot.get('output', 0)}, "
                    f"total={total}"
                )
            except Exception as e:
                log.warning(f"[AgentCleanup] Token logging failed for {agent_id}: {e}")

        # Step 5: Clean up background tasks for this agent only
        try:
            from .builtins.tasks import get_running_tasks
            running = get_running_tasks()
            agent_suffix = agent_id.split("-")[-1] if "-" in agent_id else ""
            tasks_to_remove = []
            for task_key, async_task in list(running.items()):
                if async_task is None:
                    tasks_to_remove.append(task_key)
                    continue
                if not async_task.done():
                    # Check if this task belongs to this agent
                    is_related = task_key == agent_id
                    if not is_related and agent_suffix:
                        is_related = task_key.endswith(agent_suffix)
                    if is_related:
                        async_task.cancel()
                        log.info(f"[AgentCleanup] Cancelled running task {task_key}")
                        tasks_to_remove.append(task_key)
                else:
                    # Clean up completed tasks for this agent
                    is_related = task_key == agent_id
                    if not is_related and agent_suffix:
                        is_related = task_key.endswith(agent_suffix)
                    if is_related:
                        tasks_to_remove.append(task_key)

            for key in tasks_to_remove:
                running.pop(key, None)
        except Exception as e:
            log.warning(f"[AgentCleanup] Task cleanup failed for {agent_id}: {e}")

        log.info(f"[AgentCleanup] Agent {agent_id} cleanup complete")

    @staticmethod
    async def cleanup_background_tasks(spawner) -> None:
        """Phase 4: Clean up all background tasks for an AgentSpawner.

        Iterates _background_tasks, awaits/cancels each, removes from set.
        Prevents accumulation of completed task references.
        """
        if not hasattr(spawner, "_background_tasks"):
            return

        tasks = list(spawner._background_tasks)
        for task in tasks:
            if task.done():
                spawner._background_tasks.discard(task)
                continue
            if task.cancelled():
                spawner._background_tasks.discard(task)
                continue
            try:
                task.cancel()
            except Exception:
                pass
            spawner._background_tasks.discard(task)

        log.info("[AgentCleanup] Background tasks cleaned up")
