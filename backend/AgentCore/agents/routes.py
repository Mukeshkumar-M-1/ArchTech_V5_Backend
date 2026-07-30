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
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import datetime
import os
import tempfile
import shutil
import traceback
from AgentCore.core.execution_engine import set_tool_event_queue
import AgentCore.execution.builtins 

log = logging.getLogger(__name__)
router = APIRouter()
DEFAULT_MAX_WORKERS = 1



# ── SSE helpers ─────────────────────────────────────────────────────────
def format_sse_event(data: dict) -> str:
    """Format a dictionary as an SSE data line.

    Args:
        data: The data to serialize as an SSE event.

    Returns:
        Formatted SSE data line string.
    """
    return f"data: {json.dumps(data, default=str)}\n\n"


class GenerateDocumentRequest(BaseModel):
    project_id: str
    template_type: str = "srs"


class SSEEventQueue:
    """Async queue for bridging coroutine-to-coroutine SSE events.

    Events are put into the queue by the producer coroutine and
    streamed to the client by the HTTP response consumer.
    """

    def __init__(self) -> None:
        """Initialize an empty SSE event queue."""
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        log.info("[SSEEventQueue] Event Initialized")

    async def put(self, msg: str) -> None:
        """Put an event into the queue.

        Args:
            msg: The SSE event string to queue.
        """
        log.info("[SSEEventQueue] Streaming length= %d", len(msg))
        await self._queue.put(msg)

    async def get(self) -> str | None:
        """Get the next event from the queue.

        Returns:
            The next event string, or None to signal completion.
        """
        log.info("[SSEEventQueue] get: waiting for event")
        return await self._queue.get()

    async def done(self) -> None:
        """Signal completion by putting a None sentinel into the queue."""
        log.info("[SSEEventQueue] done: signaling completion")
        await self._queue.put(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Yield events from the queue until completion sentinel."""
        while True:
            msg = await self._queue.get()
            if msg is None:
                log.info("[SSEEventQueue] stream: received None, stopping")
                break
            yield msg

class GenerateDocumentRequest(BaseModel):
    project_id: str
    template_type: str = "srs"


class SSEToolQueue:
    """
       Separate queue for raw tool events (from ExecutionEngine / QueryLoop)
    """
    def __init__(self):
        """Initialize an empty SSE tool queue."""
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        log.info("[SSEToolQueue] Tool Initialized")


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

    # INITIALIZE STREAMING QUEUE
    streaming_queue = SSEEventQueue()

    # INITIALIZE TOOL STREAMING QUEUE
    tool_events_queue = SSEToolQueue()

    # Wire the tool event queue so ExecutionEngine can push tool_call SSE events
    set_tool_event_queue(tool_events_queue._queue)

    # Helper: format and emit an SSE event onto the main streaming queue
    async def _chunk_emit(event: dict) -> None:
        await streaming_queue.put(format_sse_event(event))
        await asyncio.sleep(0)

    # Tool events forwarder: drains the tool_events_queue and emits to the main stream
    async def _tool_events_forwarder() -> None:
        try:
            while True:
                tool_event_data = await tool_events_queue._queue.get()
                if tool_event_data is None:
                    break
                await streaming_queue.put(format_sse_event(tool_event_data))
        except asyncio.CancelledError as exception:
            log.error(f"[GenerateAgentRoute] Error : {exception}")
            pass

    # DOCUMENT AGENT WORKER
    async def _document_agent_worker() -> None:
        """Runs the document generation agent and puts events on the streaming_queue.

        This coroutine runs in the background, feeding SSE events into the
        queue for the streaming response to consume.
        """
        from AgentCore.orchestration.orchestrator import MissionOrchestrator

        try:
            log.info("[GenerateAgentRoute] Initializing MissionOrchestrator for request %s for project %s", template_type, project_id)
            orchestrator = MissionOrchestrator(project_id=project_id, num_workers=DEFAULT_MAX_WORKERS)

            async for event in orchestrator.execute_mission(project_id, template_type, f"Generate {template_type} document for project {project_id}"):
                await _chunk_emit(event)

        except Exception as exception:
            log.error(f"[GenerateAgentRoute] Producer error: {exception}")
            await streaming_queue.put(format_sse_event({"type": "gen_error", "error": str(exception)}))
        finally:
            await tool_events_queue._queue.put(None)
            await streaming_queue.done()

    # DOCUMENT GENERATOR
    async def _document_generator() -> AsyncGenerator[str, None]:
        """Async generator that feeds SSE events from the producer to the client.
        Creates a producer task, streams chunks from the queue, and ensures
        cleanup on cancellation.
        """
        log.info("[GenerateAgentRoute] Starting SSE stream for document generation")
        producer_task = asyncio.create_task(_document_agent_worker())
        tool_forwarder_task = asyncio.create_task(_tool_events_forwarder())
        try:
            async for chunk in streaming_queue.stream():
                yield chunk
        finally:
            producer_task.cancel()
            tool_forwarder_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
            try:
                await tool_forwarder_task
            except asyncio.CancelledError:
                pass
            set_tool_event_queue(None)

    return StreamingResponse(
        _document_generator(),
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
    from AgentCore.execution.session_manager import SessionLifecycle
    return SessionLifecycle.get_progress(project_id)


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
    from AgentCore.execution.session_manager import SessionLifecycle
    from AgentCore.execution.abort_controller import get_hierarchy

    session = SessionLifecycle.find_active(project_id)
    if session:
        SessionLifecycle.cancel(session_id=session.session_id, project_id=project_id)

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

# ── POST /export-document ──────────────────────────────────────────────

class ExportRequest(BaseModel):
    format: str = "odt"
    filename: str = "Document"
    content: str | None = None
    project_id: str | None = None
    version: int | None = None
    template_type: str = "srs"
    document_metadata: dict | None = None
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
            "DOC_VER_DATE": "DOCUMENT DATE",
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
