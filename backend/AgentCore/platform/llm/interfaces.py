"""
LLM Interfaces

Defines stable contracts for the LLM pipeline, isolating the core framework
from specific provider implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator

class ILLMAdapter(ABC):
    """Stable interface for any LLM provider."""
    
    @abstractmethod
    def invoke(self, messages: List[Dict[str, Any]]) -> str:
        """Synchronous invocation returning the complete string."""
        pass
        
    @abstractmethod
    def stream(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """Streaming invocation yielding string chunks."""
        pass
