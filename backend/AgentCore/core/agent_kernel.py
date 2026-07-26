"""
AgentKernel - The central orchestrator of the Agent Framework.

Wires together the EventBus, StateStore, SessionManager, and ExecutionEngine.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .event_bus import EventBus, Event
from .agent_state import AgentStateStore
from .session_manager import SessionManager
from .execution_engine import ExecutionEngine
from AgentCore.execution.executor import ToolExecutor
from AgentCore.orchestration.contracts import TaskContract

log = logging.getLogger(__name__)

class AgentKernel:
    """The central orchestrator controlling the lifecycle of the agent."""

    def __init__(self, session_dir: str = None):
        self.event_bus = EventBus()
        self.agent_state_store = AgentStateStore()
        self.session_manager = SessionManager(Path(session_dir))
        self.execution_engine = ExecutionEngine(
            event_bus=self.event_bus,
            agent_state_store=self.agent_state_store,
            tool_executor=ToolExecutor()
        )
        
        self._setup_event_listeners()
        log.info("[AgentKernel] Kernel initialized and wired successfully.")

    def _setup_event_listeners(self) -> None:
        """Register kernel-level observers for events."""
        self.event_bus.subscribe("ToolFinished", self._on_tool_finished)
        self.event_bus.subscribe("TaskCompleted", self._on_task_completed)
        self.event_bus.subscribe("TurnStarted", self._on_turn_started)

    async def _on_tool_finished(self, event: Event) -> None:
        """Observer hook for tool completion."""
        payload = event.payload
        log.info(f"[AgentKernel] Tool=[{payload.get('tool_name')}] finished."
                 f"Error=[{payload.get('is_error')}], Output length=[{payload.get('content_length')}]")

    async def _on_task_completed(self, event: Event) -> None:
        """Observer hook for task completion."""
        log.info(f"[AgentKernel] Task=[{event.payload.get('task_id')}] completed successfully.")
        
    async def _on_turn_started(self, event: Event) -> None:
        """Observer hook for turn execution."""
        log.info(f"[AgentKernel] Turn=[{event.payload.get('turn')}] started.")

    async def run_task(self, task_id: str, task_contract: TaskContract, tools: List[Any], max_turns: int, session_id: str = "default_session") -> str:
        """Run a specific task through the execution engine.
        
        Args:
            task_id: Unique task identifier.
            task_contract: Current agent task
            tools: Tools to expose to the engine.
            session_id: Optional session identifier for persistence.
            
        Returns:
            The task output.
        """
        log.info(f"[AgentKernel] Running task_id: [{task_id}] in session_id: [{session_id}]")
        
        # Load Agent session state
        agent_session_state = self.session_manager.load_session(session_id)
        if agent_session_state:
            self.agent_state_store = agent_session_state
            self.execution_engine.agent_state_store = self.agent_state_store
    
        # Execute Task
        try:
            executed_agent_result = await self.execution_engine.execute_task(
                task_id=task_id,
                task_contract=task_contract,
                tools=tools,
                max_turns=max_turns
            )
        except Exception as exception:
            log.error(f"[AgentKernel] Task execution failed: {exception}", exc_info=True)
            executed_agent_result = f"[AgentKernel] Error: {str(exception)}"
            
        # Save session state
        self.session_manager.save_session(session_id, self.agent_state_store)
        
        return executed_agent_result

