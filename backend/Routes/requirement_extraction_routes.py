from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio, shutil, uuid, json, re
from pathlib import Path
from system_config import get_req_dir
from utils import string_underscore_change
import logging
from prompts import prompts
from llm_api_handler import llm_request


router = APIRouter()

log = logging.getLogger(__name__)

# Background tasks registry (kept alive by the app lifecycle)
_background_tasks: set[asyncio.Task] = set()

# Extraction tasks registry (for cancellation)
_extraction_tasks: dict = {}

# Default Datas
LLM_MODEL_OPUS = "opus46"
LLM_MODEL_SONNET = "sonnet46"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.1

class RephraseRequest(BaseModel):
    text: str
    requirement_ids: list[str] = []
    style: str = "concise"
    project_id: str = "default_project"


class AIInsightRequest(BaseModel):
    text: str
    requirement_ids: list[str] = []
    action: str = "summarize"
    user_query: Optional[str] = None
    project_id: str = "default_project"


class UpdateRequirementRequest(BaseModel):
    req_id: str
    explanation: str
    project_id: str = "default_project"


class ScanRequest(BaseModel):
    folder_path: str
    project_id: str = "default_project"


class SubmitSelectedRequest(BaseModel):
    requirement_ids: list[str]
    project_id: str = "default_project"


# Shared progress store (used by upload-requirements and extraction-progress)
progress_store: dict[str, dict] = {}


def _load_selected(ids, project_id):
    req_dir = get_req_dir(project_id)
    fpath = (req_dir / "requirements.json").resolve()
    if not fpath.exists():
        return []
    try:
        with open(fpath, encoding="utf-8") as fp:
            all_reqs = json.load(fp)
        return [r for r in all_reqs if r['id'] in ids]
    except Exception:
        return []


# ===========================================================================
# Upload Endpoints
# ===========================================================================

#   GET  /extraction-progress/{project_id}              -> get_extraction_progress
@router.get("/extraction-progress/{project_id}")
async def get_extraction_progress(project_id: str):
    """Return the current status of requirement extraction for a project."""
    return progress_store.get(project_id, {"status": "idle", "message": "Waiting..."})

#   POST /upload-requirements                           -> upload_requirements_files
@router.post("/upload-requirements")
async def upload_requirements_files(
    files: List[UploadFile] = File(...),
    project_id: str = Form("default_project")
):
    """Upload requirement files (PDFs, images, etc.), start background extraction, and return immediately."""
    from system_config import get_req_dir, get_upload_source_file_dir
    from extractor_agent import save_to_json, scan_folder

    if not files or all(f.filename == '' for f in files):
        raise HTTPException(status_code=400, detail="No files uploaded.")

    if not project_id or project_id == "default_project":
        raise HTTPException(status_code=400, detail="project_id is required. Please select or create a project first.")

    pid = string_underscore_change(project_id)
    batch_id = uuid.uuid4().hex[:8]
    log.info(f"[Upload] project_id={project_id}, batch_id={batch_id}, files={[f.filename for f in files]}")

    # Cancel any existing extraction for this project before starting a new one
    _extraction_tasks.pop(pid, None)

    try:
        batch_dir = get_upload_source_file_dir(project_id=pid)
        batch_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            if not file.filename:
                continue
            target = batch_dir / file.filename
            with target.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        req_dir = get_req_dir(pid)
        for f in req_dir.glob("*.json"):
            try:
                f.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass

        progress_store[pid] = {"status": "running", "message": f"Processing batch {batch_id}..."}

        def progress_callback(update_dict: dict):
            if pid in progress_store and progress_store[pid].get("status") != "cancelled":
                progress_store[pid].update(update_dict)

        async def _extract():
            try:
                # Import scan_file to process individual PDFs with cancellation checks
                from extractor_agent import scan_file as _scan_single_file

                all_extracted_reqs = []
                file_counters = {}
                supported_extensions = {'.pdf'}
                pdf_files = sorted(
                    f for f in Path(batch_dir).rglob("*") if f.suffix.lower() in supported_extensions
                )
                for pdf_path in pdf_files:
                    # Check cancellation between files
                    if pid in progress_store and progress_store[pid].get("status") == "cancelled":
                        log.info(f"[Extraction] {pid}: cancelled before processing {pdf_path.name}")
                        break
                    extracted = await _scan_single_file(
                        str(pdf_path),
                        counters=file_counters,
                        progress_callback=progress_callback,
                    )
                    all_extracted_reqs.extend(extracted)

                reqs = all_extracted_reqs

                # Check cancellation before saving
                if pid in progress_store and progress_store[pid].get("status") == "cancelled":
                    log.info(f"[Extraction] {pid}: cancelled before saving")
                    return

                ids = await save_to_json(reqs, req_dir)

                # Attempt to clean up old batches in the background
                try:
                    for old_batch in get_upload_source_file_dir(project_id=pid):
                        if old_batch.is_dir() and old_batch.name != batch_dir.name:
                            shutil.rmtree(old_batch, ignore_errors=True)
                except Exception:
                    pass

                progress_store[pid] = {"status": "complete", "message": "Extraction complete!"}
                log.info(f"[Upload] Success: {len(ids)} requirements extracted")

            except asyncio.CancelledError:
                progress_store[pid] = {"status": "cancelled", "message": "Extraction cancelled"}
                log.info(f"[Extraction] {pid}: task cancelled")
            except Exception as e:
                progress_store[pid] = {"status": "error", "message": str(e)}
                log.error(f"[Upload] Error: {e}", exc_info=True)

        task = asyncio.create_task(_extract())
        _extraction_tasks[pid] = task
        task.add_done_callback(lambda t: _extraction_tasks.pop(pid, None))

        return {"status": "starting", "message": f"Processing batch {batch_id}..."}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[Upload] Error: {e}", exc_info=True)
        progress_store[project_id] = {"status": "error", "message": str(e)}
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ===========================================================================
# Cancel Extraction
# ===========================================================================

@router.post("/cancel-extraction/{project_id}")
def cancel_extraction(project_id: str):
    """Cancel an in-progress requirement extraction for a project.

    Sets the cancellation flag in progress_store (checked between files)
    and cancels the asyncio task directly.
    """
    pid = string_underscore_change(project_id)
    # Set cancellation flag in progress store (checked by the extraction loop)
    if pid in progress_store:
        progress_store[pid]["status"] = "cancelled"
        progress_store[pid]["message"] = "Extraction cancelled by user"
    # Cancel the asyncio task for immediate interrupt
    task = _extraction_tasks.get(pid)
    if task and not task.done():
        task.cancel()
    return {"status": "ok", "message": "Cancellation requested"}


# ===========================================================================
# Requirement Manipulation Endpoints
# ===========================================================================

#   POST /update-requirement                            -> update_requirement_endpoint
@router.post("/update-requirement")
async def update_requirement_endpoint(request: UpdateRequirementRequest):
    """Update the explanation text for a single extracted requirement."""
    req_dir = get_req_dir(request.project_id)
    fpath = req_dir / "requirements.json"
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Requirements file not found.")

    try:
        with open(fpath, "r", encoding="utf-8") as fp:
            all_reqs = json.load(fp)

        found = False
        for r in all_reqs:
            if r['id'] == request.req_id:
                r['explanation'] = request.explanation
                found = True
                break

        if not found:
            raise HTTPException(status_code=404, detail="Requirement ID not found.")

        with open(fpath, "w", encoding="utf-8") as fp:
            json.dump(all_reqs, fp, indent=4, ensure_ascii=False)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#   GET  /requirements/{project_id}                     -> list_requirements
@router.get("/requirements/{project_id}")
def list_requirements(project_id: str):
    """List all extracted requirements for a given project."""
    req_dir = get_req_dir(project_id)
    fpath = (req_dir / "requirements.json").resolve()
    if not fpath.is_file():
        log.error(f"[Requirement_route] File path not exists: {fpath}")
        return []
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        log.info(f"[Requirement_route] Loaded {len(data)} requirements for project {project_id}")
        return data
    except Exception as e:
        log.error(f"[Requirement_route] Failed to parse requirements.json: {e}")
        return []


# ===========================================================================
# LLM Assistance Endpoints
# ===========================================================================

#   POST /ai-insight                                    -> get_ai_insight_endpoint
@router.post("/ai-insight")
async def get_ai_insight_endpoint(request: AIInsightRequest):
    """Get AI-powered insights (summarize, explain, compare) on requirements using an LLM."""
    System_Prompt = ""
    message = []
    requirement_content = []
    if len(request.requirement_ids) > 0:
        requirement_content = _load_selected(request.requirement_ids, request.project_id)

    # Build a clean text block from the raw requirement dicts
    req_text_parts = [r.get("text", "") for r in requirement_content if r.get("text")]
    req_text = "\n".join(req_text_parts) if req_text_parts else request.text

    if request.action is not None:
        if request.action == "summarize":
            System_Prompt = prompts.get_definition("summarize").render()
            message = [{"role": "user", "content": f"Summarize the following requirement(s):\n\n{req_text}"}]
        elif request.action == "rephrase":
            System_Prompt = prompts.get_definition("rephrase").render()
            message = [{"role": "user", "content": f"Rephrase the following requirement:\n\n{req_text}"}]
        elif request.action == "custom":
            System_Prompt = prompts.get_definition("custom").render()
            message = [{"role": "user", "content": f"User Query: {request.user_query}\n\nRequirements:\n{req_text}"}]

    if not System_Prompt or not message:
        return {"insight": "No system prompt configured for action: " + str(request.action)}

    try:
        result = await llm_request(
            model=LLM_MODEL_OPUS,
            system_prompt=System_Prompt,
            messages=message,
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            fallback_chain=[LLM_MODEL_OPUS],
        )
        if result:
            return {"insight": result}
        return {"insight": "Unable to generate insight. Please try again."}
    except Exception as e:
        log.error(f"[AI Insight] Error: {e}")
        return {"insight": f"Error generating insight: {str(e)}"}   
        


# ===========================================================================
# File Serving Endpoint
# ===========================================================================

#   GET  /files/{filename}                              -> serve_file
@router.get("/files/{filename:path}")
async def serve_file(filename: str, project_id: str = "default_project"):
    """Serve an uploaded source file (PDF, image, etc.) by filename."""
    from system_config import get_upload_source_file_dir
    upload_dir = get_upload_source_file_dir(project_id)
    file_path = upload_dir / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="File not found")


# ===========================================================================
# Submit Selected Requirements
# ===========================================================================

#   POST /submit-selected/{project_id}                  -> submit_selected_requirements
@router.post("/submit-selected/{project_id}")
async def submit_selected_requirements(request: SubmitSelectedRequest, project_id: str):
    """Save the user's selected requirements as selected_requirement.json and selected_ids.json."""
    req_dir = get_req_dir(project_id)
    req_file = req_dir / "requirements.json"
    if not req_file.exists():
        raise HTTPException(status_code=404, detail="Requirements file not found.")
    try:
        with open(req_file, "r", encoding="utf-8") as fp:
            all_reqs = json.load(fp)
        selected_reqs = [req_item for req_item in all_reqs if req_item["id"] in request.requirement_ids]
        # Save full requirement objects as selected_requirement.json
        output_path = req_dir / "selected_requirement.json"
        with open(output_path, "w", encoding="utf-8") as fp:
            json.dump(selected_reqs, fp, indent=4, ensure_ascii=False)
        # Also save just the IDs as selected_ids.json for fast loading on next page visit
        ids_path = req_dir / "selected_ids.json"
        with open(ids_path, "w", encoding="utf-8") as fp:
            json.dump(request.requirement_ids, fp, indent=4, ensure_ascii=False)
            
        # Fire event to the global event bus
        try:
            from AgentCore.observability.event_bus import get_global_bus, EventType
            get_global_bus().publish(
                EventType.MEMORY_UPDATED, 
                source="RequirementExtraction", 
                payload={"project_id": project_id, "type": "requirements", "count": len(selected_reqs)}
            )
        except Exception as bus_e:
            log.warning(f"[EventBus] Failed to publish MEMORY_UPDATED: {bus_e}")
            
        return {"status": "success", "saved_count": len(selected_reqs), "output": str(output_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#   GET  /selected-ids/{project_id}                     -> get_selected_ids
@router.get("/selected-ids/{project_id}")
async def get_selected_ids(project_id: str):
    """Return the list of requirement IDs the user previously selected for submission."""
    req_dir = get_req_dir(project_id)
    ids_path = req_dir / "selected_ids.json"
    if not ids_path.exists():
        return []
    try:
        return json.loads(ids_path.read_text(encoding="utf-8"))
    except Exception:
        return []
