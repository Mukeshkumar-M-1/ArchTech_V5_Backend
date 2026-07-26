"""
Repository Query Engine

Provides a clean interface for the Execution Engine to interrogate the Repository Index.
Abstracts away the underlying indexing implementation.
"""

import logging
from typing import List, Optional

from .index import RepositoryIndex, SymbolLocation

log = logging.getLogger(__name__)

class RepositoryQueryEngine:
    """Interface to query the deterministic repository index."""
    
    def __init__(self, index: RepositoryIndex):
        self.index = index
        # Ensure the index is built before we accept queries
        if not self.index.is_built:
            self.index.build()
        log.info("[RepositoryQueryEngine] Initialized and ready for queries.")

    def find_symbol(self, symbol_name: str) -> List[SymbolLocation]:
        """Find the definition locations of a class, function, or method."""
        locations = self.index.symbols.get(symbol_name, [])
        log.info(f"[RepositoryQueryEngine] Query 'find_symbol' for '{symbol_name}' returned {len(locations)} results.")
        return locations

    def find_file_imports(self, file_path: str) -> List[str]:
        """Find all modules imported by a specific file."""
        imports = list(self.index.imports.get(file_path, set()))
        log.info(f"[RepositoryQueryEngine] Query 'find_file_imports' for '{file_path}' returned {len(imports)} imports.")
        return imports

    def find_callers(self, target_function: str) -> List[SymbolLocation]:
        """
        Finds functions that call the target function.
        (Note: In Milestone 2 V1, this relies on a deeper AST pass which would be implemented
        by parsing Call nodes. Returning empty list as a stub for future extension).
        """
        log.warning(f"[RepositoryQueryEngine] 'find_callers' for '{target_function}' is not fully implemented in V1 AST parser.")
        # Future: traverse AST for ast.Call nodes matching the target_function name.
        return []

    def summarize_file(self, file_path: str) -> str:
        """Returns a structural summary of the file (classes, functions)."""
        file_meta = self.index.snapshot.get_file(file_path)
        if not file_meta:
            return f"Error: File '{file_path}' not found in snapshot."
            
        # Collect symbols in this file
        file_symbols = []
        for name, locs in self.index.symbols.items():
            for loc in locs:
                if loc.file_path == file_path:
                    file_symbols.append(loc)
                    
        # Sort by line number
        file_symbols.sort(key=lambda s: s.line_start)
        
        summary = [f"File: {file_path}"]
        summary.append(f"Imports: {', '.join(self.find_file_imports(file_path)) or 'None'}")
        summary.append("Symbols defined:")
        for s in file_symbols:
            summary.append(f"  - [{s.symbol_type}] {s.name} (Lines {s.line_start}-{s.line_end})")
            
        return "\n".join(summary)
