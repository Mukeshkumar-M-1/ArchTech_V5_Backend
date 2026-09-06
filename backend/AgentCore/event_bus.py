"""EventBus — Consolidated pub/sub messaging system.

Three distinct bus implementations serve different subsystems:

  - InfraEventBus:   Minimal sync bus for runtime state management.
    Used by: runtime_adapter, state_machine, cancellation_manager, interrupt_manager.

  - AsyncEventBus:   Async bus with concurrent callbacks for the execution engine loop.
    Used by: execution_engine, GenerationAgentKernel.

  - ObservationBus:  Typed bus with EventType enum, global singleton, structured Event.
    Used by: observability/agent_kernel, memory & requirement route handlers.

Naming conventions (all string-based, uppercase component_action):
  - Core execution:  TurnStarted, TurnCompleted, ToolStarted, ToolFinished, TaskCompleted
  - Infrastructure:  CancelRequested, InterruptRequested, OnStateChanged, OnCancelled
  - Observability:   (typed via EventType enum)
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

log = logging.getLogger(__name__)


# ====================================================================
# Shared types
# ====================================================================

class EventType(enum.Enum):
    """All event types for the ObservationBus.

    Naming convention: COMPONENT_ACTION in uppercase.
    """

    # Kernel lifecycle
    KERNEL_STARTING = "kernel_starting"
    KERNEL_STARTED = "kernel_started"
    KERNEL_STOPPING = "kernel_stopping"
    KERNEL_STOPPED = "kernel_stopped"

    # Mission / task lifecycle
    MISSION_CREATED = "mission_created"
    MISSION_PROGRESS = "mission_progress"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"

    TASK_SCHEDULED = "task_scheduled"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_REQUEUED = "task_requeued"
    TASK_DEGRADED = "task_degraded"

    # Tool execution
    TOOL_CALLING = "tool_calling"
    TOOL_EXECUTED = "tool_executed"
    TOOL_RETRIED = "tool_retried"
    TOOL_PERMISSION_DENIED = "tool_permission_denied"

    # Subagent
    SUBAGENT_SPAWNED = "subagent_spawned"
    SUBAGENT_COMPLETED = "subagent_completed"
    SUBAGENT_FAILED = "subagent_failed"

    # Verification / reflection
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    REFLECTION_STARTED = "reflection_started"
    REFLECTION_DONE = "reflection_done"

    # Memory / learning
    EXPERIENCE_EXTRACTED = "experience_extracted"
    EXPERIENCE_STORED = "experience_stored"
    MEMORY_UPDATED = "memory_updated"

    # Budget
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Blackboard
    BLACKBOARD_UPDATED = "blackboard_updated"
    CONFIDENCE_CHANGED = "confidence_changed"
    CONFIDENCE_CRITICAL = "confidence_critical"

    # Control
    CANCEL_REQUESTED = "cancel_requested"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    KERNEL_SHUTDOWN = "kernel_shutdown"

    # Compaction / recovery
    COMPACTION_TRIGGERED = "compaction_triggered"
    RECOVERY_TRIGGERED = "recovery_triggered"


@dataclass
class Event:
    """Structured event payload used by all bus implementations."""

    type: Optional[EventType] = None
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    name: str = ""  # Legacy: used by core/AsyncEventBus

    def __str__(self) -> str:
        return f"Event(type={self.type.value if self.type else self.name}, source={self.source}, payload={self.payload})"


# ====================================================================
# Infrastructure sync EventBus — minimal bus (runtime state management)
# ====================================================================

class _InfraEventBus:
    """Minimal synchronous publish/subscribe bus for runtime infrastructure.

    Used by: runtime_adapter, state_machine, cancellation_manager, interrupt_manager.

    API:
        bus.subscribe("CancelRequested", handler)   # handler receives raw payload
        bus.publish("CancelRequested", payload)      # payload is optional
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_counter: int = 0
        log.info("[EventBus] Initialized (infrastructure).")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        log.info("[EventBus] Subscribed to '%s'.", event_type)

    def publish(self, event_type: str, payload: Any = None) -> None:
        self._event_counter += 1
        log.info("[EventBus] Publishing event: %s", event_type)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(payload)
            except Exception as exception:
                log.error("[EventBus] Handler failed for '%s': %s", event_type, exception)


# Module-level class aliases for backwards compatibility
# InfraEventBus (explicit name) and EventBus (backwards compat for infra consumers)
# No type annotations needed — these are class aliases, not variables
InfraEventBus = _InfraEventBus
EventBus = _InfraEventBus


# ====================================================================
# Core async EventBus — async concurrent bus (execution engine loop)
# ====================================================================

class AsyncEventBus:
    """Asynchronous publish/subscribe bus with concurrent callback execution.

    Used by: execution_engine, GenerationAgentKernel.

    API:
        await bus.emit("ToolFinished", {"tool_name": "Bash", ...})
        bus.subscribe("ToolFinished", _on_tool_finished)  # callback receives Event
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], Coroutine[Any, Any, None]]]] = {}
        log.info("[AsyncEventBus] Initialized (core).")

    def subscribe(
        self,
        event_name: str,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
        log.info("[AsyncEventBus] Subscribed '%s' to '%s'.", callback.__name__, event_name)

    async def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        subscribers = self._subscribers.get(event_name, [])
        if not subscribers:
            log.info("[AsyncEventBus] No subscribers for '%s'.", event_name)
            return

        event = Event(name=event_name, payload=payload)
        tasks = [asyncio.create_task(self._safe_execute(cb, event)) for cb in subscribers]
        await asyncio.gather(*tasks)

    async def _safe_execute(
        self,
        callback: Callable[[Event], Coroutine[Any, Any, None]],
        event: Event,
    ) -> None:
        try:
            await callback(event)
        except Exception as e:
            log.error(
                "[AsyncEventBus] Error in '%s' for '%s': %s",
                callback.__name__, event.name, e,
                exc_info=True,
            )


# ====================================================================
# Observability ObservationBus — typed bus with singleton
# ====================================================================

class ObservationBus:
    """Typed synchronous bus with EventType enum, global singleton, and structured Event.

    Used by: observability/agent_kernel, memory/requirement route handlers.

    API:
        bus.subscribe(EventType.MEMORY_UPDATED, handler)
        bus.publish(EventType.MEMORY_UPDATED, source="MemoryManagement", payload={...})
        bus.unsubscribe(EventType.MEMORY_UPDATED, handler)
    """

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        log.info("[ObservationBus] Initialized.")

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        log.info(
            "[ObservationBus] Subscribed to %s (total: %d)",
            event_type.value,
            len(self._subscribers[event_type]),
        )

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        if event_type not in self._subscribers:
            raise ValueError(f"No handlers for {event_type.value}")
        if handler not in self._subscribers[event_type]:
            raise ValueError(f"Handler not subscribed to {event_type.value}")
        self._subscribers[event_type].remove(handler)
        log.info(
            "[ObservationBus] Unsubscribed from %s (remaining: %d)",
            event_type.value,
            len(self._subscribers[event_type]),
        )

    def publish(
        self,
        event_type: EventType,
        source: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        event = Event(type=event_type, source=source, payload=payload or {})
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            log.info("[ObservationBus] No subscribers for %s", event_type.value)
            return

        log.info(
            "[ObservationBus] Publishing %s from %s",
            event_type.value,
            source,
        )
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                log.error(
                    "[ObservationBus] Handler failed for %s: %s",
                    event_type.value,
                    exc,
                    exc_info=True,
                )

    def get_subscriber_count(self, event_type: EventType) -> int:
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        self._subscribers.clear()
        log.info("[ObservationBus] Cleared.")


# Global singleton for cross-module observability events.
_global_bus: ObservationBus = ObservationBus()


def get_global_bus() -> ObservationBus:
    """Get the global ObservationBus singleton."""
    return _global_bus
