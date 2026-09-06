"""
Prompt Registry

Central repository for registering and retrieving PromptTemplates.
Allows the CapabilityRegistry to lookup prompts by skill or mode.
"""

import logging
from typing import Dict

from .template import PromptTemplate

log = logging.getLogger(__name__)

class PromptRegistry:
    """Stores and retrieves registered prompt templates."""
    
    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        log.info("[PromptRegistry] Initialized.")

    def register(self, template: PromptTemplate) -> None:
        if template.name in self._templates:
            log.warning(f"[PromptRegistry] Overwriting existing template '{template.name}'")
        self._templates[template.name] = template
        # log.info(f"[PromptRegistry] Registered template '{template.name}'")

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            raise KeyError(f"Prompt template '{name}' not found in registry.")
        return self._templates[name]
