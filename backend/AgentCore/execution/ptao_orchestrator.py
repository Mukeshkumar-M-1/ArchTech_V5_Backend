"""
PTAO Orchestrator — A dedicated U-P-T-A-O reasoning loop.

Manages the UNDERSTAND → PLANNING → THOUGHT → ACTION → OBSERVATION cycle as a
separate multi-turn loop. The system prompt stays clean; thinking instructions
and observations are sent as user messages so the model processes them naturally.

Architecture:

    QueryLoop
        → PTAOOrchestrator.run()
            → PromptBuilder.build_messages()
            → _llm_call(messages)
            → ResponseParser.parse()
            → Validator.validate()
            → ToolExecutor.execute()
            → ObservationFormatter.format()
            → loop until done or max_turns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
import asyncio

log = logging.getLogger(__name__)

# ─── State ──────────────────────────────────────────────────────────────────


@dataclass
class PTAOState:
    """Tracks the full turn history of a PTAO reasoning session."""

    turn: int = 0
    actions: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    completed: bool = False
    retries: int = 0
    final_text: str = ""
    error: Optional[str] = None
    # NEW: Goal-driven fields
    current_section: str = ""
    current_turn_goal: str = ""
    section_completed: bool = False
    goal_status: dict = field(default_factory=dict)


# ─── Prompt Builder ─────────────────────────────────────────────────────────


class PTAOPromptBuilder:
    """Builds the message stack for each PTAO turn."""

    @classmethod
    def get_understand_instruction(cls) -> str:
        return "Briefly summarize: what have you learned so far, what is your current goal?"

    @classmethod
    def get_planning_instruction(cls) -> str:
        return "List the specific steps you will take. Name the tools you will call."

    @classmethod
    def get_thought_instruction(cls) -> str:
        return "What data do you have? What is missing? Justify your next action."

    @classmethod
    def get_action_instruction(cls) -> str:
        return (
            "Execute your plan. You MUST invoke a tool using the native function calling API."
        )

    @classmethod
    def build_initial_messages(self, system_prompt: str, user_task: str, thinking_mode: str = "suggest") -> list[dict]:
        """Build the first message stack for a PTAO turn.

        Order:
        [system]   -> Agent identity & role rules
        [user]     -> Thinking instructions (U-P-T-A-O)
        [user]     -> The actual task (template + knowledge)

        Args:
            system_prompt: The system prompt string for the agent.
            user_task: The actual task description.
            thinking_mode: Mode for thinking instructions (default "suggest").

        Returns:
            List of message dicts for the initial API call.
        """
        thinking_text = self._build_thinking_text(thinking_mode)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": thinking_text},
            {"role": "user", "content": user_task},
        ]

    @classmethod
    def _build_thinking_text(cls, mode: str = "suggest") -> str:
        """Build the thinking instruction block."""
        lines = [
            "## THINKING PROTOCOL",
            f"Mode: {mode}",
            "",
            "You must follow this reasoning sequence for every turn:",
            
            "\n### [UNDERSTAND]",
            cls.get_understand_instruction(),
            "OUTPUT: Begin your response with [UNDERSTAND] on its own line.",
            
            "\n### [PLANNING]",
            cls.get_planning_instruction(),
            "OUTPUT: Begin your response with [PLANNING] on its own line.",
            
            "\n### [THOUGHT]",
            cls.get_thought_instruction(),
            "OUTPUT: Begin your response with [THOUGHT] on its own line.",
            
            "\n### [ACTION]",
            cls.get_action_instruction(),
            "OUTPUT: Begin your response with [ACTION] on its own line."
        ]
        return "\n".join(lines)

    @classmethod
    def append_observation(self, messages: list[dict], content: str) -> None:
        """Append an [OBSERVATION] block as a user message."""
        messages.append({
            "role": "user",
            "content": f"[OBSERVATION]\n{content.strip()}",
        })

    @classmethod
    def append_recovery(self, messages: list[dict], recovery_text: str) -> None:
        """Append a recovery reminder when validation fails."""
        messages.append({
            "role": "user",
            "content": f"[RECOVERY]\n{recovery_text}",
        })

    @classmethod
    def get_thinking_system_prompt(cls, mode: str = "suggest") -> str:
        """Return the thinking protocol as a system prompt block.
        This keeps the protocol in the system context, not conversation history."""
        return cls._build_thinking_text(mode)


# ─── Response Parser ────────────────────────────────────────────────────────


class PTAOResponseParser:
    """Parses LLM responses into structured PTAO steps + tool calls."""

    STEP_PATTERN = re.compile(r'\[(UNDERSTAND|PLANNING|THOUGHT|ACTION|OBSERVATION)\]')
    REQUIRED_STEPS = {"UNDERSTAND", "PLANNING", "THOUGHT", "ACTION"}

    @classmethod
    def parse(self, text: str) -> dict[str, str]:
        """Extract content between PTAO step markers from the LLM response.

        Parses markers like [UNDERSTAND], [PLANNING], [THOUGHT], [ACTION],
        and [OBSERVATION] to produce a structured dict.

        Args:
            text: The raw LLM response text.

        Returns:
            Dict mapping step names to their content strings.
        """
        log.info("[PTAO] Parsing response text (length=%d)", len(text))
        result: dict[str, str] = {}
        for step in ["UNDERSTAND", "PLANNING", "THOUGHT", "ACTION", "OBSERVATION"]:
            pattern = re.compile(
                rf'\[{step}\]\s*\n?(.*?)(?=\n\[[A-Z]+\]|$)',
                re.DOTALL,
            )
            match = pattern.search(text)
            result[step] = match.group(1).strip() if match else ""
        return result

    @classmethod
    def get_action_text(self, parsed: dict[str, str]) -> str:
        """Extract the ACTION step content which specifies the tool to call.

        Args:
            parsed: Dict from parse() containing extracted step content.

        Returns:
            The ACTION step text string.
        """
        log.info("[PTAO] Extracted action text (length=%d)", len(parsed.get("ACTION", "")))
        return parsed.get("ACTION", "")

    @classmethod
    def has_required_steps(self, text: str) -> tuple[bool, list[str]]:
        """Check if the response contains all required step markers."""
        found = set(self.STEP_PATTERN.findall(text))
        missing = self.REQUIRED_STEPS - found
        return (len(missing) == 0, sorted(missing))


# ─── Validator ──────────────────────────────────────────────────────────────


class PTAOValidator:
    """Validates PTAO responses and generates recovery messages."""

    REQUIRED_STEPS = {"UNDERSTAND", "PLANNING", "THOUGHT", "ACTION"}

    @classmethod
    def validate(self, parsed: dict[str, str], tool_calls: list[dict]) -> dict:
        """Validate a turn response.

        If tool_calls exist, the model took action -> skip text validation.
        If no tool_calls, check which thinking steps are present.
        A final response without any PTAO markers is treated as valid
        (the model chose not to use markers for a simple completion).
        """
        if tool_calls:
            return {
                "valid": True,
                "missing": [],
                "found": ["UNDERSTAND", "PLANNING", "THOUGHT", "ACTION"],
                "recovery": None,
                "has_tool_calls": True,
            }

        # Re-validate by checking which parsed steps have non-empty content
        found = [step for step in self.REQUIRED_STEPS if parsed.get(step, "").strip()]

        if not found:
            # No PTAO markers at all -> treat as a clean final response, not a failure
            return {
                "valid": True,
                "missing": [],
                "found": [],
                "recovery": None,
                "has_tool_calls": False,
            }

        # Some steps present but not all -> partial reasoning, flag it
        missing = self.REQUIRED_STEPS - set(found)

        return {
            "valid": True,  # still valid, but log what's missing
            "missing": sorted(missing),
            "found": sorted(found),
            "recovery": None,
            "has_tool_calls": False,
        }


# ─── Observation Formatter ─────────────────────────────────────────────────


class PTAOObservationFormatter:
    """Formats tool execution results as [OBSERVATION] messages."""

    @classmethod
    def format(self, tool_name: str, tool_call_id: str, content: str, is_error: bool = False) -> dict:
        """Build a single observation message dict."""
        status = "Error" if is_error else "Status: Success"
        return {
            "role": "user",
            "content": (
                f"[OBSERVATION]\n"
                f"Tool: {tool_name}\n"
                f"ID: {tool_call_id}\n"
                f"{status}\n"
                f"{content.strip()}"
            ),
        }
