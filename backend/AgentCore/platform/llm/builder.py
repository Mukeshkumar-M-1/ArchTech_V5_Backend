"""
Message Builder

Formats the raw prompt text into the provider-agnostic list of message
dictionaries (e.g., [{'role': 'system', 'content': ...}, ...]).
"""

import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)

class MessageBuilder:
    def __init__(self, system_instruction: str):
        self.system_instruction = system_instruction
        log.info("[MessageBuilder] Initialized with system instruction.")

    def build_messages(self, user_prompt: str) -> List[Dict[str, Any]]:
        log.debug("[MessageBuilder] Building standardized message array.")
        return [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": user_prompt}
        ]
