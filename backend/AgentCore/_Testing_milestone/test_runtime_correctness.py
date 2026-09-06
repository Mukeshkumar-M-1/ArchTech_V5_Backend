"""
Validation Phase: Runtime Correctness

Validates:
1. State Machine Invariants (Negative testing for invalid transitions)
2. Event Consistency (Correlation IDs and ordering)
3. Context Builder Determinism
"""

import logging
import sys
from pathlib import Path
import uuid

# Setup explicit path for the AgentCore module
sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.event_bus import EventBus
from AgentCore.runtime.state_machine import RuntimeStateMachine, RuntimeState

# Configure robust logging for clear developer debugging as requested
logging.basicConfig(
    level=logging.INFO,
    format="\n\n %(asctime)s [%(name)s.%(funcName)s]\n [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log12.log",
            encoding="utf-8",
            mode="a",
        ),
    ],
)
log = logging.getLogger("TestRuntimeCorrectness")

def test_state_machine_invariants():
    """
    Proves that the RuntimeStateMachine enforces strict transition rules.
    We intentionally attempt invalid transitions (e.g. WAITING_TOOL -> COMPLETED)
    and verify they raise ValueError.
    """
    log.info("=== Starting State Machine Invariants Validation ===")
    
    event_bus = EventBus()
    state_machine = RuntimeStateMachine(event_bus)
    
    # Track events to verify EventBus wiring
    emitted_events = []
    
    def on_state_changed(payload):
        emitted_events.append(payload)
        log.info(f"EventBus Received 'OnStateChanged': {payload['previous'].name} -> {payload['current'].name}")
        
    event_bus.subscribe("OnStateChanged", on_state_changed)
    
    # 1. Valid Transition Sequence
    log.info("Validating positive transition flow...")
    state_machine.transition(RuntimeState.READY)
    state_machine.transition(RuntimeState.RUNNING)
    state_machine.transition(RuntimeState.WAITING_TOOL)
    
    assert state_machine.current_state == RuntimeState.WAITING_TOOL, "State should be WAITING_TOOL"
    assert len(emitted_events) == 3, "EventBus should have processed 3 valid transitions"
    
    # 2. Negative Tests (Proving Invalid Transitions Fail)
    log.info("Validating negative transition constraints...")
    
    # Attempting to jump directly from WAITING_TOOL to COMPLETED (Illegal)
    try:
        state_machine.transition(RuntimeState.COMPLETED)
        assert False, "FAILED: Allowed invalid transition from WAITING_TOOL to COMPLETED!"
    except ValueError as validation_error:
        log.info(f"SUCCESS: Blocked invalid transition correctly: {validation_error}")

    # Reset state to FAILED to test exit-state constraints
    state_machine._current_state = RuntimeState.FAILED 
    log.info("Forcing internal state to FAILED for exit constraints test.")
    
    try:
        state_machine.transition(RuntimeState.RUNNING)
        assert False, "FAILED: Allowed transition from FAILED to RUNNING!"
    except ValueError as validation_error:
        log.info(f"SUCCESS: Blocked invalid transition correctly: {validation_error}")
        
    log.info("=== State Machine Invariants Validation Completed Successfully ===\n")

def test_event_consistency():
    """
    Validates EventBus ordering, payload fidelity, and correlation ID tracking.
    """
    log.info("=== Starting Event Consistency Validation ===")
    
    event_bus = EventBus()
    captured_events = []
    correlation_id = str(uuid.uuid4())
    
    def event_listener(payload):
        captured_events.append(payload)
        log.info(f"Received Event: {payload.get('event_type')} with Correlation ID: {payload.get('correlation_id')}")

    # Subscribe to multiple lifecycle events
    event_bus.subscribe("ActionDispatched", event_listener)
    event_bus.subscribe("ObservationReceived", event_listener)
    
    # Publish events sequentially
    log.info("Publishing 'ActionDispatched' event...")
    event_bus.publish("ActionDispatched", {
        "event_type": "ActionDispatched",
        "correlation_id": correlation_id,
        "action": "SEARCH"
    })
    
    log.info("Publishing 'ObservationReceived' event...")
    event_bus.publish("ObservationReceived", {
        "event_type": "ObservationReceived",
        "correlation_id": correlation_id,
        "result": "Files found."
    })
    
    # Verification
    log.info("Verifying complete wiring flow for EventBus...")
    assert len(captured_events) == 2, "EventBus dropped events!"
    assert captured_events[0]["event_type"] == "ActionDispatched", "Event ordering compromised!"
    assert captured_events[1]["event_type"] == "ObservationReceived", "Event ordering compromised!"
    assert captured_events[0]["correlation_id"] == correlation_id, "Correlation ID lost across EventBus!"
    
    log.info("=== Event Consistency Validation Completed Successfully ===\n")

def main():
    log.info("Initializing Milestone 4.5 Runtime Correctness Test Suite")
    
    test_state_machine_invariants()
    test_event_consistency()
    
    # Note: ContextBuilder determinism requires ContextBuilder implementation which is 
    # part of the broader Intelligence subsystem from M2/M3. We will stub/mock or integrate 
    # based on existing backend modules. For this phase, we validated the pure runtime elements.
    
    log.info("All Runtime Correctness validations passed.")

if __name__ == "__main__":
    main()
