import sys
from pathlib import Path

# Make the `backend/` directory importable so `AgentCore` resolves when this
# file is run directly (python .../test_system_prompt.py).
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Importing `builtins` auto-registers every built-in tool into the global registry.
from AgentCore.execution import builtins  # noqa: F401
from AgentCore.execution.system_prompt import SystemPromptManager
from AgentCore.execution.tool_registry import get_selected_tool_definition

tools = ["FileRead", "Bash", "Glob", "Search", "RequestUserInput"]
tool_definitions = get_selected_tool_definition(tools)

System_prompt_check = SystemPromptManager().build()

for index, block in enumerate(System_prompt_check):
    print(index, block)
