"""
RequestUserInput tool — Ask the user for interactive input (select, radio, checkbox).

When the LLM calls this tool, it signals that user input is needed before continuing.
The QueryLoop pauses and emits SSE events for the frontend to render interactive UI.
"""

from __future__ import annotations

import json
import logging

from ..tool_registry import ToolDefinition
from AgentCore.shared.types import RequestUserInputInput

log = logging.getLogger(__name__)

AWAITING_MARKER = "__AWAITING_USER_INPUT__"
REQUEST_USER_INPUT_TOOL_NAME = "RequestUserInput"

def _execute(prompt: str, ui_type: str, options: list[str], title: str = "", **kwargs) -> str:
    """Execute RequestUserInput tool.

    Returns a marker string that the QueryLoop executor detects and handles as
    a pause/resume signal. Does NOT produce a final result.

    Args:
        prompt: The question or instruction text for the user.
        ui_type: One of 'select', 'radio', 'checkbox', 'text'.
        options: List of available options. Use [] for 'text' type.
        title: Optional card title.

    Returns:
        A marker string that signals the QueryLoop to pause.
    """
    log.info("[RequestUserInput] prompt=%s, ui_type=%s, options=%s, title=%s", prompt, ui_type, options, title)

    # For 'text' type, options may be empty/None — default to empty list
    if not options:
        options = []

    interaction_data = {
        "prompt": prompt,
        "ui_type": ui_type,
        "options": options,
        "title": title
    }
    return f"{AWAITING_MARKER}{json.dumps(interaction_data)}"


RequestUserInput = ToolDefinition(
    name="RequestUserInput",
    description=(
        "Ask the user for input using an interactive UI control. Use this when you need "
        "the user to make a selection, confirm a choice, or provide information before you "
        "can proceed.\n\n"
        "When to Use:\n"
        "- You need the user to choose from a set of options\n"
        "- You want the user to confirm or deny a proposed action\n"
        "- You need the user to prioritize or rank items\n"
        "- Multiple selections from a list are needed\n"
        "- You need free-form text input from the user\n\n"
        "Arguments:\n"
        "- **prompt**: The question or instruction text for the user (supports markdown: lists, line breaks, bold)\n"
        "- **ui_type**: One of:\n"
        "  * 'select' — dropdown with predefined options\n"
        "  * 'radio' — list of single-choice options\n"
        "  * 'checkbox' — multi-select options\n"
        "  * 'text' — free-form text input (pass empty list for options)\n"
        "- **options**: List of available options (2-8 recommended). Use [] for 'text' type.\n"
        "- **title**: Short plain-text label for what the question is about\n\n"
        "CRITICAL RULES:\n"
        "- **Ask ONE question at a time.** Each call must request a single piece of information.\n"
        "- **NEVER bundle multiple questions into one prompt.** If you need multiple answers,\n"
        "  call RequestUserInput sequentially: ask the first question, wait for the response,\n"
        "  then call RequestUserInput again for the next question.\n"
        "- **NEVER ask the user to provide multiple fields in one prompt.** For example,\n"
        "  if you need project name, project ID, and version, ask for project name first,\n"
        "  process the response, then ask for project ID, then version.\n"
        "- After receiving a response, always process it and call RequestUserInput again\n"
        "  for the next piece of information in the very next tool call.\n\n"
        "Notes:\n"
        "- After calling this tool, execution pauses until the user responds\n"
        "- The user's selection or text is returned as the tool result"
    ),
    input_schema=RequestUserInputInput.model_json_schema(),
    input_model=RequestUserInputInput,
    execute=_execute,
    is_concurrency_safe=True,
)
