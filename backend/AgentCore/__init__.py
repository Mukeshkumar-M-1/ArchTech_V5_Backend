"""AgentCore — Unified agent execution platform.

Merged from the original tools/ and Document_Generate/ packages.
This is the single import path for all agent functionality.

Usage:
    from AgentCore.execution.query_loop import QueryLoop
    from AgentCore.agents.document_generate_agent import DocumentGenerationAgent
    from AgentCore.observability.event_bus import EventBus
"""

from __future__ import annotations

# ====================================================================
# Execution layer — replaces tools/__init__.py
# ====================================================================

from .execution.registry import ToolRegistry, ToolDefinition, register, registry
from .execution import builtins  # noqa: F401 — registers all tool definitions

from .execution.executor import ToolExecutor, ToolExecutionResult
from .execution.query_loop import QueryLoop
from .execution.agent_spawner import AgentSpawner, AgentResult
from .execution.agent_spawner import AgentSpawner, AgentResult
from .execution.permission import PermissionChecker, PermissionMode
from .execution.compaction import CompactPipeline, Tool_compact, Assistant_compact, AutoCompact
from .execution.session_memory import SessionMemoryExtractor, SessionMemoryCache, CompactSummary
from .execution.session_memory import SessionMemoryExtractor, SessionMemoryCache, CompactSummary
from .execution.system_prompt import (
    SystemPromptManager, StaticBlockBuilder, DynamicBlockBuilder,
    UserContextBuilder, SystemContextBuilder, SystemPromptBlock, DYNAMIC_BOUNDARY,
)
from .execution.ptao_orchestrator import (
    PTAOPromptBuilder, PTAOResponseParser, PTAOValidator,
    PTAOObservationFormatter, PTAOState,
)

from .execution.abort_controller import AbortController, AbortSignal, get_hierarchy, get_task_store
from .execution.session_manager import SessionLifecycle, SessionRecord
from .execution.agent_cleanup import AgentCleaner
from .execution.transcript import TranscriptWriter, TranscriptEntry, get_transcript_dir, get_transcript_path

# Models (Pydantic input schemas — moved from tools/models.py to shared/types.py)
from .shared.types import (
    FileReadInput, FileWriteInput, FileEditInput, BashInput,
    AgentInput, GlobInput, GrepInput, TodoWriteInput, SkillInput,
    TaskCreateInput, TaskUpdateInput, TaskListInput, TaskGetInput,
    TaskOutputInput, TaskStopInput, SendMessageInput,
)

# ====================================================================
# Orchestration layer — M5 Distributed Architecture
# ====================================================================

from .orchestration.orchestrator import MissionOrchestrator
from .orchestration.contracts import AgentDescriptor, RuntimeResult, RuntimeLifecycleStatus
from .orchestration.queue_and_dispatch import TaskQueue, Dispatcher
from .orchestration.scheduling import Scheduler
from .orchestration.mission_layer import MissionParser, TaskPlanner, TaskGraphBuilder
from .orchestration.worker_management import AgentCatalog, WorkerDirectory

# ====================================================================
# Observability layer — new components
# ====================================================================

from .observability.event_bus import EventBus, EventType
from .observability.blackboard import Blackboard, ConfidenceScore
from .observability.budget_manager import BudgetManager, BudgetStatus
from .observability.agent_kernel import AgentKernel

# ====================================================================
# Shared layer — exceptions and config
# ====================================================================

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
    "SessionLifecycle", "SessionRecord",
    "PermissionChecker", "PermissionMode",
    "CompactPipeline", "Tool_compact", "Assistant_compact", "AutoCompact",
    "SessionMemoryExtractor", "SessionMemoryCache", "CompactSummary",
    "SessionMemoryExtractor", "SessionMemoryCache", "CompactSummary",
    "SystemPromptManager", "StaticBlockBuilder", "DynamicBlockBuilder",
    "UserContextBuilder", "SystemContextBuilder", "SystemPromptBlock", "DYNAMIC_BOUNDARY",
    "PTAOPromptBuilder", "PTAOResponseParser", "PTAOValidator",
    "PTAOObservationFormatter", "PTAOState",
    "ChatSessionManager", "get_session_manager",
    "AbortController", "AbortSignal", "get_hierarchy", "get_task_store",
    "AgentCleaner",
    "TranscriptWriter", "TranscriptEntry", "get_transcript_dir", "get_transcript_path",
    # Models
    "FileReadInput", "FileWriteInput", "FileEditInput", "BashInput",
    "AgentInput", "GlobInput", "GrepInput", "TodoWriteInput", "SkillInput",
    "TaskCreateInput", "TaskUpdateInput", "TaskListInput", "TaskGetInput",
    "TaskOutputInput", "TaskStopInput", "SendMessageInput",
    # Orchestration
    "MissionOrchestrator",
    "AgentDescriptor", "RuntimeResult", "RuntimeLifecycleStatus",
    "TaskQueue", "Dispatcher", "Scheduler",
    "MissionParser", "TaskPlanner", "TaskGraphBuilder",
    "AgentCatalog", "WorkerDirectory",
    # Observability
    "EventBus", "EventType",
    "Blackboard", "ConfidenceScore",
    "BudgetManager", "BudgetStatus",
    "AgentKernel",
    # Shared
    "AgentCoreError", "ToolExecutionError", "ToolPermissionError",
    "QueryLoopError", "QueryTimeoutError", "AbortRequestedError",
    "SectionGenerationError", "KnowledgeIndexError",
]
