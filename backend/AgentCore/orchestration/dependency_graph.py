"""DependencyGraph — Topological ordering based on section prerequisites."""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any

from system_config import get_project_phase3_dir

log = logging.getLogger(__name__)

class DependencyGraph:
    """DAG of section dependencies. Loads from phase3 JSON when available."""

    def __init__(self, project_id: str) -> None:
        """Initialize dependency graph with defaults and optional JSON overlay.

        Args:
            project_id: The project identifier for loading phase3 JSON.
        """
        self._dependency_data: dict[str, list[str]] = self.get_default_dependencies(document_type="srs")
        self._load_from_json(project_id)
        log.info(f"[DependencyGraph] Initialized for project '{project_id}': "
                 f"{len(self._dependency_data)} section definitions")
        # for sn, prereqs in sorted(self._dependency_data.items()):
        #     log.info(f"[DependencyGraph] Section {sn} depends on: {prereqs if prereqs else '(none)'}")

    def _load_from_json(self, project_id: str) -> None:
        """Load dependency overrides from the phase3 analysis JSON.

        Args:
            project_id: The project to load phase3 JSON for.
        """
        build_analysis_path = get_project_phase3_dir(project_id=project_id)
        analysis_file_path = (build_analysis_path / f"phase3_{project_id}.json").resolve()

        if not analysis_file_path.exists():
            log.error(f"[DependencyGraph] No phase3 JSON at {analysis_file_path}")
            return

        try:
            analysis_data = json.loads(analysis_file_path.read_text(encoding="utf-8"))
            dependency_map_data = analysis_data.get("dependency_dag", {})
            if dependency_map_data:
                for file_name_key, file_list_value in dependency_map_data.items():
                    file_name = file_name_key.split("_")[0]
                    self._dependency_data[file_name] = file_list_value
                log.info(f"[DependencyGraph] Loaded dependency graph from JSON: {len(self._dependency_data)} sections")
            else:
                log.info(f"[DependencyGraph] phase3 JSON found but no dependency_dag, using defaults")
        except Exception as exception:
            log.warning(f"[DependencyGraph] Failed to load phase3 JSON: {exception}, using defaults")

    def get_default_dependencies(self, document_type: str) -> dict[str, list[str]]:
        """Get default dependencies for a section.

        Args:
            document_type: Current document type.

        Returns:
            list[str]: List of prerequisite section identifiers.
        """
        _DEFAULT_SRS_DEPS: dict[str, list[str]] = {
            "01_project_table.md": [],
            "02_revision_history.md": [
            "01_project_table.md"
            ],
            "03_introduction.md": [
            "01_project_table.md",
            "02_revision_history.md"
            ],
            "04_overall_description.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md"
            ],
            "05_external_interfaces.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md"
            ],
            "06_functional_requirements.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md"
            ],
            "07_software_attributes.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md",
            "06_functional_requirements.md"
            ],
            "08_other_requirements.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md",
            "06_functional_requirements.md",
            "07_software_attributes.md"
            ],
            "09_requirements_traceability.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md",
            "06_functional_requirements.md",
            "07_software_attributes.md",
            "08_other_requirements.md"
            ],
            "10_appendix_a_kc_mapping.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md",
            "06_functional_requirements.md",
            "07_software_attributes.md",
            "08_other_requirements.md",
            "09_requirements_traceability.md"
            ],
            "11_appendix_b_supporting_information.md": [
            "01_project_table.md",
            "02_revision_history.md",
            "03_introduction.md",
            "04_overall_description.md",
            "05_external_interfaces.md",
            "06_functional_requirements.md",
            "07_software_attributes.md",
            "08_other_requirements.md",
            "09_requirements_traceability.md",
            "10_appendix_a_kc_mapping.md"
            ]
        }

        if document_type == "srs":
            return _DEFAULT_SRS_DEPS

        return _DEFAULT_SRS_DEPS

    def get_document_tree(self, project_id: str) -> list[dict[str, Any]]:
        """
        Load the document tree from the phase3 analysis JSON.

        Args:
            project_id: The project identifier for loading phase3 JSON.

        Returns:
            list[dict[str, Any]]: The document tree.
        """

        build_analysis_path = get_project_phase3_dir(project_id=project_id)
        analysis_file_path = (build_analysis_path / f"phase3_{project_id}.json").resolve()

        if not analysis_file_path.exists():
            log.error(f"[DependencyGraph] No phase3 JSON at {analysis_file_path}")
            return []
        
        """
        "section_number": entry.section_number,
        "heading": dt_entry.get("heading", entry.heading),
        "filename": dt_entry.get("filename", entry.filename),
        "subsections": dt_entry.get("subsections", []),
        """

        try:
            document_tree_data = []
            analysis_data = json.loads(analysis_file_path.read_text(encoding="utf-8"))
            document_tree = analysis_data.get("document_tree", [])
            

            for index_section, document_entry_data in enumerate(document_tree):
                section_file_name =  document_entry_data.get("filename", "")
                section_number = section_file_name.split("_")[0]
                section_heading = document_entry_data.get("heading", "")
                sub_section_data = document_entry_data.get("subsections", [])
                section_subsection_data = []

                for index_subsection, subsection_entry in enumerate(sub_section_data):
                    section_subsection_data.append(subsection_entry.get("heading", ""))

                document_tree_data.append({
                    "section_number": section_number,
                    "heading": section_heading,
                    "filename": section_file_name,
                    "subsections": section_subsection_data
                })

            log.info(f"[DependencyGraph] Loaded document tree from JSON: {len(document_tree)} sections")
            return document_tree_data
        except Exception as exception:
            log.warning(f"[DependencyGraph] Failed to load phase3 JSON: {exception}, using defaults")
            return []

    def get_prerequisites(self, section_filename: str) -> list[str]:
        """Get all direct prerequisites for a section.

        Args:
            section_filename: The section identifier.

        Returns:
           list of prerequisites data
        """
        if not section_filename:
            log.warning("[DependencyGraph] get_prerequisites called with empty section_filename")
            return []

        if section_filename not in self._dependency_data:
            log.warning(f"[DependencyGraph] Section '{section_filename}' not found in dependency data. "
                        f"Available sections: {list(self._dependency_data.keys())}")
            return []

        section_prerequires_data = self._dependency_data[section_filename]
        # log.info(f"[DependencyGraph] get_prerequisites('{section_filename}') -> {section_prerequires_data}")
        return section_prerequires_data

    def is_satisfied(self, section_number: str, completed: list[str]) -> bool:
        """Check if all prerequisites for a section are completed.

        Args:
            section_number: The section to check.
            completed: List of completed section identifiers.

        Returns:
            True if all prerequisites are in the completed list.
        """
        prereqs = self.get_prerequisites(section_number)
        satisfied = set(prereqs).issubset(set(completed))
        log.info(f"[DependencyGraph] is_satisfied('{section_number}'): prereqs={prereqs}, "
                  f"completed={completed[:5]}..., satisfied={satisfied}")
        return satisfied


