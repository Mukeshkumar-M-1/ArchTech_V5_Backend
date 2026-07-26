"""
Prompt Manager & Renderer

Responsible for taking a PromptTemplate, checking required variables, 
and rendering it safely into the final string.
"""

import logging
from typing import Dict, Any

from .registry import PromptRegistry

log = logging.getLogger(__name__)

class PromptRenderer:
    """Safely renders PromptVersions using Jinja2 or standard formatting."""
    
    @staticmethod
    def render(template_string: str, required_vars: list[str], variables: Dict[str, Any]) -> str:
        """Renders the template, ensuring all required variables are present."""
        for req in required_vars:
            if req not in variables:
                raise ValueError(f"Missing required prompt variable: '{req}'")
                
        # For Milestone 2, we just use standard string format.
        # In a real system, Jinja2 is highly recommended here.
        try:
            return template_string.format(**variables)
        except KeyError as e:
            raise ValueError(f"Template contains unmapped variable: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to render template: {e}")


class PromptManager:
    """Facade for managing and rendering prompts."""
    
    def __init__(self, registry: PromptRegistry):
        self.registry = registry
        self.renderer = PromptRenderer()
        log.info("[PromptManager] Initialized.")

    def build_prompt(self, template_name: str, variables: Dict[str, Any], version: str = "latest") -> str:
        """Retrieves and renders a prompt."""
        template = self.registry.get(template_name)
        prompt_version = template.get_version(version)
        
        log.info(f"[PromptManager] Rendering prompt '{template_name}' (v: {prompt_version.version})")
        
        return self.renderer.render(
            template_string=prompt_version.template_string,
            required_vars=prompt_version.required_variables,
            variables=variables
        )
