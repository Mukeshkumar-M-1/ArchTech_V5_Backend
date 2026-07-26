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
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
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
async def generate_document_stream(request: Request) -> StreamingResponse:
    """Stream document generation via Server-Sent Events.

    Args:
        request: The FastAPI HTTP request containing project_id and template_type.

    Returns:
        StreamingResponse with SSE document generation events.
    """
    body = await request.json()
    project_id = body.get("project_id", "")
    template_type = body.get("template_type", "srs").lower()
    
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
    content: str
    format: str
    filename: str

@router.post("/export-document")
def export_document(req: ExportRequest, background_tasks: BackgroundTasks):
    """Export the generated document to a specific file format (e.g., ODT)."""
    from system_config import get_reference_document_dir
    if req.format.lower() != "odt":
        raise HTTPException(status_code=400, detail="Only 'odt' format is supported at this time.")
        
    log.info(f"[Export] Request to export {req.filename}.odt")
    
    temp_dir = tempfile.mkdtemp()
    output_odt_path = os.path.join(temp_dir, f"{req.filename}.odt")
    reference_template_document_path = os.path.join(get_reference_document_dir(), "DP-VPX-0227-V1-01-SRS-1V00.odt")
    
    def cleanup():
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    background_tasks.add_task(cleanup)
    
    try:
        # # Import dynamically if needed or it's accessible from the backend root
        # import sys
        # backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        # if backend_dir not in sys.path:
        #     sys.path.insert(0, backend_dir)
            
        from converter.convert import convert_markdown_to_odt
        success = convert_markdown_to_odt(markdown_content=req.content, output_odt_file_path=output_odt_path, reference_template_odt_path=reference_template_document_path)
        if success and os.path.exists(output_odt_path):
            return FileResponse(
                path=output_odt_path,
                filename=f"{req.filename}.odt",
                media_type="application/vnd.oasis.opendocument.text"
            )
        else:
            raise HTTPException(status_code=500, detail="Document conversion failed.")
    except Exception as exception:
        log.error(f"[Export] Error during export: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(exception))
