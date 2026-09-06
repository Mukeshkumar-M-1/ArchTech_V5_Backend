"""
Built-in tools — Auto-registered tool definitions.

These tools are automatically available to the LLM without any configuration.
Each tool is a ToolDefinition that gets registered in the global registry.
"""

from __future__ import annotations

import logging

from ..tool_registry import ToolDefinition, registry
from .file_read import FileRead
from .file_write import FileWrite
from .file_edit import FileEdit
from .bash import Bash
from .agent import Agent
from .glob import Glob
from .search import Search
from .send_message import SendMessage
from .request_user_input import RequestUserInput
from .propose_content_edit import ProposeContentEdit

log = logging.getLogger(__name__)

__all__ = [
    "FileRead",
    "FileWrite",
    "FileEdit",
    "Bash",
    "Agent",
    "Glob",
    "Search",
    "SendMessage",
    "RequestUserInput",
    "ProposeContentEdit",
]

# Auto-register all builtins
for _tool in [FileRead, FileWrite, FileEdit, Bash, Agent, Glob, Search, SendMessage, RequestUserInput, ProposeContentEdit]:
    registry.register(_tool)
