"""
Cancellation Manager

Handles graceful cancellation signals across the runtime.
Ensures that running tools are aborted if possible and state transitions to CANCELLED.
"""

import logging
from typing import Callable, List
from AgentCore.event_bus import EventBus
from .state_machine import RuntimeStateMachine, RuntimeState

log = logging.getLogger(__name__)

class CancellationManager:
    def __init__(self, event_bus: EventBus, state_machine: RuntimeStateMachine):
        self.bus = event_bus
        self.state_machine = state_machine
        self._cancellation_callbacks: List[Callable] = []
        
        # Subscribe to external cancellation events
        self.bus.subscribe("CancelRequested", self.handle_cancellation)
        log.info("[CancellationManager] Initialized.")

    def register_callback(self, callback: Callable) -> None:
        """Register hooks to abort running operations (e.g., stopping a thread)."""
        self._cancellation_callbacks.append(callback)

    def handle_cancellation(self, payload=None) -> None:
        log.warning("[CancellationManager] Cancellation signal received!")
        
        # Transition state if allowed
        try:
            self.state_machine.transition(RuntimeState.CANCELLED)
        except ValueError as e:
            log.error(f"[CancellationManager] Cannot transition to CANCELLED: {e}")
            
        # Fire callbacks to interrupt running tasks
        for cb in self._cancellation_callbacks:
            try:
                cb()
            except Exception as e:
                log.error(f"[CancellationManager] Callback failure during cancellation: {e}")
                
        self.bus.publish("OnCancelled")
