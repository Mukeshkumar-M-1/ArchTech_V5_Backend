import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.domain.runtime_policy import RuntimePolicy
from AgentCore.domain.action_decision import ActionDecision, ActionDefinition
from AgentCore.domain.action_result import ActionResultStatus

from AgentCore.platform.llm.adapter import MockLLMAdapter
from AgentCore.platform.llm.parser import DecisionParser
from AgentCore.platform.llm.builder import MessageBuilder
from AgentCore.platform.llm.renderer import PromptRenderer

from AgentCore.action.action_planner import ActionPlanner
from AgentCore.action.action_executor import ActionExecutor
from AgentCore.action.tool_router import ToolRouter

from AgentCore.execution.tool_registry import ToolRegistry
from AgentCore.platform.execution.sandbox_manager import SandboxManager

from AgentCore.platform.artifacts.artifact_manager import ArtifactManager
from AgentCore.platform.artifacts.diff_engine import DiffEngine

from AgentCore.knowledge.observation_bus import ObservationBus
from AgentCore.knowledge.observation_parser import ObservationParser
from AgentCore.knowledge.evidence_manager import EvidenceManager
from AgentCore.journal.execution_journal import ExecutionJournal

from AgentCore.infrastructure.telemetry_manager import TelemetryManager, CostTracker

logging.basicConfig(
    level=logging.INFO, 
    format="\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s", 
    handlers=[
        logging.StreamHandler(), 
        logging.FileHandler(r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log8.log", encoding="utf-8", mode="a")
        ]
    )

def dummy_read_file(params):
    return ActionResultStatus.SUCCESS

def dummy_write_file(params):
    return ActionResultStatus.SUCCESS

def main():
    print("\n=== Initializing Milestone 4 Platform Capabilities ===")
    policy = RuntimePolicy.create_default()
    
    # 1. Telemetry
    cost_tracker = CostTracker()
    telemetry = TelemetryManager(cost_tracker)
    
    # 2. Artifacts
    diff_engine = DiffEngine()
    artifact_manager = ArtifactManager(diff_engine)
    
    # 3. Execution & Sandbox
    registry = ToolRegistry()
    registry.register_tool("READ_FILE", lambda p: ActionResultStatus.SUCCESS)
    registry.register_tool("SEARCH_REPO", lambda p: ActionResultStatus.SUCCESS)
    registry.register_tool("SEARCH_FILES", lambda p: ActionResultStatus.SUCCESS)
    
    sandbox = SandboxManager()
    tool_router = ToolRouter(policy, registry, sandbox)
    action_planner = ActionPlanner()
    action_executor = ActionExecutor(tool_router)
    
    # 4. LLM Adapter
    llm = MockLLMAdapter()
    parser = DecisionParser()
    builder = MessageBuilder("You are a smart agent.")
    renderer = PromptRenderer()
    
    # 5. Observation & Knowledge
    bus = ObservationBus()
    obs_parser = ObservationParser(bus)
    evidence_manager = EvidenceManager()
    journal = ExecutionJournal("mission_m4")
    
    bus.subscribe(evidence_manager.process_observation)
    bus.subscribe(journal.record_observation)
    
    print("\n=== Testing Boundries ===")
    
    # Boundary 1: LLM Adapter to Parsed Decision
    print("\n[Test 1] LLM Adapter -> Parsed Decision")
    messages = builder.build_messages("What should I do?")
    raw_response = llm.invoke(messages)
    decision = parser.parse(raw_response)
    print(f"Parsed Decision Intent: {decision.chosen_action.action_type}")
    
    # Track Telemetry
    telemetry.record_llm_call(1, prompt_tokens=50, completion_tokens=150, latency_ms=1200)
    
    # Boundary 2: ActionPlanner intent expansion
    print("\n[Test 2] ActionPlanner Expansion")
    plan = action_planner.plan_actions(decision)
    print(f"Expanded into {len(plan.steps)} actions: {[s.action.action_type for s in plan.steps]}")
    
    # Boundary 3: Sandbox Security
    print("\n[Test 3] Sandbox Security Block")
    bad_result = sandbox.execute_safely("BASH", lambda p: True, {"command": "ls -la"})
    print(f"Sandbox Result: {bad_result.status.name} - {bad_result.error_message}")
    
    # Boundary 4: Artifact Diffing
    print("\n[Test 4] Artifact Diff Before Write")
    art_result = artifact_manager.apply_patch("test.py", "print('hello')\n", "print('hello world')\n")
    
    # Boundary 5: Observation Parsing & Journaling
    print("\n[Test 5] Observation Parser & Evidence Extraction")
    obs = obs_parser.parse(art_result)
    print(f"Observation ID: {obs.observation_id}")
    
    print("\n=== Telemetry Audit ===")
    summary = telemetry.get_summary()
    print(f"Total Cost: ${summary['total_cost_usd']:.4f}")
    
    print("\n=== Milestone 4 Tests Complete ===")

if __name__ == "__main__":
    main()
