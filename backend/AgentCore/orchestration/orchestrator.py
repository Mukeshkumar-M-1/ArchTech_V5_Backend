"""
Mission Orchestrator

Encapsulates the M5 Distributed Orchestration Pipeline.
Replaces the inline cluster setup in routes.py with a formalized architectural boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from system_config import (
    get_project_generated_document_output_dir,
    start_new_version,
    record_section_version,
)

from AgentCore.orchestration.contracts import AgentDescriptor
from AgentCore.orchestration.runtime_adapter import RuntimeAdapter
from AgentCore.orchestration.worker_management import AgentCatalog, WorkerDirectory, HeartbeatMonitor
from AgentCore.orchestration.queue_and_dispatch import TaskQueue, LeaseManager, AssignmentTracker, Dispatcher
from AgentCore.orchestration.scheduling import CapabilityResolver, LeastBusyPolicy, Scheduler
from AgentCore.orchestration.mission_layer import MissionParser, TaskPlanner, TaskGraphBuilder, MissionStateManager, ReadyTaskSelector
from AgentCore.orchestration.result_layer import ResultProcessor, MissionStateUpdater
from AgentCore.execution.pause_manager import is_paused

log = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 3

# Regex to match markdown headings (e.g. "# Title", "## Subtitle")
_MARKDOWN_HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*#$)?\s*$')


def _slugify(text: str) -> str:
    """Convert heading text to a URL-friendly slug."""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text.strip())
    return text.lower()


def _parse_markdown_headings(content: str) -> list[dict]:
    """Extract markdown headings from content as structured heading nodes."""
    headings = []
    for match in _MARKDOWN_HEADING_PATTERN.finditer(content):
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append({
            "level": level,
            "text": text,
            "id": _slugify(text),
        })
    return headings


def _build_heading_tree(flat_headings: list[dict]) -> list[dict]:
    """Build a nested heading tree from flat headings."""
    root: list[dict] = []
    stack: list[tuple[int, dict]] = []  # (level, node)

    for heading_data in flat_headings:
        node = {
            "level": heading_data["level"],
            "text": heading_data["text"],
            "id": heading_data["id"],
            "children": [],
        }
        while stack and stack[-1][0] >= heading_data["level"]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root.append(node)
        stack.append((heading_data["level"], node))
    return root

class MissionOrchestrator:
    """Coordinates multi-agent execution of a mission using the M5 TaskGraph pipeline."""

    def __init__(self, project_id: str, num_workers: int = DEFAULT_MAX_WORKERS):
        """Initialize the local M5 cluster."""
        self.project_id = project_id
        self.num_workers = num_workers
        self.agent_catalog = AgentCatalog()
        self.worker_directory = WorkerDirectory()
        self.agent_run_times_adapter = {}
        self.agent_heart_beats = []
        self.task_queue = TaskQueue()
        self.lease_manager = LeaseManager()
        self.assignment_tracker = AssignmentTracker()
        
    async def boot_cluster(self):
        """Boot up the local worker cluster."""
        for worker_number in range(1, self.num_workers + 1):
            agent_id = f"worker_00{worker_number}"
            # Register worker capability profile
            agent_descriptor = AgentDescriptor(
                agent_id=agent_id, 
                agent_profile="General_Purpose",
                agent_capabilities=frozenset(["bash", "python"]),
                agent_resource_limits={},
                agent_supported_contract_versions=frozenset(["v1"])
            )
            self.agent_catalog.register_profile(agent_descriptor)
            
            # Start heartbeat monitoring
            heart_beat_monitor = HeartbeatMonitor(agent_id=agent_id, worker_directory=self.worker_directory)
            agent_heart_beat_task = asyncio.create_task(heart_beat_monitor.run())
            self.agent_heart_beats.append(agent_heart_beat_task)
            
            # Initialize agent runtime adapter
            self.agent_run_times_adapter[agent_id] = RuntimeAdapter(agent_id=agent_id, project_id=self.project_id)
            
        await asyncio.sleep(0.1) # Yield to let heartbeats start
        
        # Initialize Dispatcher for run time adapter
        self.dispatcher = Dispatcher(runtime_adapter=self.agent_run_times_adapter)

        # Initialize Scheduler for agent
        self.scheduler = Scheduler(
            capability_resolver=CapabilityResolver(self.agent_catalog),
            worker_directory=self.worker_directory,
            scheduling_policy=LeastBusyPolicy(),
            lease_manager=self.lease_manager,
            dispatcher=self.dispatcher,
            assignment_tracker=self.assignment_tracker
        )
        log.info(f"[MissionOrchestrator] Booted cluster with {self.num_workers} workers.")

    async def execute_mission(
        self,
        project_id: str,
        template_type: str,
        goal: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a mission and yield SSE-compatible event dictionaries.
        
        Args:
            project_id: Project identifier.
            template_type: Template type (e.g., srs, hld).
            goal: The overarching generation goal string.
            
        Yields:
            Dict representing progress and chunk events.
        """
        # Ensure cluster is booted
        if not self.agent_run_times_adapter:
            await self.boot_cluster()

        # Initialize Misson State Manager
        mission_state_manager = MissionStateManager()
        log.info(f"[MissionOrchestrator] Initializing state manager for project {project_id}")

        # Initialize Mission specification
        mission_specification = MissionParser().parse(raw_input=goal, project_id=project_id, template_type=template_type)
        log.info(f"[MissionOrchestrator] Initializing Mission specification for {project_id}")

        # Initialize Task planning
        planned_tasks = TaskPlanner().plan(mission_specification=mission_specification)
        log.info(f"[MissionOrchestrator] Initializing Task planning for {project_id}")

        # Initialize Task graph
        task_graph = TaskGraphBuilder().build_graph(planned_tasks=planned_tasks, mission_specification=mission_specification)
        log.info(f"[MissionOrchestrator] Initializing Task graph for {project_id}")
            
        # Initialize Mission state manager from graph
        mission_state_manager.initialize_from_graph(task_graph=task_graph)
        log.info(f"[MissionOrchestrator] Initializing Mission state manager from graph for {project_id}")
        
        # Initialize Ready Task Selector
        task_selector = ReadyTaskSelector(task_graph=task_graph, task_queue=self.task_queue)
        log.info(f"[MissionOrchestrator] Initializing Ready Task Selector for {project_id}")
        
        # Initialize State Updater
        mission_state_updater = MissionStateUpdater(task_graph=task_graph, mission_state_manager=mission_state_manager)
        log.info(f"[MissionOrchestrator] Initializing State Updater for {project_id}")
        
        # Initialize Result Processor
        result_processor = ResultProcessor(lease_manager=self.lease_manager, mission_state_updater=mission_state_updater, worker_directory=self.worker_directory)
        log.info(f"[MissionOrchestrator] Initializing Result Processor for {project_id}")
        

        yield {
            "type": "mission_started",
            "total_tasks": mission_state_manager.total_tasks,
            "project_id": project_id
        }

        # Bump document-level version at generation start
        document_version = start_new_version(project_id, template_type)
        log.info(f"[MissionOrchestrator] Document version {document_version} started for {project_id}")

        yield {
            "type": "gen_start",
            "section_count": mission_state_manager.total_tasks,
            "document_version": document_version,
        }
        
        # Dispatch pending task list
        pending_dispatch_tasks = []
        
        while mission_state_manager.completed_tasks < mission_state_manager.total_tasks:
            # Check for pause signal
            if is_paused(project_id):
                yield {"type": "paused", "reason": "user paused"}
                return

            # Inject traceability data for ready tasks (before they're marked running)
            for task_node in task_graph.task_node.values():
                if task_node.is_ready:
                    from AgentCore.orchestration.traceability_builder import build_traceability_json
                    traceability_data = build_traceability_json(project_id)
                    task_node.task.execution_context["traceability_data"] = traceability_data
                    log.info(f"[MissionOrchestrator] Injected traceability data for section {task_node.task.execution_context.get('section_number')} (task {task_node.task.task_id})")

            # Build Ready Task
            task_selector.build_ready_tasknode()

            # Run scheduling cycle to dispatch work
            agent_spawned_task_list = await self.scheduler.run_scheduling_cycle(self.task_queue)
            pending_dispatch_tasks.extend(agent_spawned_task_list)
            
            # Check for completed tasks
            if pending_dispatch_tasks:
                agent_completed_task, agent_pending_task = await asyncio.wait(
                    pending_dispatch_tasks,
                    timeout=0.1,
                    return_when=asyncio.FIRST_COMPLETED
                )
                pending_dispatch_tasks = list(agent_pending_task)
                
                # Sort by task_id so streaming order is deterministic
                # (asyncio.wait returns a set, which has no ordering guarantee)
                completed_with_ids = []
                for task_result in agent_completed_task:
                    result = task_result.result()
                    completed_with_ids.append((result.task_id, result))

                completed_with_ids.sort(key=lambda x: x[0])

                for _, agent_result_data in completed_with_ids:
                    try:
                        result_processor.process_result(agent_result_data)

                        # Extract original task context for rich frontend events
                        agent_task_node = task_graph.task_node.get(agent_result_data.task_id)
                        agent_execution_context = agent_task_node.task.execution_context if agent_task_node else {}
                        task_section_number = agent_execution_context.get("section_number", "unknown")
                        task_section_heading = agent_execution_context.get("section_heading", "unknown")

                        # Emit Start Event for the completed section
                        yield {
                            "type": "section_start",
                            "section_number": task_section_number,
                            "heading": task_section_heading,
                            "section_current": mission_state_manager.completed_tasks,
                            "section_total": mission_state_manager.total_tasks,
                        }

                        # Emit Progress Event
                        progress_pct = int((mission_state_manager.completed_tasks / max(1, mission_state_manager.total_tasks)) * 100)
                        yield {
                            "type": "progress",
                            "progress": progress_pct,
                            "phase": f"Generating: {task_section_heading}",
                            "section_current": mission_state_manager.completed_tasks,
                            "section_total": mission_state_manager.total_tasks,
                        }

                        # Extract generated result
                        generated_result_data = agent_result_data.produced_evidence or ""

                        # Write section content with document-level version
                        section_filename = agent_execution_context.get("section_filename", f"{task_section_number}_unknown.md")
                        versioned_path = Path(get_project_generated_document_output_dir(project_id)) / section_filename.replace(".md", ".json")

                        if versioned_path.exists():
                            with open(versioned_path, "r", encoding="utf-8") as f:
                                _section_data = json.load(f)
                            _section_data["document_version"] = document_version
                            _section_data["document_data"][str(document_version)] = {
                                "version": document_version,
                                "generated_data": generated_result_data
                            }
                            with open(versioned_path, "w", encoding="utf-8") as f:
                                json.dump(_section_data, f, indent=2)
                        else:
                            _section_data = {
                                "section_number": task_section_number,
                                "section_filename": section_filename,
                                "document_version": document_version,
                                "document_data": {
                                    str(document_version): {"version": document_version, "generated_data": generated_result_data}
                                }
                            }
                            with open(versioned_path, "w", encoding="utf-8") as f:
                                json.dump(_section_data, f, indent=2)

                        # Record this section in the central version tracker
                        record_section_version(project_id, section_filename, document_version)
                        log.info(f"[MissionOrchestrator] Wrote section {task_section_number} to {versioned_path.name}")

                        # Emit Chunk the final LLM output for the frontend stream
                        for chunk_idx in range(0, max(1, len(generated_result_data)), 500):
                            chunk_data = generated_result_data[chunk_idx : chunk_idx + 500]
                            if chunk_data.strip() or not generated_result_data:
                                yield {
                                    "type": "section_chunk",
                                    "section_number": task_section_number,
                                    "content": chunk_data,
                                }

                        # Parse headings from the generated content for document outline
                        section_flat_headings = _parse_markdown_headings(generated_result_data)
                        section_heading_tree = _build_heading_tree(section_flat_headings)

                        # Emit Complete Event
                        yield {
                            "type": "section_complete",
                            "section_number": task_section_number,
                            "heading": task_section_heading,
                            "headings_parsed": section_heading_tree,
                            "tools_used": getattr(agent_result_data, "tool_calls_used", []),
                        }

                    except Exception as exception:
                        log.error(f"[MissionOrchestrator] Task Execution Error: {exception}", exc_info=True)
                        yield {"type": "task_failed", "error": str(exception)}
                        mission_state_manager.completed_tasks += 1
            else:
                # Idle backoff
                await asyncio.sleep(0.1)

        yield {
            "type": "gen_complete",
            "total_sections": mission_state_manager.completed_tasks,
            "document_version": document_version,
            "document_length": 1000
        }
