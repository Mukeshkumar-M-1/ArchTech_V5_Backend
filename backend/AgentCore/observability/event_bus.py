"""EventBus — Pub/Sub communication layer for AgentCore.

All component-to-component communication goes through the EventBus.
This eliminates direct function call coupling and provides a single
point for observability, logging, and debugging.

Design principles:
- Every component publishes events it generates.
- Every component subscribes to events it cares about.
- No component directly calls another component's methods for coordination.
- Events are typed with EventType enum for compile-time checking.
- Events carry structured payloads for debugging.
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class EventType(enum.Enum):
    """All event types published by the EventBus.

    Naming convention: COMPONENT_ACTION in uppercase (e.g., TOOL_EXECUTED,
    MISSION_COMPLETED). Each event type has a unique string value and
    a documented set of subscribers.
    """

    # Kernel lifecycle events
    KERNEL_STARTING = "kernel_starting"
    KERNEL_STARTED = "kernel_started"
    KERNEL_STOPPING = "kernel_stopping"
    KERNEL_STOPPED = "kernel_stopped"

    # Mission lifecycle events
    MISSION_CREATED = "mission_created"
    MISSION_PROGRESS = "mission_progress"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"

    # Task lifecycle events
    TASK_SCHEDULED = "task_scheduled"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_REQUEUED = "task_requeued"
    TASK_DEGRADED = "task_degraded"

    # Tool execution events
    TOOL_CALLING = "tool_calling"
    TOOL_EXECUTED = "tool_executed"
    TOOL_RETRIED = "tool_retried"
    TOOL_PERMISSION_DENIED = "tool_permission_denied"

    # Subagent events
    SUBAGENT_SPAWNED = "subagent_spawned"
    SUBAGENT_COMPLETED = "subagent_completed"
    SUBAGENT_FAILED = "subagent_failed"

    # Verification and reflection events
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    REFLECTION_STARTED = "reflection_started"
    REFLECTION_DONE = "reflection_done"

    # Memory and learning events
    EXPERIENCE_EXTRACTED = "experience_extracted"
    EXPERIENCE_STORED = "experience_stored"
    MEMORY_UPDATED = "memory_updated"

    # Budget events
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"

    # Blackboard events
    BLACKBOARD_UPDATED = "blackboard_updated"
    CONFIDENCE_CHANGED = "confidence_changed"
    CONFIDENCE_CRITICAL = "confidence_critical"

    # Control events
    CANCEL_REQUESTED = "cancel_requested"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    KERNEL_SHUTDOWN = "kernel_shutdown"

    # Compaction event
    COMPACTION_TRIGGERED = "compaction_triggered"

    # Recovery event
    RECOVERY_TRIGGERED = "recovery_triggered"


@dataclass
class Event:
    """An event published by the EventBus.

    All events carry a type, source component identifier, timestamp,
    and optional structured payload for debugging.
    """

    type: EventType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        """Return a human-readable event summary."""
        return f"Event(type={self.type.value}, source={self.source}, payload={self.payload})"


class EventBus:
    """Publish/Subscribe event bus for zero-coupling component communication.

    Components subscribe to events they care about, publish events they
    generate. No direct function calls between coordinating components —
    all communication is event-mediated.

    Example:
        bus = EventBus()
        bus.subscribe(EventType.TOOL_EXECUTED, handler)
        bus.publish(EventType.TOOL_EXECUTED, source="ToolExecutor", payload={"tool": "Bash"})
    """

    def __init__(self) -> None:
        """Initialize an empty event bus."""
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        log.info("EventBus initialized")

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: The EventType to subscribe to.
            handler: Callable that receives the Event as its argument.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        log.info("Subscribed handler to %s (total handlers: %d)", event_type.value, len(self._subscribers[event_type]))

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
    ) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The EventType to unsubscribe from.
            handler: The previously subscribed handler to remove.

        Raises:
            ValueError: If the handler is not subscribed to this event type.
        """
        if event_type not in self._subscribers:
            raise ValueError(f"No handlers subscribed to {event_type.value}")
        if handler not in self._subscribers[event_type]:
            raise ValueError(f"Handler not subscribed to {event_type.value}")
        self._subscribers[event_type].remove(handler)
        log.info("Unsubscribed handler from %s (remaining: %d)", event_type.value, len(self._subscribers[event_type]))

    def publish(
        self,
        event_type: EventType,
        source: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """Publish an event to all subscribers of this type.

        All handlers are called synchronously in registration order.
        If a handler raises an exception, it is logged but does not
        prevent other handlers from running.

        Args:
            event_type: The type of event to publish.
            source: Component name that published the event (e.g., "QueryLoop", "ToolExecutor").
            payload: Optional structured data for debugging and event processing.

        Example:
            bus.publish(EventType.TOOL_EXECUTED, "ToolExecutor", {"tool": "Bash", "success": True})
        """
        event = Event(type=event_type, source=source, payload=payload or {})
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            log.info("No subscribers for %s from %s", event_type.value, source)
            return

        log.info("Publishing event %s from %s with payload keys: %s", event_type.value, source, list(event.payload.keys()))
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                log.error("Event handler failed for %s: %s", event_type.value, exc, exc_info=True)

    def get_subscriber_count(self, event_type: EventType) -> int:
        """Return the number of handlers subscribed to an event type.

        Args:
            event_type: The event type to check.

        Returns:
            Number of subscribers for the given event type.
        """
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        """Remove all subscriptions. Useful for cleanup."""
        self._subscribers.clear()
        log.info("EventBus cleared")


# Global singleton for cross-module events (e.g. Memory_Management -> AgentCore)
_global_bus = EventBus()

def get_global_bus() -> EventBus:
    """Get the global EventBus instance.

    Returns:
        The module-level EventBus singleton.
    """
    return _global_bus
