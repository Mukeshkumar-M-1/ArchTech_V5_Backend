"""BudgetManager — Centralized budget enforcement for AgentCore.

Tracks six dimensions of resource consumption and enforces hard
limits. Reports warnings at 90% threshold and errors at 100%.
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


class BudgetStatus(enum.Enum):
    """Budget status indicator for a single dimension or the full budget.

    Attributes:
        OK: Usage is within acceptable limits.
        WARNING: Usage is at 90% or above the limit (graceful degradation).
        EXCEEDED: Usage has exceeded the limit (hard stop).
    """

    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


@dataclass
class BudgetUsage:
    """Tracks current resource consumption across all dimensions.

    All counters start at zero and only increase (monotonic).

    Attributes:
        tokens_input: Number of input tokens consumed by the LLM.
        tokens_output: Number of output tokens consumed by the LLM.
        wall_clock_seconds: Total wall clock time in seconds.
        tool_executions: Number of tool calls executed.
        retry_count: Number of retries performed.
    """

    tokens_input: int = 0
    tokens_output: int = 0
    wall_clock_seconds: float = 0.0
    tool_executions: int = 0
    retry_count: int = 0


class BudgetManager:
    """Centralized budget enforcement with six dimensions.

    Tracks token usage, tool execution count, retry count, and wall
    clock time. Reports WARNING at 90% threshold and EXCEEDED at 100%.
    All limits are enforced relative to mission-level budgets.

    Example:
        budget = BudgetManager(max_tokens_input=500_000, max_tokens_output=100_000, ...)
        budget.record_token_usage(10000, 5000)
        status = budget.check("tokens_input")  # BudgetStatus.OK
    """

    # Default dimension ratios
    WARNING_RATIO = 0.9
    EXCEEDED_RATIO = 1.0

    def __init__(
        self,
        max_tokens_input: int = 500_000,
        max_tokens_output: int = 100_000,
        max_time_seconds: float = 3600.0,
        max_tools: int = 500,
        max_retries: int = 10,
    ) -> None:
        """Initialize budget manager with dimension limits.

        Args:
            max_tokens_input: Maximum input token budget for the mission.
            max_tokens_output: Maximum output token budget for the mission.
            max_time_seconds: Maximum wall clock time in seconds.
            max_tools: Maximum tool execution count for the mission.
            max_retries: Maximum retry count for the mission.
        """
        self.limits: dict[str, int | float] = {
            "tokens_input": max_tokens_input,
            "tokens_output": max_tokens_output,
            "wall_clock_seconds": max_time_seconds,
            "tool_executions": max_tools,
            "retry_count": max_retries,
        }
        self.usage: BudgetUsage = BudgetUsage()
        self._start_time: Optional[float] = None
        log.info("BudgetManager initialized: %s", {k: v for k, v in self.limits.items()})

    def check(self, dimension: str) -> BudgetStatus:
        """Check a single budget dimension against its limit.

        Args:
            dimension: One of the tracked dimension names.

        Returns:
            BudgetStatus indicating usage level (OK, WARNING, or EXCEEDED).

        Raises:
            ValueError: If the dimension name is unknown.
        """
        if dimension not in self.limits:
            raise ValueError(f"Unknown budget dimension: {dimension}")

        limit = self.limits[dimension]
        current = self._get_usage(dimension)
        ratio = current / limit if limit > 0 else 0.0

        if ratio >= self.EXCEEDED_RATIO:
            log.warning("Budget EXCEEDED: %s usage=%s, limit=%s (ratio=%.0f%%)", dimension, current, limit, ratio * 100)
            return BudgetStatus.EXCEEDED
        if ratio >= self.WARNING_RATIO:
            log.warning("Budget WARNING: %s usage=%s, limit=%s (ratio=%.0f%%)", dimension, current, limit, ratio * 100)
            return BudgetStatus.WARNING
        return BudgetStatus.OK

    def validate(self) -> BudgetStatus:
        """Check all budget dimensions and return the most severe status.

        Returns:
            BudgetStatus.OK if all within limits, or the most severe
            status across all dimensions.
        """
        statuses = [self.check(dimension) for dimension in self.limits]
        if BudgetStatus.EXCEEDED in statuses:
            return BudgetStatus.EXCEEDED
        if BudgetStatus.WARNING in statuses:
            return BudgetStatus.WARNING
        return BudgetStatus.OK

    def record_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from an LLM API call.

        Args:
            input_tokens: Number of input tokens consumed by this call.
            output_tokens: Number of output tokens consumed by this call.
        """
        self.usage.tokens_input += input_tokens
        self.usage.tokens_output += output_tokens
        log.info("Recorded tokens: input=%d, output=%d", input_tokens, output_tokens)

    def record_tool_execution(self) -> None:
        """Record a tool execution."""
        self.usage.tool_executions += 1
        log.info("Tool execution recorded (total: %d)", self.usage.tool_executions)

    def record_retry(self) -> None:
        """Record a retry."""
        self.usage.retry_count += 1
        log.info("Retry recorded (total: %d)", self.usage.retry_count)

    def start_timer(self) -> float:
        """Start timing a budget-sensitive operation.

        Returns:
            Timestamp suitable for stop_timer().
        """
        self._start_time = time.time()
        log.info("Timer started at %.3f", self._start_time)
        return self._start_time

    def stop_timer(self, start_time: float) -> None:
        """Stop timing a budget-sensitive operation and record elapsed time.

        Args:
            start_time: Timestamp from the matching start_timer() call.
        """
        elapsed = time.time() - start_time
        self.usage.wall_clock_seconds += elapsed
        log.info("Timer stopped: elapsed=%.3fs, total=%.3fs", elapsed, self.usage.wall_clock_seconds)
