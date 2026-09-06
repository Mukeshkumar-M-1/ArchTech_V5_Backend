"""
AgentSpawner — Subagent delegation with independent context.

Mirrors CCB's Agent tool (AgentTool.tsx):
- Spawns independent subagents with their own tool pool, system prompt, messages
- Subagent runs its own query loop
- Parent sees only the final result
- Supports background (async) execution

Phase 2: Abort controller hierarchy for parent→child cancellation.
Phase 3: Context isolation via contextvars.
Phase 4: Comprehensive cleanup via AgentCleaner.
Phase 5: Disk-backed transcript output.
Phase 6: Inter-agent messaging via mailbox.
Phase 9: Structured token usage tracking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL_OPUS = "opus46"
DEFAULT_MAX_TURNS = 30
DEFAULT_MAX_CONCURRENT_LLM = 5


@dataclass
class AgentResult:
    """Result of a spawned subagent execution."""

    agent_id: str
    status: str  # "completed", "failed", "error"
    content: str  # Agent's final output
    total_tool_uses: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0

    # Phase 9: structured token fields
    input_tokens: int = 0
    output_tokens: int = 0

    def to_tool_result_block(self) -> dict:
        """Convert to a tool_result block for the parent agent."""
        content = self.content if self.content is not None else ""
        usage = (
            f"<usage>\n"
            f"total_tokens: {self.total_tokens}\n"
            f"tool_uses: {self.total_tool_uses}\n"
            f"duration_ms: {self.total_duration_ms}\n"
            f"</usage>"
        )
        content = content + "\n\n" + usage

        return {
            "type": "tool_result",
            "tool_call_id": self.agent_id,
            "content": content,
            **({"is_error": True} if self.status == "error" else {}),
        }


class AgentSpawner:
    """Spawn independent subagents for subtask delegation.

    Mirrors CCB's Agent tool:
    - Subagents get their own query loop
    - Subagents have their own tool pool and system prompt
    - Parent sees only the final result
    - Supports async/background execution
    """

    def __init__(self, query_loop=None, max_concurrent: int = DEFAULT_MAX_CONCURRENT_LLM) -> None:
        """Initialize the AgentSpawner with concurrency controls.

        Args:
            query_loop: QueryLoop instance for subagents to use.
            max_concurrent: Maximum concurrent subagents.
        """
        log.info("[AgentSpawner] Initialized with max_concurrent=%d", max_concurrent)
        self.query_loop = query_loop
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._agent_counter = 0
        self._agent_lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

    async def spawn(
        self,
        agent_type: str,
        prompt: str,
        description: str = "",
        run_in_background: bool = False,
        system_prompt: str | None = None,
        tools: list[Any] | None = None,
        model: str = DEFAULT_MODEL_OPUS,
        max_turns: int = DEFAULT_MAX_TURNS,
        abort_controller: Any = None,  # Phase 2: optional parent abort controller
        project_id: str = "",
        **kwargs,
    ) -> AgentResult:
        """
        Spawn a subagent to handle a subtask.

        Args:
            agent_type: Type of subagent (general-purpose, explore, plan).
            prompt: Detailed task description for the subagent.
            description: Short description (for logging/monitoring).
            run_in_background: If True, run asynchronously.
            system_prompt: Optional system prompt for the subagent.
            tools: Tools available to the subagent.
            model: Model for the subagent.
            max_turns: Maximum turns for the subagent.
            abort_controller: Phase 2 — parent AbortController for hierarchy.
            project_id: Phase 3 — project context for path resolution.

        Returns:
            AgentResult with the subagent's output.
        """
        log.info("[AgentSpawner] spawn: type=%s, description=%s, background=%s", agent_type, description, run_in_background)
        async with self._agent_lock:
            self._agent_counter += 1
            agent_id = f"agent-{self._agent_counter}"

        if run_in_background:
            return await self._spawn_async(
                agent_id, agent_type, prompt, description,
                system_prompt, tools, model, max_turns,
                abort_controller=abort_controller,
                project_id=project_id,
            )
        else:
            return await self._spawn_sync(
                agent_id, agent_type, prompt, description,
                system_prompt, tools, model, max_turns,
                abort_controller=abort_controller,
                project_id=project_id,
            )

    async def _spawn_sync(
        self,
        agent_id: str,
        agent_type: str,
        prompt: str,
        description: str,
        system_prompt: str | None,
        tools: list[Any] | None,
        model: str,
        max_turns: int,
        abort_controller: Any = None,
        project_id: str = "",
    ) -> AgentResult:
        """Spawn a subagent synchronously (parent waits for completion).

        Args:
            agent_id: Unique identifier for the subagent.
            agent_type: Type of subagent.
            prompt: Task description for the subagent.
            description: Short description for logging.
            system_prompt: Optional system prompt override.
            tools: Tools available to the subagent.
            model: Model for the subagent.
            max_turns: Maximum turns for the subagent.
            abort_controller: Parent AbortController for hierarchy.
            project_id: Project context for path resolution.

        Returns:
            AgentResult with the subagent's final output.
        """
        log.info("[AgentSpawner] _spawn_sync: agent_id=%s, type=%s", agent_id, agent_type)
        from .abort_controller import AbortController
        from .query_loop import QueryLoop
        from .context_isolation import AgentContext, AgentContextManager
        from .message_manager import MessageManager
        from .token_usage_tracker import TokenTracker
        from .builtins.tasks import get_store, get_running_tasks
        from .transcript import get_transcript_dir, TranscriptWriter

        # Phase 2: create child abort controller
        agent_abort = AbortController(parent=abort_controller, agent_id=agent_id)

        # Phase 5: create transcript writer
        transcript_writer = None
        if project_id:
            t_dir = get_transcript_dir(project_id)
            transcript_writer = TranscriptWriter(str(t_dir))

        # Phase 3: create context isolation wrapper
        context = AgentContext(
            agent_id=agent_id,
            task_store=get_store(),  # Phase 3: per-agent isolated store
            message_manager=MessageManager(),
            abort_controller=agent_abort,
            transcript_writer=transcript_writer,
            token_tracker=TokenTracker(),
        )

        start_time = time.monotonic()

        try:
            async with AgentContextManager(context):
                # Build subagent query loop
                if self.query_loop:
                    loop = self.query_loop
                else:
                    loop = QueryLoop(
                        max_turns=max_turns,
                        fallback_chain=["opus46"],
                        abort_controller=agent_abort,
                        transcript_writer=transcript_writer,
                    )

                # Build subagent messages
                messages = [{"role": "user", "content": prompt}]

                try:
                    result_text = await loop.run(
                        initial_messages=messages,
                        system_prompt=system_prompt,
                        tools=tools,
                        model=model,
                    )

                    duration_ms = (time.monotonic() - start_time) * 1000

                    # Phase 9: collect token usage
                    tt = context.token_tracker
                    tokens = tt.get_total()

                    return AgentResult(
                        agent_id=agent_id,
                        status="completed",
                        content=result_text or "(agent returned no output)",
                        total_duration_ms=duration_ms,
                        total_tokens=tokens.get("total", 0),
                        input_tokens=tokens.get("input", 0),
                        output_tokens=tokens.get("output", 0),
                    )

                except Exception as error:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    log.error(f"[AgentSpawner] Subagent {agent_id} failed: {error}")

                    # Phase 9: collect partial token usage
                    tt = context.token_tracker
                    tokens = tt.get_total()

                    return AgentResult(
                        agent_id=agent_id,
                        status="error",
                        content=f"Subagent error: {type(error).__name__}: {error}\n{getattr(error, '__traceback__', '')}",
                        total_duration_ms=duration_ms,
                        total_tokens=tokens.get("total", 0),
                        input_tokens=tokens.get("input", 0),
                        output_tokens=tokens.get("output", 0),
                    )

        finally:
            # Phase 4 & 5: cleanup
            await self._cleanup_agent(context, agent_abort)

    async def _spawn_async(
        self,
        agent_id: str,
        agent_type: str,
        prompt: str,
        description: str,
        system_prompt: str | None,
        tools: list[Any] | None,
        model: str,
        max_turns: int,
        abort_controller: Any = None,
        project_id: str = "",
    ) -> AgentResult:
        """Spawn a subagent asynchronously (parent continues immediately).

        Creates an asyncio.Task to run the subagent in the background,
        registers it for lifecycle tracking, and returns immediately.

        Args:
            agent_id: Unique identifier for the subagent.
            agent_type: Type of subagent.
            prompt: Task description for the subagent.
            description: Short description for logging.
            system_prompt: Optional system prompt override.
            tools: Tools available to the subagent.
            model: Model for the subagent.
            max_turns: Maximum turns for the subagent.
            abort_controller: Parent AbortController for hierarchy.
            project_id: Project context for path resolution.

        Returns:
            AgentResult with status="launched" and agent_id.
        """
        log.info("[AgentSpawner] _spawn_async: agent_id=%s, type=%s", agent_id, agent_type)
        from .abort_controller import AbortController
        from .builtins.tasks import get_running_tasks

        # Phase 2: create child abort controller
        agent_abort = AbortController(parent=abort_controller, agent_id=agent_id)

        # Phase 3: register in hierarchy (uses _AbortHierarchy.register with child_id)
        from .abort_controller import get_hierarchy
        get_hierarchy().register(parent_id=agent_id, child_id=agent_id, controller=agent_abort)

        # Register in running_tasks for TaskOutput/TaskStop discovery
        running = get_running_tasks()
        running_key = f"background_{agent_id}"

        # Phase 3: create isolated context for this async agent
        from .context_isolation import AgentContext, AgentContextManager
        from .message_manager import MessageManager
        from .token_usage_tracker import TokenTracker
        from .builtins.tasks import get_store
        from .transcript import get_transcript_dir, TranscriptWriter

        transcript_writer = None
        if project_id:
            t_dir = get_transcript_dir(project_id, agent_id)
            transcript_writer = TranscriptWriter(str(t_dir))

        context = AgentContext(
            agent_id=agent_id,
            task_store=get_store(),
            message_manager=MessageManager(),
            abort_controller=agent_abort,
            transcript_writer=transcript_writer,
            token_tracker=TokenTracker(),
        )

        # Phase 4: wrapper with try/finally for cleanup
        async def _run_with_cleanup():
            try:
                return await self._spawn_sync(
                    agent_id, agent_type, prompt, description,
                    system_prompt, tools, model, max_turns,
                    abort_controller=agent_abort,
                    project_id=project_id,
                )
            finally:
                await self._cleanup_agent(context, agent_abort)

        # Run in background task — keep a reference to prevent GC
        async_task = asyncio.create_task(_run_with_cleanup())
        running[running_key] = async_task
        # Phase 6: also register by agent_id for TaskOutput lookup
        running[agent_id] = async_task

        self._background_tasks.add(async_task)
        async_task.add_done_callback(self._background_tasks.discard)

        # Phase 6: register in mailbox for message delivery
        try:
            from .agent_mailbox import get_mailbox
            mailbox = get_mailbox(agent_id)
            mailbox.send(agent_id, "parent", f"[System] Agent {agent_id} ({agent_type}) launched")
        except Exception:
            pass  # mailbox may not be set up yet

        # Return immediate result — real result comes later when task completes
        return AgentResult(
            agent_id=agent_id,
            status="launched",
            content=f"Agent {agent_id} launched in background. "
                    f"Type: {agent_type}. Prompt: {prompt[:100]}...",
            total_duration_ms=0,
        )

    async def _cleanup_agent(self, context: str | None, abort: Any) -> None:
        """Clean up resources for a completed or failed subagent.

        Delegates cleanup to AgentCleaner (called in finally block).

        Args:
            context: The AgentContext to clean up.
            abort: The AbortController to clean up.
        """
        from .agent_cleanup import AgentCleaner
        agent_id = context.agent_id if context else (abort.id if abort else "unknown")
        await AgentCleaner.cleanup(agent_id, context)

    async def send_message(self, agent_id: str, message: str) -> AgentResult:
        """
        Send a message to a running subagent.

        Mirrors CCB's SendMessage tool — used to continue or redirect
        a running subagent.

        Phase 6: Delegates to file-based mailbox.
        """
        log.info(
            f"[AgentSpawner] SendMessage to {agent_id}: {message[:100]}"
        )

        # Phase 6: write to mailbox
        try:
            from .agent_mailbox import get_mailbox
            mailbox = get_mailbox(agent_id)
            mailbox.send(agent_id, "parent", message)
        except Exception as e:
            log.warning(f"[AgentSpawner] Failed to send mailbox message: {e}")

        # Also try to resume via TaskOutput if not running
        from .builtins.tasks import get_running_tasks
        running = get_running_tasks()
        async_task = running.get(agent_id)
        if async_task and not async_task.done():
            # Agent is running — message is queued in mailbox
            return AgentResult(
                agent_id=agent_id,
                status="completed",
                content=f"Message queued for agent {agent_id}",
            )

        return AgentResult(
            agent_id=agent_id,
            status="completed",
            content=f"Message received: {message}",
        )
