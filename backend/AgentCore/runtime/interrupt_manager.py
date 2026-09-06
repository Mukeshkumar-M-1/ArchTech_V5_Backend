"""
Interrupt Manager

Handles hierarchical interrupts (Mission -> Task -> Turn -> Tool).
Interrupts can pause the workflow, inject messages, or trigger checkpoints.
"""

import logging
from enum import Enum, auto
from AgentCore.event_bus import EventBus
from .state_machine import RuntimeStateMachine, RuntimeState

log = logging.getLogger(__name__)

class InterruptScope(Enum):
    MISSION = auto()
    TASK = auto()
    TURN = auto()
    TOOL = auto()

class InterruptManager:
    def __init__(self, event_bus: EventBus, state_machine: RuntimeStateMachine):
        self.event_bus = event_bus
        self.state_machine = state_machine
        self.event_bus.subscribe("InterruptRequested", self.handle_interrupt)
        log.info("[InterruptManager] Initialized.")

    def handle_interrupt(self, payload: dict) -> None:
        scope = payload.get("scope", InterruptScope.TURN)
        reason = payload.get("reason", "Unknown interrupt.")
        
        log.warning(f"[InterruptManager] Interrupt received at {scope.name} level: {reason}")
        
        # Transition state to PAUSED so the LoopController suspends
        try:
            self.state_machine.transition(RuntimeState.PAUSED)
        except ValueError as e:
            log.error(f"[InterruptManager] Could not pause for interrupt: {e}")
            return
            
        # Specific scope handling
        if scope == InterruptScope.TOOL:
            # Tell sandbox to pause if supported
            self.event_bus.publish("PauseToolExecution")
            
        elif scope == InterruptScope.MISSION:
            # Pause all tasks
            self.event_bus.publish("PauseMission")
            
        log.info("[InterruptManager] Runtime successfully suspended for interrupt.")
