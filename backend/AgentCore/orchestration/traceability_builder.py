"""
Traceability Builder

Reads per-section JSON files from the output directory and assembles
a traceability envelope containing all previously generated sections.
"""

import json
import logging
from pathlib import Path

from system_config import get_project_generated_document_output_dir

log = logging.getLogger(__name__)


def build_traceability_json(project_id: str, max_output_chars: int = 30000) -> str:
    """Read per-section JSON files and assemble a compact traceability envelope.

    Uses the top-level document_version to pick the latest version's generated_data
    from each section file, keeping only section_number, section_filename, and generated_data.

    Args:
        project_id: Project identifier.
        max_output_chars: Maximum character count for the resulting JSON string.

    Returns:
        A JSON string containing the traceability envelope.
    """
    generated_sections_output_dir = get_project_generated_document_output_dir(project_id)

    if not generated_sections_output_dir.exists():
        log.warning(f"[TraceabilityBuilder] Output dir not found: {generated_sections_output_dir}")
        return "[]"

    all_sections = []
    for section_json_file in generated_sections_output_dir.glob("*.json"):
        # Skip version.json — it has no document_data
        if section_json_file.name == "version.json":
            continue
        try:
            with open(section_json_file, "r", encoding="utf-8") as file_path:
                envelope = json.load(file_path)
        except Exception as exception:
            log.error(f"[TraceabilityBuilder] Failed to read {section_json_file}: {exception}")
            continue

        doc_data = envelope.get("document_data", {})
        if not doc_data:
            continue

        # Use document_version to get the latest version's generated_data
        doc_version = str(envelope.get("document_version", ""))
        if doc_version not in doc_data:
            continue

        all_sections.append({
            "section_number": envelope.get("section_number", ""),
            "section_filename": envelope.get("section_filename", ""),
            "generated_data": doc_data[doc_version].get("generated_data", ""),
        })

    # Sort by section_number so output is deterministic
    all_sections.sort(key=lambda s: s.get("section_number", "99"))

    traceability_envelope_json = json.dumps(all_sections, indent=2)
    if len(traceability_envelope_json) > max_output_chars:
        while len(traceability_envelope_json) > max_output_chars and all_sections:
            all_sections.pop()
            traceability_envelope_json = json.dumps(all_sections, indent=2)
        log.warning(
            f"[TraceabilityBuilder] Truncated traceability to {len(all_sections)} "
            f"sections ({len(traceability_envelope_json)} chars)"
        )

    return traceability_envelope_json
