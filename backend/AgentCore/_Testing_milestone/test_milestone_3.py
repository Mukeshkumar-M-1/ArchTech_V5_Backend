import logging
from pathlib import Path
import sys
import logging

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.domain.runtime_policy import RuntimePolicy
from AgentCore.domain.reasoning_state import ReasoningState
from AgentCore.context.execution_context import ExecutionContext

from AgentCore.knowledge.observation_bus import ObservationBus
from AgentCore.knowledge.observation_engine import ObservationEngine
from AgentCore.journal.execution_journal import ExecutionJournal

from AgentCore.action.tool_router import ToolRouter
from AgentCore.execution.tool_registry import ToolRegistry
from AgentCore.platform.execution.sandbox_manager import SandboxManager
from AgentCore.action.action_executor import ActionExecutor

from AgentCore.reasoning.reason_engine import ReasoningEngine
from AgentCore.reasoning.turn_manager import TurnManager

from AgentCore.cognitive.reflection_engine import ReflectionEngine
from AgentCore.cognitive.verifier_engine import VerifierEngine
from AgentCore.cognitive.repair_engine import RepairEngine

from AgentCore.orchestration.workflow import LoopController, WorkflowRunner
from AgentCore.orchestration.planner_engine import PlanningEngine, TaskScheduler, MissionManager

logging.basicConfig(
    level=logging.INFO, 
    format="\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s", 
    handlers=[
        logging.StreamHandler(), 
        logging.FileHandler(r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log7.log", encoding="utf-8", mode="a")
        ]
    )

def main():
    print("\n=== Initializing Milestone 3 Architecture ===")
    policy = RuntimePolicy.create_default()
    
    # 1. Bus & Journal
    obs_bus = ObservationBus()
    journal = ExecutionJournal("mission_001")
    obs_bus.subscribe(journal.record_observation)
    
    # 2. Tactical Layer
    obs_engine = ObservationEngine(obs_bus)
    tool_register = ToolRegistry()
    sandbox_manager = SandboxManager()
    tool_router = ToolRouter(policy, tool_register, sandbox_manager)
    action_exec = ActionExecutor(tool_router)
    reasoning = ReasoningEngine(policy)
    turn_manager = TurnManager(reasoning, action_exec, obs_engine)
    
    # 3. Cognitive Branches
    reflection = ReflectionEngine()
    verifier = VerifierEngine()
    repair = RepairEngine()
    
    # 4. Controllers & Planners
    loop_controller = LoopController(policy, turn_manager, reflection, verifier, repair)
    runner = WorkflowRunner(loop_controller)
    planner = PlanningEngine()
    scheduler = TaskScheduler()
    mission_manager = MissionManager(planner, scheduler)
    
    print("\n=== Running Mission ===")
    mission_manager.start_mission("Implement Agent Core.")
    task = scheduler.get_next_task()
    
    if task:
        # Create an immutable Context and mutable State
        context = ExecutionContext(
            task_id=task.task_id,
            directive=task.directive,
            memory_snapshot={},
            repository_summary="",
            history_window=[]
        )
        state = ReasoningState(current_goal=task.directive)
        
        # Execute the task
        status = runner.run_task(context, state)
        if status.name == "COMPLETED":
            scheduler.mark_completed(task.task_id)
            
    print("\n=== Execution Journal Audit ===")
    for entry in journal.get_history():
        print(f"[{entry['type']}] {entry['payload'].get('source_tool')} -> Conf: {entry['payload'].get('confidence')}")

if __name__ == "__main__":
    main()
