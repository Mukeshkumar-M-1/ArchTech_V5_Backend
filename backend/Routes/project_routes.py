"""
Project routes — Project lifecycle management.

POST /init-project   — Initialize a project's directory structure on disk
"""

from __future__ import annotations

import logging
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

log = logging.getLogger(__name__)

class Project_init(BaseModel):
    project_id: str
    name: str


@router.post("/init-project")
async def init_project(request: Project_init):
    """Initialize a project's directory structure on the backend.

    Creates .Archtech/{project_id}/ and all subdirectories:
    requirements/, uploads/, memory/, templates/, sessions/, projects/,
    chat_sessions/, transcripts/
    """
    project_id = request.project_id
    name = request.name

    from project_context import ProjectContext
    ProjectContext.set(project_id)

    from system_config import (
        get_req_dir,
        get_project_base_dir,
        get_upload_source_file_dir,
        get_project_source_memory_dir,
        get_knowledge_source_dir,
        get_project_template_dir,
        get_transcript_dir,
        get_session_transcript_dir,
        get_project_transcript_dir,
        get_chat_session_dir,
    )
    # Touch every subdirectory — mkdir(parents=True, exist_ok=True)
    get_req_dir(project_id)
    get_upload_source_file_dir(project_id)
    get_project_source_memory_dir(project_id)
    get_knowledge_source_dir(project_id)
    get_project_template_dir(project_id)
    get_transcript_dir(project_id)
    get_session_transcript_dir(project_id)
    get_project_transcript_dir(project_id)
    get_chat_session_dir(project_id)

    log.info(f"[InitProject] Initialized project {project_id} at {get_project_base_dir()}")
    return {
        "status": "ok",
        "project_id": project_id,
        "message": f"Project '{project_id}' initialized",
    }
