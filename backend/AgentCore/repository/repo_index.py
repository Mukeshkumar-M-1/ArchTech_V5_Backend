"""
Repository Index

Parses files in a RepositorySnapshot to build deterministic indexes
covering symbols, requirements, metadata, and cross-references.
Uses a single parser engine with registered query packs per file format,
mirroring the Cursor/tree-sitter architecture.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .repo_snapshot import RepositorySnapshot, FileMetadata

log = logging.getLogger(__name__)


# ====================================================================
# Data structures
# ====================================================================

@dataclass
class SymbolLocation:
    """A named symbol (class, function, requirement, heading) at a file location."""
    name: str
    symbol_type: str
    file_path: str
    line_start: int
    line_end: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ParserResult:
    """All index entries produced for one file."""
    symbols: List[SymbolLocation] = field(default_factory=list)
    requirements: List[Tuple[str, SymbolLocation]] = field(default_factory=list)
    front_matter: Optional[Dict[str, Any]] = None
    placeholder_names: List[str] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)
    json_keys: List[str] = field(default_factory=list)
    keyword_terms: List[str] = field(default_factory=list)


# ====================================================================
# Tokenizer — pluggable keyword extraction
# ====================================================================

class Tokenizer(ABC):
    """Abstract tokenizer for keyword extraction."""

    @abstractmethod
    def tokenize(self, text: str) -> Set[str]:
        ...


class SimpleEnglishTokenizer(Tokenizer):
    """Lowercase, split on non-alphanumeric, filter stopwords."""

    STOPWORDS: Set[str] = {
        "the", "and", "for", "this", "that", "with", "from", "are", "was",
        "were", "been", "being", "have", "has", "had", "but", "not", "all",
        "also", "can", "into", "some", "than", "then", "may", "should",
        "will", "would", "your", "our", "its", "their", "each", "every",
        "any", "both", "few", "more", "most", "other", "these", "those",
        "system", "must", "shall", "shall", "support", "used", "use",
    }

    def tokenize(self, text: str) -> Set[str]:
        words = re.findall(r"\b\w{3,}\b", text)
        return {w.lower() for w in words if w.lower() not in self.STOPWORDS}


# ====================================================================
# Domain extractor — regex-based semantic passes on text content
# ====================================================================

DomainExtractorCallback = Callable[[re.Match, str, str, ParserResult], None]


@dataclass
class DomainExtractor:
    """A compiled regex pattern with an associated action for semantic extraction."""
    pattern: re.Pattern
    action: DomainExtractorCallback


# ====================================================================
# Query pack — semantic rules for one file extension
# ====================================================================

@dataclass
class QueryPack:
    """Semantic extraction rules for a file extension.

    Registered into the single RepositoryParser instead of having
    separate parser classes per format.
    """
    parse_method: Callable[[str, FileMetadata, Tokenizer], ParserResult]


# ====================================================================
# ArchTech schema map — configurable file-type grouping
# ====================================================================

DEFAULT_ARCHTECH_SCHEMA_MAP: Dict[str, Dict[str, List[str]]] = {
    "requirement": {
        "path_prefixes": ["requirements/", "memory/knowledge/requirements/"]
    },
    "version": {
        "path_prefixes": ["_output/version.json"]
    },
    "section_output": {
        "path_prefixes": ["_output/0", "_output/1"]
    },
    "session": {
        "path_prefixes": ["sessions/", "chat_sessions/"]
    },
    "template": {
        "path_prefixes": ["templates/"]
    },
    "knowledge": {
        "path_prefixes": ["memory/knowledge/"]
    },
    "analysis": {
        "path_prefixes": ["Template_Analysis/"]
    },
}


class ArchTechSchemaConfig:
    """Holds the schema configuration. Load from external file or use defaults."""

    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        self._schema = schema or DEFAULT_ARCHTECH_SCHEMA_MAP

    def load_from_file(self, config_path: str) -> None:
        """Load schema mapping from a JSON config file."""
        try:
            with open(config_path, "r") as f:
                self._schema = json.load(f)
            log.info(f"[ArchTechSchemaConfig] Loaded schema from [{config_path}]")
        except (OSError, json.JSONDecodeError) as e:
            log.warning(f"[ArchTechSchemaConfig] Failed to load [{config_path}], using defaults: [{e}]")

    def get_path_prefixes(self, file_type: str) -> List[str]:
        entry = self._schema.get(file_type, {})
        return entry.get("path_prefixes", [])


# ====================================================================
# Format-specific parsers — functions, not classes
# ====================================================================

# Strict ArchTech requirement ID pattern
_RE_ARCHTECH_REQ_ID = re.compile(r"\b(?:HAR|FUN|NFR|SOF)-\d{4}\b")
_RE_PLACEHOLDER = re.compile(r"\{\{([\w-]+)\}\}")
_RE_CROSS_REF = re.compile(r"\[((?:HAR|FUN|NFR|SOF)-\d{4})\]\([^)]+\)")

def _extract_front_matter(source_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Extract YAML front matter from markdown source, return (dict, remainder)."""
    import yaml
    stripped = source_text.lstrip()
    if not stripped.startswith("---"):
        return None, source_text
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return None, source_text
    fm_text = parts[1]
    remainder = parts[2].lstrip("\n")
    try:
        fm_data = yaml.safe_load(fm_text)
        if not isinstance(fm_data, dict):
            return None, remainder
        return fm_data, remainder
    except yaml.YAMLError:
        return None, remainder


def _parse_markdown_file(
    source_path: str,
    file_meta: FileMetadata,
    tokenizer: Tokenizer,
) -> ParserResult:
    """Parse a .md file for headings, requirements, placeholders, and cross-refs."""
    result = ParserResult()
    source_text = ""
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            source_text = f.read()
    except (OSError, UnicodeDecodeError):
        return result

    front_matter, body_text = _extract_front_matter(source_text)
    result.front_matter = front_matter

    # If front matter indicates a requirement, register it
    if front_matter and front_matter.get("type") == "requirement":
        req_id = front_matter.get("id", "")
        if req_id:
            req_location = SymbolLocation(
                name=req_id,
                symbol_type="requirement",
                file_path=file_meta.path,
                line_start=1,
                line_end=len(source_text.splitlines()),
                metadata=dict(front_matter),
            )
            result.requirements.append((req_id, req_location))

    # Parse headings as symbols
    lines = source_text.splitlines()
    for line_idx, line in enumerate(lines):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            sym_type = f"heading_h{level}"
            loc = SymbolLocation(
                name=heading_text,
                symbol_type=sym_type,
                file_path=file_meta.path,
                line_start=line_idx + 1,
                line_end=line_idx + 1,
            )
            result.symbols.append(loc)

    # Domain-specific extractions
    found_req_ids = set()
    for match in _RE_ARCHTECH_REQ_ID.finditer(source_text):
        req_id = match.group(0)
        if req_id not in found_req_ids:
            found_req_ids.add(req_id)
            line_num = source_text[:match.start()].count("\n") + 1
            ref_location = SymbolLocation(
                name=req_id,
                symbol_type="requirement_reference",
                file_path=file_meta.path,
                line_start=line_num,
                line_end=line_num,
            )
            result.requirements.append((req_id, ref_location))

    for match in _RE_PLACEHOLDER.finditer(source_text):
        result.placeholder_names.append(match.group(1))

    for match in _RE_CROSS_REF.finditer(source_text):
        result.cross_references.append(match.group(1))

    # Keywords from front matter or body text
    if front_matter and "keywords" in front_matter:
        kw_list = front_matter["keywords"]
        if isinstance(kw_list, list):
            result.keyword_terms.extend(kw_list)
        elif isinstance(kw_list, str):
            result.keyword_terms.extend(tokenizer.tokenize(kw_list))
    else:
        result.keyword_terms.extend(tokenizer.tokenize(body_text))

    return result


def _parse_python_file(
    source_path: str,
    file_meta: FileMetadata,
    tokenizer: Tokenizer,
) -> ParserResult:
    """Parse a .py file using AST for symbols and imports."""
    import ast as py_ast
    result = ParserResult()
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            source_text = f.read()
        tree = py_ast.parse(source_text, filename=file_meta.path)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return result

    file_imports: Set[str] = set()

    for node in py_ast.walk(tree):
        if isinstance(node, py_ast.ClassDef):
            result.symbols.append(SymbolLocation(
                name=node.name,
                symbol_type="class",
                file_path=file_meta.path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
            ))
            for body_node in node.body:
                if isinstance(body_node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
                    full_name = f"{node.name}.{body_node.name}"
                    result.symbols.append(SymbolLocation(
                        name=full_name,
                        symbol_type="method",
                        file_path=file_meta.path,
                        line_start=body_node.lineno,
                        line_end=getattr(body_node, "end_lineno", body_node.lineno) or body_node.lineno,
                    ))
        elif isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
            result.symbols.append(SymbolLocation(
                name=node.name,
                symbol_type="function",
                file_path=file_meta.path,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno) or node.lineno,
            ))
        elif isinstance(node, py_ast.Import):
            for alias in node.names:
                file_imports.add(alias.name)
        elif isinstance(node, py_ast.ImportFrom):
            if node.module:
                file_imports.add(node.module)

    result.cross_references.extend(sorted(file_imports))
    return result


def _parse_json_file(
    source_path: str,
    file_meta: FileMetadata,
    _tokenizer: Tokenizer,
) -> ParserResult:
    """Parse a .json file for structure, requirements, and keys."""
    result = ParserResult()
    source_text = ""
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            source_text = f.read()
        data = json.loads(source_text)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return result

    result.json_keys.append("root")

    def _extract_json_obj(obj: Any, prefix: str, depth: int) -> None:
        if depth > 5:
            return
        if isinstance(obj, dict):
            req_id = obj.get("id", "")
            if _RE_ARCHTECH_REQ_ID.fullmatch(req_id):
                char_pos = source_text.find(json.dumps(req_id)) if req_id else -1
                approx_line = source_text[:char_pos].count("\n") + 1 if char_pos >= 0 else 1
                metadata_dict = {k: v for k, v in obj.items() if k not in ("text", "explanation")}
                req_location = SymbolLocation(
                    name=req_id,
                    symbol_type="requirement",
                    file_path=file_meta.path,
                    line_start=approx_line,
                    line_end=approx_line + 10,
                    metadata=metadata_dict,
                )
                result.requirements.append((req_id, req_location))
                related_ids = obj.get("related_ids", [])
                result.cross_references.extend(
                    rid for rid in related_ids if _RE_ARCHTECH_REQ_ID.fullmatch(rid)
                )
                kw_field = obj.get("keywords", [])
                if isinstance(kw_field, list):
                    result.keyword_terms.extend(kw_field)

            for key, value in obj.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                result.json_keys.append(child_prefix)
                if isinstance(value, dict):
                    _extract_json_obj(value, child_prefix, depth + 1)
                elif isinstance(value, list):
                    _extract_json_obj(value, child_prefix, depth + 1)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _extract_json_obj(item, f"{prefix}[{idx}]", depth + 1)

    if isinstance(data, dict):
        _extract_json_obj(data, "", 0)
    elif isinstance(data, list):
        _extract_json_obj(data, "", 0)

    return result


def _parse_jsonl_file(
    source_path: str,
    file_meta: FileMetadata,
    tokenizer: Tokenizer,
) -> ParserResult:
    """Parse a .jsonl file, treating each line as a JSON object."""
    result = ParserResult()
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        msg_text = obj.get("content", "") or obj.get("text", "")
                        if msg_text:
                            result.keyword_terms.extend(tokenizer.tokenize(msg_text))
                        req_matches = _RE_ARCHTECH_REQ_ID.findall(msg_text)
                        for req_id in req_matches:
                            full_id = f"{req_id}"
                            if full_id not in [r[0] for r in result.requirements]:
                                ref_location = SymbolLocation(
                                    name=full_id,
                                    symbol_type="requirement_reference",
                                    file_path=file_meta.path,
                                    line_start=line_num,
                                    line_end=line_num,
                                )
                                result.requirements.append((full_id, ref_location))
                except json.JSONDecodeError:
                    continue
    except (OSError, UnicodeDecodeError):
        pass
    return result


# ====================================================================
# Modular index components
# ====================================================================

class RequirementIndex:
    """Owns requirement ID → locations mapping and keyword inverted index."""

    def __init__(self):
        self.requirement_locations: Dict[str, List[SymbolLocation]] = {}
        self.keyword_index: Dict[str, Set[str]] = {}
        self._file_ownership: Dict[str, Set[str]] = {}

    def add(self, req_id: str, location: SymbolLocation, keywords: List[str]) -> None:
        if req_id not in self.requirement_locations:
            self.requirement_locations[req_id] = []
        self.requirement_locations[req_id].append(location)

        file_path = location.file_path
        if file_path not in self._file_ownership:
            self._file_ownership[file_path] = set()
        self._file_ownership[file_path].add(req_id)

        for kw in keywords:
            kw_lower = kw.lower() if isinstance(kw, str) else str(kw).lower()
            if kw_lower not in self.keyword_index:
                self.keyword_index[kw_lower] = set()
            self.keyword_index[kw_lower].add(req_id)

    def remove(self, file_path: str) -> None:
        req_ids_to_remove = self._file_ownership.pop(file_path, set())
        for req_id in req_ids_to_remove:
            if req_id in self.requirement_locations:
                self.requirement_locations[req_id] = [
                    loc for loc in self.requirement_locations[req_id]
                    if loc.file_path != file_path
                ]
                if not self.requirement_locations[req_id]:
                    del self.requirement_locations[req_id]

            for _kw, ids in self.keyword_index.items():
                ids.discard(req_id)

    def find_by_id(self, req_id: str) -> List[SymbolLocation]:
        return self.requirement_locations.get(req_id, [])

    def find_by_keyword(self, keyword: str) -> List[SymbolLocation]:
        matched_ids = self.keyword_index.get(keyword.lower(), set())
        results: List[SymbolLocation] = []
        for req_id in matched_ids:
            results.extend(self.find_by_id(req_id))
        return results


class SymbolIndex:
    """Owns symbol name → locations mapping and imports."""

    def __init__(self):
        self.symbols: Dict[str, List[SymbolLocation]] = {}
        self.imports: Dict[str, Set[str]] = {}

    def add(self, location: SymbolLocation) -> None:
        if location.name not in self.symbols:
            self.symbols[location.name] = []
        self.symbols[location.name].append(location)

    def remove(self, file_path: str) -> None:
        for name in list(self.symbols.keys()):
            self.symbols[name] = [
                loc for loc in self.symbols[name] if loc.file_path != file_path
            ]
            if not self.symbols[name]:
                del self.symbols[name]

    def get_file_symbols(self, file_path: str) -> List[SymbolLocation]:
        results: List[SymbolLocation] = []
        for locs in self.symbols.values():
            results.extend(loc for loc in locs if loc.file_path == file_path)
        return results


class MetadataIndex:
    """Owns front matter, placeholders, dependencies, json keys per file."""

    def __init__(self):
        self.front_matter: Dict[str, Dict[str, Any]] = {}
        self.placeholders: Dict[str, List[str]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.json_keys: Dict[str, List[str]] = {}

    def add(self, file_path: str, parse_result: ParserResult) -> None:
        if parse_result.front_matter:
            self.front_matter[file_path] = parse_result.front_matter
        if parse_result.placeholder_names:
            self.placeholders[file_path] = parse_result.placeholder_names
        if parse_result.cross_references:
            self.dependencies[file_path] = parse_result.cross_references
        if parse_result.json_keys:
            self.json_keys[file_path] = parse_result.json_keys

    def remove(self, file_path: str) -> None:
        self.front_matter.pop(file_path, None)
        self.placeholders.pop(file_path, None)
        self.dependencies.pop(file_path, None)
        self.json_keys.pop(file_path, None)


# ====================================================================
# Format detectors — content-based, not extension-based
# ====================================================================

_FORMAT_DETECTOR_JSON = re.compile(r"^[\s\{\[]")
_FORMAT_DETECTOR_PYTHON_IMPORT = re.compile(r"^(?:from\s+\w|import\s+\w)")


def _detect_format_from_content(source_text: str) -> Optional[str]:
    """Determine file format from content. Returns format name or None."""
    stripped = source_text.strip()
    if not stripped:
        return None

    first_char = stripped[0]

    # JSON: starts with { or [
    if first_char in ("{", "["):
        try:
            json.loads(stripped)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass

    # JSONL: every non-empty line is valid JSON
    non_empty_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(non_empty_lines) > 1:
        jsonl_count = sum(
            1 for line in non_empty_lines
            if line and line[0] in ("{", "[") and _FORMAT_DETECTOR_JSON.match(line)
        )
        if jsonl_count > len(non_empty_lines) * 0.7:
            return "jsonl"

    # Python: top-level import/from/class/def statements
    has_import = any(
        _FORMAT_DETECTOR_PYTHON_IMPORT.match(line) for line in non_empty_lines[:30]
    )
    if has_import:
        return "python"

    # Markdown / general text: everything else with at least some structure
    return "markdown"


@dataclass
class FormatHandler:
    """A format's detector + parser, registered by name."""
    detect_from_content: Callable[[str], bool]
    parse_method: Callable[[str, FileMetadata, Tokenizer], ParserResult]


def _detect_json(content: str) -> bool:
    return _detect_format_from_content(content) == "json"


def _detect_jsonl(content: str) -> bool:
    return _detect_format_from_content(content) == "jsonl"


def _detect_python(content: str) -> bool:
    return _detect_format_from_content(content) == "python"


def _detect_markdown(content: str) -> bool:
    return _detect_format_from_content(content) == "markdown"


# Registered format handlers — content-driven, extension-agnostic
REGISTERED_FORMAT_HANDLERS: List[FormatHandler] = [
    FormatHandler(detect_from_content=_detect_json,     parse_method=_parse_json_file),
    FormatHandler(detect_from_content=_detect_jsonl,    parse_method=_parse_jsonl_file),
    FormatHandler(detect_from_content=_detect_python,   parse_method=_parse_python_file),
    FormatHandler(detect_from_content=_detect_markdown, parse_method=_parse_markdown_file),
]


# Extension → format name fast-path (optional hint, not authoritative)
_EXTENSION_FORMAT_HINTS: Dict[str, str] = {
    ".md": "markdown",
    ".py": "python",
    ".json": "json",
    ".jsonl": "jsonl",
}


class RepositoryParser:
    """Single parser engine — content-based, not extension-based.

    Dispatches to the correct parser by examining file content.
    Extension is only a fast-path hint when available.
    """

    def __init__(self, schema_config: Optional[ArchTechSchemaConfig] = None):
        self.schema_config = schema_config or ArchTechSchemaConfig()
        self._tokenizer = SimpleEnglishTokenizer()
        self._format_handlers: List[FormatHandler] = list(REGISTERED_FORMAT_HANDLERS)

    def register_format_handler(self, handler: FormatHandler) -> None:
        """Register a new format detector + parser for content-driven dispatch."""
        self._format_handlers.append(handler)

    def _read_file_content(self, source_path: str) -> Optional[str]:
        """Read file content. Returns None on read failure."""
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None

    def _resolve_format(self, source_path: str, file_meta: FileMetadata) -> Optional[str]:
        """Determine format: extension hint first, then content detection."""
        ext = Path(file_meta.path).suffix

        # Fast-path: if extension is known, use it
        if ext in _EXTENSION_FORMAT_HINTS:
            hint = _EXTENSION_FORMAT_HINTS[ext]
            for handler in self._format_handlers:
                if handler.detect_from_content is globals().get(f"_detect_{hint}"):
                    return hint
            return hint

        # Content-based detection
        content = self._read_file_content(source_path)
        if content is not None:
            return _detect_format_from_content(content)

        return None

    def parse(self, root_path: str, file_meta: FileMetadata) -> ParserResult:
        """Parse a single file using content-based format detection."""
        source_path = os.path.join(root_path, file_meta.path)
        detected_format = self._resolve_format(source_path, file_meta)
        if not detected_format:
            return ParserResult()

        # Find the handler for this format
        for handler in self._format_handlers:
            handler_name = handler.detect_from_content.__name__
            if handler_name == f"_detect_{detected_format}":
                return handler.parse_method(source_path, file_meta, self._tokenizer)

        return ParserResult()

    def get_project_files_by_type(self, file_type: str, all_files: Set[str]) -> List[str]:
        """Return files matching a semantic type via schema config."""
        path_prefixes = self.schema_config.get_path_prefixes(file_type)
        if not path_prefixes:
            return []
        return [f for f in all_files if any(f.startswith(p) for p in path_prefixes)]


# Default parser instance
DEFAULT_PARSER = RepositoryParser()


# ====================================================================
# RepositoryIndex — coordinates modular index components
# ====================================================================

class RepositoryIndex:
    """Builds a deterministic index from a repository snapshot.

    Composes RequirementIndex, SymbolIndex, and MetadataIndex for
    modular ownership. Supports incremental rebuild via Merkle hashing.
    """

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        parser: Optional[RepositoryParser] = None,
    ):
        self.snapshot = snapshot
        self._parser = parser or DEFAULT_PARSER
        self.requirements = RequirementIndex()
        self.symbols = SymbolIndex()
        self.metadata = MetadataIndex()
        self._indexed_hashes: Dict[str, str] = {}
        self.is_built = False
        log.info(f"[RepositoryIndex] Initialized for snapshot {snapshot.snapshot_id}")

    def _parse_single_file(self, file_meta: FileMetadata) -> ParserResult:
        return self._parser.parse(self.snapshot.root_path, file_meta)

    def _apply_file_result(self, rel_path: str, file_meta: FileMetadata, parse_result: ParserResult) -> None:
        """Apply all index entries from a single file's parse result."""
        self.metadata.add(rel_path, parse_result)

        for sym in parse_result.symbols:
            self.symbols.add(sym)

        for req_id, req_location in parse_result.requirements:
            self.requirements.add(req_id, req_location, parse_result.keyword_terms)

        # Preserve Python imports in symbol index
        if parse_result.cross_references and file_meta.path.endswith(".py"):
            self.symbols.imports[rel_path] = set(parse_result.cross_references)

    def _unapply_file(self, file_path: str) -> None:
        """Remove all indexed entries belonging to a single file."""
        self.metadata.remove(file_path)
        self.symbols.remove(file_path)
        self.requirements.remove(file_path)

    def build(self, previous_index: Optional["RepositoryIndex"] = None) -> None:
        """Build or update the index.

        When previous_index is provided, performs incremental rebuild:
        only re-parses files whose SHA-256 hash changed.
        """
        log.info("[RepositoryIndex] Building index...")

        if previous_index:
            # Copy unchanged entries
            for file_path in previous_index._indexed_hashes:
                if file_path in self.snapshot.files:
                    old_hash = previous_index._indexed_hashes[file_path]
                    new_meta = self.snapshot.files[file_path]
                    if old_hash == new_meta.sha256_hash:
                        # File unchanged — skip reparse
                        self._indexed_hashes[file_path] = new_meta.sha256_hash
                        continue
                # File removed or changed — will be re-parsed below
                self._unapply_file(file_path)

        files_to_parse = list(self.snapshot.files.items())

        # Use thread pool for I/O-bound parsing on large repos
        use_parallel = len(files_to_parse) > 100
        if use_parallel:
            with ThreadPoolExecutor(max_workers=4) as pool:
                parse_results = list(pool.map(
                    self._parse_single_file,
                    [m for _, m in files_to_parse],
                ))
        else:
            parse_results = [
                self._parse_single_file(m) for _, m in files_to_parse
            ]

        for (rel_path, file_meta), parse_result in zip(files_to_parse, parse_results):
            # If file was previously indexed, unapply first
            if rel_path in self._indexed_hashes:
                self._unapply_file(rel_path)

            self._apply_file_result(rel_path, file_meta, parse_result)
            self._indexed_hashes[rel_path] = file_meta.sha256_hash

        self.is_built = True
        total_symbols = sum(len(locs) for locs in self.symbols.symbols.values())
        total_requirements = sum(
            len(locs) for locs in self.requirements.requirement_locations.values()
        )
        log.info(
            f"[RepositoryIndex] Index built: {total_symbols} symbols, "
            f"{total_requirements} requirement references across "
            f"{len(self.snapshot.files)} files."
        )

    def rebuild(self, new_snapshot: RepositorySnapshot) -> None:
        """Incremental rebuild using apply/unapply per-file ownership.

        Compares file hashes to detect added, modified, and deleted files.
        Only re-parses the files that actually changed.
        """
        self.snapshot = new_snapshot
        log.info("[RepositoryIndex] Incremental rebuild...")

        reparse_count = 0

        for rel_path, file_meta in new_snapshot.files.items():
            was_indexed = rel_path in self._indexed_hashes
            hash_changed = (
                was_indexed
                and self._indexed_hashes[rel_path] != file_meta.sha256_hash
            )
            if not was_indexed or hash_changed:
                self._unapply_file(rel_path)
                parse_result = self._parse_single_file(file_meta)
                self._apply_file_result(rel_path, file_meta, parse_result)
                self._indexed_hashes[rel_path] = file_meta.sha256_hash
                reparse_count += 1

        # Detect and remove deleted files
        deleted_paths = [
            old_path for old_path in self._indexed_hashes
            if old_path not in new_snapshot.files
        ]
        for old_path in deleted_paths:
            self._unapply_file(old_path)
            del self._indexed_hashes[old_path]

        log.info(
            f"[RepositoryIndex] Rebuild complete: re-parsed {reparse_count} files, "
            f"removed {len(deleted_paths)} deleted files."
        )

        