"""Orchestration layer — manages generation tasks, dependencies, and goal progression.

This package provides the core orchestration logic for DocumentGenerationAgent.
"""

from .contracts import AgentDescriptor, RuntimeResult, RuntimeLifecycleStatus
from .dependency_graph import DependencyGraph
from .mission_layer import MissionParser, TaskPlanner, TaskGraphBuilder
from .lease_manager import TaskQueue, Dispatcher
from .scheduling_manager import SchedulerManager
from .worker_management import AgentCatalog, WorkerDirectory
from .orchestrator import MissionOrchestrator
from .section_registry import SectionRegistry, SectionRegistryEntry
from .context_builder import ContextBuilder

__all__ = [
    "AgentDescriptor",
    "RuntimeResult",
    "RuntimeLifecycleStatus",
    "DependencyGraph",
    "MissionParser",
    "TaskPlanner",
    "TaskGraphBuilder",
    "TaskQueue",
    "Dispatcher",
    "SchedulerManager",
    "AgentCatalog",
    "WorkerDirectory",
    "MissionOrchestrator",
    "SectionRegistry",
    "SectionRegistryEntry",
    "ContextBuilder",
]
