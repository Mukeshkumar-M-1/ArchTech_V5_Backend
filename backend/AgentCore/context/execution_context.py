"""
Execution Context Domain Object

The definitive state object passed into the ExecutionEngine. It contains all 
necessary information for a single turn of execution.
"""

from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class ExecutionContext:
    task_id: str
    directive: str
    memory_snapshot: Dict[str, Any]
    repository_summary: str
    history_window: List[Dict[str, str]]
    # Optional limits/budgets
    max_tokens: int = 8000
