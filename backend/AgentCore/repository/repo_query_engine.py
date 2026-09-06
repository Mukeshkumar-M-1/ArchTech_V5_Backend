"""
Repository Query Engine

Provides a clean interface for the Execution Engine to interrogate the
Repository Index. Supports both code-repo queries (symbols, imports) and
document-repo queries (requirements, placeholders, categories).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from .repo_index import RepositoryIndex, SymbolLocation

log = logging.getLogger(__name__)


class RepositoryQueryEngine:
    """Interface to query the deterministic repository index."""

    def __init__(self, repo_index: RepositoryIndex):
        self.repo_index = repo_index
        if not self.repo_index.is_built:
            self.repo_index.build()
        log.info("[RepositoryQueryEngine] Initialized and ready for queries.")

    # ------------------------------------------------------------------
    # Original code-repo queries (backward compatible)
    # ------------------------------------------------------------------

    def find_symbol(self, symbol_name: str) -> List[SymbolLocation]:
        """Find the definition locations of a class, function, or method."""
        locations = self.repo_index.symbols.symbols.get(symbol_name, [])
        log.info(
            f"[RepositoryQueryEngine] Query 'find_symbol' for '{symbol_name}' "
            f"returned {len(locations)} results."
        )
        return locations

    def find_file_imports(self, file_path: str) -> List[str]:
        """Find all modules imported by a specific file."""
        imports = list(self.repo_index.symbols.imports.get(file_path, set()))
        log.info(
            f"[RepositoryQueryEngine] Query 'find_file_imports' for '{file_path}' "
            f"returned {len(imports)} imports."
        )
        return imports

    def find_callers(self, target_function: str) -> List[SymbolLocation]:
        """
        Finds functions that call the target function.
        Not fully implemented — returns empty list as a stub.
        """
        log.warning(
            f"[RepositoryQueryEngine] 'find_callers' for '{target_function}' "
            "is not fully implemented in V1 AST parser."
        )
        return []

    # ------------------------------------------------------------------
    # Document-repo queries
    # ------------------------------------------------------------------

    def find_requirement(self, req_id: str) -> List[SymbolLocation]:
        """Exact requirement lookup by ID. O(1)."""
        results = self.repo_index.requirements.find_by_id(req_id)
        log.info(
            f"[RepositoryQueryEngine] Query 'find_requirement' for '{req_id}' "
            f"returned {len(results)} results."
        )
        return results

    def find_requirements_by_category(
        self, category: str, sub_category: Optional[str] = None
    ) -> List[SymbolLocation]:
        """Filter requirements by front matter category/sub_category fields."""
        matched_req_ids: List[str] = []
        for _file_path, front_matter in self.repo_index.metadata.front_matter.items():
            if front_matter.get("category") == category:
                if sub_category is None or front_matter.get("sub_category") == sub_category:
                    req_id = front_matter.get("id", "")
                    if req_id:
                        matched_req_ids.append(req_id)

        results: List[SymbolLocation] = []
        for req_id in matched_req_ids:
            results.extend(self.repo_index.requirements.find_by_id(req_id))
        log.info(
            f"[RepositoryQueryEngine] Query 'find_requirements_by_category' "
            f"for '{category}' returned {len(results)} results."
        )
        return results

    def find_requirements_by_keyword(self, keyword: str) -> List[SymbolLocation]:
        """O(1) keyword lookup via inverted index."""
        results = self.repo_index.requirements.find_by_keyword(keyword)
        log.info(
            f"[RepositoryQueryEngine] Query 'find_requirements_by_keyword' "
            f"for '{keyword}' returned {len(results)} results."
        )
        return results

    def get_related_requirements(self, req_id: str) -> List[str]:
        """Get cross-referenced requirement IDs for a given requirement."""
        req_locations = self.repo_index.requirements.find_by_id(req_id)
        related_ids: set = set()

        for location in req_locations:
            file_path = location.file_path
            if file_path in self.repo_index.metadata.dependencies:
                related_ids.update(self.repo_index.metadata.dependencies[file_path])
            if location.metadata and "related_ids" in location.metadata:
                related_list = location.metadata["related_ids"]
                if isinstance(related_list, list):
                    related_ids.update(related_list)

        related_ids.discard(req_id)
        return list(related_ids)

    def get_project_files_by_type(self, file_type: str) -> List[str]:
        """Semantic file grouping driven by ArchTech schema config."""
        all_file_paths = set(self.repo_index.snapshot.files.keys())

        results = self.repo_index._parser.get_project_files_by_type(
            file_type, all_file_paths
        )
        log.info(
            f"[RepositoryQueryEngine] Query 'get_project_files_by_type' for "
            f"'{file_type}' returned {len(results)} files."
        )
        return results

    def get_placeholders(self, file_path: str) -> List[str]:
        """Return template placeholder names for a file."""
        return self.repo_index.metadata.placeholders.get(file_path, [])

    def get_version_info(self) -> Optional[Dict[str, Any]]:
        """Return document version tracking data from _output/version.json."""
        version_file_path = "_output/version.json"
        version_file_meta = self.repo_index.snapshot.get_file(version_file_path)
        if not version_file_meta:
            return None
        root = self.repo_index.snapshot.root_path
        full_path = os.path.join(root, version_file_path)
        try:
            with open(full_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Format-aware file summary
    # ------------------------------------------------------------------

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _extract_req_ids_from_file(self, file_path: str) -> List[str]:
        """Collect requirement IDs referencing a given file."""
        found: List[str] = []
        for req_id, locations in self.repo_index.requirements.requirement_locations.items():
            for loc in locations:
                if loc.file_path == file_path and req_id not in found:
                    found.append(req_id)
        return found

    def summarize_file(self, file_path: str) -> str:
        """Format-aware structural summary of a file."""
        file_meta = self.repo_index.snapshot.get_file(file_path)
        if not file_meta:
            return f"Error: File '{file_path}' not found in snapshot."

        ext = Path(file_path).suffix
        summary_parts: List[str] = [
            f"File: {file_path} ({self._format_size(file_meta.size_bytes)})"
        ]

        # Front matter (markdown files)
        front_matter = self.repo_index.metadata.front_matter.get(file_path)
        if front_matter:
            summary_parts.append(f"Front Matter: {json.dumps(front_matter, indent=2, default=str)}")

        # Requirement IDs found in this file
        file_req_ids = self._extract_req_ids_from_file(file_path)
        if file_req_ids:
            summary_parts.append(f"Requirement IDs: {', '.join(file_req_ids)}")

        # Placeholders (template files)
        file_placeholders = self.repo_index.metadata.placeholders.get(file_path, [])
        if file_placeholders:
            summary_parts.append(f"Placeholders: {', '.join(set(file_placeholders))}")

        # Cross-references / dependencies
        file_dependencies = self.repo_index.metadata.dependencies.get(file_path, [])
        if file_dependencies:
            summary_parts.append(f"Related to: {', '.join(file_dependencies)}")

        # Code symbols
        file_symbols = self.repo_index.symbols.get_file_symbols(file_path)
        if file_symbols:
            summary_parts.append(f"Symbols: {len(file_symbols)} defined")

        # Imports (Python files)
        if ext == ".py":
            imports = self.find_file_imports(file_path)
            if imports:
                summary_parts.append(f"Imports: {', '.join(imports)}")

        return "\n".join(summary_parts)