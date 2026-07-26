"""
Runtime State Machine

The central source of truth for runtime lifecycle.
Prevents implicit state changes and ensures predictable transitions.
"""

import logging
from enum import Enum, auto
from typing import Dict, Set
from ..infrastructure.event_bus import EventBus

log = logging.getLogger(__name__)

class RuntimeState(Enum):
    CREATED = auto()
    READY = auto()
    RUNNING = auto()
    WAITING_TOOL = auto()
    WAITING_USER = auto()
    REFLECTING = auto()
    VERIFYING = auto()
    REPAIRING = auto()
    CHECKPOINTING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

class RuntimeStateMachine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._current_state = RuntimeState.CREATED
        
        # Valid state transitions
        self._valid_transitions: Dict[RuntimeState, Set[RuntimeState]] = {
            RuntimeState.CREATED: {RuntimeState.READY, RuntimeState.FAILED, RuntimeState.CANCELLED},
            RuntimeState.READY: {RuntimeState.RUNNING, RuntimeState.FAILED, RuntimeState.CANCELLED},
            RuntimeState.RUNNING: {
                RuntimeState.WAITING_TOOL, RuntimeState.WAITING_USER, 
                RuntimeState.CHECKPOINTING, RuntimeState.COMPLETED, 
                RuntimeState.PAUSED, RuntimeState.CANCELLED, RuntimeState.FAILED
            },
            RuntimeState.WAITING_TOOL: {RuntimeState.REFLECTING, RuntimeState.PAUSED, RuntimeState.FAILED, RuntimeState.CANCELLED},
            RuntimeState.WAITING_USER: {RuntimeState.RUNNING, RuntimeState.CANCELLED},
            RuntimeState.REFLECTING: {RuntimeState.VERIFYING, RuntimeState.RUNNING, RuntimeState.CHECKPOINTING, RuntimeState.REPAIRING, RuntimeState.FAILED},
            RuntimeState.VERIFYING: {RuntimeState.COMPLETED, RuntimeState.REPAIRING, RuntimeState.FAILED},
            RuntimeState.REPAIRING: {RuntimeState.RUNNING, RuntimeState.FAILED},
            RuntimeState.CHECKPOINTING: {RuntimeState.RUNNING, RuntimeState.PAUSED},
            RuntimeState.PAUSED: {RuntimeState.RUNNING, RuntimeState.CANCELLED},
            RuntimeState.COMPLETED: set(),
            RuntimeState.FAILED: set(),
            RuntimeState.CANCELLED: set()
        }
        log.info(f"[RuntimeStateMachine] Initialized in {self._current_state.name}.")

    @property
    def current_state(self) -> RuntimeState:
        return self._current_state

    def transition(self, next_state: RuntimeState) -> None:
        """Attempts to transition to a new state and emits an event if successful."""
        if next_state not in self._valid_transitions[self._current_state]:
            error_msg = f"Invalid transition from {self._current_state.name} to {next_state.name}."
            log.error(f"[RuntimeStateMachine] {error_msg}")
            raise ValueError(error_msg)
            
        previous_state = self._current_state
        self._current_state = next_state
        
        log.info(f"[RuntimeStateMachine] Transition: {previous_state.name} -> {self._current_state.name}")
        
        # Emit cross-cutting event
        self.event_bus.publish("OnStateChanged", {
            "previous": previous_state,
            "current": self._current_state
        })
