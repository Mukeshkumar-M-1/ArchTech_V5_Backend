"""
config.py  —  ArchTech RAG v3 Centralized Configuration

This module centralizes all directory paths, model paths, and operational settings
to facilitate easy environment configuration for agents and developers.
"""

from pathlib import Path
import json
import os

# ─── Base Directories ────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
_ROOT_FOLDER_NAME = ".ArchTech" 

# ─── Model Paths ─────────────────────────────────────────────────────────────
"""
    1. all-MiniLM-L6-v2 (Default)
    2. BAAI/bge-large-en-v1.5 (Best)
    3. intfloat/e5-large-v2 (Best)
"""
EMBEDDING_MODEL_PATH = BASE_DIR / "Embedding_model" / "E5_large" 
EMBEDDING_MODEL_PATH_EXCEPTION = BASE_DIR / "Embedding_model" / "E5_large"

# ─── Phase 2 : Requirement Extraction Process ────────────────────────────────
# ─── Stage 2: Segmentation Pipeline Settings ─────────────────────────────────
SEGMENTATION_ENABLE_LLM = True

# ─── Stage 3: Detection Pipeline Settings ────────────────────────────────────
DETECTION_ENABLE_LLM = True

# ─── Stage 4: Normalization Pipeline Settings ────────────────────────────────
NORMALIZATION_ENABLE_LLM = True

# ─── Stage 5: Classification Pipeline Settings ───────────────────────────────
CLASSIFICATION_ENABLE_LLM = True

# ─── Stage 6: Explanation Pipeline Settings ──────────────────────────────────
EXPLAIN_ENABLE_LLM = True

# ─── Stage 7: Scoring Pipeline Settings ──────────────────────────────────────
SCORING_ENABLE_LLM = True

# ─── Stage 8: Dedup Pipeline Settings ────────────────────────────────────────
DEDUP_ENABLE_LLM = True
#------------------------------------------------------------------------------


# ─── Operational Settings ────────────────────────────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 8015
API_URL = "https://llmgw.datapatterns.co.in/v1"
API_KEY = "sk-dpllm-oL5QSppnfr1QRLSmV6moGey"
API_TIME_OUT  = 120.0

def get_project_base_dir() -> Path:
    "Return the project-specific base directory."
    project_base_dir = BASE_DIR / f"{_ROOT_FOLDER_NAME}"
    project_base_dir.mkdir(parents=TimeoutError, exist_ok=True)
    return project_base_dir

def get_req_dir(project_id: str) -> Path:
    """Returns the project-specific requirements directory."""
    project_requirement_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "requirements" 
    project_requirement_path.mkdir(parents=True, exist_ok=True)
    return project_requirement_path

def get_upload_source_file_dir(project_id: str) -> Path:
    """Returns the project-specific Source file upload directory."""
    project_src_upload_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "uploads" 
    project_src_upload_path.mkdir(parents=True, exist_ok=True)
    return project_src_upload_path

def get_project_source_memory_dir(project_id: str) -> Path:
    """Returna the project-specific memory directory. """
    project_memory_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "memory" 
    project_memory_path.mkdir(parents=True, exist_ok=True)
    return project_memory_path

def get_knowledge_source_dir(project_id: str) -> Path:
    project_knowledge_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "memory" / "knowledge"
    project_knowledge_path.mkdir(parents=True, exist_ok=True)
    return project_knowledge_path

def get_project_internal_memory_source_dir(project_id: str) -> Path:
    project_internal_memory_path = BASE_DIR/ f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "memory" / "Internal_Memory"
    project_internal_memory_path.mkdir(parents=True, exist_ok=True)
    return project_internal_memory_path

def get_internal_memory_source_data_dir() -> Path:
    project_internal_memory_source_path = BASE_DIR / "Internal_Memory"
    project_internal_memory_source_path.mkdir(parents=True, exist_ok=True)
    return project_internal_memory_source_path

def get_project_template_dir(project_id: str, template_type: str = "Topic_Template") -> Path:
    """Get or create the project-specific template directory.

    If template_type is a template name (e.g. 'Standard', 'Detailed'), returns
    .ArchTech/{project_id}/templates/{template_type}/. Otherwise defaults to
    .ArchTech/{project_id}/templates/Topic_Template/ for backward compatibility.
    """
    project_template_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "templates" / template_type
    project_template_path.mkdir(parents=True, exist_ok=True)
    return project_template_path

def get_source_template_dir() -> Path:
    """Get or create the project-specific source template directory."""
    project_source_template_path = BASE_DIR / "Document_Section" / "SRS_Section" / "Topic_Template"
    project_source_template_path.mkdir(parents=True, exist_ok=True)
    return project_source_template_path


def get_template_registry() -> dict:
    """Load the SRS template registry containing definitions for all template types.

    Returns a dict of the form:
        {"templates": {"Standard": {...}, "Compact": {...}}}
    """
    template_registry_path = BASE_DIR / "Document_Section" / "SRS_Section" / "templates_registry.json"
    if template_registry_path.exists():
        return json.loads(template_registry_path.read_text(encoding="utf-8"))
    return {"templates": {}}


def get_source_template_directory(template_name: str) -> Path:
    """Return the filesystem path where source section files for a template type are stored."""
    return BASE_DIR / "Document_Section" / "SRS_Section" / template_name / "Topic_Template"


def get_project_template_metadata_directory(project_id: str) -> Path:
    """Return the directory where project-level template metadata is persisted."""
    project_template_metadata_directory = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "templates" / "meta"
    project_template_metadata_directory.mkdir(parents=True, exist_ok=True)
    return project_template_metadata_directory


def get_section_lock_mapping(project_id: str) -> dict:
    """Return whether the selected template's sections are locked.

    Reads `template_locks.json` (locked template name) and compares it with
    `selected_template.json` (selected template name). If they match, returns `{\"__all__\": True}`.
    Otherwise returns `{}` (no sections locked).
    """
    locked_template_path = get_project_template_metadata_directory(project_id) / "template_locks.json"
    if locked_template_path.exists():
        data = json.loads(locked_template_path.read_text(encoding="utf-8"))
        locked_name = data.get("template_type")
        if locked_name:
            selected_name = retrieve_selected_template_name(project_id)
            if locked_name == selected_name:
                return {"__all__": True}
    return {}


def persist_section_lock_mapping(project_id: str, section_lock_mapping: dict) -> None:
    """Save the locked template name to disk.

    Accepts `{\"__all__\": True}` format from callers — persists only the
    currently selected template name as the locked one.
    """
    locked_template_path = get_project_template_metadata_directory(project_id) / "template_locks.json"
    if section_lock_mapping.get("__all__"):
        selected_name = retrieve_selected_template_name(project_id)
        locked_template_path.write_text(json.dumps({"template_type": selected_name}, indent=2), encoding="utf-8")
    else:
        # No sections locked — clear the file
        locked_template_path.write_text(json.dumps({}, indent=2), encoding="utf-8")


def get_locked_template_name(project_id: str) -> str:
    """Return the name of the currently locked template, or empty string if none."""
    locked_template_path = get_project_template_metadata_directory(project_id) / "template_locks.json"
    if locked_template_path.exists():
        data = json.loads(locked_template_path.read_text(encoding="utf-8"))
        locked_name = data.get("template_type")
        if locked_name:
            return locked_name
    return ""


def persist_locked_template_name(project_id: str, template_name: str) -> None:
    """Record which template type has its sections locked."""
    locked_template_path = get_project_template_metadata_directory(project_id) / "template_locks.json"
    locked_template_path.write_text(json.dumps({"template_type": template_name}, indent=2), encoding="utf-8")


def retrieve_selected_template_name(project_id: str) -> str:
    """Return the template type the user has selected for this project."""
    selected_template_path = get_project_template_metadata_directory(project_id) / "selected_template.json"
    if selected_template_path.exists():
        return json.loads(selected_template_path.read_text(encoding="utf-8")).get("template_type", "Standard")
    return "Standard"


def persist_selected_template_name(project_id: str, selected_template_name: str) -> None:
    """Record which template type the user has chosen for this project."""
    selected_template_path = get_project_template_metadata_directory(project_id) / "selected_template.json"
    selected_template_path.write_text(json.dumps({"template_type": selected_template_name}, indent=2), encoding="utf-8")


# ─── Per-Project Template Registry ─────────────────────────────────────────────
# Each project gets its own templates_registry.json under .ArchTech/{project_id}/templates/meta/
# On first access, it merges the global entries (origin="global") with any project-specific
# directories found on disk (origin="project"). This isolates user template CRUD from the
# global Document_Section/SRS_Section/ source.


def get_project_template_registry_path(project_id: str) -> Path:
    """Return the filesystem path to the per-project template registry JSON."""
    return get_project_template_metadata_directory(project_id) / "templates_registry.json"


def get_project_template_registry(project_id: str) -> dict:
    """Load the per-project template registry.

    If the file doesn't exist yet, bootstrap it by:
    1. Copying all global registry entries and marking them origin='global'
    2. Scanning .ArchTech/{project_id}/templates/ for any extra directories
       (user-created templates) and marking them origin='project'

    Returns a dict of the form:
        {"templates": {"Standard": {...}, "Compact": {...}, "MyTemplate": {...}}}
    """
    project_registry_path = get_project_template_registry_path(project_id)

    # Fast path: registry already exists
    if project_registry_path.exists():
        return json.loads(project_registry_path.read_text(encoding="utf-8"))

    # --- Bootstrap from global registry ---
    # Global registry uses object format: {"templates": {"Standard": {...}, ...}}
    global_registry = get_template_registry()
    global_registry_templates = global_registry.get("templates", {})
    global_template_names = set(global_registry_templates.keys())

    # Scan the project's templates directory for any folders not in the global registry
    # These are user-created templates (e.g. Sample_1) that already exist on disk
    project_templates_base = BASE_DIR / _ROOT_FOLDER_NAME / project_id / "templates"
    existing_project_dirs = set()
    if project_templates_base.exists():
        for child in project_templates_base.iterdir():
            # Skip meta/ (metadata) and Topic_Template/ (legacy default)
            if child.is_dir() and child.name not in ("meta", "Topic_Template"):
                existing_project_dirs.add(child.name)

    # Build the merged registry as a dict keyed by template name
    templates_dict = {}

    # Add all global entries with origin marker
    for name, entry in global_registry_templates.items():
        templates_dict[name] = {**entry, "name": name, "origin": "global"}

    # Add any project-specific directories found on disk that aren't global templates
    for dirname in sorted(existing_project_dirs - global_template_names):
        # Count .md section files in the directory
        section_count = 0
        d = project_templates_base / dirname
        if d.exists():
            section_count = sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".md")
        templates_dict[dirname] = {
            "name": dirname,
            "path": dirname,
            "locked": False,
            "section_count": section_count,
            "origin": "project",
            "created": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }

    # Persist the bootstrapped registry and return
    result = {"templates": templates_dict}
    project_registry_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def ensure_project_template_metadata(project_id: str) -> None:
    """Bootstrap template_locks.json and selected_template.json on first project access."""
    project_registry = get_project_template_registry(project_id)
    templates_dict = project_registry.get("templates", {})
    first_template_name = next(iter(templates_dict))

    locked_template_path = get_project_template_metadata_directory(project_id) / "template_locks.json"
    if not locked_template_path.exists():
        locked_template_path.write_text(
            json.dumps({"template_type": first_template_name}, indent=2), encoding="utf-8"
        )

    selected_template_path = get_project_template_metadata_directory(project_id) / "selected_template.json"
    if not selected_template_path.exists():
        selected_template_path.write_text(
            json.dumps({"template_type": first_template_name}, indent=2), encoding="utf-8"
        )


def update_project_template_registry(project_id: str, registry: dict) -> None:
    """Save the per-project template registry back to disk.

    Called after create/delete operations to persist changes.
    """
    project_registry_path = get_project_template_registry_path(project_id)
    project_registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def get_reference_document_dir() -> Path:
    """Get the reference document for export the odt document"""
    project_reference_document_path = BASE_DIR / "Document_Section" / "SRS_Reference"
    project_reference_document_path.mkdir(parents=True, exist_ok=True)
    return project_reference_document_path

def get_transcript_dir(project_id: str) -> Path:
    """Get or create the project-specific source template transcript directory."""
    project_source_transcript_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "transcripts"
    project_source_transcript_path.mkdir(parents=True, exist_ok=True)
    return project_source_transcript_path

def get_session_transcript_dir(project_id: str) -> Path:
    """Get or create the project-specific source session transcript directory."""
    project_session_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "sessions"
    project_session_path.mkdir(parents=True, exist_ok=True)
    return project_session_path

def get_project_transcript_dir(project_id: str) -> Path:
    """Get or create the project-specific source project transcript directory."""
    project_transcript_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "projects"
    project_transcript_path.mkdir(parents=True, exist_ok=True)
    return project_transcript_path

def get_project_phase3_dir(project_id: str) -> Path:
    """Get or create the project-specific source project Phase3 [Template Analysis Agent] directory."""
    project_template_analysis_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "Template_Analysis"
    project_template_analysis_path.mkdir(parents=True, exist_ok=True)
    return project_template_analysis_path


def get_project_generated_document_output_dir(project_id: str) -> Path:
    """Get or create the project-specific source project generated document output directory."""
    project_generated_document_output_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "_output"
    project_generated_document_output_path.mkdir(parents=True, exist_ok=True)
    return project_generated_document_output_path


# ─── Document Version Tracking ────────────────────────────────────────────────

_VERSION_JSON_FILENAME = "version.json"


def _get_version_file_path(project_id: str) -> Path:
    """Return the path to the central version.json for a project."""
    return get_project_generated_document_output_dir(project_id) / _VERSION_JSON_FILENAME


def get_document_version(project_id: str) -> dict:
    """Read the central version.json and return its contents.

    If the file doesn't exist yet (no generation has run), returns
    a fresh bootstrap structure with version 0.
    """
    version_path = _get_version_file_path(project_id)
    if version_path.exists():
        try:
            import json
            return json.loads(version_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Bootstrap
    return {"document": "", "current_version": 0, "sections": {}}


def start_new_version(project_id: str, template_type: str) -> int:
    """Atomically bump the document version at generation start.

    Returns the new version number that all sections should be tagged with.
    """
    import json
    version_path = _get_version_file_path(project_id)

    data = get_document_version(project_id)
    data["document"] = template_type.upper()
    data["current_version"] += 1
    new_version = data["current_version"]

    version_path.write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    return new_version


def record_section_version(project_id: str, section_filename: str, version: int) -> None:
    """Record that a section was written for a given document version."""
    import json
    version_path = _get_version_file_path(project_id)
    data = json.loads(version_path.read_text(encoding="utf-8"))

    if section_filename not in data["sections"]:
        data["sections"][section_filename] = {"latest_version": version}
    else:
        data["sections"][section_filename]["latest_version"] = version

    version_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_chat_session_dir(project_id: str) -> Path:
    """Get or create the project-specific chat sessions directory.

    Mirrors the pattern used by session_manager.py — paths under
    .Archtech/{project_id}/ for project-scoped data.
    """
    chat_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "chat_sessions"
    chat_path.mkdir(parents=True, exist_ok=True)
    return chat_path

def get_agent_mail_box_dir(project_id: str) -> Path:
    """Get or create the project-specific Agent message directory."""
    project_agent_mail_box_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "agent_messages"
    project_agent_mail_box_path.mkdir(parents=True, exist_ok=True)
    return project_agent_mail_box_path


