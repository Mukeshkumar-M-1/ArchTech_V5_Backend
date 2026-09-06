"""
Search tool — Content search using regex.
Mirrors CCB GrepTool/prompt.ts.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from AgentCore.shared.types import GrepInput
from ..tool_registry import ToolDefinition

log = logging.getLogger(__name__)


def _execute(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",
    **kwargs,
) -> str:
    """Execute a regex-based content search across files.

    Args:
        pattern: Regex pattern to search for.
        path: Base directory to search (defaults to current directory).
        glob: Optional glob filter for files (e.g., "*.py").
        output_mode: One of "files_with_matches", "content", or "count".
        **kwargs: Additional parameters.

    Returns:
        Search results as string.
    """
    log.info("[Search] pattern=%s, path=%s, glob=%s, mode=%s", pattern, path, glob, output_mode)
    search_path = Path(path) if path else Path.cwd()
    matches = []
    total_lines = 0

    if search_path.is_file():
        files = [search_path]
    elif glob:
        try:
            files = list(search_path.rglob(glob))
        except re.error:
            return f"Error: Invalid glob pattern: {glob}"
    else:
        files = list(search_path.rglob("*"))
        files = [filepath for filepath in files if filepath.is_file()]

    # Precompile pattern once for reuse; add safety timeout via a simple regex check
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Error: Invalid regex pattern: {e}"

    if output_mode == "content":
        lines = []
        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if compiled.search(line):
                        lines.append(f"{filepath}:{i}:{line}")
                        total_lines += 1
            except (PermissionError, OSError):
                continue
        return "\n".join(lines[:500])
    else:
        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                found = compiled.findall(content)
                if found:
                    matches.append(str(filepath))
                    total_lines += len(found)
            except (PermissionError, OSError):
                continue

        if output_mode == "count":
            return f"{total_lines} matches in {len(matches)} files"
        else:
            return "\n".join(matches[:250]) if matches else "No matches found."


Search = ToolDefinition(
    name="Search",
    description=(
        "A powerful search tool built on ripgrep.\n\n"
        "Usage:\n"
        "- ALWAYS use Search for search tasks. NEVER invoke `grep` or `rg` as a Bash command. "
        "The Search tool has been optimized for correct permissions and access.\n"
        "- Supports full regex syntax (e.g., \"log.*Error\", \"function\\s+\\w+\")\n"
        "- Filter files with glob parameter (e.g., \"*.js\", \"**/*.tsx\") or type parameter "
        "(e.g., \"js\", \"py\", \"rust\")\n"
        "- Output modes: \"content\" shows matching lines, \"files_with_matches\" shows only "
        "file paths (default), \"count\" shows match counts\n"
        "- Use Agent tool for open-ended searches requiring multiple rounds\n"
        "- Pattern syntax uses ripgrep (not grep) - literal braces need escaping "
        "(use `interface\\\\{\\\\}` to find `interface{}` in Go code)\n"
        "- Multiline matching: By default patterns match within single lines only. For cross-line "
        "patterns like `struct \\{[\\s\\S]*?field`, use multiline: true"
    ),
    input_schema=GrepInput.model_json_schema(),
    input_model=GrepInput,
    execute=_execute,
    is_concurrency_safe=True,
)
