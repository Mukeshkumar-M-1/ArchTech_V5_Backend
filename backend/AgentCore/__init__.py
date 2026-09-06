"""AgentCore — Unified agent execution platform.

Merged from the original tools/ and Document_Generate/ packages.
This is the single import path for all agent functionality.

Usage:
    from AgentCore.execution.query_loop import QueryLoop
    from AgentCore.agents.document_generate_agent import DocumentGenerationAgent
    from AgentCore.event_bus import EventBus
"""

from __future__ import annotations

# ====================================================================
# Execution layer — replaces tools/__init__.py
# ====================================================================

from .execution.tool_registry import ToolRegistry, ToolDefinition, register, registry
from .execution import builtins  # noqa: F401 — registers all tool definitions

from .execution.tool_executor import ToolExecutor, ToolExecutionResult
from .execution.query_loop import QueryLoop
from .execution.agent_spawner import AgentSpawner, AgentResult
from .execution.agent_spawner import AgentSpawner, AgentResult
from .execution.permission_manager import PermissionManager, PermissionMode
from .execution.context_compaction import ContextCompactPipeline, ContextToolCompact, ContextAssistantCompact, ContextAutoCompact
from .execution.session_memory import SessionMemoryExtractor, SessionMemoryCache, CompactSummary
from .execution.system_prompt import (
    SystemPromptManager, StaticBlockBuilder, DynamicBlockBuilder,
    UserContextBuilder, SystemContextBuilder, SystemPromptBlock, DYNAMIC_BOUNDARY,
)
from .execution.abort_controller import AbortController, AbortSignal, get_hierarchy, get_task_store
from .execution.session_manager import ChatSessionManager, GenerationSessionManager, SessionRecord
from .execution.agent_cleanup import AgentCleaner
from .execution.transcript_writer import TranscriptWriter, TranscriptEntry, get_transcript_dir, get_transcript_path

# Models (Pydantic input schemas — moved from tools/models.py to shared/types.py)
from .shared.types import (
    FileReadInput, FileWriteInput, FileEditInput, BashInput,
    AgentInput, GlobInput, GrepInput,
    SendMessageInput, ProposeContentEditInput, 
    RequestUserInputInput
)

# ====================================================================
# Orchestration layer — M5 Distributed Architecture
# ====================================================================

from .orchestration.orchestrator import MissionOrchestrator
from .orchestration.contracts import AgentDescriptor, RuntimeResult, RuntimeLifecycleStatus
from .orchestration.lease_manager import TaskQueue, Dispatcher
from .orchestration.scheduling_manager import SchedulerManager
from .orchestration.mission_layer import MissionParser, TaskPlanner, TaskGraphBuilder
from .orchestration.worker_management import AgentCatalog, WorkerDirectory

# ====================================================================
# Observability layer — new components
# ====================================================================

from AgentCore.event_bus import EventBus, EventType
from .observability.blackboard import Blackboard, ConfidenceScore
from .observability.budget_manager import BudgetManager, BudgetStatus
from .observability.agent_kernel import ChatAgentKernel, GenerationAgentKernel



# ====================================================================
# Shared layer — exceptions and config
# ====================================================================

# ====================================================================
# Repository intelligence — format-agnostic indexing
# ====================================================================

from .repository import (
    FileMetadata,
    RepositorySnapshot,
    SnapshotManager,
    SymbolLocation,
    RepositoryIndex,
    RepositoryQueryEngine,
)

from .shared.exceptions import (
    AgentCoreError,
    ToolExecutionError,
    ToolPermissionError,
    QueryLoopError,
    QueryTimeoutError,
    AbortRequestedError,
    SectionGenerationError,
    KnowledgeIndexError,
)

__all__ = [
    # Execution
    "ToolRegistry", "ToolDefinition", "register", "registry",
    "ToolExecutor", "ToolExecutionResult",
    "QueryLoop",
    "AgentSpawner", "AgentResult",
    "AgentSpawner", "AgentResult",
    "ChatSessionManager", "GenerationSessionManager", "SessionRecord",
    "PermissionManager", "PermissionMode",
    "ContextCompactPipeline", "ContextToolCompact", "ContextAssistantCompact", "ContextAutoCompact",
    "SessionMemoryExtractor", "SessionMemoryCache", "CompactSummary",
    "SystemPromptManager", "StaticBlockBuilder", "DynamicBlockBuilder",
    "UserContextBuilder", "SystemContextBuilder", "SystemPromptBlock", "DYNAMIC_BOUNDARY",
    "AbortController", "AbortSignal", "get_hierarchy", "get_task_store",
    "AgentCleaner",
    "TranscriptWriter", "TranscriptEntry", "get_transcript_dir", "get_transcript_path",
    # Tool Input Models
    "FileReadInput", "FileWriteInput", "FileEditInput", "BashInput",
    "AgentInput", "GlobInput", "GrepInput",
    "SendMessageInput", "ProposeContentEditInput", "RequestUserInputInput",
    # Orchestration
    "MissionOrchestrator",
    "AgentDescriptor", "RuntimeResult", "RuntimeLifecycleStatus",
    "TaskQueue", "Dispatcher", "SchedulerManager",
    "MissionParser", "TaskPlanner", "TaskGraphBuilder",
    "AgentCatalog", "WorkerDirectory",
    # Observability
    "EventBus", "EventType",
    "Blackboard", "ConfidenceScore",
    "BudgetManager", "BudgetStatus",
    "ChatAgentKernel", "GenerationAgentKernel",
    # Shared
    "AgentCoreError", "ToolExecutionError", "ToolPermissionError",
    "QueryLoopError", "QueryTimeoutError", "AbortRequestedError",
    "SectionGenerationError", "KnowledgeIndexError",
    # Repository
    "FileMetadata", "RepositorySnapshot", "SnapshotManager",
    "SymbolLocation", "RepositoryIndex", "RepositoryQueryEngine",
]
