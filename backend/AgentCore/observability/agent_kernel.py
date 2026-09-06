"""AgentKernels — Central runtime orchestrators for AgentCore.

This module contains two kernel implementations for different workflows:

  - ChatAgentKernel: Lifecycle manager with observability, budgeting, and blackboard.
    Used by: public API, route handlers, runtime_adapter.

  - GenerationAgentKernel: Task executor with LLM interaction loop and tool execution.
    Used by: document generation, task execution pipelines.

Both share the same EventBus subsystem (ObservationBus) for lifecycle events.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from AgentCore.event_bus import AsyncEventBus, Event, EventBus, EventType, get_global_bus
from .blackboard import Blackboard
from .budget_manager import BudgetManager, BudgetStatus
from ..core.agent_state import AgentStateStore
from ..core.agent_session_manager import AgentSessionManager
from ..core.execution_engine import ExecutionEngine
from AgentCore.execution.tool_executor import ToolExecutor
from AgentCore.orchestration.contracts import TaskContract

log = logging.getLogger(__name__)


class ChatAgentKernel:
    """Single runtime orchestrator. Owns lifecycle, budget, events.

    This is the public-facing kernel that manages the agent lifecycle,
    budget, blackboard state, and publishes observability events.

    Lifecycle states:
        IDLE (0): Initial and final state
        INITIALIZING (1): Creating subsystems
        RUNNING (2): Active execution
        PAUSED (3): Execution suspended
        CANCELLED (4): Execution cancelled
        COMPLETE (5): Execution completed successfully
        FAILED (6): Execution failed

    Example:
        kernel = ChatAgentKernel(project_id="proj-123", session_id="sess-456")
        kernel.start()
        # ... agent runs ...
        kernel.cleanup()
    """

    IDLE = 0
    INITIALIZING = 1
    RUNNING = 2
    PAUSED = 3
    CANCELLED = 4
    COMPLETE = 5
    FAILED = 6

    # State names for logging
    _state_names: dict[int, str] = {
        IDLE: "IDLE",
        INITIALIZING: "INITIALIZING",
        RUNNING: "RUNNING",
        PAUSED: "PAUSED",
        CANCELLED: "CANCELLED",
        COMPLETE: "COMPLETE",
        FAILED: "FAILED",
    }

    def __init__(self, project_id: str, session_id: str) -> None:
        """Initialize the agent kernel with project and session context.

        Creates the EventBus, Blackboard, and BudgetManager but does NOT
        start the agent lifecycle. Call start() to begin.

        Args:
            project_id: The project identifier for file path resolution.
            session_id: The session identifier for cross-session memory.
        """
        self._state: int = self.IDLE
        self.project_id: str = project_id
        self.session_id: str = session_id
        self.event_bus: EventBus = get_global_bus()
        self.blackboard: Blackboard = Blackboard()
        self.budget: BudgetManager = BudgetManager()
        log.info("ChatAgentKernel created: project_id=%s, session_id=%s", project_id, session_id)

    @property
    def state(self) -> int:
        """Return the current lifecycle state.

        Returns:
            Integer state code (IDLE, INITIALIZING, RUNNING, etc.).
        """
        return self._state

    def start(self) -> None:
        """Start the agent kernel lifecycle.

        Transitions state from INITIALIZING to RUNNING.
        Publishes KERNEL_STARTED event to all subscribers.
        """
        if self._state != self.IDLE:
            log.warning("ChatAgentKernel.start() called in state %s, expected IDLE", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.INITIALIZING
        log.info("ChatAgentKernel starting: transitioning from IDLE to INITIALIZING")
        self.budget.start_timer()
        self.event_bus.publish(EventType.KERNEL_STARTING, source="ChatAgentKernel", payload={"project_id": self.project_id, "session_id": self.session_id})
        self._state = self.RUNNING
        log.info("ChatAgentKernel started: state = RUNNING")
        self.event_bus.publish(EventType.KERNEL_STARTED, source="ChatAgentKernel", payload={})

    def cancel(self, reason: str = "cancelled") -> None:
        """Cancel the agent kernel with an optional reason.

        Transitions state from RUNNING to CANCELLED. Publishes
        CANCEL_REQUESTED event which causes the Scheduler to abort
        all running tasks.

        Args:
            reason: Human-readable reason for the cancellation.
        """
        if self._state != self.RUNNING:
            log.warning("ChatAgentKernel.cancel() called in state %s, expected RUNNING", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.CANCELLED
        log.info("ChatAgentKernel cancelled: reason=%s", reason)
        self.event_bus.publish(EventType.CANCEL_REQUESTED, source="ChatAgentKernel", payload={"reason": reason})

    def pause(self) -> None:
        """Pause the agent kernel execution.

        Transitions state from RUNNING to PAUSED.
        """
        if self._state != self.RUNNING:
            log.warning("ChatAgentKernel.pause() called in state %s, expected RUNNING", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.PAUSED
        log.info("ChatAgentKernel paused")
        self.event_bus.publish(EventType.RUN_PAUSED, source="ChatAgentKernel", payload={})

    def resume(self) -> None:
        """Resume the agent kernel execution.

        Transitions state from PAUSED to RUNNING.
        """
        if self._state != self.PAUSED:
            log.warning("ChatAgentKernel.resume() called in state %s, expected PAUSED", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.RUNNING
        log.info("ChatAgentKernel resumed")
        self.event_bus.publish(EventType.RUN_RESUMED, source="ChatAgentKernel", payload={})

    def cleanup(self) -> None:
        """Clean up the agent kernel and return to IDLE state.

        Publishes KERNEL_STOPPING and KERNEL_STOPPED events.
        Validates the final budget status.
        """
        if self._state == self.IDLE:
            log.info("ChatAgentKernel.cleanup() called while already IDLE, skipping")
            return

        log.info("ChatAgentKernel cleaning up from state %s", self._state_names.get(self._state, "UNKNOWN"))
        self.event_bus.publish(EventType.KERNEL_STOPPING, source="ChatAgentKernel", payload={})

        # Final budget validation
        budget_status = self.budget.validate()
        if budget_status == BudgetStatus.EXCEEDED:
            log.warning("Budget exceeded at cleanup: %s", budget_status.value)
        else:
            log.info("Budget OK at cleanup: %s", budget_status.value)

        self.event_bus.publish(EventType.KERNEL_STOPPED, source="ChatAgentKernel", payload={"budget_status": budget_status.value})
        self.event_bus.clear()
        self.blackboard.clear()
        self._state = self.IDLE
        log.info("ChatAgentKernel cleaned up: state = IDLE")

    def check_budget(self) -> BudgetStatus:
        """Validate all budget dimensions and return the most severe status.

        Returns:
            BudgetStatus indicating overall budget health.
        """
        status = self.budget.validate()
        if status == BudgetStatus.EXCEEDED:
            log.error("Budget check FAILED: overall status = %s", status.value)
        elif status == BudgetStatus.WARNING:
            log.warning("Budget check WARNING: overall status = %s", status.value)
        else:
            log.info("Budget check OK: overall status = %s", status.value)
        return status

    def get_state_name(self) -> str:
        """Return the human-readable name of the current state.

        Returns:
            State name string (e.g., "RUNNING", "CANCELLED").
        """
        return self._state_names.get(self._state, "UNKNOWN")


class GenerationAgentKernel:
    """Task executor for document generation and LLM interaction loops.

    This kernel wires together the EventBus, StateStore, AgentSessionManager,
    and ExecutionEngine to run LLM-driven tasks with tool execution.

    Unlike ChatAgentKernel (lifecycle manager), this is a pure task executor
    that runs the Turn -> Tool -> LLM call loop.

    Example:
        kernel = GenerationAgentKernel(session_dir="/path/to/sessions")
        result = await kernel.run_task(task_id="task-1", task_contract=contract, tools=["Bash"], max_turns=10)
    """

    def __init__(self, session_dir: str = None, message_manager=None) -> None:
        """Initialize the generation kernel.

        Args:
            session_dir: Directory for persisting agent sessions.
            message_manager: Optional SSEGenerationMessageManager for event emission.
        """
        self.event_bus = AsyncEventBus()
        self.agent_state_store = AgentStateStore()
        self.session_manager = AgentSessionManager(Path(session_dir))
        self._message_manager = message_manager
        self.execution_engine = ExecutionEngine(
            event_bus=self.event_bus,
            agent_state_store=self.agent_state_store,
            tool_executor=ToolExecutor(),
            message_manager=self._message_manager,
        )

        self._setup_event_listeners()
        log.info("[GenerationAgentKernel] Kernel initialized and wired successfully.")

    def _setup_event_listeners(self) -> None:
        """Register kernel-level observers for events."""
        self.event_bus.subscribe("ToolFinished", self._on_tool_finished)
        self.event_bus.subscribe("TaskCompleted", self._on_task_completed)
        self.event_bus.subscribe("TurnStarted", self._on_turn_started)

    async def _on_tool_finished(self, event: Event) -> None:
        """Observer hook for tool completion."""
        payload = event.payload
        log.info("[GenerationAgentKernel] Tool=[%s] finished. Error=[%s], Output length=[%s]",
                 payload.get('tool_name'), payload.get('is_error'), payload.get('content_length'))

    async def _on_task_completed(self, event: Event) -> None:
        """Observer hook for task completion."""
        log.info("[GenerationAgentKernel] Task=[%s] completed successfully.", event.payload.get('task_id'))

    async def _on_turn_started(self, event: Event) -> None:
        """Observer hook for turn execution."""
        log.info("[GenerationAgentKernel] Turn=[%s] started.", event.payload.get('turn'))

    async def run_task(
        self,
        task_id: str,
        task_contract: TaskContract,
        tools: List[Any],
        max_turns: int,
        session_id: str = "default_session"
    ) -> str:
        """Run a specific task through the execution engine.

        Args:
            task_id: Unique task identifier.
            task_contract: Current agent task contract.
            tools: Tools to expose to the execution engine.
            max_turns: Maximum number of LLM turns before forcing exit.
            session_id: Optional session identifier for persistence.

        Returns:
            The task output string.
        """
        log.info("[GenerationAgentKernel] Running task_id: [%s] in session_id: [%s]", task_id, session_id)

        # Load Agent session state
        agent_session_state = self.session_manager.load_session(session_id)
        if agent_session_state:
            self.agent_state_store = agent_session_state
            self.execution_engine.agent_state_store = self.agent_state_store

        # Execute Task
        try:
            executed_agent_result = await self.execution_engine.execute_task(
                task_id=task_id,
                task_contract=task_contract,
                tools=tools,
                max_turns=max_turns
            )
        except Exception as exception:
            log.error("[GenerationAgentKernel] Task execution failed: %s", exception, exc_info=True)
            executed_agent_result = f"[GenerationAgentKernel] Error: {str(exception)}"

        # Save session state
        self.session_manager.save_session(session_id, self.agent_state_store)

        return executed_agent_result
