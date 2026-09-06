"""
Bash tool — Execute shell commands.

Usage by LLM:
    ToolCall(name="Bash", args={"command": "ls -la", "timeout": 30})
"""

from __future__ import annotations

import asyncio
import logging

from ..tool_registry import ToolDefinition
from AgentCore.shared.types import BashInput

log = logging.getLogger(__name__)


async def _execute(command: str, timeout: int = 30, **kwargs) -> str:
    """Execute a bash command and return stdout + stderr.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds.
        **kwargs: Additional parameters.

    Returns:
        Command output (stdout/stderr), or an error string.
    """
    log.info("[Bash] Executing command: %s (timeout=%ds)", command[:100], timeout)
    # Reject empty or null commands
    if not command or not command.strip():
        return "Error: Command is empty"

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass  # best-effort wait
        return f"Error: Command timed out after {timeout}s"

    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        return (
            f"Exit code {proc.returncode}\n"
            f"stdout: {stdout_text[:5000]}\n"
            f"stderr: {stderr_text[:5000]}"
        )
    return stdout_text or "(no output)"


Bash = ToolDefinition(
    name="Bash",
    description=(
        "Executes a given bash command and returns its output.\n\n"
        "The working directory persists between commands, but shell state does not. "
        "The shell environment is initialized from the user's profile (bash or zsh).\n\n"
        "IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` "
        "commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. "
        "Instead, use the appropriate dedicated tool as this will provide a much better experience for the user:\n"
        "- File search: Use Glob (NOT find or ls)\n"
        "- Content search: Use Search (NOT grep or rg)\n"
        "- Read files: Use Read (NOT cat/head/tail)\n"
        "- Edit files: Use Edit (NOT sed/awk)\n"
        "- Write files: Use Write (NOT echo >/cat <<EOF)\n"
        "- Communication: Output text directly (NOT echo/printf)\n\n"
        "While the Bash tool can do similar things, it's better to use the built-in tools as they provide a better user experience and make it easier to review tool calls and give permission.\n\n"
        "# Instructions\n"
        "- If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.\n"
        "- Always quote file paths that contain spaces with double quotes in your command (e.g., cd \"path with spaces/file.txt\")\n"
        "- Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.\n"
        "- You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). By default, your command will timeout after 120000ms (2 minutes).\n"
        "- You can use run_in_background to run the command in the background. Only use this if you don't need the result immediately and are OK being notified when the command completes later. You do not need to check the output right away - you'll be notified when it finishes. You do not need to use '&' at the end of the command when using this parameter.\n"
        "- When issuing multiple commands:\n"
        "  - If the commands are independent and can run in parallel, make multiple Bash tool calls in a single message. Example: if you need to run \"git status\" and \"git diff\", send a single message with two Bash tool calls in parallel.\n"
        "  - If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together.\n"
        "  - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail.\n"
        "  - DO NOT use newlines to separate commands (newlines are ok in quoted strings).\n"
        "- For git commands:\n"
        "  - Prefer to create a new commit rather than amending an existing commit.\n"
        "  - Before running destructive operations (e.g., git reset --hard, git push --force, git checkout --), consider whether there is a safer alternative that achieves the same goal. Only use destructive operations when they are truly the best approach.\n"
        "  - Never skip hooks (--no-verify) or bypass signing (--no-gpg-sign, -c commit.gpgsign=false) unless the user explicitly asks for it. If a hook fails, investigate and fix the underlying issue.\n"
        "- Avoid unnecessary `sleep` commands:\n"
        "  - Do not sleep between commands that can run immediately -- just run them.\n"
        "  - If your command is long running and you would like to be notified when it finishes -- use `run_in_background`. No sleep needed.\n"
        "  - Do not retry failing commands in a sleep loop -- diagnose the root cause.\n"
        "  - If waiting for a background task you started with `run_in_background`, you will be notified when it completes -- do not poll.\n"
        "  - If you must poll an external process, use a check command (e.g. `gh run view`) rather than sleeping first.\n"
        "  - If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user."
    ),
    input_schema=BashInput.model_json_schema(),
    input_model=BashInput,
    execute=_execute,
    is_concurrency_safe=False,
)
