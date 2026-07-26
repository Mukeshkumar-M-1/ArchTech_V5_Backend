"""
template_analysis_routes.py — API endpoints for SRS template section management.

Supports: listing, viewing, creating, deleting, and LLM-generating
document sections per project.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path
from system_config import get_project_template_dir, get_source_template_dir
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared state (same pattern as memory_management_routes.py)
# ---------------------------------------------------------------------------
template_progress_store: dict[str, dict] = {}
_background_tasks: set[asyncio.Task] = set()

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
_SOURCE_TEMPLATE_DIR = get_source_template_dir()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class UpdateFileRequest(BaseModel):
    content: str


class CreateFileRequest(BaseModel):
    filename: str


class GenerateRequest(BaseModel):
    filename: str | None = None


class ValidateRequest(BaseModel):
    sections: list[str] | None = None  # None = validate all


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _sync_project_templates(project_id: str) -> None:
    """Copy shared templates to project dir only if they don't already exist."""
    proj_dir = get_project_template_dir(project_id)
    for src_file in _SOURCE_TEMPLATE_DIR.iterdir():
        if src_file.is_file():
            dst = proj_dir / src_file.name
            if not dst.exists():
                shutil.copy2(src_file, dst)

def _parse_section_metadata(filename: str) -> tuple[int, str]:
    """Parse '01_introduction.md' -> (1, 'Introduction')."""
    section_re = re.compile(r"^(\d{2})_(.+)\.md$")
    m = section_re.match(filename)
    if m:
        return int(m.group(1)), m.group(2).replace("_", " ").title()
    app_re = re.compile(r"^appendix_([a-z])\.md$")
    m = app_re.match(filename)
    if m:
        return 0, f"Appendix {m.group(1).upper()}"
    return 0, filename.replace(".md", "").replace("_", " ").title()

def _next_section_number(proj_dir: Path) -> str:
    """Find next available section number, e.g. '08_'."""
    if not proj_dir.exists():
        return "01_"
    existing = [
        f.name for f in proj_dir.iterdir()
        if f.is_file() and re.match(r"^\d{2}_", f.name)
    ]
    if not existing:
        return "01_"
    max_num = 0
    for name in existing:
        m = re.match(r"^(\d{2})_", name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{max_num + 1:02d}_"

def _sanitize_filename(user_input: str) -> str:
    """Strip path components, ensure .md extension."""
    name = Path(user_input).name
    if not name.lower().endswith(".md"):
        name += ".md"
    return name.replace(" ", "_")

def _resolve_file_path(project_id: str, filename: str) -> Path:
    """Resolve and validate file path with traversal protection."""
    proj_dir = get_project_template_dir(project_id).resolve()
    target = (proj_dir / filename).resolve()
    if not str(target).startswith(str(proj_dir)):
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected")
    return target


# ===========================================================================
# 1. GET /template-sections/{project_id} — List sections
# ===========================================================================

@router.get("/template-sections/{project_id}")
def get_template_sections(project_id: str):
    """List all template sections available for a project."""
    _sync_project_templates(project_id)
    proj_dir = get_project_template_dir(project_id)
    result = []
    if proj_dir.exists():
        for file_data_item in sorted(proj_dir.iterdir()):
            if file_data_item.is_file() and file_data_item.suffix.lower() == ".md":
                section_num, title = _parse_section_metadata(file_data_item.name)
                content = file_data_item.read_text(encoding="utf-8")
                placeholders = re.findall(r"<([^>]+)>", content)
                is_generated = len(placeholders) == 0
                result.append({
                    "filename": file_data_item.name,
                    "path": file_data_item.name,
                    "section_number": section_num,
                    "title": title,
                    "is_generated": is_generated,
                })
    result.sort(key=lambda x: (x["section_number"], x["filename"]))
    return result


# ===========================================================================
# 2. GET /template-section/{project_id}/{filename:path} — View file
# ===========================================================================

@router.get("/template-section/{project_id}/{filename:path}")
def get_template_file(project_id: str, filename: str):
    """Return the content of a specific template file."""
    _sync_project_templates(project_id)
    target = _resolve_file_path(project_id, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=404, detail="Not a file")
    if target.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Not a markdown file")
    return {
        "filename": target.name,
        "content": target.read_text(encoding="utf-8"),
        "path": str(target.relative_to(get_project_template_dir(project_id))),
    }


# ===========================================================================
# 3. DELETE /template-section/{project_id}/{filename:path} — Delete file
# ===========================================================================

@router.delete("/template-section/{project_id}/{filename:path}")
def delete_template_file(project_id: str, filename: str):
    """Delete a template file from the project-specific directory only."""
    target = _resolve_file_path(project_id, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.is_dir():
        raise HTTPException(status_code=404, detail="Not a file")
    try:
        target.unlink()
        return {"status": "ok", "message": f"Deleted {filename}"}
    except Exception as e:
        log.error(f"[TemplateRoute] Delete failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# 5a. POST /template-section/{project_id}/cancel — Cancel generation
# ===========================================================================

@router.post("/template-section/{project_id}/cancel")
def cancel_template_generation(project_id: str):
    """Cancel the running generation task for a project."""
    from AgentCore.execution.session_manager import SessionLifecycle
    from AgentCore.execution.abort_controller import get_hierarchy

    session = SessionLifecycle.find_active(project_id=project_id)
    if session:
        SessionLifecycle.cancel(session_id=session.session_id, project_id=project_id)

    try:
        hierarchy = get_hierarchy()
        if session:
            hierarchy.abort_tree(session.session_id, reason="user cancelled")
        else:
            hierarchy.abort_tree(project_id, reason="user cancelled")
    except Exception:
        pass

    return {"status": "ok", "message": "Generation cancelled"}


# ===========================================================================
# 5. POST /template-section/{project_id}/generate — LLM-generate section(s)
# ===========================================================================

@router.post("/template-section/{project_id}/generate")
async def generate_template_section(project_id: str, request: GenerateRequest = GenerateRequest()):
    """Run Phase 3 analysis on template sections."""
    from AgentCore.execution.session_manager import SessionLifecycle
    from Template_analysis.template_analysis_agent import TemplateAnalysisAgent

    session = SessionLifecycle.create_generation(project_id=project_id, target_sections=[request.filename] if request.filename else None)

    async def _run_analysis():
        try:

            agent = TemplateAnalysisAgent(project_id=project_id, session_id=session.session_id)
            result = await agent.run()

            total = len(result.table_of_contents) if result.table_of_contents else 0

            SessionLifecycle.update_progress(
                project_id=project_id,
                session_id=session.session_id,
                status="complete",
                progress=100,
                current_phase=f"Phase 3 complete — {total} sections analyzed, JSON saved",
            )
        except Exception as e:
            SessionLifecycle.update_progress(
                project_id=project_id,
                session_id=session.session_id,
                status="error",
                error=str(e),
            )
            log.error(f"[TemplateRoute] Analysis failed: {e}", exc_info=True)

    task = asyncio.create_task(_run_analysis())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "started", "session_id": session.session_id}


# ===========================================================================
# 6. POST /template-section/{project_id}/create — Create new file
# ===========================================================================

@router.post("/template-section/{project_id}/create")
def create_template_file(project_id: str, request: CreateFileRequest):
    """Create a new template file with auto-assigned section numbering."""
    _sync_project_templates(project_id)
    proj_dir = get_project_template_dir(project_id)

    base_name = _sanitize_filename(request.filename)
    if base_name.endswith(".md"):
        base_name = base_name[:-3]

    prefix = _next_section_number(proj_dir)
    final_name = f"{prefix}{base_name}.md"

    target = proj_dir / final_name
    counter = 1
    while target.exists():
        final_name = f"{prefix}{base_name}_{counter}.md"
        target = proj_dir / final_name
        counter += 1

    title = base_name.replace("_", " ").title()
    content = f"# {title}\n\n<!-- New section. Edit content below. -->\n"
    target.write_text(content, encoding="utf-8")

    section_num, title_parsed = _parse_section_metadata(final_name)
    return {
        "status": "ok",
        "filename": final_name,
        "path": final_name,
        "section_number": section_num,
        "title": title_parsed,
    }


# ===========================================================================
# 7a. PUT /template-section/{project_id}/{filename:path} — Update file content
# ===========================================================================

@router.put("/template-section/{project_id}/{filename:path}")
def update_template_file(project_id: str, filename: str, request: UpdateFileRequest):
    """Update the content of a template section file."""
    _sync_project_templates(project_id)
    target = _resolve_file_path(project_id, filename)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if target.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Not a markdown file")
    try:
        target.write_text(request.content, encoding="utf-8")
        return {"status": "ok", "message": f"Updated {filename}"}
    except Exception as e:
        log.error(f"[TemplateRoute] Update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# 7b. GET /template-analysis/{project_id} — Fetch Phase 3 analysis JSON
# ===========================================================================

@router.get("/template-analysis/{project_id}")
def get_phase3_analysis(project_id: str):
    """Return the Phase 3 analysis JSON file for a project."""
    from system_config import get_project_phase3_dir
    details_dir = get_project_phase3_dir(project_id)
    filepath = details_dir / f"phase3_{project_id}.json"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Phase 3 analysis not found")
    return json.loads(filepath.read_text(encoding="utf-8"))


# ===========================================================================
# 7. GET /template-progress/{project_id} — Progress polling
# ===========================================================================

@router.get("/template-progress/{project_id}")
def get_template_progress(project_id: str):
    """Return session progress data for a project."""
    from AgentCore.execution.session_manager import SessionLifecycle
    return SessionLifecycle.get_progress(project_id)



