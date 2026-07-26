"""
FileWrite tool — Write content to a file.

Usage by LLM:
    ToolCall(name="FileWrite", args={"file_path": "path/to/file.txt", "content": "..."})
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from system_config import get_project_base_dir
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import FileWriteInput

log = logging.getLogger(__name__)


def _validate_path(file_path: str, base_dir: Path | None = None) -> Path:
    """Validate that file_path is within an allowed directory.

    Args:
        file_path: The file path to validate.
        base_dir: Base directory for validation (defaults to project base).

    Returns:
        The resolved Path object.

    Raises:
        PermissionError: If the path is outside the allowed directory.
    """
    if base_dir is None:
        base_dir = get_project_base_dir()
    resolved = Path(file_path).resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError:
        raise PermissionError(
            f"Path traversal detected: {file_path} is outside the allowed directory {base_dir}"
        )
    return resolved


def _execute(file_path: str, content: str, **kwargs) -> str:
    """Write content to a file using atomic write (temp file + os.replace).

    Args:
        file_path: Absolute path to the destination file.
        content: The text content to write.
        **kwargs: Additional parameters.

    Returns:
        Success message with character count, or error string.
    """
    log.info("[FileWrite] Writing %d chars to: %s", len(content), file_path)
    try:
        path = _validate_path(file_path)
    except PermissionError:
        return f"Error: Permission denied — path traversal blocked: {file_path}"

    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except Exception as exception:
            os.unlink(tmp_path)
            return f"Error: Failed to unlink tempfiles {tmp_path}: {exception}"
    except PermissionError:
        return f"Error: Permission denied writing to file: {file_path}"
    except OSError as exception:
        return f"Error: Could not write file {file_path}: {exception}"


FileWrite = ToolDefinition(
    name="FileWrite",
    description=(
        "Writes a file to the local filesystem.\n\n"
        "Usage:\n"
        "- This tool will overwrite the existing file if there is one at the provided path.\n"
        "- If this is an existing file, you MUST use the FileRead tool first to read the file's contents. "
        "This tool will fail if you did not read the file first.\n"
        "- Prefer the Edit tool for modifying existing files — it only sends the diff. "
        "Only use this tool to create new files or for complete rewrites.\n"
        "- NEVER create documentation files (*.md) or README files unless explicitly requested by the User.\n"
        "- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked."
    ),
    input_schema=FileWriteInput.model_json_schema(),
    input_model=FileWriteInput,
    execute=_execute,
    is_concurrency_safe=False,
)
