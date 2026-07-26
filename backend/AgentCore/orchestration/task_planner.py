"""TaskPlanner — Deterministic planner that decides the next turn goal."""

from __future__ import annotations

import logging
from typing import Any, Optional
from .next_goal import NextGoal

log = logging.getLogger(__name__)


class TaskPlanner:
    """Decides what the model should do next. Never self-decides — purely code-driven."""

    def __init__(
        self,
        all_section_numbers: list[str],
        dependency_graph: Any = None,
    ) -> None:
        """Initialize the task planner.

        Args:
            all_section_numbers: List of all section identifiers.
            dependency_graph: Optional DependencyGraph for ordering.
        """
        self._all: list[str] = all_section_numbers
        self._dep_graph = dependency_graph
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._current_section: str = ""
        self._turn_count: int = 0
        self._max_turns_per_section: int = 50
        log.info(f"[TaskPlanner] Initialized with {len(all_section_numbers)} sections, "
                 f"has_deps={dependency_graph is not None}")

    def set_current_section(self, section_number: str) -> None:
        """Set the current working section and reset turn count.

        Args:
            section_number: The section to work on.
        """
        self._current_section = section_number
        self._turn_count = 0
        log.info(f"[TaskPlanner] Set current section to {section_number}, turn_count reset to 0")

    def record_completed(self, section_number: str) -> None:
        """Record a section as completed and clear current section.

        Args:
            section_number: The completed section identifier.
        """
        self._completed.add(section_number)
        if self._current_section == section_number:
            log.info(f"[TaskPlanner] Section {section_number} marked completed, clearing current section")
            self._current_section = ""
        log.info(f"[TaskPlanner] Completed: {self._completed}, remaining: {len(self._all) - len(self._completed) - len(self._failed)}")

    def record_failed(self, section_number: str) -> None:
        """Record a section as failed.

        Args:
            section_number: The failed section identifier.
        """
        self._failed.add(section_number)
        if self._current_section == section_number:
            log.info(f"[TaskPlanner] Section {section_number} marked failed, clearing current section")
            self._current_section = ""
        log.info(f"[TaskPlanner] Failed: {self._failed}")

    def increment_turn(self) -> None:
        """Increment the turn counter for the current section.

        Tracks how many turns have been used within the current section
        relative to the max turns limit.
        """
        self._turn_count += 1
        log.info(f"[TaskPlanner] Turn count for section {self._current_section}: {self._turn_count}/{self._max_turns_per_section}")

    def decide_next_turn_goal(self) -> NextGoal:
        """Return the next goal. Call this each turn.

        Returns:
            The NextGoal with section, objective, and completion flags.
        """
        # Check if all done
        done = self._completed | self._failed
        if len(done) >= len(self._all):
            log.info(f"[TaskPlanner] All sections accounted for ({len(done)}/{len(self._all)}), document complete")
            return NextGoal.finished()

        log.info(f"[TaskPlanner] Current section='{self._current_section}', turns={self._turn_count}, "
                  f"completed={len(self._completed)}, failed={len(self._failed)}")

        # If currently in a section and haven't hit max turns, stay here
        if self._current_section and self._turn_count < self._max_turns_per_section:
            obj = f"Continue generating section {self._current_section}. Turn {self._turn_count + 1}."
            log.info(f"[TaskPlanner] Returning continue goal for section {self._current_section}: '{obj}'")
            return NextGoal(
                section_number=self._current_section,
                objective=obj,
            )

        # Advance to next available section
        next_section = self._find_next_section()
        if next_section:
            self._current_section = next_section
            self._turn_count = 0
            obj = f"Start generating section {next_section}."
            log.info(f"[TaskPlanner] Advancing to new section {next_section}: '{obj}'")
            return NextGoal(
                section_number=next_section,
                objective=obj,
            )

        log.info("[TaskPlanner] No next section found, returning finished")
        return NextGoal.finished()

    def _find_next_section(self) -> Optional[str]:
        """Find the next section whose prerequisites are satisfied.

        Iterates through all sections, skipping completed/failed ones,
        and checks dependency graph constraints.

        Returns:
            The next available section identifier, or None.
        """
        for s in self._all:
            if s in self._completed or s in self._failed:
                log.info(f"[TaskPlanner] Skipping section {s}: {'completed' if s in self._completed else 'failed'}")
                continue
            if self._dep_graph and not self._dep_graph.is_satisfied(s, list(self._completed)):
                prereqs = self._dep_graph.get_prerequisites(s) if hasattr(self._dep_graph, 'get_prerequisites') else set()
                log.info(f"[TaskPlanner] Section {s} blocked: deps not met (prereqs={prereqs})")
                continue
            log.info(f"[TaskPlanner] Found available section: {s}")
            return s
        return None
