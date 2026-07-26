"""ProjectContext — Stores the current active project ID for the session."""

import logging

log = logging.getLogger(__name__)

class ProjectContext:
    """Stores the current active project ID for the session."""
    _project_id: str | None = None

    @classmethod
    def set(self, project_id: str) -> None:
        log.info("[project_context] set -> '%s'", project_id)
        self._project_id = project_id

    @classmethod
    def get(self) -> str | None:
        result = self._project_id
        log.info("[project_context] get -> '%s'", result)
        return result

    @classmethod
    def clear(self) -> None:
        was = self._project_id
        self._project_id = None
        log.info("[project_context] clear -> '%s'", was)
