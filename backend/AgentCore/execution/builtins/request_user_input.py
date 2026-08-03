"""
RequestUserInput tool — Ask the user for interactive input (select, radio, checkbox).

When the LLM calls this tool, it signals that user input is needed before continuing.
The QueryLoop pauses and emits SSE events for the frontend to render interactive UI.
"""

from __future__ import annotations

import json
import logging

from AgentCore.execution.registry import ToolDefinition
from AgentCore.shared.types import RequestUserInputInput

log = logging.getLogger(__name__)

AWAITING_MARKER = "__AWAITING_USER_INPUT__"


def _execute(prompt: str, ui_type: str, options: list[str], title: str = "", **kwargs) -> str:
    """Execute RequestUserInput tool.

    Returns a marker string that the QueryLoop executor detects and handles as
    a pause/resume signal. Does NOT produce a final result.

    Args:
        prompt: The question or instruction text for the user.
        ui_type: One of 'select', 'radio', 'checkbox'.
        options: List of available options.
        title: Optional card title.

    Returns:
        A marker string that signals the QueryLoop to pause.
    """
    log.info("[RequestUserInput] prompt=%s, ui_type=%s, options=%s, title=%s", prompt, ui_type, options, title)

    interaction_data = {
        "prompt": prompt,
        "ui_type": ui_type,
        "options": options,
        "title": title
    }
    return f"{AWAITING_MARKER}|{json.dumps(interaction_data)}"


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
        "- Multiple selections from a list are needed\n\n"
        "Arguments:\n"
        "- **prompt**: The question or instruction text for the user\n"
        "- **ui_type**: 'select' (dropdown), 'radio' (list of choices), 'checkbox' (multi-select)\n"
        "- **options**: List of available options (2-8 recommended)\n"
        "- **title**: Optional short title for the tool card\n\n"
        "Notes:\n"
        "- After calling this tool, execution pauses until the user responds\n"
        "- The user's selection is returned as the tool result\n"
        "- Use 'select' for a single dropdown choice, 'radio' for a single list choice, "
        "'checkbox' for multiple selections"
    ),
    input_schema=RequestUserInputInput.model_json_schema(),
    input_model=RequestUserInputInput,
    execute=_execute,
    is_concurrency_safe=True,
)
