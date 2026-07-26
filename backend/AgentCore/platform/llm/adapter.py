"""
Mock LLM Adapter

A stubbed implementation of the ILLMAdapter for Milestone 4 testing.
Returns a perfectly formatted JSON string to feed the DecisionParser.
"""

import logging
import json
from typing import List, Dict, Any, Generator
from .interfaces import ILLMAdapter

log = logging.getLogger(__name__)

class MockLLMAdapter(ILLMAdapter):
    def __init__(self):
        log.info("[MockLLMAdapter] Initialized.")

    def invoke(self, messages: List[Dict[str, Any]]) -> str:
        log.info(f"[MockLLMAdapter] Invoking mock LLM with {len(messages)} messages.")
        
        # Simulate an LLM JSON response
        response = {
            "hypothesis": "The WorkflowRunner is isolated from the turn manager.",
            "confidence": 0.9,
            "action_type": "SEARCH",
            "parameters": {"query": "WorkflowRunner"},
            "reason": "Verify class definition.",
            "expected_evidence": "class WorkflowRunner",
            "expected_observation": "Source file containing WorkflowRunner.",
            "exit_condition": "Found class definition.",
            "alternatives": ["READ File"]
        }
        return json.dumps(response)

    def stream(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        response_str = self.invoke(messages)
        # Yield character by character to simulate streaming
        for char in response_str:
            yield char
