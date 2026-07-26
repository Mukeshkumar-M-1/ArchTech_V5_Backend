"""
Prompt Template & Versioning

Defines the structure of version-controlled prompts. This replaces hardcoded
f-strings scattered throughout the application.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict

log = logging.getLogger(__name__)

@dataclass
class PromptVersion:
    """Represents a specific version of a prompt."""
    version: str
    template_string: str
    required_variables: List[str]
    description: str

class PromptTemplate:
    """A prompt with multiple versions."""
    
    def __init__(self, name: str):
        self.name = name
        self.versions: Dict[str, PromptVersion] = {}
        log.info(f"[PromptTemplate] Created '{name}'")

    def add_version(self, version: str, template: str, required_vars: List[str], desc: str = "") -> None:
        self.versions[version] = PromptVersion(version, template, required_vars, desc)
        log.info(f"[PromptTemplate] Added version {version} to '{self.name}'")

    def get_version(self, version: str = "latest") -> PromptVersion:
        if version == "latest":
            # Just return the most recently added for simplicity in this V1
            if not self.versions:
                raise ValueError(f"No versions available for prompt '{self.name}'")
            return list(self.versions.values())[-1]
            
        if version not in self.versions:
            raise KeyError(f"Version '{version}' not found for prompt '{self.name}'")
            
        return self.versions[version]
