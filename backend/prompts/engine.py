"""
engine.py — Core PromptEngine for ArchTech V5.
Inspired by Claude Code's system-prompt architecture:
- Static registry (loaded once, never changes)
- Dynamic sections (computed per-call, cached per-session)
- Template rendering ({variable} substitution)
- Cache management (clear_cache = /clear equivalent)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

from .models import PromptDefinition


@dataclass
class PromptEngine:
    """
    Production-ready system prompt engine.
    Mirrors Claude Code architecture:
    - Static registry (loaded once, never changes)
    - Dynamic sections (computed per-call, cached per-session)
    - Template rendering ({variable} substitution)
    - Cache management (clear_cache = /clear equivalent)
    """

    prompts_dir: Path = field(default_factory=lambda: Path(__file__).parent / "System_Prompts")
    _registry: Dict[str, PromptDefinition] = field(default_factory=dict)
    _cache: Dict[str, str] = field(default_factory=dict)
    _dynamic_sections: Dict[str, Callable] = field(default_factory=dict)
    _dynamic_cache: Dict[str, str] = field(default_factory=dict)
    _cache_version: int = 0
    _load_done: bool = False

    def __post_init__(self):
        if not self._load_done:
            self._load_registry()
            self._load_done = True

    # ── Static Registry ──────────────────────────────────────────────────

    def _load_registry(self):
        """Load all .txt prompt files into the registry at startup (recursively)."""
        if not self.prompts_dir.exists():
            log.warning(f"Prompts directory not found: {self.prompts_dir}")
            return

        for txt_file in sorted(self.prompts_dir.rglob("*.txt")):
            if txt_file.name.startswith("_"):
                continue
            if txt_file.name.startswith("PROMPT_") and txt_file.name.endswith("_override.txt"):
                continue
            try:
                prompt = self._load_prompt_file(txt_file)
                # log.info(f"[prompts] Name :[{prompt.name}] v[{prompt.version}] from [{txt_file.relative_to(self.prompts_dir)}]")
                self._registry[prompt.name] = prompt
            except Exception as e:
                log.error(f"[prompts] Failed to load {txt_file.name}: {e}")

    def _load_prompt_file(self, path: Path) -> PromptDefinition:
        """
        Parse a .txt file into a PromptDefinition.
        Supports metadata header:
            # @version: 1.0
            # @category: system|user
            # @template: true|false
            # @source: stage_2|stage_3|utilities|inference
        """
        raw = path.read_text(encoding="utf-8")
        content = raw

        # Extract metadata from comment header
        version = "1.0"
        category = "system"
        is_template = True
        source = ""
        metadata: Dict[str, str] = {}

        for line in raw.split("\n"):
            if line.startswith("# @version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("# @category:"):
                category = line.split(":", 1)[1].strip()
            elif line.startswith("# @template:"):
                is_template = line.split(":", 1)[1].strip().lower() in ("true", "yes", "1")
            elif line.startswith("# @source:"):
                source = line.split(":", 1)[1].strip()
            elif line.startswith("# @"):
                key = line[3:].split(":", 1)[0].strip()
                val = line[3:].split(":", 1)[1].strip() if ":" in line[3:] else ""
                metadata[key] = val

        # Remove metadata lines from content
        content = re.sub(r'^#\s*@.*\n?', '', content, flags=re.MULTILINE).strip()

        # Prompt name is filename without .txt extension
        name = path.stem.lower()

        return PromptDefinition(
            name=name,
            content=content,
            version=version,
            category=category,
            is_template=is_template,
            source=source,
            metadata=metadata,
        )

    def register(self, name: str, content: str, **meta) -> PromptDefinition:
        """Dynamically register a prompt (for env overrides, runtime injection)."""
        prompt = PromptDefinition(name=name, content=content, **meta)
        self._registry[name] = prompt
        log.info(f"[prompts] Registered prompt: {name} v{prompt.version}")
        return prompt

    def get_definition(self, name: str) -> Optional[PromptDefinition]:
        """Get a prompt definition by name."""
        return self._registry.get(name)

    def list_prompts(self) -> List[str]:
        """List all registered prompt names."""
        return sorted(self._registry.keys())

    # ── Dynamic Rendering ────────────────────────────────────────────────

    def render(self, name: str, **kwargs) -> str:
        """
        Render a prompt with template substitution.
        Uses cache if kwargs are empty (static hit).
        Falls back to original text if placeholder is missing.
        """
        prompt = self.get_definition(name)
        
        if not prompt:
            log.warning(f"[prompts] Unknown prompt: '{name}' — returning empty string")
            return ""

        # If no variables, return cached version or compute once
        if not kwargs:
            if name in self._cache and self._cache_version == self._prompt_cache_key():
                return self._cache[name]
            result = prompt.render()
            self._cache[name] = result
            return result

        # With variables: check dynamic cache
        cache_key = f"{name}:{self._cache_key(kwargs)}"
        if cache_key in self._dynamic_cache:
            return self._dynamic_cache[cache_key]

        result = prompt.render(**kwargs)
        self._dynamic_cache[cache_key] = result
        return result

    def render_or_default(self, name: str, default: str, **kwargs) -> str:
        """Render prompt, or return default if not registered."""
        if name in self._registry:
            return self.render(name, **kwargs)
        return default

    def build_message(
        self,
        name: str,
        role: str = "system",
        content: str = None,
        **kwargs,
    ) -> Dict[str, str]:
        """
        Build a single message dict.
        If role='system', renders the prompt by name as content.
        If role='user', the content parameter is used directly.
        """
        if role == "system":
            return {"role": "system", "content": self.render(name, **kwargs)}
        return {"role": "user", "content": content or ""}

    def build_messages(self, system_name: str, user_content: str = None, **kwargs) -> List[Dict[str, str]]:
        """
        Build a full messages array for API calls.
        Mirrors Claude Code's pattern:
          [
            {"role": "system", "content": <rendered system prompt>},
            {"role": "user", "content": <user content>},
          ]
        """
        messages = [{"role": "system", "content": self.render(system_name, **kwargs)}]
        if user_content:
            messages.append({"role": "user", "content": user_content})
        return messages

    # ── Dynamic Sections ─────────────────────────────────────────────────

    def add_dynamic_section(self, name: str, compute_fn: Callable) -> str:
        """
        Register a dynamic section (like Claude Code's systemPromptSection).
        compute_fn is called once, result is cached until clear_cache().
        Returns the name for later reference.
        """
        self._dynamic_sections[name] = compute_fn
        # Force cache invalidation for this section
        self._dynamic_cache.pop(name, None)
        return name

    def get_dynamic_section(self, name: str) -> Optional[str]:
        """Get a cached dynamic section. Recomputes if cache miss."""
        if name in self._dynamic_cache:
            return self._dynamic_cache[name]

        compute_fn = self._dynamic_sections.get(name)
        if not compute_fn:
            return None

        result = compute_fn()
        self._dynamic_cache[name] = result
        return result

    # ── Pipeline Assembly ────────────────────────────────────────────────

    def build_pipeline_prompt(
        self,
        stage_name: str,
        context: Optional[Dict] = None,
        **kwargs,
    ) -> str:
        """
        Assemble the full system prompt for a pipeline stage.
        Combines:
        1. Base static prompt (from .txt file), rendered with kwargs
        2. Stage-specific context dict (key-value appended as sections)
        3. Registered dynamic sections
        """
        prompt = self.get_definition(stage_name)
        if not prompt:
            log.warning(f"[prompts] No prompt registered for stage: {stage_name}")
            return ""

        parts = [prompt.render(**kwargs)]

        # Append context dict entries as sections
        if context:
            for key, value in context.items():
                if value:
                    parts.append(f"\n## Context: {key}\n{value}")

        # Append any registered dynamic sections
        for sec_name in self._dynamic_sections:
            sec_content = self.get_dynamic_section(sec_name)
            if sec_content:
                parts.append(f"\n## Dynamic Section: {sec_name}\n{sec_content}")

        return "\n\n".join(parts)

    # ── Cache Management ─────────────────────────────────────────────────

    def clear_cache(self):
        """Clear all cached rendered prompts. Equivalent to /clear in Claude Code."""
        self._cache.clear()
        self._dynamic_cache.clear()
        self._cache_version += 1
        log.info(f"[prompts] Cache cleared (version {self._cache_version})")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss stats for debugging."""
        return {
            "static_cache_hits": len(self._cache),
            "dynamic_cache_hits": len(self._dynamic_cache),
            "registered_prompts": len(self._registry),
            "dynamic_sections": len(self._dynamic_sections),
            "cache_version": self._cache_version,
        }

    # ── Private Helpers ──────────────────────────────────────────────────

    def _cache_key(self, kwargs: Dict) -> str:
        """Generate a cache key from kwargs dict."""
        return ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)

    def _prompt_cache_key(self) -> int:
        """Unique key for current prompt state (for cache invalidation)."""
        return hash(tuple(sorted(self._registry.keys())))
