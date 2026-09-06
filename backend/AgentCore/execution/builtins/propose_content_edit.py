"""
ProposeContentEdit tool — Suggest an edit to a specific section block in the editor.

When the LLM calls this tool, it signals that an edit proposal is ready for user review.
The QueryLoop pauses and emits SSE events for the frontend to render a diff view UI.
"""

from __future__ import annotations

import json
import logging
from pydantic import BaseModel, Field

from ..tool_registry import ToolDefinition
from .request_user_input import AWAITING_MARKER
from AgentCore.shared.types import ProposeContentEditInput

log = logging.getLogger(__name__)


def _execute(
    section_filename: str, 
    version: int, 
    block_number: int, 
    original_text: str, 
    proposed_text: str, 
    rationale: str = "", 
    **kwargs
) -> str:
    """Execute ProposeContentEdit tool.

    Returns a marker string that the QueryLoop executor detects and handles as
    a pause/resume signal. Does NOT produce a final result.
    """
    log.info("[ProposeContentEdit] section=%s, block=%s", section_filename, block_number)

    payload = {
        "section_filename": section_filename,
        "version": version,
        "block_number": block_number,
        "original_text": original_text,
        "proposed_text": proposed_text,
        "rationale": rationale,
    }
    
    # We pass the payload as a JSON object after the marker.
    # The frontend will parse this JSON to render the diff UI.
    interaction_data = {
        "prompt": f"Please review the proposed edit for '{section_filename}'",
        "ui_type": "content_edit",
        "options": [payload],
        "title": "Proposed Edit"
    }
    return f"{AWAITING_MARKER}{json.dumps(interaction_data)}"


ProposeContentEdit = ToolDefinition(
    name="ProposeContentEdit",
    description=(
        "Propose an edit to a specific content block from the editor. Use this tool "
        "when the user asks you to rewrite, modify, or update a specific section or text block.\n\n"
        "Arguments:\n"
        "- **section_filename**: The filename of the section (e.g., '01_project_table.md')\n"
        "- **version**: The version number of the section\n"
        "- **block_number**: The block index\n"
        "- **original_text**: The exact original text that you are modifying\n"
        "- **proposed_text**: The full new text that should replace the original text\n"
        "- **rationale**: A short sentence explaining why you made these changes\n\n"
        "Notes:\n"
        "- After calling this tool, execution pauses until the user accepts or rejects the edit.\n"
        "- The user's decision (accepted or rejected) is returned as the tool result."
    ),
    input_schema=ProposeContentEditInput.model_json_schema(),
    input_model=ProposeContentEditInput,
    execute=_execute,
    is_concurrency_safe=True,
)
