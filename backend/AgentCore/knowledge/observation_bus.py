"""
Observation Bus

A dedicated PubSub bus specifically for distributing immutable Observations.
Memory, KnowledgeGraph, and the ExecutionJournal subscribe to this bus.
"""

import logging
from typing import Callable, List, Awaitable

from .observation import Observation

log = logging.getLogger(__name__)

class ObservationBus:
    """Synchronous/Asynchronous dispatcher for Observations."""
    
    def __init__(self):
        self.subscribers: List[Callable[[Observation], None]] = []
        log.info("[ObservationBus] Initialized.")

    def subscribe(self, callback: Callable[[Observation], None]) -> None:
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            log.debug(f"[ObservationBus] Registered subscriber: {callback.__name__}")

    def publish(self, observation: Observation) -> None:
        """Broadcasts the observation to all subscribers."""
        log.info(f"[ObservationBus] Publishing observation {observation.observation_id} from {observation.source_tool}")
        for callback in self.subscribers:
            try:
                callback(observation)
            except Exception as e:
                log.error(f"[ObservationBus] Subscriber {callback.__name__} failed: {e}")
