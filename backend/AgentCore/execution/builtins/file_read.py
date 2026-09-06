"""
FileRead tool — Read file contents.

Usage by LLM:
    ToolCall(name="FileRead", args={"file_path": "path/to/file.txt"})
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..tool_registry import ToolDefinition
from AgentCore.shared.types import FileReadInput

log = logging.getLogger(__name__)

DEFAULT_FILE_READ_CHAR_SIZE = 100_000

def _execute(file_path: str, **kwargs) -> str:
    """Read file contents from disk, truncating if excessively large.

    Args:
        file_path: Absolute path to the file.
        **kwargs: Additional parameters.

    Returns:
        File content as string.
    """
    log.info("[FileRead] Reading file: %s", file_path)
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")
    try:
        content = path.read_text(encoding="utf-8")
    except PermissionError:
        raise
    except UnicodeDecodeError:
        raise

    # Truncate very large files (100k chars) to prevent overwhelming the LLM
    if len(content) > DEFAULT_FILE_READ_CHAR_SIZE:
        content = content[:DEFAULT_FILE_READ_CHAR_SIZE] + f"\n\n... [truncated, {len(content) - DEFAULT_FILE_READ_CHAR_SIZE} more characters]"
        return content + "\n\n[FILE TRUNCATED -- original file exceeded 100,000 characters]"
    return content


FileRead = ToolDefinition(
    name="FileRead",
    description=(
        "Reads a file from the local filesystem. You can access any file directly by using this tool. "
        "Assume this tool is able to read all files on the machine. If the User provides a path to a file "
        "assume that path is valid. It is okay to read a file that does not exist; an error will be returned.\n\n"
        "CRITICAL RULE: DO NOT read the same file multiple times across tool calls. Keep track of what you have already read in your context. "
        "If you find yourself repeatedly reading files, you must STOP and proceed with your task.\n\n"
        "Usage:\n"
        "- The file_path parameter must be an absolute path, not a relative path\n"
        "- By default, it reads up to 2000 lines starting from the beginning of the file\n"
        "- You can optionally specify a line offset and limit (especially handy for long files), "
        "but it's recommended to read the whole file by not providing these parameters\n"
        "- When you already know which part of the file you need, only read that part.\n"
        "- Results are returned using cat -n format, with line numbers starting at 1\n"
        "- This tool allows Claude Code to read images (eg PNG, JPG, etc). When reading an image file the contents are "
        "presented visually as Claude Code is a multimodal LLM.\n"
        "- This tool can read PDF files (.pdf). For large PDFs (more than 10 pages), you MUST provide the "
        "pages parameter to read specific page ranges (e.g., pages: '1-5'). Reading a large PDF without the pages parameter will fail. Maximum 20 pages per request.\n"
        "- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, "
        "combining code, text, and visualizations.\n"
        "- This tool can only read files, not directories. To read a directory, use an ls command via the Bash tool.\n"
        "- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, "
        "ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths.\n"
        "- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."
    ),
    input_schema=FileReadInput.model_json_schema(),
    input_model=FileReadInput,
    execute=_execute,
    is_concurrency_safe=True,
)
