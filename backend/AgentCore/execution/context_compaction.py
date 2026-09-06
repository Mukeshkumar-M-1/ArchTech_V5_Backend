"""
Compaction pipeline — Keeps conversation under the context window limit.

Mirrors CCB's context management chain (query.ts:509-637):
1. Snip Compact — Replace large file contents with stubs (msg count > 30)
2. MicroCompact — Clear old tool results with placeholder (time-based)
3. Auto-Compact — Summarize old messages when tokens exceed budget (emergency)

The pipeline runs every API turn. It returns modified messages that fit within
the context budget. Auto-compact delegates summary generation to the caller
(session_memory.py for session memory reuse, or a legacy fallback).
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

log = logging.getLogger(__name__)

TOOL_COMPACT_THRESHOLD = 5_000
ASSISTANT_COMPACT_THRESHOLD = 5_000
MESSAGE_THRESHOLD = -50
DEFAULT_TOKEN_BUDGET = 100_000
MICROCOMPACT_INTERVAL = 5
PRESERVE_TOOL_RESULTS = 2


@dataclass
class ContextCompactState:
    consecutive_fails: int = 0
    micro_turn_counter: int = 0
    breaker_open_until: float = 0.0


class ContextTokenEstimator:
    """Token estimator using tiktoken cl100k_base (Claude tokenization).

    Falls back to character-based estimation if tiktoken unavailable.
    """

    _ENCODER = None

    @classmethod
    def _get_encoder(cls):
        if cls._ENCODER is None:
            try:
                import tiktoken
                cls._ENCODER = tiktoken.get_encoding("cl100k_base")
            except Exception:
                cls._ENCODER = "fallback"
        return cls._ENCODER

    @staticmethod
    def estimate(messages: list[dict]) -> int:
        """Estimate token count from a list of messages.

        Args:
            messages: List of message dicts.

        Returns:
            Estimated token count.
        """
        encoder = ContextTokenEstimator._get_encoder()
        total = 0

        for msg in messages:
            text = json.dumps(msg, default=str)
            if encoder == "fallback":
                total += max(1, len(text) // 3)
            else:
                total += len(encoder.encode(text))

        return total

# TOOL COMPACT
class ContextToolCompact:
    """Compact large tool result messages by truncating their content.

    Scans messages for tool_result blocks and truncates content exceeding
    TOOL_COMPACT_THRESHOLD characters to a manageable stub.
    """

    PATH_PATTERNS = [
        re.compile(r"([A-Za-z]:\\[^\s]+)"),
        re.compile(r"(/[^ \n]+)"),
        re.compile(r"([\w./-]+\.(py|ts|js|md|txt|json|yaml|toml))"),
    ]

    @classmethod
    def extract_path(self, content: str) -> Optional[str]:
        """Extract a file path from tool output content.

        Args:
            content: The tool output to scan for a file path.

        Returns:
            The first matched file path, or None.
        """
        text = "\n".join(content.splitlines()[:10])

        for pattern in self.PATH_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)

        return None

    @classmethod
    def run(self, messages: list[dict]) -> list[dict]:
        """Run tool compaction on the message list, truncating large outputs.

        Args:
            messages: List of message dicts to compact.

        Returns:
            Compacted message list with truncated tool outputs.
        """
        result = []
        for message_item in messages[MESSAGE_THRESHOLD:]:

            copy_message_item = copy.deepcopy(message_item)

            # VALID TOOL ROLE ONLY
            if message_item.get("role") != "tool":
                continue
            
            tool_name = message_item.get("name")
            tool_content = str(message_item.get("content", ""))
            tool_path_extracted = self.extract_path(tool_content)

            if len(tool_content) >= TOOL_COMPACT_THRESHOLD:
                if tool_path_extracted:
                    copy_message_item["content"] = (
                        f"Tool Name: {tool_name}\n"
                        f"[File: {tool_path_extracted}, "
                        f"{len(tool_content.splitlines())} lines]\n"
                        f"[Tool Raw content truncated: {tool_content[:TOOL_COMPACT_THRESHOLD]}]"
                    )
                else:
                    copy_message_item["content"] = (
                        f"Tool Name: {tool_name}\n"
                        f"[Tool Raw content truncated: {tool_content[:TOOL_COMPACT_THRESHOLD]}]\n"
                        f"[Tool result truncated: {len(tool_content)} chars]"
                    )
            result.append(copy_message_item)

        return result


class ContextAssistantCompact:
    """Compact long assistant messages that exceed the token threshold.

    Only text-only assistant messages (without tool calls) are compacted.
    Long responses are truncated with a preview to keep within budget.
    """

    @staticmethod
    def run(messages: list[dict]) -> list[dict]:
        """Compact assistant messages that exceed the token threshold.

        Only text-only assistant messages (no tool calls) are compacted.

        Args:
            messages: List of message dicts to compact.

        Returns:
            The compacted message list.
        """
        log.info("[Assistant_compact] Running on %d messages", len(messages))
        result = []
        for message_item in messages[MESSAGE_THRESHOLD:]:
            copy_message_item = copy.deepcopy(message_item)

            # VALID ASSISTANT ROLE ONLY
            if message_item.get("role") != "assistant":
                continue

            assistant_content = str(message_item.get("content", ""))
            tool_calls = message_item.get("tool_calls")

            # Only compact text-only assistant messages (no tool calls)
            if tool_calls:
                result.append(copy_message_item)
                continue

            if len(assistant_content) >= ASSISTANT_COMPACT_THRESHOLD:
                copy_message_item["content"] = (
                    f"[Assistant response truncated: {len(assistant_content)} chars]\n\n"
                    f"Preview:\n{assistant_content[:ASSISTANT_COMPACT_THRESHOLD]}"
                )

            result.append(copy_message_item)

        return result


class ContextAutoCompact:
    """Emergency auto-compaction when messages exceed the token budget.

    When the estimated token count exceeds the budget, replaces old messages
    with a summary generated by the provided summarize_fn. Includes a circuit
    breaker to prevent runaway compaction.
    """

    BREAKER_TIMEOUT = 300

    @staticmethod
    def run(
        messages: list[dict],
        token_budget: int,
        summarize_fn: Optional[Callable],
        state: ContextCompactState,
    ) -> Tuple[list[dict], Optional[str]]:
        """Run auto-compaction when token budget is exceeded.

        Uses a circuit breaker to avoid repeated failed compactions.
        Delegates summary generation to summarize_fn if available.

        Args:
            messages: Current conversation messages.
            token_budget: Maximum allowed token count.
            summarize_fn: Optional callable to generate summaries.
            state: Current compaction state for breaker logic.

        Returns:
            Tuple of (compacted messages, summary string or None).
        """
        log.info("[ContextAutoCompact] Checking %d messages against budget %d", len(messages), token_budget)
        now = time.time()

        if state.breaker_open_until > now:
            return messages, None

        tokens = ContextTokenEstimator.estimate(messages)

        if tokens <= token_budget:
            return messages, None

        log.info(
            f"Context exceeded budget "
            f"({tokens} > {token_budget})"
        )

        running = 0
        split_index = 0

        for i, msg in enumerate(messages):
            running += ContextTokenEstimator.estimate([msg])

            if running >= tokens * 0.4:
                split_index = i
                break

        old_messages = messages[:split_index]
        recent_messages = messages[split_index:]

        summary = None

        if summarize_fn:

            try:
                summary = summarize_fn(old_messages)

                if summary and len(summary.strip()) > 10:
                    state.consecutive_fails = 0
                else:
                    summary = None
                    state.consecutive_fails += 1

            except Exception as e:
                log.warning(
                    f"Summary failed: {e}"
                )
                state.consecutive_fails += 1

        if state.consecutive_fails >= 3:

            state.breaker_open_until = (
                time.time() +
                ContextAutoCompact.BREAKER_TIMEOUT
            )

            log.warning(
                "Compaction breaker opened"
            )

            return messages, None

        compacted = [
            {
                "role": "system",
                "content": (
                    f"[Messages 1-{split_index} "
                    f"were compacted]"
                ),
            }
        ]

        if summary:
            compacted.append(
                {
                    "role": "system",
                    "content": summary,
                }
            )

        compacted.extend(recent_messages)

        return compacted, summary


class ContextCompactPipeline:
    """Run the full compaction pipeline: tool compact, assistant compact, auto compact.

    Orchestrates three compaction strategies in sequence:
    1. Tool_compact — truncate large tool outputs
    2. Assistant_compact — truncate long assistant messages
    3. AutoCompact — emergency summary when budget is exceeded

    The pipeline is designed to be idempotent and safe to run every turn.
    All steps process messages in-place to preserve conversation ordering.

    Attributes:
        token_budget: Maximum token budget before auto-compaction triggers.
        summarize_fn: Optional callable for generating summaries during auto-compaction.
        state: CompactState tracking compaction health.
    """

    def __init__(
        self,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ):
        """Initialize the compaction pipeline.

        Args:
            token_budget: Maximum token budget before auto-compaction triggers.
        """
        log.info("[CompactPipeline] Initialized with token_budget=%d", token_budget)
        self.token_budget = token_budget
        self.summarize_fn = None
        self.state = ContextCompactState()

    def set_summarize_fn(
        self,
        fn: Callable,
    ) -> None:
        """Set the summary generation function for auto-compaction.

        Args:
            fn: Callable that takes a list of messages and returns a summary string.
        """
        log.info("[CompactPipeline] set_summarize_fn: summary function configured")
        self.summarize_fn = fn

    def run(
        self,
        messages: list[dict],
    ) -> Tuple[list[dict], Optional[str]]:
        """Run the full compaction pipeline: tool, assistant, and auto-compaction.

        Processes messages in-place to preserve turn-by-turn ordering.
        Each compaction step modifies content without reordering.

        Args:
            messages: List of message dicts to compact.

        Returns:
            Tuple of (compacted messages, summary string or None).
        """
        # Deep copy to avoid mutating the original — preserves original order
        result = copy.deepcopy(messages)

        # Step 1: Tool compact — truncate oversized tool outputs in-place
        result = self._apply_tool_compact(result)

        # Step 2: Assistant compact — truncate oversized assistant messages in-place
        result = self._apply_assistant_compact(result)

        # Step 3: Auto compact — summarize old portion when budget exceeded
        result, summary = ContextAutoCompact.run(
            messages=result,
            token_budget=self.token_budget,
            summarize_fn=self.summarize_fn,
            state=self.state,
        )

        return result, summary

    @staticmethod
    def _apply_tool_compact(messages: list[dict]) -> list[dict]:
        """Truncate large tool result content, preserving message order."""
        for msg in messages:
            if msg.get("role") != "tool":
                continue
            tool_content = str(msg.get("content", ""))
            if len(tool_content) < TOOL_COMPACT_THRESHOLD:
                continue

            tool_name = msg.get("name", "unknown")
            tool_path = ContextToolCompact.extract_path(tool_content)
            if tool_path:
                msg["content"] = (
                    f"Tool Name: {tool_name}\n"
                    f"[File: {tool_path}, "
                    f"{len(tool_content.splitlines())} lines]\n"
                    f"[Tool Raw content truncated: {tool_content[:TOOL_COMPACT_THRESHOLD]}]"
                )
            else:
                msg["content"] = (
                    f"Tool Name: {tool_name}\n"
                    f"[Tool Raw content truncated: {tool_content[:TOOL_COMPACT_THRESHOLD]}]\n"
                    f"[Tool result truncated: {len(tool_content)} chars]"
                )
            log.info(
                "[CompactPipeline] Tool_compact truncated '%s' from %d chars",
                tool_name, len(tool_content),
            )
        return messages

    @staticmethod
    def _apply_assistant_compact(messages: list[dict]) -> list[dict]:
        """Truncate long text-only assistant messages, preserving message order."""
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            if msg.get("tool_calls"):
                continue
            assistant_content = str(msg.get("content", ""))
            if len(assistant_content) < ASSISTANT_COMPACT_THRESHOLD:
                continue

            msg["content"] = (
                f"[Assistant response truncated: {len(assistant_content)} chars]\n\n"
                f"Preview:\n{assistant_content[:ASSISTANT_COMPACT_THRESHOLD]}"
            )
            log.info(
                "[CompactPipeline] Assistant_compact truncated from %d chars",
                len(assistant_content),
            )
        return messages

    def reset(self) -> None:
        """Reset the compaction state (breaker, counters, etc.)."""
        log.info("[ContextCompactPipeline] Reset compaction state")
        self.state = ContextCompactState()

    def reset_failures(self) -> None:
        """Reset only the consecutive failure counter."""
        log.info("[CompactPipeline] Reset failure counter")
        self.state.consecutive_fails = 0
