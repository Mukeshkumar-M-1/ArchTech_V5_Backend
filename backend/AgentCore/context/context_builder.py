"""
Context Builder

The sole producer of the ExecutionContext. It queries the Repository, 
StoreManager, and Task definition to build a complete state object.
"""

import logging
from typing import Any, Dict, List

from .execution_context import ExecutionContext
from .context_selector import ContextSelector
# from AgentCore.memory.store_manager import StoreManager
# from AgentCore.repository.query_engine import RepositoryQueryEngine

log = logging.getLogger(__name__)

class ContextBuilder:
    """Assembles the ExecutionContext for the runtime loop."""
    
    def __init__(self, selector: ContextSelector):
        self.selector = selector
        log.info("[ContextBuilder] Initialized.")

    def build_context(
        self, 
        task_id: str, 
        directive: str, 
        memory_manager: Any, 
        repo_engine: Any,
        raw_history: List[Dict[str, str]]
    ) -> ExecutionContext:
        """
        Compiles the ExecutionContext.
        """
        log.info(f"[ContextBuilder] Building context for task '{task_id}'")
        
        # 1. Pull memory
        memory_snap = memory_manager.get_snapshot() if memory_manager else {}
        selected_memory = self.selector.summarize_memory(memory_snap)
        
        # 2. Pull repository summary (e.g., core structural info)
        # In a real scenario, this might just pull the entry point or requested files.
        # For Milestone 2, we just stub it or return a tiny summary.
        repo_summary = "Repository index active."
        if repo_engine:
            # E.g. get root files or requested context
            pass
            
        # 3. Reduce history
        selected_history = self.selector.select_history(raw_history)
        
        context = ExecutionContext(
            task_id=task_id,
            directive=directive,
            memory_snapshot=selected_memory,
            repository_summary=repo_summary,
            history_window=selected_history
        )
        
        log.info(f"[ContextBuilder] Successfully built ExecutionContext for '{task_id}'")
        return context
