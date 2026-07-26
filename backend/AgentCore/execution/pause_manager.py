"""Pause signal management for document generation sessions."""

import logging
from typing import Dict

log = logging.getLogger(__name__)

# Per-project pause signals: project_id -> bool
_paused: Dict[str, bool] = {}


def is_paused(project_id: str) -> bool:
    """Check if a project has been paused."""
    return _paused.get(project_id, False)


def set_paused(project_id: str) -> None:
    """Set the pause signal for a project."""
    _paused[project_id] = True
    log.info(f"[PauseManager] Project {project_id} paused")


def clear_paused(project_id: str) -> None:
    """Clear the pause signal for a project (used on new generation start)."""
    if project_id in _paused:
        del _paused[project_id]
    log.info(f"[PauseManager] Cleared pause signal for project {project_id}")
