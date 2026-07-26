"""ContextBuilder — Assembles the full context payload for each LLM turn."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from .next_goal import NextGoal

log = logging.getLogger(__name__)


class ContextBuilder:
    """Builds the complete context for each turn, reading from memory modules."""

    def __init__(self, project_id: str) -> None:
        """Initialize the context builder with memory modules.

        Args:
            project_id: The project identifier for memory scoping.
        """
        self._project_id = project_id
        log.info(f"[ContextBuilder] Initialized for project '{project_id}'")

    def build_turn_context(self, next_goal: NextGoal, completed_sections: list[str],
                           section_name: str = "") -> dict[str, str]:
        """Assemble the complete turn context message.

        Reads from memory modules (requirements, sections, decisions, summaries)
        to build a comprehensive context payload.

        Args:
            next_goal: The NextGoal for this turn.
            completed_sections: List of completed section numbers.
            section_name: Optional human-readable section name.

        Returns:
            A message dict with role 'user' and the assembled context string.
        """
        global_goal = f"Generate a complete technical document for project {self._project_id}."
        phase = next_goal.section_name if next_goal.section_name else "In progress"

        log.info(f"[ContextBuilder] Building context for section {next_goal.section_number} ({section_name}), "
                 f"completed={len(completed_sections)}, phase='{phase}'")

        # Completed sections list
        completed_text = "\n".join([f"  {sn}" for sn in completed_sections]) if completed_sections else "  (none yet)"
        log.info(f"[ContextBuilder] Completed sections: {len(completed_sections)}")

        # Decisions logic handled implicitly if we pass them, but here we only have summaries currently.
        decisions_text = ""
        
        # Next objective
        next_text = next_goal.objective if next_goal.objective else "No next objective."

        # Build working context message
        section_str = f"{next_goal.section_number} {next_goal.section_name}" if next_goal.section_name else next_goal.section_number
        parts = [
            "## GLOBAL GOAL",
            global_goal,
            "",
            "## PHASE",
            phase,
            "",
            "## CURRENT SECTION",
            section_str,
            "",
            "## TURN GOAL",
            next_text,
            "",
            "## COMPLETED SECTIONS",
            completed_text or "  (none yet)",
            "",
            "## DECISIONS",
            decisions_text or "  (none yet)",
            "",
            "## NEXT",
            next_text,
        ]
        content = "\n".join(parts)
        log.info(f"[ContextBuilder] Context assembled: {len(content)} chars")
        return {"role": "user", "content": content}

    # ── Knowledge index builder ─────────────────────────────────────────
    # (Copied from document_generate_agent.py for reuse if needed)

    @staticmethod
    def build_knowledge_index_block(project_id: str) -> str:
        """Build a compact index of available knowledge files.

        Lists overview, prerequisites, categories, and subcategories
        from the project's knowledge directory.

        Args:
            project_id: The project identifier for path resolution.

        Returns:
            Formatted knowledge index string.
        """
        from system_config import get_knowledge_source_dir

        parts: list[str] = []
        knowledge_path = get_knowledge_source_dir(project_id)

        if not knowledge_path.exists():
            return "No knowledge files found."

        # Read overview.md content
        overview = knowledge_path / "overview.md"
        if overview.exists():
            content = overview.read_text(encoding="utf-8")
            if "---" in content:
                content = content.split("---", 2)[-1].strip()
            parts.append(f"## overview.md\n\n{content}")

        # Read MEMORY.md content
        memory_md = knowledge_path / "MEMORY.md"
        if memory_md.exists():
            content = memory_md.read_text(encoding="utf-8")
            if "---" in content:
                content = content.split("---", 2)[-1].strip()
            parts.append(f"## MEMORY.md\n\n{content}")

        # Read relationships.md content
        rel = knowledge_path / "relationships.md"
        if rel.exists():
            parts.append(f"## relationships.md\n\n{rel.read_text(encoding='utf-8')}")

        # List requirements with file paths
        req_dir = knowledge_path / "requirements"
        if req_dir.exists():
            req_files = sorted(file_entry.name for file_entry in req_dir.iterdir() if file_entry.is_file())
            if req_files:
                req_list = "\n".join(f"  - {file_name}" for file_name in req_files)
                parts.append(f"## Requirements ({len(req_files)} files):\n{req_list}")

        # List categories
        cat_dir = knowledge_path / "categories"
        if cat_dir.exists():
            cat_files = sorted(file_entry.name for file_entry in cat_dir.iterdir() if file_entry.is_file())
            if cat_files:
                cat_list = "\n".join(f"  - {file_name}" for file_name in cat_files)
                parts.append(f"## Categories ({len(cat_files)} files):\n{cat_list}")

        # List subcategories
        sub_dir = knowledge_path / "subcategories"
        if sub_dir.exists():
            sub_files = sorted(file_entry.name for file_entry in sub_dir.iterdir() if file_entry.is_file())
            if sub_files:
                sub_list = "\n".join(f"  - {file_name}" for file_name in sub_files)
                parts.append(f"## Subcategories ({len(sub_files)} files):\n{sub_list}")

        result = "\n\n".join(parts) if parts else "No knowledge files found."
        log.info(f"[ContextBuilder] Knowledge index built: {len(parts)} entries, {len(result)} chars")
        return result
