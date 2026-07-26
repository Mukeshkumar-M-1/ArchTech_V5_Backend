"""SectionRegistry — Scans template directory and extracts section metadata."""

from __future__ import annotations

from importlib.resources import read_text
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from system_config import get_project_template_dir

log = logging.getLogger(__name__)


@dataclass
class SectionRegistryEntry:
    section_number: str
    filename: str
    heading: str


class SectionRegistry:
    """Builds an ordered list of sections from the template directory."""

    _SECTION_FILE_NAME_RE = re.compile(r"^(\d{2})_(.+)\.md$")

    @classmethod
    def parse_template_dir(self, project_id: str) -> list[SectionRegistryEntry]:
        """Parse all markdown files from a project's template directory.

        Args:
            project_id: The project identifier for path resolution.

        Returns:
            Sorted list of SectionRegistryEntry objects.
        """
        section_registry_entry: list[SectionRegistryEntry] = []
        base_template_folder = get_project_template_dir(project_id)


        if not base_template_folder.exists():
            log.warning(f"[SectionRegistry] Template directory not found: {base_template_folder}")
            return []
        log.info(f"[SectionRegistry] Scanning template directory: {base_template_folder}")

        for template_file_item in sorted(base_template_folder.iterdir()):
            # log.info(f"[SectionRegistry] Found template file: {template_file_item.name}")
            
            if not template_file_item.is_file() or template_file_item.suffix.lower() != ".md":
                log.info(f"[SectionRegistry] Skipping non-markdown file: {template_file_item.name}")
                continue

            valid_file_name = self._SECTION_FILE_NAME_RE.match(template_file_item.name)
            if valid_file_name:
                section_num = valid_file_name.group(1)
                section_title = valid_file_name.group(2).replace("_", " ").title()
                # log.info(f"[SectionRegistry] Parsed Section: [{section_num}:{section_title}] -> [{template_file_item.name}]")
                section_registry_entry.append(SectionRegistryEntry(
                    section_number=section_num,
                    filename=template_file_item.name,
                    heading=section_title,
                ))

        section_registry_entry = sorted(section_registry_entry, key=lambda entry_item: entry_item.section_number)
        log.info(f"[SectionRegistry] Parsed {len(section_registry_entry)} sections from template dir: {len(section_registry_entry)} sections")
        return section_registry_entry

    @classmethod
    def build_section_content_data(self, project_id: str, section_registry_entry: list[SectionRegistryEntry]) -> dict[str, str]:
        """Look up a single section entry by its number.

        Args:
            project_id: The project identifier for path resolution.
            section_registry_entry: The list of all section section_registry_entry.

        Returns:
            The matching SectionRegistryEntry, or None if not found.
        """
        section_content_data: dict[str, str] = {}
        base_template_folder = get_project_template_dir(project_id)

        for entry_item in section_registry_entry:
            if entry_item.section_number is not None:
                section_file_path = (base_template_folder / entry_item.filename).resolve()
                if section_file_path.is_file():
                    section_content_data[entry_item.section_number] = section_file_path.read_text(encoding="utf-8")
                    # log.info(f"[SectionRegistry] Read section content : [{entry_item.section_number}]")
                else:
                    log.error(f"[SectionRegistry] Section file not found: {section_file_path}")
        return section_content_data
    