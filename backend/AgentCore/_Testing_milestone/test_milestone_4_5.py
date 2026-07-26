import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.infrastructure.event_bus import EventBus
from AgentCore.infrastructure.policy_manager import PolicyManager
from AgentCore.runtime.state_machine import RuntimeStateMachine, RuntimeState
from AgentCore.runtime.failure_classifier import FailureClassifier
from AgentCore.runtime.cancellation_manager import CancellationManager
from AgentCore.runtime.interrupt_manager import InterruptManager, InterruptScope
from AgentCore.runtime.checkpoint_manager import CheckpointManager, Checkpoint
from AgentCore.journal.execution_journal import ExecutionJournal
from AgentCore.runtime.replay_engine import ReplayEngine, ReplayMode

logging.basicConfig(
    level=logging.INFO, 
    format="\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s", 
    handlers=[
        logging.StreamHandler(), 
        logging.FileHandler(r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log7.log", encoding="utf-8", mode="a")
        ]
    )

def main():
    print("\n=== Initializing Milestone 4.5 Runtime Hardening ===")
    
    # 1. Core Infrastructure
    bus = EventBus()
    state_machine = RuntimeStateMachine(bus)
    
    # 2. Hardening Managers
    cancellation = CancellationManager(bus, state_machine)
    interrupts = InterruptManager(bus, state_machine)
    classifier = FailureClassifier()
    policy = PolicyManager()
    
    # 3. Checkpointing & Replay
    checkpoints = CheckpointManager("./test_checkpoints")
    journal = ExecutionJournal("mission_m45")
    replay = ReplayEngine(journal, checkpoints)
    
    print("\n=== Testing State Machine ===")
    try:
        state_machine.transition(RuntimeState.READY)
        state_machine.transition(RuntimeState.RUNNING)
        state_machine.transition(RuntimeState.WAITING_TOOL)
    except ValueError as e:
        print(f"State transition failed: {e}")
        
    print(f"Current State: {state_machine.current_state.name}")
    
    print("\n=== Testing Failure Classifier ===")
    strategy = classifier.classify_error("TimeoutError", "The API request experienced a timeout after 30s")
    print(f"Classified 'timeout' error as Strategy: {strategy.name}")
    
    print("\n=== Testing Policy Manager ===")
    eval_safe = policy.evaluate("BASH", {"command": "ls -la"})
    print(f"Safe Action Decision: {eval_safe.decision.name} - {eval_safe.reason}")
    
    eval_unsafe = policy.evaluate("BASH", {"command": "rm -rf /cache"})
    print(f"Unsafe Action Decision: {eval_unsafe.decision.name} - {eval_unsafe.reason}")
    if eval_unsafe.rewritten_action:
        print(f"Rewritten to: {eval_unsafe.rewritten_parameters['command']}")
        
    print("\n=== Testing Interrupts ===")
    bus.publish("InterruptRequested", {"scope": InterruptScope.MISSION, "reason": "User requested pause."})
    print(f"State after interrupt: {state_machine.current_state.name}")
    
    print("\n=== Testing Checkpoint Manager ===")
    ckpt = Checkpoint(
        checkpoint_id="test_m45_01",
        version="v1",
        runtime_state=state_machine.current_state.name,
        reasoning_state={"hypothesis": "Testing"},
        memory_snapshot={"context": 10},
        journal_offset=5,
        pending_events=[{"type": "ResumeMission"}]
    )
    path = checkpoints.save_checkpoint(ckpt)
    loaded_ckpt = checkpoints.load_checkpoint(ckpt.checkpoint_id)
    print(f"Loaded Checkpoint: {loaded_ckpt.checkpoint_id}, State: {loaded_ckpt.runtime_state}")

    print("\n=== Milestone 4.5 Initialization Complete ===")

if __name__ == "__main__":
    main()
