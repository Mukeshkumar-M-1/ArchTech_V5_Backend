"""
models.py — PromptDefinition dataclass for the ArchTech V5 Prompt Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PromptDefinition:
    """A single prompt definition in the registry."""

    name: str  # Unique identifier, e.g., "segmentation"
    content: str  # Raw prompt text (template or static)
    version: str = "1.0"  # Prompt version for tracking
    category: str = "system"  # "system" or "user"
    is_template: bool = True  # Supports {variable} substitution
    source: str = ""  # Which stage/module it belongs to
    metadata: Dict[str, str] = field(default_factory=dict)  # Extra tags

    def render(self, **kwargs) -> str:
        """Apply template substitution. Missing placeholders kept as-is."""
        if not self.is_template:
            return self.content
        try:
            return self.content.format(**kwargs)
        except (KeyError, IndexError):
            # Graceful fallback: return original with missing placeholders visible
            return self.content

    def build_system_message(self, user_content: str = None, **kwargs) -> Dict[str, str]:
        """Build {role: 'system', content: ...} message dict."""
        return {
            "role": "system",
            "content": self.render(**kwargs),
        }

    def build_messages(self, user_content: str = None, **kwargs) -> List[Dict[str, str]]:
        """Build full messages array for API call."""
        messages = [{"role": "system", "content": self.render(**kwargs)}]
        if user_content:
            messages.append({"role": "user", "content": user_content})
        return messages
