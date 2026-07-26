"""
Glob tool — Fast file pattern matching.
Mirrors CCB GlobTool/prompt.ts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from AgentCore.shared.types import GlobInput
from AgentCore.execution.registry import ToolDefinition

log = logging.getLogger(__name__)


def _execute(pattern: str, path: Optional[str] = None, **kwargs) -> str:
    """Execute a glob pattern search and return matching file paths.

    Args:
        pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts").
        path: Base directory to search (defaults to current directory).
        **kwargs: Additional parameters.

    Returns:
        Newline-separated list of matching file paths, or a message if none found.
    """
    log.info("[Glob] Searching pattern=%s in path=%s", pattern, path or "cwd")
    search_dir = Path(path) if path else Path.cwd()
    if not search_dir.is_dir():
        return f"Error: Path is not a directory: {path}"
    matches = []
    for match_path in search_dir.rglob(pattern):
        try:
            mtime = match_path.stat().st_mtime
            matches.append((match_path, mtime))
        except OSError:
            continue
    matches.sort(key=lambda x: x[1], reverse=True)
    results = [str(filepath) for filepath, _ in matches[:100]]
    truncated_note = ""
    if len(matches) > 100:
        truncated_note = f"\n...(showing 100 of {len(matches)} results)"
    return "\n".join(results) + truncated_note if results else "No files matched."


Glob = ToolDefinition(
    name="Glob",
    description=(
        "- Fast file pattern matching tool that works with any codebase size\n"
        "- Supports glob patterns like \"**/*.js\" or \"src/**/*.ts\"\n"
        "- Returns matching file paths sorted by modification time\n"
        "- Use this tool when you need to find files by name patterns\n"
        "- When you are doing an open ended search that may require multiple rounds of globbing "
        "and grepping, use the Agent tool instead"
    ),
    input_schema=GlobInput.model_json_schema(),
    input_model=GlobInput,
    execute=_execute,
    is_concurrency_safe=True,
)
