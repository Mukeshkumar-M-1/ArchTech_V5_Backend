"""
version_manage_routes.py  —  API endpoints for document version management.

Serves version-centric data from central version.json + per-section JSON files
written by the orchestrator under .ArchTech/{project_id}/_output/.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from system_config import (
    get_project_generated_document_output_dir,
    get_document_version,
)

log = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIRST_HEADING = re.compile(r'^#{1,6}\s+\S', re.MULTILINE)


def _strip_agent_preamble(md: str) -> str:
    """Remove any text before the first markdown heading (agent thinking noise)."""
    m = _FIRST_HEADING.search(md)
    if m:
        return md[m.start():]
    return md.strip()


def _read_section_json(output_dir: Path, json_file: Path) -> dict:
    """Load and return parsed section JSON data."""
    try:
        return json.loads(json_file.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[VersionRoutes] Failed to read {json_file.name}: {e}")
        return {}


def _sections_for_version(output_dir: Path, version: int) -> list[dict]:
    """Return list of sections that belong to the given document version."""
    result = []
    ver_key = str(version)
    for json_file in sorted(output_dir.iterdir()):
        if json_file.suffix.lower() != ".json" or json_file.name == "version.json":
            continue
        data = _read_section_json(output_dir, json_file)
        doc_data = data.get("document_data", {})
        if ver_key in doc_data:
            entry = doc_data[ver_key]
            result.append({
                "section_number": data.get("section_number", ""),
                "section_filename": data.get("section_filename", json_file.name.replace(".json", ".md")),
                "has_content": bool(entry.get("generated_data")),
            })
    result.sort(key=lambda s: int(s["section_number"]) if s["section_number"].isdigit() else 0)
    return result


# ---------------------------------------------------------------------------
# 1. GET /document-versions/{project_id}
#    Return all document-level versions (newest first) with section counts.
# ---------------------------------------------------------------------------

@router.get("/document-versions/{project_id}")
def get_document_versions(project_id: str):
    """List every document version with its section count."""
    output_dir = get_project_generated_document_output_dir(project_id)

    if not output_dir.exists():
        return []

    version_info = get_document_version(project_id)
    current_version = version_info.get("current_version", 0)

    versions = []
    for v in range(current_version, 0, -1):
        sections = _sections_for_version(output_dir, v)
        versions.append({
            "version": v,
            "section_count": len(sections),
            "sections": sections,
        })

    return versions


# ---------------------------------------------------------------------------
# 2. GET /document-version/{project_id}/{version}
#    Return all sections for a specific document version.
# ---------------------------------------------------------------------------

@router.get("/document-version/{project_id}/{version}")
def get_document_version_sections(project_id: str, version: int):
    """Return the list of sections generated for a given document version."""
    output_dir = get_project_generated_document_output_dir(project_id)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    version_info = get_document_version(project_id)
    current_version = version_info.get("current_version", 0)

    if version < 1 or version > current_version:
        available = list(range(1, current_version + 1))
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found. Available: {available}",
        )

    sections = _sections_for_version(output_dir, version)
    return {
        "version": version,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# 3. GET /document-version-content/{project_id}/{section_filename}/{version}
#    Return the cleaned markdown content for a specific section + version.
# ---------------------------------------------------------------------------

@router.get("/document-version-content/{project_id}/{section_filename}/{version}")
def get_document_version_content(project_id: str, section_filename: str, version: int):
    """Return the cleaned markdown content for a specific section version."""
    output_dir = get_project_generated_document_output_dir(project_id)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    # Find the corresponding JSON file
    base_name = section_filename
    if base_name.lower().endswith(".md"):
        base_name = base_name[:-3]
    json_filename = f"{base_name}.json"
    json_file = output_dir / json_filename

    if not json_file.exists():
        # Try matching by section_number prefix
        matched = False
        for f in output_dir.iterdir():
            if f.suffix.lower() == ".json" and f.name.startswith(base_name.split("_")[0]):
                json_file = f
                matched = True
                break
        if not matched:
            raise HTTPException(status_code=404, detail=f"Section file not found: {section_filename}")

    data = _read_section_json(output_dir, json_file)
    if not data:
        raise HTTPException(status_code=500, detail="Failed to read section data")

    doc_data = data.get("document_data", {})
    version_key = str(version)

    if version_key not in doc_data:
        available = sorted([int(k) for k in doc_data.keys() if k.isdigit()])
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for this section. Available: {available}",
        )

    entry = doc_data[version_key]
    raw_content = entry.get("generated_data", "")

    return {
        "section_number": data.get("section_number", ""),
        "section_filename": data.get("section_filename", section_filename),
        "version": version,
        "content": _strip_agent_preamble(raw_content) if raw_content else "",
    }