"""
Skill tool — Invoke specialized skills/directives.
Mirrors CCB SkillTool/prompt.ts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import SkillInput

log = logging.getLogger(__name__)

# Session-scoped skill invocation tracking
_invoked_skills: list[str] = []


def _execute(skill: str, args: Optional[str] = None, **kwargs) -> str:
    """Load and return a skill's instructions from a SKILL.md file.

    Args:
        skill: Skill name to load.
        args: Optional arguments string.
        **kwargs: Additional parameters.

    Returns:
        Skill content with instructions, or error message if not found.
    """
    log.info("[Skill] Loading skill: %s", skill)
    # Sanitize skill name to prevent path traversal
    if ".." in skill or skill.startswith("/") or skill.startswith("~"):
        return f"Error: Invalid skill name '{skill}'"

    search_dirs = [
        Path.cwd() / ".claude" / "skills" / skill,
        Path.cwd() / "src" / "skills" / "bundled" / skill,
    ]

    for skill_dir in search_dirs:
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            _invoked_skills.append(skill)
            result = f"Skill '{skill}' loaded.\n\n{content}"
            if args:
                result += f"\n\nArguments: {args}"
            return result

    return (
        f"Error: Skill '{skill}' not found. "
        f"Available skills are listed in system-reminder messages. "
        f"Search paths checked: {', '.join(str(d) for d in search_dirs)}"
    )


Skill = ToolDefinition(
    name="Skill",
    description=(
        "Execute a skill within the main conversation.\n\n"
        "When users ask you to perform tasks, check if any of the available skills match. "
        "Skills provide specialized capabilities and domain knowledge.\n\n"
        "When users reference a slash command or '/<something>' "
        "(e.g., '/commit', '/review-pr'), they are referring to a skill. "
        "Use this tool to invoke it.\n\n"
        "How to invoke:\n"
        "- skill: 'pdf' — invoke the pdf skill\n"
        "- skill: 'commit', args: '-m Fix bug' — invoke with arguments\n"
        "- skill: 'review-pr', args: '123' — invoke with arguments\n"
        "- skill: 'ms-office-suite:pdf' — invoke using fully qualified name\n\n"
        "Important:\n"
        "- Available skills are listed in system-reminder messages.\n"
        "- When a skill matches, this is a BLOCKING REQUIREMENT: "
        "invoke the Skill tool BEFORE generating any other response.\n"
        "- NEVER mention a skill without actually calling this tool.\n"
        "- Do not invoke a skill that is already running.\n"
        "- Do not use this tool for built-in CLI commands (/help, /clear, etc.).\n"
        "- If you see a <command-name> tag, the skill is ALREADY loaded — "
        "follow the instructions directly instead of calling again."
    ),
    input_schema=SkillInput.model_json_schema(),
    input_model=SkillInput,
    execute=_execute,
    is_concurrency_safe=True,
)
