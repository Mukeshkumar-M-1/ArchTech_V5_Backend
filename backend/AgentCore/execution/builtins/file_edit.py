"""
FileEdit tool — Replace a specific range in a file with new text.

Usage by LLM:
    ToolCall(name="FileEdit", args={
        "file_path": "path/to/file.txt",
        "range": {"start_line": 10, "end_line": 20},
        "insert_content": "replacement text"
    })
"""

from __future__ import annotations

import logging
from pathlib import Path

from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import FileEditInput

log = logging.getLogger(__name__)


def _execute(
    file_path: str,
    range: dict,
    insert_content: str,
    **kwargs,
) -> str:
    """Replace lines in a file from start_line to end_line with new content.

    Args:
        file_path: Path to the file to edit.
        range: Dict with start_line and end_line keys.
        insert_content: New text to insert.
        **kwargs: Additional parameters.

    Returns:
        Success message with line count, or error string.
    """
    log.info("[FileEdit] Editing file: %s, range=%s, lines=%d", file_path, range, len(insert_content.splitlines()))
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    if path.is_dir():
        return f"Error: Path is a directory, not a file: {file_path}"

    try:
        lines = path.read_text(encoding="utf-8").splitlines(True)
        start_line = max(1, range.get("start_line", 1))
        end_line = range.get("end_line")
        if end_line is None:
            return "Error: end_line is required in range. Missing end_line defaults to entire file which is destructive."
        end_line = max(start_line, min(end_line, len(lines)))

        new_lines = (
            lines[: start_line - 1]
            + insert_content.splitlines(True)
            + lines[end_line:]
        )
        path.write_text("".join(new_lines), encoding="utf-8")
        return (
            f"Replaced lines {start_line}-{end_line} in {file_path} "
            f"with {len(insert_content.splitlines())} line(s)"
        )
    except PermissionError:
        return f"Error: Permission denied editing file: {file_path}"
    except OSError as e:
        return f"Error: Could not edit file {file_path}: {e}"


FileEdit = ToolDefinition(
    name="FileEdit",
    description=(
        "Performs exact string replacements in files.\n\n"
        "Usage:\n"
        "- You must use the FileRead tool at least once in the conversation before editing. "
        "This tool will error if you attempt an edit without reading the file.\n"
        "- When editing text from FileRead tool output, ensure you preserve the exact indentation "
        "(tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: "
        "spaces + line number + arrow. Everything after that is the actual file content to match. "
        "Never include any part of the line number prefix in the old_string or new_string.\n"
        "- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.\n"
        "- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n"
        "- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string "
        "with more surrounding context to make it unique or use `replace_all` to change every instance.\n"
        "- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful "
        "if you want to rename a variable for instance."
    ),
    input_schema=FileEditInput.model_json_schema(),
    input_model=FileEditInput,
    execute=_execute,
    is_concurrency_safe=False,
)
