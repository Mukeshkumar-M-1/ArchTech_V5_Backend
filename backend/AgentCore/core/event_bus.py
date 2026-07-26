"""
EventBus - Central asynchronous Pub/Sub messaging system for the Agent Framework.

Provides decoupled communication between Agent components (e.g. ToolExecutor emitting
ToolFinished events, which Observer can consume).
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List

log = logging.getLogger(__name__)

class Event:
    """Base class for all events in the system."""
    def __init__(self, name: str, payload: Dict[str, Any]):
        self.name = name
        self.payload = payload


class EventBus:
    """A simple asynchronous publish-subscribe event bus."""
    
    def __init__(self):
        # Maps event_name to a list of async callbacks
        self._subscribers: Dict[str, List[Callable[[Event], Coroutine[Any, Any, None]]]] = {}
        log.info("[EventBus] Initialized.")

    def subscribe(self, event_name: str, callback: Callable[[Event], Coroutine[Any, Any, None]]) -> None:
        """Register a callback for a specific event name.
        
        Args:
            event_name: The name of the event to listen for.
            callback: An async function that takes an Event object.
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(callback)
        log.info(f"[EventBus] Subscribed '{callback.__name__}' to event '{event_name}'.")

    async def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish an event to all registered subscribers.
        
        Args:
            event_name: The name of the event.
            payload: The data associated with the event.
        """
        log.info(f"[EventBus] Emitting event '{event_name}'. Payload keys: {list(payload.keys())}")
        
        event = Event(name=event_name, payload=payload)
        subscribers = self._subscribers.get(event_name, [])
        
        if not subscribers:
            log.info(f"[EventBus] No subscribers for event '{event_name}'.")
            return
            
        # Execute all callbacks concurrently
        tasks = [asyncio.create_task(self._safe_execute(callback, event)) for callback in subscribers]
        await asyncio.gather(*tasks)

    async def _safe_execute(self, callback: Callable[[Event], Coroutine[Any, Any, None]], event: Event) -> None:
        """Execute a callback safely, catching any exceptions."""
        try:
            await callback(event)
        except Exception as e:
            log.error(f"[EventBus] Error in subscriber '{callback.__name__}' for event '{event.name}': {e}", exc_info=True)

