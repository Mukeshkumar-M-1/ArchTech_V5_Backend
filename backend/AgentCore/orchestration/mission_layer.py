"""
Mission Layer

Owns the high-level objective, execution graph, and state management.
"""

import logging
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
import uuid
import json

from AgentCore.orchestration.contracts import TaskContract
from AgentCore.orchestration.lease_manager import TaskQueue

log = logging.getLogger(__name__)

# --- Graph Models ---

@dataclass
class TaskNode:
    task: TaskContract
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    is_completed: bool = False
    is_running: bool = False
    
    @property
    def is_ready(self) -> bool:
        return not self.is_completed and not self.is_running and len(self.dependencies) == 0

class TaskGraph:
    """Manages node dependencies (dependencies, dependents, critical_path)."""
    def __init__(self):
        self.task_node: Dict[str, TaskNode] = {}
        
    def add_task(self, task: TaskContract, dependencies: List[str] = None):
        if dependencies is None:
            dependencies = []
            
        new_task_node = TaskNode(task=task, dependencies=set(dependencies))
        self.task_node[task.task_id] = new_task_node
        
        # Update dependents of upstream tasks
        for dependency_data_item in dependencies:
            if dependency_data_item in self.task_node:
                self.task_node[dependency_data_item].dependents.add(task.task_id)
            
        # log.info(f"[TaskGraph] Added TaskNode [{task.task_id}] with [{len(self.task_node[task.task_id].dependencies)}] dependencies and with [{len(self.task_node[task.task_id].dependents)}] dependents")
        
    def complete_task(self, task_id: str):
        if task_id not in self.task_node:
            return
            
        current_task_node = self.task_node[task_id]
        current_task_node.is_completed = True
        current_task_node.is_running = False
        
        # Unblock dependents
        for dep_id in current_task_node.dependents:
            dep_node = self.task_node.get(dep_id)
            if dep_node and task_id in dep_node.dependencies:
                dep_node.dependencies.remove(task_id)
        
        log.info(f"[TaskGraph] Marked Task {task_id} as completed. Unblocked {len(current_task_node.dependents)} dependents.")

# --- Mission State ---

@dataclass
class MissionSpecification:
    mission_id: str
    project_id: str
    template_type: str
    goal: str
    template_context: Dict[str, str]
    knowledge_content: str = ""
    internal_memory_content: str = ""
    document_tree_data: list = field(default_factory=list)
    dependency_graph: Any = None

class MissionParser:
    """Parses the raw user request/mission."""
    def parse(self, raw_input: str, project_id: str, template_type: str) -> MissionSpecification:
        # Parse registry and dependencies directly
        from AgentCore.orchestration.section_registry import SectionRegistry
        from AgentCore.orchestration.dependency_graph import DependencyGraph

        # log.info(f"[MissionParser] Parsing mission for project {project_id}, type {template_type}")

        # Build Mission ID
        mission_id = str(uuid.uuid4())
        # log.info(f"[MissionParser] Built mission ID: {mission_id}")

        # Build Section Registry Entry
        section_registry_entry = SectionRegistry.parse_template_dir(project_id=project_id)
        if not section_registry_entry:
            raise ValueError(f"Failed to initialize templates for project {project_id}: No sections found in template directory")

        # Build Dependency Graph
        dependency_graph = DependencyGraph(project_id)
        
        # Build Document Tree Data
        document_tree_data = dependency_graph.get_document_tree(project_id=project_id)
        
        # Build global knowledge content block
        knowledge_content = self._build_knowledge_index_block(project_id=project_id)

        # Build global internal memory block
        internal_memory_content = self._build_internal_memory_index_block(project_id=project_id)

        # Build template context
        template_context = SectionRegistry.build_section_content_data(project_id=project_id, section_registry_entry=section_registry_entry)

        return MissionSpecification(
            mission_id=mission_id,
            project_id=project_id,
            template_type=template_type,
            goal=raw_input,
            template_context=template_context,
            knowledge_content=knowledge_content,
            internal_memory_content=internal_memory_content,
            document_tree_data=document_tree_data,
            dependency_graph=dependency_graph
        )
        
    def _build_knowledge_index_block(self, project_id: str) -> str:
        """Build a compact index of available knowledge files with paths + content."""
        from system_config import get_knowledge_source_dir

        parts = []
        knowledge_dir = get_knowledge_source_dir(project_id)

        if not knowledge_dir.exists():
            log.info(f"[Knowledge] Directory not found: {knowledge_dir}")
            return "No knowledge files found."

        for fname in ["overview.md", "MEMORY.md", "relationships.md"]:
            fpath = knowledge_dir / fname
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                if "---" in content:
                    content = content.split("---", 2)[-1].strip()
                parts.append(f"## {fname}\n\n{content}")

        for subdir in ("requirements", "categories", "subcategories"):
            sdir = knowledge_dir / subdir
            if sdir.exists():
                files = sorted([filepath.name, filepath.resolve()] for filepath in sdir.iterdir() if filepath.is_file())
                if files:
                    lines = "\n".join(f"  - [{file_name}][{file_path}]" for file_name,file_path in files)
                    parts.append(f"## {subdir}/\n{lines}")

        return "\n\n".join(parts)

    def _build_internal_memory_index_block(self, project_id: str) -> str:
        """Build a compact index of available Internal Memory files with paths + content."""
        import shutil

        from system_config import get_project_internal_memory_source_dir, get_internal_memory_source_data_dir

        internal_memory_parts = []
        internal_memory_dir = get_project_internal_memory_source_dir(project_id=project_id)

        if not internal_memory_dir.exists():
            log.info(f"[Internal_Memory] Directory not found: {internal_memory_dir}")
            return "No internal memory files found."

        # Copy source data if project internal memory dir is empty
        if not any(internal_memory_dir.iterdir()):
            source_data_dir = get_internal_memory_source_data_dir()
            if source_data_dir.exists():
                log.info(f"[Internal_Memory] Empty project dir — copying from {source_data_dir} → {internal_memory_dir}")
                for source_data_item in source_data_dir.iterdir():
                    dest = internal_memory_dir / source_data_item.name
                    if source_data_item.is_dir():
                        shutil.copytree(source_data_item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_data_item, dest)
            else:
                log.warning(f"[Internal_Memory] Source data dir not found: {source_data_dir}")
                return "No internal memory files found."

        for fname in ["MEMORY.md"]:
            file_path = internal_memory_dir / fname
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                if "---" in content:
                    content = content.split("---", 2)[-1].strip()
                internal_memory_parts.append(f"## {fname}\n\n{content}")

        # List all subdirectories and their files
        for subdir in sorted(internal_memory_dir.iterdir()):
            if subdir.is_dir():
                sub_dir_files = sorted(subdir.iterdir())
                if sub_dir_files:
                    file_path_data = "\n".join(f"  - [{file_item.name}][{str(file_item.resolve())}]" for file_item in sub_dir_files if file_item.is_file())
                    internal_memory_parts.append(f"## {subdir.name}/\n{file_path_data}")
        
        return ("\n\n").join(internal_memory_parts)
        
    
class TaskPlanner:
    """Decides the actual work required to satisfy the specification."""
    def plan(self, mission_specification: MissionSpecification) -> List[dict]:
        log.info(f"[TaskPlanner] Planning tasks for mission {mission_specification.mission_id} ({len(mission_specification.document_tree_data)} sections)")
        build_task_list = []
        section_dependency_data = []
        
        # Build tasks based on parsed template sections
        for document_entry_data in mission_specification.document_tree_data:
            section_number = document_entry_data["section_number"] if isinstance(document_entry_data, dict) else getattr(document_entry_data, "section_number")
            section_heading = document_entry_data["heading"] if isinstance(document_entry_data, dict) else getattr(document_entry_data, "heading")
            section_filename = document_entry_data["filename"] if isinstance(document_entry_data, dict) else getattr(document_entry_data, "filename")
            section_sub_section = document_entry_data["subsections"] if isinstance(document_entry_data, dict) else getattr(document_entry_data, "subsections")
            section_dependency_data = []

            if mission_specification.dependency_graph:
                section_dependency = list(mission_specification.dependency_graph.get_prerequisites(section_filename))

                if section_dependency is None:
                    section_dependency_data = []
                else:
                    for section_dependency_item in section_dependency:
                        section_dependency_data.append(f"{mission_specification.project_id}_section_{section_dependency_item}")
                
            build_task_list.append({
                "section_task_id": f"{mission_specification.project_id}_section_{section_filename}",
                "section_number": section_number,
                "secion_heading": section_heading,
                "section_filename": section_filename,                
                "section_subsection": section_sub_section,
                "section_goal": "Produce the final section content using the provided template, knowledge data, and task instructions.",
                "section_dependency": section_dependency_data
            })
            
        return build_task_list

class TaskGraphBuilder:
    """Generates a DAG of TaskContracts based on the planner."""
    def build_graph(self, planned_tasks: List[dict], mission_specification: MissionSpecification) -> TaskGraph:
        
        build_task_graph = TaskGraph()        
        
        for planned_task_item in planned_tasks:
            section_template_content = mission_specification.template_context[planned_task_item["section_number"]]
            section_task_contract = TaskContract(
                task_id=planned_task_item["section_task_id"],
                goal=planned_task_item["section_goal"],
                execution_context={
                    "project_id": mission_specification.project_id,
                    "section_number": planned_task_item["section_number"],
                    "section_heading": planned_task_item["secion_heading"],
                    "section_filename": planned_task_item["section_filename"],
                    "section_subsection": planned_task_item["section_subsection"],
                    "section_dependency_data": planned_task_item["section_dependency"],
                    "section_template_content": section_template_content,
                    "knowledge_content": mission_specification.knowledge_content,
                    "internal_memory_content": mission_specification.internal_memory_content,
                    "required_capabilities": ["bash", "python"]
                }
            )

            build_task_graph.add_task(task=section_task_contract, dependencies=planned_task_item["section_dependency"])
        return build_task_graph

# --- State Management ---

class MissionStateManager:
    """Tracks global state of the mission."""
    def __init__(self):
        self.total_tasks = 0
        self.completed_tasks = 0
        self.pending_tasks = 0
        self.failed_tasks = 0
        
    def initialize_from_graph(self, task_graph: TaskGraph):
        self.total_tasks = len(task_graph.task_node)
        self.pending_tasks = self.total_tasks
        self.completed_tasks = 0
        self.failed_tasks = 0

# --- Queue Feeder ---

class ReadyTaskSelector:
    """Exposes only unblocked tasks to the Queue."""
    def __init__(self, task_graph: TaskGraph, task_queue: TaskQueue):
        self.task_graph = task_graph
        self.task_queue = task_queue
        
    def build_ready_tasknode(self):
        """Finds ready tasks and pushes them to the queue."""
        total_running_task_count = 0
        for current_task_node in self.task_graph.task_node.values():
            if current_task_node.is_ready:
                current_task_node.is_running = True # Mark as running so we don't enqueue twice
                self.task_queue.enqueue(current_task_node.task)
                total_running_task_count += 1
                
        if total_running_task_count > 0:
            log.info(f"[ReadyTaskSelector] Swept and enqueued {total_running_task_count} ready tasks.")
