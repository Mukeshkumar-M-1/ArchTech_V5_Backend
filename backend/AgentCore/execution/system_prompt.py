"""
System Prompt — Block-structured system prompt with caching scopes.

Designed for the ArchTech Document Generation pipeline:
- Static prefix (identity, rules, document-writing guidelines) gets global cache scope
- Dynamic tail (MCP, memory, env info) gets null cache scope
- __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ separates static from dynamic
- CLAUDE.md + date injected as synthetic user message (Layer 2)
- Git status appended to system prompt (Layer 2)
- Prompt priority: override > custom > default > append
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from .ptao_orchestrator import PTAOPromptBuilder

log = logging.getLogger(__name__)

# Sentinel marking the boundary between static and dynamic blocks
DYNAMIC_BOUNDARY = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"


@dataclass
class SystemPromptBlock:
    """A single block of the system prompt with optional caching scope."""
    content: str
    cache_scope: Optional[str] = None  # "global", "org", or None
    is_cached: bool = False


class StaticBlockBuilder:
    """Builds the static system prompt prefix (identity, rules, tone, tools).

    All blocks get cache_scope="global" — shared across all users/sessions.
    Inserts DYNAMIC_BOUNDARY at the end.
    """

    def build(self, tool_definitions, global_goal_text: str | None = None, phase_text: str | None = None) -> list[SystemPromptBlock]:
        blocks = []

        # Document generation identity
        blocks.append(SystemPromptBlock(
            content=(
                "You are an autonomous AI agent for technical document generation.\n"
                "You work in a multi-turn loop: understand the task, plan, execute tool calls,\n"
                "observe results, and repeat until the section is complete.\n"
                "For every turn you MUST follow the PTAO thinking protocol below.\n"
                "Follow the instructions below every time the user sends a message."
            ),
            cache_scope="global",
        ))

        # Core behavior rules
        blocks.append(SystemPromptBlock(
            content=(
                "# Core behavior rules\n"
                "All instructions are mandatory. Follow them in order of priority.\n"
                "You are operating inside a tool-based environment — use tools to read, write, search, and navigate.\n"
                "The block [!IMPORTANT], [!CAUTION], [!NOTE] in templates are EXAMPLES — remove them and replace with real data.\n"
                "You must NEVER provide a code block as a response, unless specifically requested.\n"
                "You must NEVER leave placeholders like {{variable}} in output — fill everything with real data or 'TBD'."
            ),
            cache_scope="global",
        ))

        # System / tool environment
        blocks.append(SystemPromptBlock(
            content=(
                "# Environment\n"
                "You may have access to FileRead Glob, Search, and other tools.\n"
                "When you call a tool, the result is returned to you as an observation on the next turn.\n"
                "Results may include <system-reminder> or other tags. Tags contain information from the system.\n"
                "They bear no direct relation to the specific tool results or user messages in which they appear."
            ),
            cache_scope="global",
        ))

        # Document writing guidelines
        blocks.append(SystemPromptBlock(
            content=(
                "# Document Writing Rules\n"
                "You are writing technical documents from templates and knowledge files.\n"
                "The template shows the STRUCTURE only. You must:\n"
                "a) Replace every {{variable}} placeholder with real data from knowledge files or TBD\n"
                "b) Remove ALL instructional callouts like [!IMPORTANT], [!CAUTION], [!NOTE]\n"
                "c) Fill every empty table cell with real data from knowledge files or 'TBD'\n"
                "d) Keep the markdown structure (headings, tables, formatting) from the template\n"
                "e) Do NOT echo the template back verbatim — transform it by filling in real data\n"
                "f) Do NOT explain what you are doing. Do NOT say 'I will now read...'. Do NOT apologize.\n"
                "g) Do NOT use triple backticks around your output.\n"
                "h) Your response when generating document content must contain NOTHING except the document itself —\n"
                "   no introductory sentences, no explanations, no trailing text. The output starts with the first\n"
                "   character of the document and ends with the last character of the document.\n"
            ),
            cache_scope="global",
        ))

        # Actions / tool use
        blocks.append(SystemPromptBlock(
            content=(
                "# Tool Use\n"
                "You have access to a set of tools (functions). You MUST invoke them natively using the provided function calling interface.\n"
                "Do NOT output markdown blocks like ```tool_code``` to call tools. The tools are passed directly via the API schema.\n"
                "When using the Agent tool, specify a subagent_type parameter to select which agent type to use."
            ),
            cache_scope="global",
        ))

        # Tone and style — applies ONLY during tool-use turns, NEVER on the final answer turn
        blocks.append(SystemPromptBlock(
            content=(
                "# Tone and style\n"
                "Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked.\n"
                "Your responses should be short and concise.\n"
                "When referencing specific functions or pieces of code include the pattern file_path:line_number.\n"
                "Do not use a colon before tool calls.\n"
                "Text output (does not apply to tool calls):\n"
                "Assume tool call results are visible to you. Before your first tool call, state in one sentence what you're about to do.\n"
                "While working, give short updates at key moments: when you find something, when you change direction, or when you hit a blocker.\n"
                "CRITICAL EXCEPTION: The above communication rules apply ONLY to intermediate turns where you are calling tools. "
                "When your response is the FINAL document content (no tool calls), you must output ZERO commentary, ZERO summaries, "
                "ZERO updates. The final turn output must be the raw document text alone — nothing else. "
                "Never wrap the final document in code fences, markdown blocks, or introductory sentences."
            ),
            cache_scope="global",
        ))

        # Output efficiency
        blocks.append(SystemPromptBlock(
            content=(
                "# Output efficiency\n"
                "State results and decisions directly.\n"
                "Don't write walls of text."
            ),
            cache_scope="global",
        ))

        # # PTAO Thinking Protocol — part of default system prompt
        # blocks.append(SystemPromptBlock(
        #     content=PTAOPromptBuilder._build_thinking_text("suggest"),
        #     cache_scope="global",  # cached with static prefix
        # ))

        # Global goal + phase — injected by DocumentController at runtime
        # goal_content = ""
        # if global_goal_text:
        #     goal_content += f"## GLOBAL GOAL\n{global_goal_text}\n\n"
        # if phase_text:
        #     goal_content += f"## PHASE\n{phase_text}\n\n"
        # if goal_content:
        #     blocks.append(SystemPromptBlock(
        #         content=goal_content,
        #         cache_scope="global",
        #     ))

        # Dynamic boundary marker
        blocks.append(SystemPromptBlock(
            content=DYNAMIC_BOUNDARY,
            cache_scope=None,  # Boundary itself is never cached
        ))

        return blocks


class DynamicBlockBuilder:
    """Builds the dynamic system prompt tail (changes per session/turn).

    All blocks get cache_scope=None (session-scoped, never shared).
    MCP instructions are always recomputed (servers connect/disconnect).
    """

    def build(
        self,
        session_memory: dict | None = None
    ) -> list[SystemPromptBlock]:
        blocks = []

        if session_memory:
            lines = []
            if session_memory.get("files"):
                lines.append("## Files referenced in conversation:")
                for file_data_item in session_memory["files"][-50:]:
                    lines.append(f"- {file_data_item}") 
            if session_memory.get("decisions"):
                lines.append("## Key decisions:")
                for decision_data_item in session_memory["decisions"][-50:]:
                    lines.append(f"- {decision_data_item}")
            if lines:
                blocks.append(SystemPromptBlock(
                    content="\n".join(lines),
                    cache_scope=None,
                ))

        return blocks


class UserContextBuilder:
    """Builds the synthetic user message that injects CLAUDE.md + date.

    Mirrors CCB's getUserContext() — prepended as a synthetic user message
    before each API call, appearing as if the user typed it.
    """

    def build(self, claude_md: str = "") -> dict:
        from datetime import date
        parts = []
        if claude_md:
            parts.append(f"Here are your project instructions:\n\n{claude_md}")
        parts.append(f"Todays Date : {date.today().isoformat()}")
        content = "\n\n".join(parts)
        return {
            "role": "user",
            "content": content,
        }


class SystemContextBuilder:
    """Builds the system context block appended to the system prompt.

    Mirrors CCB's getSystemContext() — git status appended to system prompt array.
    """

    def build(self, git_status: str = "") -> SystemPromptBlock:
        if not git_status:
            return SystemPromptBlock(content="", cache_scope=None)
        return SystemPromptBlock(
            content=f"This is the git status at the start of the conversation.\n{git_status}",
            cache_scope=None,
        )


class SystemPromptManager:
    """Assembles the full system prompt from static + dynamic blocks.

    Manages cache state, handles priority (override > custom > default).
    """

    def __init__(self):
        self._static_builder = StaticBlockBuilder()
        self._dynamic_builder = DynamicBlockBuilder()
        self._user_context_builder = UserContextBuilder()
        self._system_context_builder = SystemContextBuilder()
        self._cache: dict[str, list[SystemPromptBlock]] = {}

    def build(
        self,
        tool_definitions: list[Any] | None = None,
        override_prompt: str | None = None,
        custom_system_prompt: str | None = None,
        session_memory: dict | None = None,
        global_goal_text: str | None = None,
        phase_text: str | None = None,
    ) -> list[SystemPromptBlock]:
        """Build the full system prompt following priority:
        1. Override > 2. Custom > 3. Default (static + dynamic)

        IMPORTANT: override_prompt and custom_prompt are PREPENDED to the
        base system prompt — they extend it, never replace it.
        This preserves trained tool-use patterns while adding custom domain instructions.
        """
        # Build the base system prompt
        static_blocks = self._static_builder.build(
            tool_definitions=tool_definitions,
            global_goal_text=global_goal_text,
            phase_text=phase_text,
        )

        # Build dynamic blocks
        dynamic_blocks = self._dynamic_builder.build(
            session_memory=session_memory,
        )

        base_blocks = static_blocks + dynamic_blocks

        # Prepend override_prompt if provided (highest priority — injected first)
        if override_prompt:
            base_blocks.insert(0, SystemPromptBlock(
                content=override_prompt, cache_scope=None,
            ))

        # Prepend custom_prompt as well (second-highest — injected second)
        if custom_system_prompt:
            base_blocks.insert(1, SystemPromptBlock(
                content=custom_system_prompt, cache_scope=None,
            ))

        return base_blocks

    def get_user_context(self, claude_md: str = "") -> dict:
        """Get the synthetic user context message."""
        return self._user_context_builder.build(claude_md=claude_md)

    def get_system_context(self, git_status: str = "") -> SystemPromptBlock:
        """Get the system context block."""
        return self._system_context_builder.build(git_status=git_status)

    def clear_cache(self, session_id: str | None = None) -> None:
        """Clear cached system prompt blocks (called on /clear or /compact)."""
        if session_id:
            self._cache.pop(session_id, None)
        else:
            self._cache.clear()
        log.info("[SystemPrompt] Cleared all system prompt caches")
