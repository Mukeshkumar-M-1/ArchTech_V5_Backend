"""Config — Thin wrapper around system_config for AgentCore.

Provides consistent path resolution for all AgentCore modules.
Wraps the external system_config module so that internal modules
don't depend directly on it.
"""

from __future__ import annotations

import logging
from typing import Optional

# Import from external system_config module
try:
    from system_config import (
        get_project_base_dir,
        get_project_template_dir,
        get_knowledge_source_dir,
        get_transcript_dir,
        get_session_transcript_dir,
        get_project_transcript_dir,
        _ROOT_FOLDER_NAME,
    )

    _system_config_available = True
except ImportError:
    _system_config_available = False

log = logging.getLogger(__name__)
if not _system_config_available:
    log.warning("system_config module not available — path resolution will be disabled")


def get_project_base_path(project_id: str) -> Optional[str]:
    """Get the base path for a project.

    Args:
        project_id: The project identifier.

    Returns:
        The base path string, or None if system_config is unavailable.
    """
    if not _system_config_available:
        return None
    try:
        path = get_project_base_dir(project_id)
        log.info("Project base path resolved: %s", path)
        return path
    except Exception as exc:
        log.error("Failed to resolve project base path for project_id=%s: %s", project_id, exc)
        return None


def get_template_path(project_id: str, template_type: str = "srs") -> Optional[str]:
    """Get the template directory path for a project.

    Args:
        project_id: The project identifier.
        template_type: Template category (e.g., "srs", "sdd").

    Returns:
        The template directory path, or None if unavailable.
    """
    if not _system_config_available:
        return None
    try:
        path = get_project_template_dir(project_id, template_type)
        log.info("Template path resolved: %s", path)
        return path
    except Exception as exc:
        log.error("Failed to resolve template path for project_id=%s, type=%s: %s", project_id, template_type, exc)
        return None


def get_knowledge_path(project_id: str) -> Optional[str]:
    """Get the knowledge source directory for a project.

    Args:
        project_id: The project identifier.

    Returns:
        The knowledge directory path, or None if unavailable.
    """
    if not _system_config_available:
        return None
    try:
        path = get_knowledge_source_dir(project_id)
        log.info("Knowledge path resolved: %s", path)
        return path
    except Exception as exc:
        log.error("Failed to resolve knowledge path for project_id=%s: %s", project_id, exc)
        return None


def get_transcript_path(project_id: str) -> Optional[str]:
    """Get the transcript directory for a project.

    Args:
        project_id: The project identifier.

    Returns:
        The transcript directory path, or None if unavailable.
    """
    if not _system_config_available:
        return None
    try:
        path = get_transcript_dir(project_id)
        log.info("Transcript path resolved: %s", path)
        return path
    except Exception as exc:
        log.error("Failed to resolve transcript path for project_id=%s: %s", project_id, exc)
        return None


def get_root_folder_name() -> str:
    """Get the root folder name used by system_config.

    Returns:
        The root folder name string (default: ".Archtech").
    """
    if not _system_config_available:
        return ".Archtech"
    return _ROOT_FOLDER_NAME


def is_config_available() -> bool:
    """Check if the system_config module is available.

    Returns:
        True if system_config is importable, False otherwise.
    """
    return _system_config_available
