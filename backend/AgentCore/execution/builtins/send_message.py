"""
SendMessage tool — Send a message to another agent.

Phase 6: File-based mailbox delivery.
Mirrors CCB's SendMessageTool.ts.
"""
from __future__ import annotations

import logging
from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import SendMessageInput

log = logging.getLogger(__name__)


def _execute(to: str, message: str, message_type: str = "text", **kwargs) -> str:
    """Send a message to another agent via the mailbox system.

    Args:
        to: Recipient agent ID.
        message: The message text.
        message_type: Type of message (text, shutdown_request, etc.).
        **kwargs: Additional parameters.

    Returns:
        Success or error message string.
    """
    log.info("[SendMessage] to=%s, type=%s, from=%s", to, message_type, from_agent)
    from AgentCore.execution.agent_mailbox import get_mailbox
    from AgentCore.execution.context_isolation import get_agent_id

    from_agent = get_agent_id() or "unknown"

    if to == "*":
        # Phase 6: broadcast -- would iterate all mailbox managers
        # For now, log and return
        log.info(f"[SendMessage] Broadcast attempt from {from_agent}: {message[:100]}")
        return f"Broadcast attempted from {from_agent}"

    mailbox = get_mailbox(to)
    success = mailbox.send(to, from_agent, message)
    if success:
        return f"Message sent to agent '{to}' successfully."
    return f"Error: Failed to send message to agent '{to}'."


SendMessage = ToolDefinition(
    name="SendMessage",
    description=(
        "Send a message to another agent (subagent, teammate, or running task).\n\n"
        "When to Use:\n"
        "- To redirect a running agent's attention to a new task\n"
        "- To share information between concurrent agents\n"
        "- To request status updates from background agents\n"
        "- To send shutdown or plan approval signals\n\n"
        "Arguments:\n"
        "- **to**: Recipient agent ID, name, or \"*\" for broadcast\n"
        "- **message**: The message text\n"
        "- **message_type**: \"text\" (default), \"shutdown_request\", \"plan_approval\"\n\n"
        "Notes:\n"
        "- Messages are queued in the recipient's mailbox\n"
        "- For running agents, messages are picked up automatically\n"
        "- For evicted agents, messages are held in the mailbox file"
    ),
    input_schema=SendMessageInput.model_json_schema(),
    input_model=SendMessageInput,
    execute=_execute,
    is_concurrency_safe=True,  # read-only mailbox append
)
