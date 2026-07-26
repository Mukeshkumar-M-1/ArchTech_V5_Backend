"""
Event Bus

A global publish/subscribe bus for cross-cutting runtime events 
(e.g., state transitions, lifecycle hooks) that shouldn't couple domains directly.
"""

import logging
from typing import Callable, Dict, List, Any

log = logging.getLogger(__name__)

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        log.info("[EventBus] Initialized")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        log.info(f"[EventBus] Subscribed to {event_type}.")

    def publish(self, event_type: str, payload: Any = None) -> None:
        log.info(f"[EventBus] Emitting event: {event_type}")
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(payload)
                except Exception as e:
                    log.error(f"[EventBus] Handler failed for {event_type}: {e}")
