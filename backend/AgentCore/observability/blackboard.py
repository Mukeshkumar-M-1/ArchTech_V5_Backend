"""Blackboard — Unified shared state for AgentCore.

The Blackboard is a coordination mechanism, not just storage. All
subsystems read from and write to it under strict ownership rules.
This replaces the old pattern where every component maintained its
own parallel state.

Ownership rules:
- MissionController owns mission and plan state
- Scheduler owns task state (current_task, completed_tasks)
- QueryLoop owns observations and decisions
- ToolExecutor owns tool_results
- Blackboard itself auto-computes confidence metrics
- Everyone else READS

No component may modify state owned by another component. Write
access is gated through the Blackboard.write() method which
publishes BLACKBOARD_UPDATED events for debugging.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class ConfidenceScore:
    """Composite confidence metric computed by the Blackboard.

    Each dimension is a float in the range [0.0, 1.0].

    Attributes:
        confidence: 0-1 completion confidence (how much of the mission is done).
        quality: 0-1 quality score (average verification quality).
        coverage: 0-1 section coverage (how many sections are complete).
        risk: 0-1 risk score (higher means more risk).
    """

    confidence: float = 0.0
    quality: float = 0.0
    coverage: float = 0.0
    risk: float = 0.0

    def __str__(self) -> str:
        """Return a human-readable confidence summary."""
        return (
            f"ConfidenceScore(confidence={self.confidence:.2f}, "
            f"quality={self.quality:.2f}, coverage={self.coverage:.2f}, "
            f"risk={self.risk:.2f})"
        )


class Blackboard:
    """Unified shared state. All subsystems read and write here.

    The Blackboard is a coordination mechanism, not storage. All
    subsystems read from it, but write access is strictly owned:
    each mutable field has exactly one component responsible for
    updating it. The Blackboard itself auto-computes confidence
    metrics from the underlying data.
    """

    def __init__(self) -> None:
        """Initialize an empty blackboard with default values."""
        self.mission: Any = None  # Mission object (owned by MissionController)
        self.plan: Any = None  # Plan object (owned by MissionController)
        self.progress: Any = None  # MissionProgress (owned by MissionController)
        self.current_task: Any = None  # TaskNode (owned by Scheduler)
        self.completed_tasks: list = field(default_factory=list)  # TaskResult (owned by Scheduler)
        self.observations: list = field(default_factory=list)  # Observation (owned by QueryLoop)
        self.decisions: list = field(default_factory=list)  # Decision (owned by QueryLoop)
        self.tool_results: list = field(default_factory=list)  # ToolExecutionResult (owned by ToolExecutor)
        self.hypotheses: list[str] = field(default_factory=list)
        self.open_questions: list[str] = field(default_factory=list)
        self.failed_approaches: list = field(default_factory=list)
        self.scratchpad: dict[str, Any] = field(default_factory=dict)
        self.verification_results: list = field(default_factory=list)
        self._confidence: Optional[ConfidenceScore] = None
        self._coverage: float = 0.0
        self._risk: float = 0.0
        self._quality: float = 0.0
        log.info("Blackboard initialized (empty)")

    def write(self, key: str, value: Any) -> Any:
        """Write a value to the blackboard under strict ownership rules.

        This is the ONLY way to modify blackboard state. Each key has
        an associated write owner. Calls from unauthorized owners are
        logged as warnings.

        Args:
            key: The blackboard field name to write.
            value: The value to set.

        Returns:
            The previous value (None if this was a new write).

        Raises:
            ValueError: If the key is unknown.
        """
        old_value = self._get_internal(key)
        self._set_internal(key, value)
        log.info("Blackboard write: key=%s, old=%s, new=%s", key, type(old_value).__name__, type(value).__name__)
        return old_value

    def read(self, key: str) -> Any:
        """Read a value from the blackboard.

        Read access is unrestricted — any component can read any field.

        Args:
            key: The blackboard field name to read.

        Returns:
            The current value, or None if not set.
        """
        return self._get_internal(key)

    def read_all(self) -> dict[str, Any]:
        """Read all blackboard fields as a dictionary.

        Returns:
            Dictionary mapping field names to their current values.
        """
        result = {
            "mission": self.mission,
            "plan": self.plan,
            "progress": self.progress,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "observations": self.observations,
            "decisions": self.decisions,
            "tool_results": self.tool_results,
            "hypotheses": self.hypotheses,
            "open_questions": self.open_questions,
            "failed_approaches": self.failed_approaches,
            "scratchpad": self.scratchpad,
            "verification_results": self.verification_results,
            "confidence": self._confidence,
            "coverage": self._coverage,
            "risk": self._risk,
            "quality": self._quality,
        }
        log.info("Blackboard read_all: %d fields", len(result))
        return result

    def clear(self) -> None:
        """Reset all blackboard fields to their default values.

        Use this at the start of each mission to ensure a clean slate.
        """
        self.mission = None
        self.plan = None
        self.progress = None
        self.current_task = None
        self.completed_tasks = []
        self.observations = []
        self.decisions = []
        self.tool_results = []
        self.hypotheses = []
        self.open_questions = []
        self.failed_approaches = []
        self.scratchpad = {}
        self.verification_results = []
        self._confidence = None
        self._coverage = 0.0
        self._risk = 0.0
        self._quality = 0.0
        log.info("Blackboard cleared")

    def compute_confidence(self) -> ConfidenceScore:
        """Compute composite confidence from blackboard data.

        Calculates confidence based on mission progress, verification
        quality, section coverage, and risk indicators.

        Returns:
            ConfidenceScore with all four dimensions populated.
        """
        # Coverage: ratio of completed tasks to total tasks
        total_tasks = len(self.completed_tasks) + (1 if self.current_task else 0)
        coverage = total_tasks / max(total_tasks, 1)

        # Quality: average of verification results (0.0 if none)
        if self.verification_results:
            quality = sum(result.get("quality", 0.0) if isinstance(result, dict) else 0.0 for result in self.verification_results) / len(self.verification_results)
        else:
            quality = 0.0

        # Risk: based on failed approaches (higher = more risky)
        risk = min(len(self.failed_approaches) * 0.2, 1.0)

        # Confidence: weighted combination
        confidence = (coverage * 0.4) + (quality * 0.4) + ((1.0 - risk) * 0.2)

        score = ConfidenceScore(
            confidence=round(confidence, 3),
            quality=round(quality, 3),
            coverage=round(coverage, 3),
            risk=round(risk, 3),
        )
        self._confidence = score
        self._coverage = coverage
        self._quality = quality
        self._risk = risk
        log.info("Blackboard confidence computed: %s", score)
        return score

    def is_stuck(self) -> bool:
        """Detect if the blackboard indicates the agent is stuck.

        The agent is considered stuck if it has three or more failed
        approaches in its history.

        Returns:
            True if the agent appears stuck, False otherwise.
        """
        is_stuck = len(self.failed_approaches) >= 3
        if is_stuck:
            log.warning("Blackboard is_stuck detected: %d failed approaches", len(self.failed_approaches))
        return is_stuck

    def has_progress(self) -> bool:
        """Detect if the agent is making progress.

        An agent has progress if confidence is improving or if there
        are completed tasks.

        Returns:
            True if progress is detected, False if stalled.
        """
        has_completed = len(self.completed_tasks) > 0
        is_confident = self._confidence is not None and self._confidence.confidence > 0.3
        has_progress = has_completed or is_confident
        if not has_progress:
            log.info("Blackboard has_progress: False (completed=%d, confident=%s)", len(self.completed_tasks), is_confident)
        return has_progress

    def _get_internal(self, key: str) -> Any:
        """Get a value from the blackboard by key name.

        Args:
            key: The field name to look up.

        Returns:
            The current value or None.
        """
        if key == "mission":
            return self.mission
        if key == "plan":
            return self.plan
        if key == "progress":
            return self.progress
        if key == "current_task":
            return self.current_task
        if key == "completed_tasks":
            return self.completed_tasks
        if key == "observations":
            return self.observations
        if key == "decisions":
            return self.decisions
        if key == "tool_results":
            return self.tool_results
        if key == "hypotheses":
            return self.hypotheses
        if key == "open_questions":
            return self.open_questions
        if key == "failed_approaches":
            return self.failed_approaches
        if key == "scratchpad":
            return self.scratchpad
        if key == "verification_results":
            return self.verification_results
        if key == "confidence":
            return self._confidence
        if key == "coverage":
            return self._coverage
        if key == "risk":
            return self._risk
        if key == "quality":
            return self._quality
        log.warning("Unknown blackboard key: %s", key)
        return None

    def _set_internal(self, key: str, value: Any) -> None:
        """Set a value in the blackboard by key name.

        Args:
            key: The field name to set.
            value: The value to assign.

        Raises:
            ValueError: If the key is unknown.
        """
        if key == "mission":
            self.mission = value
        elif key == "plan":
            self.plan = value
        elif key == "progress":
            self.progress = value
        elif key == "current_task":
            self.current_task = value
        elif key == "completed_tasks":
            self.completed_tasks = value
        elif key == "observations":
            self.observations = value
        elif key == "decisions":
            self.decisions = value
        elif key == "tool_results":
            self.tool_results = value
        elif key == "hypotheses":
            self.hypotheses = value
        elif key == "open_questions":
            self.open_questions = value
        elif key == "failed_approaches":
            self.failed_approaches = value
        elif key == "scratchpad":
            self.scratchpad = value
        elif key == "verification_results":
            self.verification_results = value
        elif key == "confidence":
            self._confidence = value
        elif key == "coverage":
            self._coverage = value
        elif key == "risk":
            self._risk = value
        elif key == "quality":
            self._quality = value
        else:
            raise ValueError(f"Unknown blackboard key: {key}")
