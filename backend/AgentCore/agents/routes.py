"""
document_generate_routes.py — API endpoints for document generation.

POST /generate-document-stream      — SSE streaming endpoint
GET  /document-generation-progress/{project_id} — Poll progress
POST /document-generation-cancel/{project_id}   — Cancel generation
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import datetime
import os
import tempfile
import shutil
import traceback
import AgentCore.execution.builtins

log = logging.getLogger(__name__)
router = APIRouter()
DEFAULT_MAX_WORKERS = 1


class GenerateDocumentRequest(BaseModel):
    project_id: str
    template_type: str = "srs"


# ── POST /generate-document-stream ─────────────────────────────────────

@router.post("/generate-document-stream")
async def generate_document_stream(request: GenerateDocumentRequest) -> StreamingResponse:
    """Stream document generation via Server-Sent Events.

    Args:
        request: Pydantic model containing project_id and template_type.

    Returns:
        StreamingResponse with SSE document generation events.
    """
    project_id = request.project_id
    template_type = request.template_type.lower()

    log.info(f"[GenerateAgentRoute] project_id={project_id} template_type={template_type}")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    # Clear any stale pause signal from a previous session
    from AgentCore.execution.pause_manager import clear_paused
    clear_paused(project_id)

    # Create unified SSE message manager
    from AgentCore.execution.message_manager import SSEGenerationMessageManager
    sse_generation_message_manager = SSEGenerationMessageManager()

    # DOCUMENT AGENT WORKER
    async def _emit_document_generated_data() -> None:
        """Runs the document generation agent and feeds events to the sse_generation_message_manager's queue.

        This coroutine runs in the background, with all events (tool, section, mission)
        flowing through the single SSEGenerationMessageManager.
        """
        from AgentCore.orchestration.orchestrator import MissionOrchestrator

        try:
            log.info("[GenerateAgentRoute] Initializing MissionOrchestrator for document [%s] for project_ID [%s]", template_type, project_id)
            mission_orchestrator = MissionOrchestrator(
                project_id=project_id,
                num_workers=DEFAULT_MAX_WORKERS,
                message_manager=sse_generation_message_manager,
            )
            await mission_orchestrator.execute_mission(
                project_id,
                template_type,
                f"Generate {template_type} document for project {project_id}",
            )
        except Exception as exception:
            log.error(f"[GenerateAgentRoute] mission orchestrator error: {exception}")
            sse_generation_message_manager.emit_error(str(exception))
        finally:
            await sse_generation_message_manager.done()

    # DOCUMENT STREAMING HANDLER
    async def _document_streaming_handler() -> AsyncGenerator[str, None]:
        """Streams SSE events from the sse_generation_message_manager's queue to the client.

        Creates a producer task, yields formatted SSE chunks, and ensures
        cleanup on cancellation.
        """
        log.info("[GenerateAgentRoute] Document generation streaming data")
        document_worker_task = asyncio.create_task(_emit_document_generated_data())
        try:
            async for chunk in sse_generation_message_manager.stream():
                yield chunk
        finally:
            document_worker_task.cancel()
            try:
                await document_worker_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _document_streaming_handler(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── GET /document-generation-progress/{project_id} ─────────────────────

@router.get("/document-generation-progress/{project_id}")
def get_document_generation_progress(project_id: str) -> dict:
    """Return session progress data for a project.

    Args:
        project_id: The project identifier to query.

    Returns:
        Dict containing status, progress, phase, and timing data.
    """
    log.info("[GenerateAgentRoute] Progress query for project %s", project_id)
    from AgentCore import GenerationSessionManager
    return GenerationSessionManager.get_progress(project_id)


# ── POST /document-generation-cancel/{project_id} ──────────────────────

@router.post("/document-generation-cancel/{project_id}")
def cancel_document_generation(project_id: str) -> dict:
    """Cancel a running document generation by aborting sessions and hierarchies.

    Args:
        project_id: The project identifier whose generation should be cancelled.

    Returns:
        Dict with status and confirmation message.
    """
    log.info("[GenerateAgentRoute] Cancelling document generation for project %s", project_id)
    from AgentCore import GenerationSessionManager
    from AgentCore.execution.abort_controller import get_hierarchy

    session = GenerationSessionManager.find_active(project_id)
    if session:
        GenerationSessionManager.cancel(session_id=session.session_id, project_id=project_id)

    try:
        hierarchy = get_hierarchy()
        if session:
            hierarchy.abort_tree(session.session_id, reason="user cancelled document generation")
        else:
            hierarchy.abort_tree(project_id, reason="user cancelled document generation")
    except Exception:
        pass

    return {"status": "ok", "message": "Generation cancelled"}


# ── POST /document-generation-pause/{project_id} ───────────────────────

@router.post("/document-generation-pause/{project_id}")
def pause_document_generation(project_id: str) -> dict:
    """Pause a running document generation."""
    from AgentCore.execution.pause_manager import set_paused

    log.info(f"[GenerateAgentRoute] Pausing document generation for project {project_id}")
    set_paused(project_id)
    return {"status": "ok", "message": "Generation paused"}


# ── POST /document-generation-resume/{project_id} ──────────────────────

@router.post("/document-generation-resume/{project_id}")
def resume_document_generation(project_id: str) -> dict:
    """Resume a paused document generation (starts fresh)."""
    from AgentCore.execution.pause_manager import clear_paused

    log.info(f"[GenerateAgentRoute] Resuming document generation for project {project_id}")
    clear_paused(project_id)
    return {"status": "ok", "message": "Generation resumed"}


# ── POST /generation-interact ──────────────────────────────────────────

class GenerationInteractRequest(BaseModel):
    project_id: str
    task_id: str
    tool_call_id: str
    response: Any


@router.post("/generation-interact")
def generation_interact(request_body: GenerationInteractRequest) -> dict:
    """Receive user response for a pending generation interaction (RequestUserInput / ProposeContentEdit).

    Signals the engine's asyncio.Event so the in-flight execute_task() loop can
    resume, and feeds the user response into the query loop for the next LLM turn.
    """
    from AgentCore.core.execution_engine import get_generation_loop, get_generation_engine, unregister_generation_loop

    log.info(f"[GenerateAgentRoute] Generation interaction for project {request_body.project_id}, task {request_body.task_id}, tool {request_body.tool_call_id}")
    log.info(f"[GenerateAgentRoute] [Request_Body] : {request_body}")

    interaction_key = f"{request_body.task_id}_{request_body.tool_call_id}"
    query_loop = get_generation_loop(interaction_key)
    execution_engine = get_generation_engine(interaction_key)
    if not query_loop or not execution_engine:
        return {"status": "error", "message": "No pending interaction for this task"}

    # Store the user response and signal the waiting engine
    execution_engine._user_response = request_body.response
    unregister_generation_loop(interaction_key)

    # Signal the asyncio.Event — the execution engine is currently blocked on
    # await self._input_ready_event.wait() inside execute_task().
    # DO NOT clear _awaiting_input or _user_response here — let execute_task
    # handle the cleanup after injecting the tool response into the turn.
    if execution_engine._input_ready_event and not execution_engine._input_ready_event.is_set():
        execution_engine._input_ready_event.set()

    log.info("[GenerateAgentRoute] Generation interaction resumed for task %s", request_body.task_id)
    return {"status": "resumed"}


# ── POST /regenerate-section-stream ────────────────────────────────────

class RegenerateSectionRequest(BaseModel):
    project_id: str
    template_type: str = "srs"
    section_filename: str
    document_version: int | None = None


@router.post("/regenerate-section-stream")
async def regenerate_section_stream(request: RegenerateSectionRequest) -> StreamingResponse:
    """Stream section regeneration via Server-Sent Events.

    Creates a new document version, copies all existing sections from the
    previous version, then regenerates only the requested section.
    """
    log.info(f"Generated Document version : {request}")
    project_id = request.project_id
    template_type = request.template_type.lower()
    section_filename = request.section_filename
    previous_document_version = request.document_version

    log.info("[RegenerateSectionRoute] project_id=%s section=%s template_type=%s", project_id, section_filename, template_type)

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not section_filename:
        raise HTTPException(status_code=400, detail="section_filename is required")

    # Clear any stale pause signal from a previous session
    from AgentCore.execution.pause_manager import clear_paused
    clear_paused(project_id)

    # Create unified SSE message manager
    from AgentCore.execution.message_manager import SSEGenerationMessageManager
    sse_generation_message_manager = SSEGenerationMessageManager()

    # ── Section Regeneration Worker ──
    async def _emit_section_regenerated_data() -> None:
        """Runs the section regeneration agent and feeds events to the SSE queue."""
        from AgentCore.orchestration.orchestrator import MissionOrchestrator
        from system_config import start_new_version, copy_sections_to_new_version

        try:
            # Copy previous version sections so only the target changes
            document_new_version = start_new_version(project_id, template_type)
            if document_new_version > 1:
                copy_sections_to_new_version(project_id, previous_document_version, document_new_version)

            log.info("[RegenerateSectionRoute] Regenerating section [%s] for project [%s]", section_filename, project_id)
            mission_orchestrator = MissionOrchestrator(
                project_id=project_id,
                num_workers=1,
                message_manager=sse_generation_message_manager,
            )
            await mission_orchestrator.execute_mission(
                project_id,
                template_type,
                f"Regenerate section {section_filename} for project {project_id}",
                target_section=section_filename,
            )
        except Exception as exception:
            log.error("[RegenerateSectionRoute] mission orchestrator error: %s", exception)
            sse_generation_message_manager.emit_error(str(exception))
        finally:
            await sse_generation_message_manager.done()

    # ── Streaming Handler ──
    async def _section_streaming_handler() -> AsyncGenerator[str, None]:
        log.info("[RegenerateSectionRoute] Section regeneration streaming")
        section_worker_task = asyncio.create_task(_emit_section_regenerated_data())
        try:
            async for chunk in sse_generation_message_manager.stream():
                yield chunk
        finally:
            section_worker_task.cancel()
            try:
                await section_worker_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _section_streaming_handler(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── POST /export-document ──────────────────────────────────────────────
class ExportRequest(BaseModel):
    format: str = "odt"
    filename: str = "Document"
    content: str | None = None
    project_id: str | None = None
    version: int | None = None
    template_type: str = "srs"
    document_metadata: dict | None = None


@router.post("/export-document")
def export_document(request: ExportRequest, background_tasks: BackgroundTasks):
    """Export the generated document to a specific file format (e.g., ODT).

    Two modes:
    - Section-aware: when project_id + version are provided, reads per-section
      content from stored JSON files so the converter can style tables/sections
      by identity rather than position.
    - Raw content: when content is provided directly, converts the flat markdown
      string without section metadata.
    """
    from system_config import get_reference_document_dir
    from converter.convert import get_template_config
    if request.format.lower() != "odt":
        raise HTTPException(status_code=400, detail="Only 'odt' format is supported at this time.")

    template_type = (request.template_type or "srs").lower()
    log.info(f"[Export] Request to export {request.filename}.odt (template_type={template_type})")

    temp_dir = tempfile.mkdtemp()
    output_odt_path = os.path.join(temp_dir, f"{request.filename}.odt")
    template_cfg = get_template_config(template_type)
    reference_template_document_path = os.path.join(
        get_reference_document_dir(),
        template_cfg["reference_document_filename"],
    )

    def cleanup():
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    background_tasks.add_task(cleanup)

    try:
        from converter.convert import convert_markdown_to_odt

        sections = None
        if request.project_id and request.version:
            sections = _fetch_version_sections(request.project_id, request.version)

        document_metadata = request.document_metadata or {
            "PRJ_ID": "DP-COMMON-0001",
            "PRJ_FG": "000",
            "PRJ_VERSION": "V1",
            "TYPE_ID": "01",
            "DOC_TYPE": "SRS",
            "DOC_VER_MAJOR": "0",
            "DOC_VER_MINOR": "01",
            "DOC_DATE": "DATE",
        }

        success = convert_markdown_to_odt(
            markdown_content=request.content,
            output_odt_file_path=output_odt_path,
            reference_template_odt_path=reference_template_document_path,
            sections=sections,
            template_type=template_type,
            document_metadata=document_metadata,
        )

        if success and os.path.exists(output_odt_path):
            return FileResponse(
                path=output_odt_path,
                filename=f"{request.filename}.odt",
                media_type="application/vnd.oasis.opendocument.text"
            )
        else:
            raise HTTPException(status_code=500, detail="Document conversion failed.")
    except Exception as exception:
        log.error(f"[Export] Error during export: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exception))


def _fetch_version_sections(project_id: str, version: int) -> list[dict]:
    """Read all section content for a given document version from stored JSON."""
    from system_config import get_project_generated_document_output_dir
    output_dir = get_project_generated_document_output_dir(project_id)
    if not output_dir.exists():
        return []

    ver_key = str(version)
    sections = []
    for json_file in sorted(output_dir.iterdir()):
        if json_file.suffix.lower() != ".json" or json_file.name == "version.json":
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        doc_data = data.get("document_data", {})
        if ver_key not in doc_data:
            continue
        content = doc_data[ver_key].get("generated_data", "").strip()
        if content:
            sections.append({
                "section_filename": data.get("section_filename", json_file.name.replace(".json", ".md")),
                "content": content,
            })
    return sections