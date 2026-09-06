"""
Agent tool — Spawn a subagent to handle a subtask independently.

Usage by LLM:
    ToolCall(name="Agent", args={
        "agent_type": "explore",
        "prompt": "Research the codebase structure for X",
        "description": "Explore codebase",
        "run_in_background": False,
    })
"""

from __future__ import annotations

import logging

from ..tool_registry import ToolDefinition
from AgentCore.shared.types import AgentInput

log = logging.getLogger(__name__)


async def _execute(
    agent_type: str,
    prompt: str,
    description: str = "",
    run_in_background: bool = False,
    **kwargs,
) -> str:
    """Spawn a subagent and return its result.

    Args:
        agent_type: Type of subagent (general-purpose, explore, plan).
        prompt: Detailed task description for the subagent.
        description: Short description for logging.
        run_in_background: Whether to run asynchronously.
        **kwargs: Additional options (model, max_turns, etc.).

    Returns:
        Combined content and usage string from the agent result.
    """
    log.info("[Agent] Spawning agent_type=%s, description=%s, background=%s", agent_type, description, run_in_background)
    from AgentCore.execution.agent_spawner import AgentSpawner
    from ..tool_registry import registry as tool_registry

    # Pass the full tool definitions so the subagent can use them
    all_tools = tool_registry.get_all()

    spawner = AgentSpawner()
    result = await spawner.spawn(
        agent_type=agent_type,
        prompt=prompt,
        description=description,
        run_in_background=run_in_background,
        tools=all_tools,
        model=kwargs.get("model", "opus46"),
        max_turns=kwargs.get("max_turns", 20),
    )

    # Register in running_tasks if launched async
    from .tasks import get_running_tasks
    if result.status == "launched" and run_in_background:
        agent_id = result.agent_id
        running = get_running_tasks()
        # Find the background task just created — it matches by agent_id prefix
        for task_key, async_task in list(running.items()):
            if task_key.startswith("background_"):
                running[agent_id] = async_task
                del running[task_key]
                break

    usage = (
        f"\n<usage>\n"
        f"tool_uses: {result.total_tool_uses}\n"
        f"duration_ms: {result.total_duration_ms:.0f}\n"
        f"</usage>"
    )
    return result.content + usage


Agent = ToolDefinition(
    name="Agent",
    description=(
        "Launch a new agent to handle complex, multi-step tasks. Each agent type has "
        "specific capabilities and tools available to it.\n\n"
        "Available agent types and the tools they have access to:\n"
        "- general-purpose: General-purpose agent for researching complex questions, "
        "searching for code, and executing multi-step tasks. When you are searching for a "
        "keyword or file and are not confident that you will find the right match in the first "
        "few tries use this agent to perform the search for you.\n"
        "- explore: Fast agent specialized for exploring codebases. Use this when you need to "
        "quickly find files by patterns (e.g., \"src/components/**/*.tsx\"), search code for "
        "keywords (e.g., \"API endpoints\"), or answer questions about the codebase "
        "(e.g., \"how do API endpoints work?\"). When calling this agent, specify the desired "
        "thoroughness level: \"quick\" for basic searches, \"medium\" for moderate exploration, "
        "or \"very thorough\" for comprehensive analysis across multiple locations and naming conventions.\n"
        "- plan: Software architect agent for designing implementation plans. Use this when "
        "you need to plan the implementation strategy for a task. Returns step-by-step plans, "
        "identifies critical files, and considers architectural trade-offs.\n\n"
        "## When not to use\n\n"
        "If the target is already known, use the direct tool: Read for a known path, "
        "`grep` via the Bash tool for a specific symbol or string. Reserve this tool for "
        "open-ended questions that span the codebase, or tasks that match an available agent type.\n\n"
        "## Usage notes\n\n"
        "- Always include a short description (3-5 words) summarizing what the agent will do.\n"
        "- You can run agents in the background using run_in_background — you will be "
        "automatically notified when it completes. Do NOT sleep, poll, or proactively check.\n"
        "- Foreground (default): use when you need the agent's results before you can proceed "
        "-- e.g., research agents whose findings inform your next steps. Use background when "
        "you have genuinely independent work to do in parallel.\n"
        "- Clearly tell the agent whether you expect it to write code or just do research "
        "(search, file reads, web fetches, etc.), since it is not aware of the user's intent.\n"
        "- If the agent description mentions that it should be used proactively, then you "
        "should try your best to use it without the user having to ask for it first.\n"
        "- With `isolation: \"worktree\"`, the worktree is automatically cleaned up if the "
        "agent makes no changes; otherwise the path and branch are returned in the result.\n"
        "- Writing the prompt\n"
        "Brief the agent like a smart colleague who just walked into the room -- it hasn't "
        "seen this conversation, doesn't know what you've tried, doesn't understand why this "
        "task matters.\n"
        "- Explain what you're trying to accomplish and why.\n"
        "- Describe what you've already learned or ruled out.\n"
        "- Give enough context about the surrounding problem that the agent can make judgment "
        "calls rather than just following a narrow instruction.\n"
        "- If you need a short response, say so (\"report in under 200 words\")."
    ),
    input_schema=AgentInput.model_json_schema(),
    input_model=AgentInput,
    execute=_execute,
    is_concurrency_safe=False,
)
