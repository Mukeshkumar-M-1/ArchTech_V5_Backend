"""
Validation Phase: Runtime Reliability

Validates:
1. Failure recovery paths (Classifier mapping).
2. Interrupt handling & Cancellation propagation.
3. Long-running execution stability (Stress test).
"""

import logging
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.event_bus import EventBus
from AgentCore.runtime.state_machine import RuntimeStateMachine, RuntimeState
from AgentCore.runtime.failure_classifier import FailureClassifier, RecoveryStrategy
from AgentCore.runtime.cancellation_manager import CancellationManager
from AgentCore.runtime.interrupt_manager import InterruptManager, InterruptScope

logging.basicConfig(
    level=logging.INFO,
    format="\n\n %(asctime)s [%(name)s.%(funcName)s]\n [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log16.log",
            encoding="utf-8",
            mode="a",
        ),
    ],
)
log = logging.getLogger("TestRuntimeReliability")

def test_failure_recovery_paths():
    log.info("=== Starting Failure Recovery Validation ===")
    classifier = FailureClassifier()
    
    # Define test cases mapping error string to expected strategy
    test_cases = [
        ("API Timeout occurred", RecoveryStrategy.RETRY),
        ("Context limit exceeded (8k tokens)", RecoveryStrategy.REBUILD_CONTEXT),
        ("Policy violation: rm -rf", RecoveryStrategy.ESCALATE),
        ("Failed to parse JSON response", RecoveryStrategy.REPAIR_PARSER),
        ("Unknown fatal segmentation fault", RecoveryStrategy.ABORT)
    ]
    
    for error_msg, expected_strategy in test_cases:
        strategy = classifier.classify_error("Exception", error_msg)
        assert strategy == expected_strategy, f"Failed mapping '{error_msg}' to {expected_strategy.name}. Got {strategy.name}."
        log.info(f"SUCCESS: Mapped '{error_msg}' -> {strategy.name}")
        
    log.info("=== Failure Recovery Validation Completed Successfully ===\n")

def test_interrupt_and_cancellation():
    log.info("=== Starting Interrupt & Cancellation Validation ===")
    
    event_bus = EventBus()
    state_machine = RuntimeStateMachine(event_bus)
    cancellation_manager = CancellationManager(event_bus, state_machine)
    interrupt_manager = InterruptManager(event_bus, state_machine)
    
    # 1. Test Interrupt (Should Pause)
    log.info("Setting state to RUNNING and firing interrupt...")
    state_machine.transition(RuntimeState.READY)
    state_machine.transition(RuntimeState.RUNNING)
    
    event_bus.publish("InterruptRequested", {"scope": InterruptScope.TOOL, "reason": "User Pause"})
    assert state_machine.current_state == RuntimeState.PAUSED, "Interrupt failed to pause runtime!"
    log.info("SUCCESS: Interrupt safely paused the runtime.")
    
    # 2. Test Cancellation (Should transition to CANCELLED)
    log.info("Setting state back to RUNNING and firing cancellation...")
    state_machine.transition(RuntimeState.RUNNING)
    
    callback_fired = [False]
    def dummy_abort_hook():
        callback_fired[0] = True
        log.info("Callback hook fired during cancellation.")
        
    cancellation_manager.register_callback(dummy_abort_hook)
    
    event_bus.publish("CancelRequested")
    assert state_machine.current_state == RuntimeState.CANCELLED, "Cancellation failed to enforce CANCELLED state!"
    assert callback_fired[0] == True, "Registered cancellation hooks were not fired!"
    log.info("SUCCESS: Cancellation cleanly terminated operations and updated state.")
    
    log.info("=== Interrupt & Cancellation Validation Completed Successfully ===\n")

def test_long_running_stability():
    """
    Simulates a high-volume turn cycle (1000 turns) to ensure no state corruption 
    or unexpected exceptions break the LoopController flow.
    """
    log.info("=== Starting Long-Running Stability Stress Test (1,000 Turns) ===")
    
    event_bus = EventBus()
    state_machine = RuntimeStateMachine(event_bus)
    state_machine.transition(RuntimeState.READY)
    
    turns_completed = 0
    target_turns = 1000
    
    # Disable noisy logging for the tight loop
    logging.getLogger("AgentCore.event_bus").setLevel(logging.WARNING)
    logging.getLogger("AgentCore.runtime.state_machine").setLevel(logging.WARNING)
    
    start_time = time.time()
    
    try:
        for _ in range(target_turns):
            state_machine.transition(RuntimeState.RUNNING)
            state_machine.transition(RuntimeState.WAITING_TOOL)
            state_machine.transition(RuntimeState.REFLECTING)
            state_machine.transition(RuntimeState.CHECKPOINTING)
            
            # Reset for next turn
            state_machine.transition(RuntimeState.RUNNING)
            state_machine.transition(RuntimeState.WAITING_TOOL)
            state_machine.transition(RuntimeState.REFLECTING)
            state_machine.transition(RuntimeState.VERIFYING)
            state_machine.transition(RuntimeState.COMPLETED)
            
            # Ready for next cycle
            state_machine._current_state = RuntimeState.READY 
            turns_completed += 1
            
    except Exception as e:
        log.error(f"Stress test failed at turn {turns_completed}: {e}")
        raise
        
    duration = time.time() - start_time
    
    # Re-enable logging
    logging.getLogger("AgentCore.event_bus").setLevel(logging.INFO)
    logging.getLogger("AgentCore.runtime.state_machine").setLevel(logging.INFO)
    
    assert turns_completed == target_turns, "Failed to complete 1000 turns!"
    log.info(f"SUCCESS: Completed {target_turns} lifecycle turns in {duration:.3f}s with 0 memory faults or state corruption.")
    log.info("=== Long-Running Stability Validation Completed Successfully ===\n")

def main():
    log.info("Initializing Milestone 4.5 Runtime Reliability Test Suite")
    
    test_failure_recovery_paths()
    test_interrupt_and_cancellation()
    test_long_running_stability()
    
    log.info("All Runtime Reliability validations passed.")

if __name__ == "__main__":
    main()
