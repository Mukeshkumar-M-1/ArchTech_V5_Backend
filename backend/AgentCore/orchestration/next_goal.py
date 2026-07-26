"""NextGoal — The deterministic next objective for the agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

log = logging.getLogger(__name__)


@dataclass
class NextGoal:
    """Produced by TaskPlanner each turn with the next objective.

    Attributes:
        section_number: The section this goal targets.
        section_name: Human-readable section name.
        objective: What this turn should accomplish.
        is_section_complete: Whether the section is complete.
        is_section_complete: Whether the goal is complete.
        is_document_complete: Whether the entire document is complete.
        context_requires: Required context dependencies.
        memory_sources: Memory sources to include.
    """
    section_number: str = ""
    section_name: str = ""
    objective: str = ""  # what this turn should accomplish
    is_section_complete: bool = False
    is_document_complete: bool = False
    context_requires: list[str] = field(default_factory=list)
    memory_sources: list[str] = field(default_factory=list)

    @classmethod
    def finished(cls) -> "NextGoal":
        """Factory producing a finished/complete NextGoal sentinel.

        Returns:
            A NextGoal instance with is_document_complete=True.
        """
        log.info("[NextGoal] Document complete reached")
        return cls(is_document_complete=True, objective="All sections complete.")
