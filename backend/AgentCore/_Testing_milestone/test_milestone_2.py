import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.repository.snapshot import SnapshotManager
from AgentCore.repository.index import RepositoryIndex
from AgentCore.repository.query_engine import RepositoryQueryEngine
from AgentCore.memory.manager import MemoryManager
from AgentCore.context.selector import ContextSelector
from AgentCore.context.builder import ContextBuilder
from AgentCore.prompt.template import PromptTemplate
from AgentCore.prompt.registry import PromptRegistry
from AgentCore.prompt.manager import PromptManager
from AgentCore.knowledge.observation import Observation
from AgentCore.knowledge.graph import KnowledgeGraph, KnowledgeUpdater

logging.basicConfig(
    level=logging.INFO, 
    format="\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s", 
    handlers=[
        logging.StreamHandler(), 
        logging.FileHandler(r"/home/devusr/Mukesh/ArchTech_V5_1/Frontend/_Logs/Log6.log", encoding="utf-8", mode="a")
        ]
    )

def main():
    print("\n=== Testing Phase 2.1: Repository Intelligence ===")
    root_dir = Path(__file__).parent.parent
    snapshot = SnapshotManager(str(root_dir)).create_snapshot()
    repo_index = RepositoryIndex(snapshot)
    repo_engine = RepositoryQueryEngine(repo_index)
    
    print("\n=== Testing Phase 2.2: Memory Layer ===")
    memory = MemoryManager()
    memory.attach_mission("mission_99")
    memory.working_store.add_question("How does the Execution Engine work?")
    memory.working_store.record_evidence("Code Search", "Found ExecutionEngine class in execution_engine.py")
    memory.scratchpad_store.write("TODO", "Refactor turn manager.")
    print("Memory Snapshot:", memory.get_snapshot())

    print("\n=== Testing Phase 2.3: Context Assembly ===")
    selector = ContextSelector(max_history_turns=2)
    builder = ContextBuilder(selector)
    raw_history = [{"role": "user", "text": "Start"}, {"role": "assistant", "text": "Ok"}, {"role": "user", "text": "Do this"}]
    exec_context = builder.build_context(
        task_id="task_1",
        directive="Analyze the system.",
        memory_manager=memory,
        repo_engine=repo_engine,
        raw_history=raw_history
    )
    print("Execution Context Directive:", exec_context.directive)
    print("Execution Context History Length:", len(exec_context.history_window))
    
    print("\n=== Testing Phase 2.4: Prompt Runtime ===")
    registry = PromptRegistry()
    template = PromptTemplate("planning_mode")
    template.add_version("1.0", "Goal: {directive}\nMemory: {memory}", ["directive", "memory"])
    registry.register(template)
    
    prompt_manager = PromptManager(registry)
    rendered = prompt_manager.build_prompt(
        "planning_mode", 
        variables={"directive": exec_context.directive, "memory": "Has 1 open question"}
    )
    print("Rendered Prompt:\n", rendered)

    print("\n=== Testing Phase 2.5: Knowledge Layer ===")
    graph = KnowledgeGraph()
    updater = KnowledgeUpdater(graph)
    
    obs = Observation.create("AST_Parser", "Found relationship between AgentKernel and ExecutionEngine")
    updater.process_observation(obs, [
        {"source": "AgentKernel", "target": "ExecutionEngine", "relationship": "instantiates"}
    ])
    
    edges = graph.query_relationships("AgentKernel")
    for e in edges:
        print(f"Graph Edge: {e.source_entity} --[{e.relationship}]--> {e.target_entity} (obs: {e.evidence_observation_id})")

if __name__ == "__main__":
    main()
