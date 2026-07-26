"""
config.py  —  ArchTech RAG v3 Centralized Configuration

This module centralizes all directory paths, model paths, and operational settings
to facilitate easy environment configuration for agents and developers.
"""

from pathlib import Path
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
API_URL = "https://api.groq.com/openai/v1"
API_KEY = os.getenv("GROQ_API_KEY", "")
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

def get_project_template_dir(project_id: str) -> Path:
    """Get or create the project-specific template directory."""
    project_template_path = BASE_DIR / f"{_ROOT_FOLDER_NAME}" / f"{project_id}" / "templates" / "Topic_Template"
    project_template_path.mkdir(parents=True, exist_ok=True)
    return project_template_path

def get_source_template_dir() -> Path:
    """Get or create the project-specific source template directory."""
    project_source_template_path = BASE_DIR / "Document_Section" / "SRS_Section" / "Topic_Template"
    project_source_template_path.mkdir(parents=True, exist_ok=True)
    return project_source_template_path

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


