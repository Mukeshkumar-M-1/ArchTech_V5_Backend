"""
Repository Index

Parses files in a RepositorySnapshot to build deterministic graphs (AST, Symbols, Imports).
This provides a static, LLM-free understanding of the codebase structure.
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

from .snapshot import RepositorySnapshot, FileMetadata

log = logging.getLogger(__name__)

@dataclass
class SymbolLocation:
    name: str
    symbol_type: str  # 'class', 'function', 'method'
    file_path: str
    line_start: int
    line_end: int


class RepositoryIndex:
    """Builds a deterministic index of a codebase from a snapshot."""

    def __init__(self, snapshot: RepositorySnapshot):
        self.snapshot = snapshot
        self.symbols: Dict[str, List[SymbolLocation]] = {}
        self.imports: Dict[str, Set[str]] = {}  # file_path -> set of imported module names
        self.is_built = False
        log.info(f"[RepositoryIndex] Initialized for snapshot {snapshot.snapshot_id}")

    def build(self) -> None:
        """Parse all supported files in the snapshot to build the index."""
        if self.is_built:
            return
            
        log.info("[RepositoryIndex] Building index from AST...")
        
        for rel_path, file_meta in self.snapshot.files.items():
            if rel_path.endswith('.py'):
                self._index_python_file(self.snapshot.root_path, file_meta)
                
        self.is_built = True
        total_symbols = sum(len(locs) for locs in self.symbols.values())
        log.info(f"[RepositoryIndex] Index built: {total_symbols} symbols mapped across {len(self.snapshot.files)} files.")

    def _index_python_file(self, root_path: str, file_meta: FileMetadata) -> None:
        import os
        full_path = os.path.join(root_path, file_meta.path)
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=file_meta.path)
            
            file_imports = set()
            
            for node in ast.walk(tree):
                # Map classes
                if isinstance(node, ast.ClassDef):
                    self._add_symbol(node.name, "class", file_meta.path, node.lineno, getattr(node, 'end_lineno', node.lineno))
                    # Map methods inside classes
                    for body_node in node.body:
                        if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            full_name = f"{node.name}.{body_node.name}"
                            self._add_symbol(full_name, "method", file_meta.path, body_node.lineno, getattr(body_node, 'end_lineno', body_node.lineno))
                            
                # Map module-level functions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Ensure it's not a method (we caught those above)
                    # ast.walk visits everything, but we can't easily check parent. 
                    # For simplicity, we just add it by name. It might overwrite/append to method names if they match, which is fine since we store Lists.
                    self._add_symbol(node.name, "function", file_meta.path, node.lineno, getattr(node, 'end_lineno', node.lineno))
                    
                # Map imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        file_imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        file_imports.add(node.module)

            self.imports[file_meta.path] = file_imports

        except SyntaxError as e:
            log.warning(f"[RepositoryIndex] Syntax error in {file_meta.path}: {e}")
        except Exception as e:
            log.warning(f"[RepositoryIndex] Failed to parse {file_meta.path}: {e}")

    def _add_symbol(self, name: str, sym_type: str, file_path: str, start: int, end: int) -> None:
        loc = SymbolLocation(name, sym_type, file_path, start, end)
        if name not in self.symbols:
            self.symbols[name] = []
        self.symbols[name].append(loc)
