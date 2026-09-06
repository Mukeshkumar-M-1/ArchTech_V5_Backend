"""
Runtime Adapter

Implements the IAgentRuntime interface, encapsulating the M4.5 internal execution components 
(EventBus, StateMachine, CheckpointManager, LoopController) into a clean Black-Box.
"""

import logging
from typing import Any

from AgentCore.orchestration.contracts import (
    IAgentRuntime, 
    TaskContract, 
    RuntimeResult, 
    RuntimeLifecycleStatus
)
from AgentCore.event_bus import EventBus
from AgentCore.runtime.state_machine import RuntimeStateMachine, RuntimeState
from AgentCore.runtime.cancellation_manager import CancellationManager
from AgentCore.runtime.interrupt_manager import InterruptManager
from AgentCore.observability.agent_kernel import GenerationAgentKernel
from AgentCore.execution.message_manager import SSEGenerationMessageManager
from system_config import get_session_transcript_dir

log = logging.getLogger(__name__)

class RuntimeAdapter(IAgentRuntime):
    """
    Adapter that exposes the orchestration-friendly IAgentRuntime interface
    while internally managing the complex M4.5 execution loop components.
    """
    
    def __init__(self, agent_id: str, project_id: str, message_manager: SSEGenerationMessageManager | None=None):
        self.agent_id = agent_id
        self._message_manager = message_manager
        self.event_bus = EventBus()
        self.state_machine = RuntimeStateMachine(event_bus=self.event_bus)
        self.cancellation_manager = CancellationManager(event_bus=self.event_bus, state_machine=self.state_machine)
        self.interrupt_manager = InterruptManager(event_bus=self.event_bus, state_machine=self.state_machine)
        self.agent_kernel = GenerationAgentKernel(
            get_session_transcript_dir(project_id=project_id),
            message_manager=self._message_manager,
        )
        
        log.info(f"[RuntimeAdapter] Initialized for worker {self.agent_id}")

    def _reset_internals(self):
        """Re-initializes frozen M4.5 terminal states for a new task."""
        log.info(f"[RuntimeAdapter] Reset Internal hooks")
        self.state_machine = RuntimeStateMachine(event_bus=self.event_bus)
        self.cancellation_manager = CancellationManager(event_bus=self.event_bus, state_machine=self.state_machine)
        self.interrupt_manager = InterruptManager(event_bus=self.event_bus, state_machine=self.state_machine)

    async def execute(self, task: TaskContract) -> RuntimeResult:
        log.info(f"[RuntimeAdapter - {self.agent_id}] Executing task: {task.task_id} - {task.goal}")
        
        self._reset_internals()
        # Transition state machine
        self.state_machine.transition(RuntimeState.READY)        
        try:
            self.state_machine.transition(RuntimeState.RUNNING)

            agent_result = await self.agent_kernel.run_task(
                task_id=task.task_id,
                task_contract=task,
                tools= ["FileRead", "Bash", "Glob", "Search", "RequestUserInput"],
                session_id=task.task_id,
                max_turns= 50
            )

            self.state_machine.transition(RuntimeState.COMPLETED)
            
            return RuntimeResult(
                task_id=task.task_id,
                status=RuntimeLifecycleStatus.COMPLETED,
                produced_evidence=agent_result,
                cost_usd=0.01  
            )
            
        except Exception as exception:
            log.error(f"[RuntimeAdapter - {self.agent_id}] Execution failed: {exception}")
            self.state_machine._current_state = RuntimeState.FAILED
            
            return RuntimeResult(
                task_id=task.task_id,
                status=RuntimeLifecycleStatus.FAILED,
                failure_reason=str(exception)
            )

    async def pause(self) -> None:
        log.info(f"[RuntimeAdapter - {self.agent_id}] Pausing execution.")
        self.event_bus.publish("InterruptRequested", {"reason": "Orchestrator Pause"})

    async def resume(self) -> None:
        log.info(f"[RuntimeAdapter - {self.agent_id}] Resuming execution.")
        if self.state_machine.current_state == RuntimeState.PAUSED:
            self.state_machine.transition(RuntimeState.RUNNING)

    async def checkpoint(self) -> str:
        log.info(f"[RuntimeAdapter - {self.agent_id}] Forcing explicit checkpoint.")
        if self.state_machine.current_state != RuntimeState.CHECKPOINTING:
            current = self.state_machine.current_state
            # Force transition for demonstration of interface adherence
            self.state_machine._current_state = RuntimeState.CHECKPOINTING
            checkpoint_id = f"chk_{self.agent_id}_{int(self.event_bus._event_counter)}"
            self.state_machine._current_state = current
            return checkpoint_id
        return "chk_existing"

    async def cancel(self) -> None:
        log.warning(f"[RuntimeAdapter - {self.agent_id}] Cancelling execution!")
        self.event_bus.publish("CancelRequested")
        
    async def status(self) -> RuntimeLifecycleStatus:
        internal_state = self.state_machine.current_state
        
        # Map internal granular states to external orchestration status
        mapping = {
            RuntimeState.CREATED: RuntimeLifecycleStatus.PAUSED,
            RuntimeState.READY: RuntimeLifecycleStatus.PAUSED,
            RuntimeState.RUNNING: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.WAITING_TOOL: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.REFLECTING: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.VERIFYING: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.CHECKPOINTING: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.REPAIRING: RuntimeLifecycleStatus.RUNNING,
            RuntimeState.PAUSED: RuntimeLifecycleStatus.PAUSED,
            RuntimeState.CANCELLED: RuntimeLifecycleStatus.CANCELLED,
            RuntimeState.FAILED: RuntimeLifecycleStatus.FAILED,
            RuntimeState.COMPLETED: RuntimeLifecycleStatus.COMPLETED
        }
        return mapping.get(internal_state, RuntimeLifecycleStatus.FAILED)
