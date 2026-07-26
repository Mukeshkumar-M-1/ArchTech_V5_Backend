"""AgentKernel — Central runtime orchestrator for AgentCore.

The AgentKernel is NOT a manager that delegates — it IS the execution
environment. It owns lifecycle, budget, events, and the single
source of truth for the agent's operational state.

All other components (DocumentGenerationAgent, DocumentController,
QueryLoop) are created and owned by the AgentKernel, not by
external callers.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..observability.event_bus import EventBus, EventType, get_global_bus
from ..observability.blackboard import Blackboard
from ..observability.budget_manager import BudgetManager, BudgetStatus

log = logging.getLogger(__name__)


class AgentKernel:
    """Single runtime orchestrator. Owns lifecycle, budget, events.

    Lifecycle states:
        IDLE (0): Initial and final state
        INITIALIZING (1): Creating subsystems
        RUNNING (2): Active execution
        PAUSED (3): Execution suspended
        CANCELLED (4): Execution cancelled
        COMPLETE (5): Execution completed successfully
        FAILED (6): Execution failed

    Example:
        kernel = AgentKernel(project_id="proj-123", session_id="sess-456")
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
        log.info("AgentKernel created: project_id=%s, session_id=%s", project_id, session_id)

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
            log.warning("AgentKernel.start() called in state %s, expected IDLE", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.INITIALIZING
        log.info("AgentKernel starting: transitioning from IDLE to INITIALIZING")
        self.budget.start_timer()
        self.event_bus.publish(EventType.KERNEL_STARTING, source="AgentKernel", payload={"project_id": self.project_id, "session_id": self.session_id})
        self._state = self.RUNNING
        log.info("AgentKernel started: state = RUNNING")
        self.event_bus.publish(EventType.KERNEL_STARTED, source="AgentKernel", payload={})

    def cancel(self, reason: str = "cancelled") -> None:
        """Cancel the agent kernel with an optional reason.

        Transitions state from RUNNING to CANCELLED. Publishes
        CANCEL_REQUESTED event which causes the Scheduler to abort
        all running tasks.

        Args:
            reason: Human-readable reason for the cancellation.
        """
        if self._state != self.RUNNING:
            log.warning("AgentKernel.cancel() called in state %s, expected RUNNING", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.CANCELLED
        log.info("AgentKernel cancelled: reason=%s", reason)
        self.event_bus.publish(EventType.CANCEL_REQUESTED, source="AgentKernel", payload={"reason": reason})

    def pause(self) -> None:
        """Pause the agent kernel execution.

        Transitions state from RUNNING to PAUSED.
        """
        if self._state != self.RUNNING:
            log.warning("AgentKernel.pause() called in state %s, expected RUNNING", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.PAUSED
        log.info("AgentKernel paused")
        self.event_bus.publish(EventType.RUN_PAUSED, source="AgentKernel", payload={})

    def resume(self) -> None:
        """Resume the agent kernel execution.

        Transitions state from PAUSED to RUNNING.
        """
        if self._state != self.PAUSED:
            log.warning("AgentKernel.resume() called in state %s, expected PAUSED", self._state_names.get(self._state, "UNKNOWN"))
            return

        self._state = self.RUNNING
        log.info("AgentKernel resumed")
        self.event_bus.publish(EventType.RUN_RESUMED, source="AgentKernel", payload={})

    def cleanup(self) -> None:
        """Clean up the agent kernel and return to IDLE state.

        Publishes KERNEL_STOPPING and KERNEL_STOPPED events.
        Validates the final budget status.
        """
        if self._state == self.IDLE:
            log.info("AgentKernel.cleanup() called while already IDLE, skipping")
            return

        log.info("AgentKernel cleaning up from state %s", self._state_names.get(self._state, "UNKNOWN"))
        self.event_bus.publish(EventType.KERNEL_STOPPING, source="AgentKernel", payload={})

        # Final budget validation
        budget_status = self.budget.validate()
        if budget_status == BudgetStatus.EXCEEDED:
            log.warning("Budget exceeded at cleanup: %s", budget_status.value)
        else:
            log.info("Budget OK at cleanup: %s", budget_status.value)

        self.event_bus.publish(EventType.KERNEL_STOPPED, source="AgentKernel", payload={"budget_status": budget_status.value})
        self.event_bus.clear()
        self.blackboard.clear()
        self._state = self.IDLE
        log.info("AgentKernel cleaned up: state = IDLE")

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
