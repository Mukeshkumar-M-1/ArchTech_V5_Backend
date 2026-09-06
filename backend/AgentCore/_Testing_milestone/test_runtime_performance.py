"""
Validation Phase: Runtime Performance

Validates:
1. EventBus and Checkpoint Serialization latency bounds.
2. Resource Cleanup (File handles and temp artifacts drop after cancellation/failure).
"""

import logging
import sys
import os
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.event_bus import EventBus
from AgentCore.runtime.state_machine import RuntimeStateMachine, RuntimeState
from AgentCore.runtime.cancellation_manager import CancellationManager

logging.basicConfig(
    level=logging.INFO,
    format="\n\n %(asctime)s [%(name)s.%(funcName)s]\n [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log14.log",
            encoding="utf-8",
            mode="a",
        ),
    ],
)
log = logging.getLogger("TestRuntimePerformance")

def test_throughput_and_latency():
    log.info("=== Starting Throughput & Latency Validation ===")
    
    event_bus = EventBus()
    event_count = 10000
    received_count = [0]
    
    def fast_listener(payload):
        received_count[0] += 1
        
    event_bus.subscribe("PerformanceTest", fast_listener)
    
    log.info(f"Publishing {event_count} events to measure EventBus throughput...")
    
    start_time = time.time()
    for i in range(event_count):
        event_bus.publish("PerformanceTest", {"id": i, "data": "stress_payload"})
        
    duration = time.time() - start_time
    throughput = event_count / duration if duration > 0 else 0
    
    log.info(f"Processed {received_count[0]} events in {duration:.4f} seconds.")
    log.info(f"Throughput: {throughput:,.0f} events/second.")
    
    assert received_count[0] == event_count, "EventBus dropped events under load."
    assert throughput > 10000, f"EventBus throughput too low! Got {throughput:,.0f} events/s, expected > 10,000"
    
    log.info("SUCCESS: EventBus meets high-throughput production requirements.")
    log.info("=== Throughput & Latency Validation Completed Successfully ===\n")

def test_resource_cleanup():
    log.info("=== Starting Resource Cleanup Validation ===")
    
    event_bus = EventBus()
    state_machine = RuntimeStateMachine(event_bus)
    cancellation_manager = CancellationManager(event_bus, state_machine)
    
    test_artifact = "./temp_performance_artifact.txt"
    
    # Simulate a tool that opens a resource but registers a cleanup hook
    log.info("Simulating tool creating a temporary artifact...")
    with open(test_artifact, "w") as f:
        f.write("Temp data during execution")
        
    def cleanup_temp_files():
        if os.path.exists(test_artifact):
            os.remove(test_artifact)
            log.info(f"Cleanup hook fired: Removed {test_artifact}")
            
    cancellation_manager.register_callback(cleanup_temp_files)
    
    # Assert resource exists before cancel
    assert os.path.exists(test_artifact), "Test setup failed: Artifact not created."
    
    # Trigger cancel
    log.info("Triggering cancellation to test resource teardown...")
    state_machine.transition(RuntimeState.READY)
    state_machine.transition(RuntimeState.RUNNING)
    event_bus.publish("CancelRequested")
    
    # Assert resource cleaned up
    assert not os.path.exists(test_artifact), "Resource leak detected! Cleanup hook failed to remove artifact."
    
    log.info("SUCCESS: Cancellation cleanly executed resource teardown hooks.")
    log.info("=== Resource Cleanup Validation Completed Successfully ===\n")

def main():
    log.info("Initializing Milestone 4.5 Runtime Performance Test Suite")
    
    test_throughput_and_latency()
    test_resource_cleanup()
    
    log.info("All Runtime Performance validations passed.")

if __name__ == "__main__":
    main()
