"""
Context Selector

Applies strategies to select the most relevant history and evidence 
to fit within the token budget.
"""

import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)

class ContextSelector:
    """Strategy for reducing context to fit token budgets."""
    
    def __init__(self, max_history_turns: int = 10):
        self.max_history_turns = max_history_turns
        log.info(f"[ContextSelector] Initialized with max_history_turns={max_history_turns}")

    def select_history(self, full_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Trims the conversation history to the most recent turns.
        Always preserves the first user message (system prompt/initial directive) if necessary.
        """
        if len(full_history) <= self.max_history_turns:
            return full_history
            
        # Example strategy: keep the oldest 1 (system/initial) and the most recent N
        first = full_history[0:1]
        recent = full_history[-(self.max_history_turns - 1):]
        log.debug(f"[ContextSelector] Trimmed history from {len(full_history)} to {len(first) + len(recent)} turns.")
        return first + recent

    def summarize_memory(self, memory_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        In a real implementation, this might compress long evidence strings.
        For now, returns the snapshot unmodified.
        """
        return memory_snapshot
