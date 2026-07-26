"""
MessageManager — Tracks and emits agent progress events.

Phase 3: Provides per-agent messaging capabilities including
progress emission and context clearing.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class MessageManager:
    """Manages per-agent messages and progress events."""

    def __init__(self) -> None:
        self._messages: list[dict] = []

    def emit_progress_event(
        self, content: str = "", tokens_in: int = 0, tokens_out: int = 0
    ) -> None:
        """Emit a progress update event.

        Args:
            content: Text content of the progress update.
            tokens_in: Number of input tokens for this turn.
            tokens_out: Number of output tokens for this turn.
        """
        event = {
            "type": "progress",
            "content": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        self._messages.append(event)
        log.info(
            "[MessageManager] Progress event: tokens_in=%d, tokens_out=%d, content_len=%d",
            tokens_in,
            tokens_out,
            len(content),
        )

    def clear_context(self) -> None:
        """Clear all messages in this agent's context."""
        count = len(self._messages)
        self._messages.clear()
        log.info("[MessageManager] Cleared %d messages", count)
