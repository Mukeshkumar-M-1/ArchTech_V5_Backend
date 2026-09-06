from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from system_config import get_knowledge_source_dir, get_upload_source_file_dir
from utils import string_underscore_change
from logging import getLogger

log = getLogger(__name__)
router = APIRouter()

# ===========================================================================
# Memory Enrichment State
# ===========================================================================

# Memory enrichment progress store
memory_progress_store: dict[str, dict] = {}

# Background tasks registry
import asyncio
_background_tasks: set[asyncio.Task] = set()

# Running agent instances (for cancellation)
_memory_agents: dict = {}
_memory_tasks: dict = {}

# ===========================================================================
# Knowledge File Listing
# ===========================================================================

@router.get("/{project_id}/knowledge-files")
def get_knowledge_files(project_id: str):
    """List all markdown memory files for a project.

    Returns a list of .md files from the project's knowledge directory,
    including their relative path and filename.
    """
    from pathlib import Path

    knowledge_dir = get_knowledge_source_dir(project_id=string_underscore_change(project_id))
    files = []
    if knowledge_dir.exists():
        for md in knowledge_dir.rglob("*.md"):
            rel = str(md.relative_to(knowledge_dir))
            files.append({"path": rel, "name": md.name, "type": "markdown"})
    return files


# ===========================================================================
# Knowledge File Endpoints
# ===========================================================================

@router.get("/{project_id}/uploaded-files")
def get_uploaded_files(project_id: str):
    """List source files uploaded by the user for a project.

    Returns file name, size in bytes, and file extension for each uploaded file.
    """
    from pathlib import Path

    upload_dir = Path(get_upload_source_file_dir(project_id=string_underscore_change(project_id)))
    files = []
    if upload_dir.exists():
        for file_item in upload_dir.iterdir():
            if file_item.is_file():
                files.append({
                    "name": file_item.name,
                    "size": file_item.stat().st_size,
                    "ext": file_item.suffix.lower(),
                })
    return files


@router.get("/{project_id}/knowledge-file/{filepath:path}")
def get_knowledge_file(project_id: str, filepath: str):
    """Get content of a single knowledge markdown file.

    Serves individual .md files from the knowledge directory.
    Blocks paths that conflict with other route patterns (memory-progress, uploaded-files, etc.).
    Only serves .md files and prevents directory traversal.
    """
    from pathlib import Path

    base = Path(get_knowledge_source_dir(project_id=string_underscore_change(project_id))).resolve()
    target = (base / filepath).resolve()
    log.info(f"[MemoryManagement] Base : {base} \n Target : {target}")
    try:
        target.relative_to(base)
    except ValueError:
        log.warning(f"[MemoryManagement] Directory traversal attempt detected: {filepath}")
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=404, detail="Not a file")
    if target.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Not a markdown file")
    return {
        "name": target.name,
        "content": target.read_text(encoding="utf-8"),
    }


@router.get("/{project_id}/memory-progress")
def get_memory_progress(project_id: str):
    """Return the current status of memory enrichment for a project.

    Tracks background memory generation progress set by the generate-memory endpoint.
    """
    pid = string_underscore_change(project_id)
    return memory_progress_store.get(pid, {"status": "idle", "progress": 0})


# ===========================================================================
# Memory Generation Endpoint
# ===========================================================================
@router.post("/{project_id}/generate-memory")
async def generate_memory(project_id: str):
    """Trigger memory enrichment (MemoryManagementAgent) for a project.

    Starts an async background task that enriches extracted requirements
    with memory-based knowledge. Progress is tracked via memory_progress_store.
    Returns immediately so the frontend can poll /memory-progress.
    """
    from Memory_Management.memory_management_agent import MemoryManagementAgent

    pid = string_underscore_change(project_id)

    _memory_agents[pid] = None  # placeholder; set after agent creation

    async def _run():
        try:
            memory_progress_store[pid] = {
                "status": "running",
                "progress": 0,
                "phase": "Initializing",
            }

            def _on_progress(phase: str, current: int, total: int):
                pct = int((current / max(total, 1)) * 100)
                memory_progress_store[pid] = {
                    "status": "running",
                    "progress": pct,
                    "phase": f"{phase} ({current}/{total})",
                }

            agent = MemoryManagementAgent(progress_callback=_on_progress)
            _memory_agents[pid] = agent
            stats = await agent.run(pid)
            total_written = stats.get("phase_a", {}).get("written", 0)
            memory_progress_store[pid] = {
                "status": "complete",
                "progress": 100,
                "phase": f"Done — {total_written} requirements enriched",
            }
            log.info(f"[MemoryManagementAgent] {pid}: enriched — {stats}")

            # Fire event to global event bus
            try:
                from AgentCore.event_bus import get_global_bus, EventType
                get_global_bus().publish(
                    EventType.MEMORY_UPDATED,
                    source="MemoryManagement",
                    payload={"project_id": pid, "type": "knowledge", "count": total_written}
                )
            except Exception as bus_e:
                log.warning(f"[EventBus] Failed to publish MEMORY_UPDATED: {bus_e}")
        except asyncio.CancelledError:
            _memory_agents.pop(pid, None)
            _memory_tasks.pop(pid, None)
            memory_progress_store[pid] = {
                "status": "cancelled",
                "progress": memory_progress_store.get(pid, {}).get("progress", 0),
                "phase": "Cancelled",
            }
            log.info(f"[MemoryManagementAgent] {pid}: cancelled")
        except Exception as exception:
            _memory_agents.pop(pid, None)
            _memory_tasks.pop(pid, None)
            memory_progress_store[pid] = {
                "status": "error",
                "error": str(exception),
            }
            log.error(f"[MemoryManagementAgent] {pid}: failed — {exception}", exc_info=True)

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    _memory_tasks[pid] = task

    return {"status": "started", "message": "Memory generation started in background"}


# ===========================================================================
# Cancel Memory Generation
# ===========================================================================
@router.post("/{project_id}/cancel-memory")
def cancel_memory_generation(project_id: str):
    """Cancel an in-progress memory generation for a project.

    Sets the cancellation flag on the agent and cancels the asyncio task.
    """
    pid = string_underscore_change(project_id)
    agent = _memory_agents.get(pid)
    if agent and hasattr(agent, "_cancelled"):
        agent._cancelled.set()
    task = _memory_tasks.get(pid)
    if task and not task.done():
        task.cancel()
    return {"status": "ok", "message": "Cancellation requested"}


# ===========================================================================
# Clear Memory
# ===========================================================================
@router.post("/{project_id}/clear-memory")
def clear_memory(project_id: str):
    """Delete all knowledge files for a project.

    Removes the entire knowledge directory and the memory progress entry.
    """
    from pathlib import Path

    pid = string_underscore_change(project_id)
    knowledge_dir = Path(get_knowledge_source_dir(project_id=pid))

    if knowledge_dir.exists():
        import shutil
        shutil.rmtree(knowledge_dir)

    memory_progress_store.pop(pid, None)

    return {"status": "ok", "message": "Memory cleared"}
