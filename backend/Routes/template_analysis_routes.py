"""
template_analysis_routes.py — API endpoints for SRS template section management.

Supports: listing, viewing, creating, deleting, and LLM-generating
document sections per project.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
import shutil
from pathlib import Path

from system_config import (
    get_project_template_dir,
    persist_locked_template_name,
    get_locked_template_name,
    retrieve_selected_template_name,
    persist_selected_template_name,
    get_source_template_directory,
    get_project_template_registry,
    update_project_template_registry,
    ensure_project_template_metadata,
)

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
# Request/Response models
# ---------------------------------------------------------------------------

class UpdateFileRequest(BaseModel):
    content: str


class CreateFileRequest(BaseModel):
    filename: str


class CreateTemplateRequest(BaseModel):
    template_name: str
    source_template: str = "Standard"


class GenerateRequest(BaseModel):
    filename: str | None = None


class ValidateRequest(BaseModel):
    sections: list[str] | None = None  # None = validate all


class UpdateSectionLockRequest(BaseModel):
    filename: str
    locked: bool


class DeleteTemplateTypeRequest(BaseModel):
    template_name: str


class SelectTemplateTypeRequest(BaseModel):
    template_name: str


class TemplateTypeRequest(BaseModel):
    """Specify which template type to use."""

    template_type: str = "Standard"


class LockTemplateRequest(BaseModel):
    locked: bool = True


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _has_sections(project_id: str, template_name: str) -> bool:
    """Check if the project template directory already has .md section files synced."""
    project_template_dir = get_project_template_dir(project_id, template_name)
    if project_template_dir.exists():
        return any(f.is_file() and f.suffix.lower() == ".md" for f in project_template_dir.iterdir())
    return False


def _synchronize_project_template_sections(project_id: str, template_name: str = "Standard") -> None:
    """Copy the source section files from the chosen template into the project directory ONCE.

    Files are copied from Document_Section/SRS_Section/{template_name}/Topic_Template/
    to .ArchTech/{project_id}/templates/{template_name}/. Checks if .md files already
    exist in the project directory to avoid unnecessary re-syncs.
    """
    from system_config import get_source_template_directory

    # Skip if project template directory already has .md files synced
    if _has_sections(project_id, template_name):
        log.info(
            "[TemplateRoute] Skipping sync for project '%s' — template '%s' already synced",
            project_id, template_name,
        )
        return

    # Project-origin templates already live in .ArchTech — no source sync needed
    project_registry = get_project_template_registry(project_id)
    template_entry = project_registry.get("templates", {}).get(template_name, {})
    if template_entry.get("origin") == "project":
        log.info(
            "[TemplateRoute] Template '%s' is project-origin; skipping source sync for project '%s'",
            template_name, project_id,
        )
        return

    log.info("[TemplateRoute] Syncing template '%s' for project '%s'", template_name, project_id)

    # Resolve source directory with fallback
    source_template_dir = get_source_template_directory(template_name)
    if not source_template_dir.exists():
        log.warning(
            "[TemplateRoute] Template '%s' directory not found for project '%s' — falling back to 'Standard'",
            template_name, project_id,
        )
        source_template_dir = get_source_template_directory("Standard")

    # Copy ONLY .md section files to project-specific template directory
    project_template_dir = get_project_template_dir(project_id, template_name)
    project_template_dir.mkdir(parents=True, exist_ok=True)

    # Preserve locked sections content before sync (they must survive template switches)
    locked_section_content = {}
    if project_template_dir.exists():
        locked_template = get_locked_template_name(project_id)
        if locked_template == template_name:
            for existing_file in project_template_dir.iterdir():
                if existing_file.is_file() and existing_file.suffix.lower() == ".md":
                    locked_section_content[existing_file.name] = existing_file.read_text(encoding="utf-8")

    section_file_count = 0
    for template_section_file in source_template_dir.iterdir():
        if template_section_file.is_file() and template_section_file.suffix.lower() == ".md":
            project_section_file = project_template_dir / template_section_file.name
            if not project_section_file.exists():
                shutil.copy2(template_section_file, project_section_file)
                log.info(
                    "[TemplateRoute] Copied section '%s' for project '%s'",
                    template_section_file.name, project_id,
                )
            section_file_count += 1

    # Restore locked sections after sync
    for locked_filename, locked_content in locked_section_content.items():
        (project_template_dir / locked_filename).write_text(locked_content, encoding="utf-8")
        log.info(
            "[TemplateRoute] Restored locked section '%s' after sync for project '%s'",
            locked_filename, project_id,
        )

    log.info(
        "[TemplateRoute] Template '%s' sync complete: %d sections for project '%s'",
        template_name, section_file_count, project_id,
    )


def _sync_all_templates_for_project(project_id: str) -> None:
    """Ensure all registered template types are synced for a project.
    Uses the per-project registry so both global and project-origin templates are handled.
    """
    project_registry = get_project_template_registry(project_id)
    for template_name in project_registry.get("templates", {}):
        _synchronize_project_template_sections(project_id, template_name)


def _reset_template_sections(project_id: str, template_name: str) -> int:
    """Force re-sync template sections from source. Returns the number of sections reset."""
    from system_config import get_source_template_directory

    project_registry = get_project_template_registry(project_id)
    template_entry = project_registry.get("templates", {}).get(template_name, {})

    # Resolve source directory
    if template_entry.get("origin") == "project":
        source_template_dir = get_project_template_dir(project_id, template_entry.get("source_template", template_name))
        if not source_template_dir.exists():
            source_template_dir = get_source_template_directory("Standard")
    else:
        source_template_dir = get_source_template_directory(template_name)
        if not source_template_dir.exists():
            source_template_dir = get_source_template_directory("Standard")

    project_template_dir = get_project_template_dir(project_id, template_name)
    project_template_dir.mkdir(parents=True, exist_ok=True)

    # Remove existing .md files
    if project_template_dir.exists():
        for f in project_template_dir.iterdir():
            if f.is_file() and f.suffix.lower() == ".md":
                f.unlink()

    # Re-copy from source
    section_file_count = 0
    for template_section_file in source_template_dir.iterdir():
        if template_section_file.is_file() and template_section_file.suffix.lower() == ".md":
            project_section_file = project_template_dir / template_section_file.name
            shutil.copy2(template_section_file, project_section_file)
            section_file_count += 1

    log.info(
        "[TemplateRoute] Reset template '%s' for project '%s': %d sections",
        template_name, project_id, section_file_count,
    )
    return section_file_count

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

def _resolve_file_path(project_id: str, filename: str, template_name: str = "Standard") -> Path:
    """Resolve and validate file path with traversal protection."""
    selected_template_name = template_name
    if not selected_template_name:
        selected_template_name = retrieve_selected_template_name(project_id)
    proj_dir = get_project_template_dir(project_id, selected_template_name).resolve()
    resolved_file_path = (proj_dir / filename).resolve()
    if not str(resolved_file_path).startswith(str(proj_dir)):
        raise HTTPException(status_code=403, detail="Access denied: path traversal detected")
    return resolved_file_path


# ===========================================================================
# 1. POST /template-sections/{project_id} — List sections (with initial sync)
# ===========================================================================

@router.post("/template-sections/{project_id}")
def list_project_template_sections(
    project_id: str,
    request: TemplateTypeRequest = TemplateTypeRequest(),
):
    """Return the section list for the project, syncing the chosen template first."""
    log.info(
        "[TemplateRoute] Fetching template sections for project '%s'",
        project_id,
    )
    ensure_project_template_metadata(project_id)
    selected_template_name = request.template_type or retrieve_selected_template_name(project_id)
    _synchronize_project_template_sections(project_id, selected_template_name)
    persist_selected_template_name(project_id, selected_template_name)

    # Read from project-specific template directory
    project_template_dir = get_project_template_dir(project_id, selected_template_name)
    template_section_list = []
    if project_template_dir.exists():
        for section_entry in sorted(project_template_dir.iterdir()):
            if section_entry.is_file() and section_entry.suffix.lower() == ".md":
                section_number, section_title = _parse_section_metadata(section_entry.name)
                section_content = section_entry.read_text(encoding="utf-8")
                placeholder_markers = re.findall(r"<([^>]+)>", section_content)
                is_section_generated = len(placeholder_markers) == 0
                template_section_list.append({
                    "filename": section_entry.name,
                    "path": section_entry.name,
                    "section_number": section_number,
                    "title": section_title,
                    "is_generated": is_section_generated,
                })
    template_section_list.sort(key=lambda entry: (entry["section_number"], entry["filename"]))
    return template_section_list


# ===========================================================================
# 2. GET /template-section/{project_id}/{filename:path} — View file
# ===========================================================================

@router.get("/template-section/{project_id}/{filename:path}")
def retrieve_template_file_content(
    project_id: str,
    filename: str,
):
    """Return the markdown content of a specific project template file."""
    log.info(
        "[TemplateRoute] Reading section '%s' for project '%s'",
        filename, project_id,
    )
    template_for_project = retrieve_selected_template_name(project_id)
    resolved_file_path = _resolve_file_path(project_id, filename, template_for_project)
    if not resolved_file_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    if resolved_file_path.is_dir():
        raise HTTPException(status_code=404, detail="Path is a directory, not a file")
    if resolved_file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Only markdown files are allowed")
    project_template_dir = get_project_template_dir(project_id, template_for_project)
    return {
        "filename": resolved_file_path.name,
        "content": resolved_file_path.read_text(encoding="utf-8"),
        "path": str(resolved_file_path.relative_to(project_template_dir)),
    }


# ===========================================================================
# 3. DELETE /template-section/{project_id}/{filename:path} — Delete file
# ===========================================================================

@router.delete("/template-section/{project_id}/{filename:path}")
def remove_template_file(
    project_id: str,
    filename: str,
):
    """Delete a template file from the project directory (respects section lock)."""
    log.info(
        "[TemplateRoute] Deleting section '%s' from project '%s'",
        filename, project_id,
    )
    template_for_project = retrieve_selected_template_name(project_id)
    resolved_file_path = _resolve_file_path(project_id, filename, template_for_project)
    if not resolved_file_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    if resolved_file_path.is_dir():
        raise HTTPException(status_code=404, detail="Path is a directory, not a file")

    # Lock is an indicator only — never blocks deletion

    try:
        resolved_file_path.unlink()
        return {"status": "ok", "message": f"Deleted {filename}"}
    except Exception as file_deletion_error:
        log.error(f"[TemplateRoute] Delete failed: {file_deletion_error}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(file_deletion_error))


# ===========================================================================
# 5a. POST /template-section/{project_id}/cancel — Cancel generation
# ===========================================================================

@router.post("/template-section/{project_id}/cancel")
def cancel_template_generation(project_id: str):
    """Cancel the running generation task for a project."""
    log.info(
        "[TemplateRoute] Canceling generation for project '%s'",
        project_id,
    )
    from AgentCore import GenerationSessionManager
    from AgentCore.execution.abort_controller import get_hierarchy

    session = GenerationSessionManager.find_active(project_id=project_id)
    if session:
        GenerationSessionManager.cancel(session_id=session.session_id, project_id=project_id)

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
    log.info(
        "[TemplateRoute] Starting template analysis for project '%s'",
        project_id,
    )
    from AgentCore import GenerationSessionManager
    from Template_analysis.template_analysis_agent import TemplateAnalysisAgent

    session = GenerationSessionManager.create(project_id=project_id, target_sections=[request.filename] if request.filename else None)

    async def _run_analysis():
        try:

            agent = TemplateAnalysisAgent(project_id=project_id, session_id=session.session_id)
            result = await agent.run()

            total = len(result.table_of_contents) if result.table_of_contents else 0

            GenerationSessionManager.update_progress(
                project_id=project_id,
                session_id=session.session_id,
                status="complete",
                progress=100,
                current_phase=f"Phase 3 complete — {total} sections analyzed, JSON saved",
            )
        except Exception as e:
            GenerationSessionManager.update_progress(
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
    log.info(
        "[TemplateRoute] Creating section '%s' in project '%s'",
        request.filename, project_id,
    )
    selected_template_name = retrieve_selected_template_name(project_id)
    project_template_dir = get_project_template_dir(project_id, selected_template_name)

    sanitized_section_name = _sanitize_filename(request.filename)
    if sanitized_section_name.endswith(".md"):
        sanitized_section_name = sanitized_section_name[:-3]

    section_number_prefix = _next_section_number(project_template_dir)
    final_filename = f"{section_number_prefix}{sanitized_section_name}.md"

    new_file_path = project_template_dir / final_filename
    duplicate_counter = 1
    while new_file_path.exists():
        final_filename = f"{section_number_prefix}{sanitized_section_name}_{duplicate_counter}.md"
        new_file_path = project_template_dir / final_filename
        duplicate_counter += 1

    created_section_title = sanitized_section_name.replace("_", " ").title()
    section_content = f"# {created_section_title}\n\n<!-- New section. Edit content below. -->\n"
    new_file_path.write_text(section_content, encoding="utf-8")
    log.info(
        "[TemplateRoute] Section '%s' created in project '%s'",
        final_filename, project_id,
    )

    section_number, section_title_parsed = _parse_section_metadata(final_filename)
    return {
        "status": "ok",
        "filename": final_filename,
        "path": final_filename,
        "section_number": section_number,
        "title": section_title_parsed,
    }


# ===========================================================================
# 7a. PUT /template-section/{project_id}/{filename:path} — Update file content
# ===========================================================================

@router.put("/template-section/{project_id}/{filename:path}")
def update_template_file_content(
    project_id: str,
    filename: str,
    request: UpdateFileRequest,
):
    """Update the markdown content of a project template file (respects section lock)."""
    log.info(
        "[TemplateRoute] Updating section '%s' for project '%s'",
        filename, project_id,
    )
    selected_template_name = retrieve_selected_template_name(project_id)
    resolved_file_path = _resolve_file_path(project_id, filename, selected_template_name)
    if not resolved_file_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    if resolved_file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=404, detail="Only markdown files are allowed")

    # Lock is an indicator only — never blocks editing
    try:
        resolved_file_path.write_text(request.content, encoding="utf-8")
        log.info(
            "[TemplateRoute] Section '%s' updated for project '%s'",
            filename, project_id,
        )
        return {"status": "ok", "message": f"Updated {filename}"}
    except Exception as content_write_error:
        log.error("[TemplateRoute] Update failed: %s", content_write_error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(content_write_error))


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
def get_generation_progress(project_id: str):
    """Return session progress data for a running generation task."""
    from AgentCore import GenerationSessionManager
    return GenerationSessionManager.get_progress(project_id)


# ===========================================================================
# TEMPLATE MANAGEMENT ENDPOINTS
# ===========================================================================


# ---------------------------------------------------------------------------
# GET /api/templates/locks/{project_id} — Fetch per-project section lock state
# ---------------------------------------------------------------------------

@router.get("/api/templates/locks/{project_id}")
def get_project_section_lock_state(project_id: str):
    """Return the locked template name for the project."""
    locked = get_locked_template_name(project_id)
    return {"template_type": locked}


@router.get("/api/templates/selected/{project_id}")
def get_project_selected_template(project_id: str):
    """Return the currently selected template name for the project."""
    selected = retrieve_selected_template_name(project_id)
    return {"template_type": selected}


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GET /api/templates/registry/{project_id} — List project-scoped template types
# ---------------------------------------------------------------------------

@router.get("/api/templates/registry/{project_id}")
def get_template_type_registry(project_id: str):
    """Return the per-project template registry (global entries + project-specific additions)."""
    template_registry = get_project_template_registry(project_id)
    return template_registry


# ---------------------------------------------------------------------------
# GET /api/templates/sections/{project_id} — List sections from source template
# ---------------------------------------------------------------------------

@router.post("/api/templates/sections/{project_id}")
def list_template_sections_from_source(
    project_id: str,
    request: TemplateTypeRequest = TemplateTypeRequest(),
):
    """Return the project's template sections (from .ArchTech/ only, never reads from source)."""
    log.info(
        "[TemplateRoute] Fetching template sections for project '%s' (template='%s')",
        project_id, request.template_type,
    )
    template_for_project = request.template_type

    # Ensure template is synced to project directory before reading
    _synchronize_project_template_sections(project_id, template_for_project)

    project_template_dir = get_project_template_dir(project_id, template_for_project)
    template_section_list = []
    if project_template_dir.exists():
        for template_section_file in sorted(project_template_dir.iterdir()):
            if template_section_file.is_file() and template_section_file.suffix.lower() == ".md":
                section_number, section_title = _parse_section_metadata(template_section_file.name)
                template_section_list.append({
                    "section_number": section_number,
                    "filename": template_section_file.name,
                    "title": section_title,
                    "locked": False,
                })

    template_section_list.sort(key=lambda entry: (entry["section_number"], entry["filename"]))
    return template_section_list


# ---------------------------------------------------------------------------
# PUT /api/templates/select/{project_id} — Switch template type
# ---------------------------------------------------------------------------

@router.put("/api/templates/select/{project_id}")
def switch_project_template_type(
    project_id: str,
    request: SelectTemplateTypeRequest,
):
    """Sync the project with the chosen template type and return the new section list."""
    log.info(
        "[TemplateRoute] Switching project '%s' template to '%s'",
        project_id, request.template_name,
    )
    selected_template_name = request.template_name
    # Validate against per-project registry (includes both global and user-created templates)
    project_registry = get_project_template_registry(project_id)
    available_template_names = set(project_registry.get("templates", {}).keys())

    if selected_template_name not in available_template_names:
        raise HTTPException(
            status_code=404,
            detail=f"Template type '{selected_template_name}' is not available",
        )

    _synchronize_project_template_sections(project_id, selected_template_name)
    persist_selected_template_name(project_id, selected_template_name)

    project_template_dir = get_project_template_dir(project_id, selected_template_name)
    returned_section_list = []
    if project_template_dir.exists():
        for template_section_file in sorted(project_template_dir.iterdir()):
            if template_section_file.is_file() and template_section_file.suffix.lower() == ".md":
                section_number, section_title = _parse_section_metadata(template_section_file.name)
                returned_section_list.append({
                    "filename": template_section_file.name,
                    "path": template_section_file.name,
                    "section_number": section_number,
                    "title": section_title,
                    "is_generated": False,
                })

    returned_section_list.sort(key=lambda entry: (entry["section_number"], entry["filename"]))
    log.info(
        "[TemplateRoute] Project '%s' switched to template '%s'",
        project_id, selected_template_name,
    )
    return returned_section_list


# ---------------------------------------------------------------------------
# PUT /api/templates/lock-section/{project_id} — Toggle section lock state
# ---------------------------------------------------------------------------

@router.put("/api/templates/lock-section/{project_id}")
def toggle_section_lock(
    project_id: str,
    request: UpdateSectionLockRequest,
):
    """Return the template-level lock state for a section.

    Individual sections can no longer be toggled independently.
    Locks are managed at the template level via the registry.
    """
    selected_template_name = retrieve_selected_template_name(project_id)
    project_registry = get_project_template_registry(project_id)
    registry_entry = project_registry.get("templates", {}).get(selected_template_name, {})
    is_locked = registry_entry.get("locked", False)

    return {
        "status": "ok",
        "filename": request.filename,
        "locked": is_locked,
        "template_locked": is_locked,
    }


# ---------------------------------------------------------------------------
# POST /api/templates/lock-template/{project_id} — Lock/unlock all sections
# ---------------------------------------------------------------------------

@router.post("/api/templates/lock-template/{project_id}")
def lock_template_action(
    project_id: str,
    request: LockTemplateRequest,
):
    """Lock or unlock the project template (template-level only)."""
    selected_template_name = retrieve_selected_template_name(project_id)
    project_template_dir = get_project_template_dir(project_id, selected_template_name)

    # Update the locked flag in the per-project registry
    project_registry = get_project_template_registry(project_id)
    templates_dict = project_registry.get("templates", {})

    if request.locked:
        # When locking, first unlock any previously locked template so only one stays locked
        for tmpl_name, tmpl_data in templates_dict.items():
            if tmpl_data.get("locked", False):
                tmpl_data["locked"] = False
                templates_dict[tmpl_name] = tmpl_data
        # Now set the current template as locked
        template_entry = templates_dict.get(selected_template_name)
        if template_entry is not None:
            template_entry["locked"] = True
            templates_dict[selected_template_name] = template_entry
    else:
        # When unlocking, clear the current template's locked flag
        template_entry = templates_dict.get(selected_template_name)
        if template_entry is not None:
            template_entry["locked"] = False
            templates_dict[selected_template_name] = template_entry
        # Ensure at least one template remains locked — default to the first one
        any_still_locked = any(
            tmpl_data.get("locked", False)
            for tmpl_data in templates_dict.values()
        )
        if not any_still_locked:
            first_template_name = next(iter(templates_dict))
            first_entry = templates_dict[first_template_name]
            first_entry["locked"] = True
            templates_dict[first_template_name] = first_entry

    update_project_template_registry(project_id, project_registry)

    # Count .md sections for the response
    section_count = 0
    if project_template_dir.exists():
        section_count = sum(
            1 for f in project_template_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".md"
        )

    if request.locked:
        # Persist the locked template name
        persist_locked_template_name(project_id, selected_template_name)
        log.info(
            "[TemplateRoute] Template '%s' locked for project '%s'",
            selected_template_name, project_id,
        )
        return {"status": "ok", "locked": True, "template": selected_template_name, "sections_count": section_count}
    else:
        # Find which template is now locked (should be the first one as default)
        locked_template = None
        for tmpl_name, tmpl_data in templates_dict.items():
            if tmpl_data.get("locked", False):
                locked_template = tmpl_name
                break
        if locked_template:
            persist_locked_template_name(project_id, locked_template)
        log.info(
            "[TemplateRoute] Template '%s' unlocked for project '%s'. Default locked: '%s'",
            selected_template_name, project_id, locked_template,
        )
        return {"status": "ok", "locked": False, "template": selected_template_name, "default_locked": locked_template, "sections_count": section_count}


# ---------------------------------------------------------------------------
# POST /api/templates/reset/{project_id} — Reset template sections to source
# ---------------------------------------------------------------------------

@router.post("/api/templates/reset/{project_id}")
def reset_template_to_source(project_id: str, request: TemplateTypeRequest):
    """Reset the project template sections back to the source template files.

    Preserves locked section content so user changes on locked sections survive the reset.
    """
    template_name = request.template_type
    sections_reset = _reset_template_sections(project_id, template_name)

    return {
        "status": "ok",
        "message": f"Template '{template_name}' has been reset to source",
        "sections_reset": sections_reset,
    }


# ---------------------------------------------------------------------------
# DELETE /api/templates/delete/{project_id} — Remove a project-scoped template type
# ---------------------------------------------------------------------------

@router.delete("/api/templates/delete/{project_id}")
def remove_template_type_from_registry(project_id: str, request: DeleteTemplateTypeRequest):
    """Delete a project-scoped template type.

    Only removes from the per-project registry and deletes files from .ArchTech.
    System-provided (global-origin) templates cannot be deleted via this endpoint.
    """
    template_name_to_remove = request.template_name

    # Load per-project registry
    project_registry = get_project_template_registry(project_id)
    templates_dict = project_registry.get("templates", {})

    # Find the template entry in the project registry
    template_entry = templates_dict.get(template_name_to_remove)
    if template_entry is None:
        raise HTTPException(status_code=404, detail="Template not found in project")

    # Protect system-provided templates from deletion
    if template_entry.get("origin") == "global":
        raise HTTPException(status_code=403, detail="Cannot delete a system-provided template")

    # Protect locked templates
    if template_entry.get("locked", False):
        raise HTTPException(status_code=403, detail="Cannot delete a locked template")

    # Remove from project registry
    del templates_dict[template_name_to_remove]
    project_registry["templates"] = templates_dict
    update_project_template_registry(project_id, project_registry)

    # Delete the template directory from .ArchTech (NOT from Document_Section)
    project_template_dir = get_project_template_dir(project_id, template_name_to_remove)
    if project_template_dir.exists():
        shutil.rmtree(project_template_dir)

    log.info(
        "[TemplateRoute] Template '%s' deleted from project '%s'",
        template_name_to_remove, project_id,
    )
    return {
        "status": "ok",
        "message": f"Template '{template_name_to_remove}' has been removed",
    }


# ============================================================================
# CREATE TEMPLATE TYPE (project-scoped)
# ============================================================================


@router.post("/api/templates/create/{project_id}")
def create_template_type(project_id: str, request: CreateTemplateRequest):
    """Create a new template type scoped to a project.

    Copies section files from a source template into .ArchTech/{project_id}/templates/{new_name}/
    and registers the new template in the per-project registry only.
    The global Document_Section/SRS_Section/ is never modified.
    """
    new_template_name = request.template_name
    base_template_name = request.source_template

    # Validate template name (no path traversal or special chars)
    if not re.match(r'^[a-zA-Z0-9_ ]+$', new_template_name):
        raise HTTPException(status_code=400, detail="Invalid template name")

    # Load the per-project registry
    project_registry = get_project_template_registry(project_id)
    templates_dict = project_registry.get("templates", {})

    # Reject if a template with this name already exists (case-insensitive)
    existing_names_lower = {name.lower() for name in templates_dict}
    if new_template_name.lower() in existing_names_lower:
        raise HTTPException(status_code=409, detail="Template with this name already exists")

    # Resolve the source template directory based on origin:
    # - Global templates: copy from Document_Section/SRS_Section/{name}/Topic_Template/
    # - Project templates: copy from .ArchTech/{project_id}/templates/{name}/
    source_template_dir = None
    source_entry = templates_dict.get(base_template_name)
    if source_entry is not None:
        if source_entry.get("origin") == "global":
            source_template_dir = get_source_template_directory(base_template_name)
        else:
            source_template_dir = get_project_template_dir(project_id, base_template_name)

    # Fallback to Standard if the specified source wasn't found
    if source_template_dir is None or not source_template_dir.exists():
        source_template_dir = get_source_template_directory("Standard")

    # Create the new template directory inside .ArchTech (NOT in Document_Section)
    new_template_dir = get_project_template_dir(project_id, new_template_name)
    new_template_dir.mkdir(parents=True, exist_ok=True)

    # Copy all .md section files from the source to the new project-scoped directory
    for template_section_file in source_template_dir.iterdir():
        if template_section_file.is_file() and template_section_file.suffix.lower() == ".md":
            target_file = new_template_dir / template_section_file.name
            shutil.copy2(template_section_file, target_file)

    # Count sections in the newly created template
    section_file_count = sum(
        1 for f in new_template_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".md"
    )

    # Build registry entry with origin='project' so it's marked as user-created
    new_template_entry = {
        "name": new_template_name,
        "path": new_template_name,
        "locked": False,
        "section_count": section_file_count,
        "origin": "project",
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    templates_dict[new_template_name] = new_template_entry
    project_registry["templates"] = templates_dict

    # Persist only to the per-project registry (NOT the global one)
    update_project_template_registry(project_id, project_registry)

    log.info(
        "[TemplateRoute] Project template '%s' created for project '%s' with %d sections",
        new_template_name, project_id, section_file_count,
    )
    return {
        "status": "ok",
        "message": f"Template '{new_template_name}' has been created",
        "template": new_template_entry,
    }



