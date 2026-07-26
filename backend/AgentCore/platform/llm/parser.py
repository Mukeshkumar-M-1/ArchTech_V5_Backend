"""
Decision Parser

Parses the raw text output from the LLMAdapter into the strictly typed
Decision domain object.
"""

import logging
import json
from ...domain.decision import Decision, ActionDefinition

log = logging.getLogger(__name__)

class DecisionParser:
    def __init__(self):
        log.info("[DecisionParser] Initialized.")

    def parse(self, raw_llm_response: str) -> Decision:
        log.debug("[DecisionParser] Parsing raw LLM response into Decision object.")
        try:
            # In production, this robustly extracts JSON and handles malformed output
            # For this milestone skeleton, we assume perfect JSON
            data = json.loads(raw_llm_response)
            
            action_def = ActionDefinition(
                action_type=data.get("action_type", "UNKNOWN"),
                parameters=data.get("parameters", {})
            )
            
            return Decision(
                hypothesis=data.get("hypothesis", ""),
                confidence=float(data.get("confidence", 0.0)),
                chosen_action=action_def,
                reason=data.get("reason", ""),
                expected_evidence=data.get("expected_evidence", ""),
                expected_observation=data.get("expected_observation", ""),
                exit_condition=data.get("exit_condition", ""),
                alternatives=data.get("alternatives", [])
            )
            
        except Exception as e:
            log.error(f"[DecisionParser] Parse failure: {e}")
            raise ValueError(f"Failed to parse decision: {e}")
