"""
TokenUsageTracker — Tracks token usage across agent turns.

Phase 9: Records per-turn token consumption and provides
aggregate summaries for billing and monitoring.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class TokenUsageTracker:
    """Tracks token usage across all turns of an agent session."""

    def __init__(self) -> None:
        self._total_input = 0
        self._total_output = 0
        self._total = 0

    def record_turn(self, turn_number: int, tokens_in: int, tokens_out: int) -> None:
        """Record token usage for a single LLM turn.

        Args:
            turn_number: The turn being recorded.
            tokens_in: Number of input/prompt tokens.
            tokens_out: Number of output/completion tokens.
        """
        self._total_input += tokens_in
        self._total_output += tokens_out
        self._total = self._total_input + self._total_output
        log.info(
            "[TokenTracker] Turn %d: in=%d, out=%d, total_input=%d, total_output=%d, total=%d",
            turn_number,
            tokens_in,
            tokens_out,
            self._total_input,
            self._total_output,
            self._total,
        )

    def get_total(self) -> dict:
        """Get aggregate token usage summary.

        Returns:
            Dict with 'input', 'output', and 'total' counts.
        """
        return {
            "input": self._total_input,
            "output": self._total_output,
            "total": self._total,
        }
