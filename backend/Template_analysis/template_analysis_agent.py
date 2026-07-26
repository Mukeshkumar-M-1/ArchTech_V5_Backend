"""
TemplateAnalysisAgent -- Phase 3: Template Understanding (Blueprint Scanner)

Orchestrates the 5 sub-phases:
  3.1 Parse Template          -> DocumentTreeNode list
  3.2 Identify Sections       -> TableOfContents list[dict]
  3.3 Identify Required Fields -> FieldsList (with vague template inference)
  3.4 Build Dependency Graph  -> DependencyDAG dict
  3.5 Determine Output Types  -> StylingRule list

All LLM calls use llm_api_handler.llm_request with retry, backoff,
model fallback chain, and auto JSON correction. Each sub-phase has a
default_fallback() heuristic.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from llm_api_handler import llm_request, DEFAULT_TIMEOUT
from prompts.engine import PromptEngine
from system_config import get_project_template_dir, get_source_template_dir
from pydantic import BaseModel

# ===================================================================
# Pydantic Models — Phase 3 Output Types
# ===================================================================

class DocumentTreeNode(BaseModel):
    heading: str
    level: int
    filename: str
    subsections: list["DocumentTreeNode"] = []
    section_number: int = 0


class Field(BaseModel):
    name: str
    location: str
    field_type: str
    placeholder_value: str | None = None
    inferred_from: str | None = None


class FieldsList(BaseModel):
    fields_by_file: dict[str, list[dict]] = {}


DocumentTreeNode.model_rebuild()

log = logging.getLogger("TemplateAnalyzer.Agent")
DEFAULT_MODEL = "opus46"
DEFAULT_TOKEN = 8192
DEFAULT_LLM_TEMPERATURE = 0.1


# ------------------------------------------------------------------
# Validation models
# ------------------------------------------------------------------

class ValidationIssue(BaseModel):
    filename: str
    severity: str                   # "error" | "warning"
    message: str
    suggestion: str


class ValidationReport(BaseModel):
    project_id: str
    total_sections: int
    valid_sections: int
    issues: list[ValidationIssue]
    is_valid: bool


# ------------------------------------------------------------------
# Top-level result
# ------------------------------------------------------------------

class Phase3Result(BaseModel):
    document_tree: list[DocumentTreeNode]
    table_of_contents: list[dict]     # {"filename", "title", "section_number", "level"}
    fields: FieldsList
    dependency_dag: dict[str, list[str]]   # section -> list of upstream sections
    styling_rules: dict[str, list[dict]]    # grouped by filename: {"FileName.md": [rule_dict, ...]}
    output_file: str = ""             # Path to the saved JSON file


class TemplateAnalysisAgent:
    """Analyzes a user-uploaded template document before content generation."""
    def __init__(self, project_id: str, session_id: str = ""):
        self.project_id = project_id
        self.session_id = session_id
        self.project_template_dir = get_project_template_dir(project_id)
        self.source_template_dir = get_source_template_dir()
        self.prompt_engine = PromptEngine()
        self.context_buffer_data = ""
        self._section_content_cache: dict[str, str] = {}

    # =========================================================================
    # Public entry point
    # =========================================================================

    async def run(self) -> Phase3Result:
        """Run all 5 sub-phases in sequence and return Phase3Result.

        Reports progress to session if session_id is provided.
        """
        from AgentCore.execution.session_manager import SessionLifecycle

        sess_id = self.session_id
        # --- Phase 3.2: Identify Sections (TOC) ---
        toc_entries = await self._phase3_2_identify_sections()
        if toc_entries:
            if sess_id:
                SessionLifecycle.update_progress( project_id=self.project_id,
                    session_id=sess_id, progress=10, current_phase="Identifying sections"
                )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="3.2 Identify Sections", status="ok")

        if not toc_entries:
            log.warning("[Phase3] No template sections found — returning empty result")
            result = Phase3Result(
                document_tree=[], table_of_contents=[],
                fields=FieldsList(fields_by_file={}),
                dependency_dag={}, styling_rules={},
            )
        else:
            # --- Phase 3.1: Parse Template ---
            doc_tree = await self._phase3_1_parse_template(toc_entries)
            if sess_id:
                SessionLifecycle.update_progress(project_id=self.project_id,
                    session_id=sess_id, progress=20, current_phase="Parsing template tree"
                )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="3.1 Parse Template", status="ok")

            # --- Phase 3.3: Identify Required Fields ---
            fields_list = await self._phase3_3_identify_fields(toc_entries)

            # Report per-file progress for field detection
            if sess_id and toc_entries:
                for i, entry in enumerate(toc_entries, start=1):
                    pct = 20 + int((i / len(toc_entries)) * 40)  # 20-60%
                    SessionLifecycle.update_progress(
                        project_id=self.project_id,
                        session_id=sess_id,
                        progress=pct,
                        current_phase=f"Identifying fields in {entry['filename']} ({i}/{len(toc_entries)})",
                    )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="3.3 Identify Fields", status="ok")

            # --- Phase 3.4: Build Dependency DAG ---
            dag = await self._phase3_4_build_dependency_dag(toc_entries)
            if sess_id:
                SessionLifecycle.update_progress(
                    project_id=self.project_id, session_id=sess_id, progress=60, current_phase="Building dependency graph"
                )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="3.4 Build Dependency DAG", status="ok")

            # --- Phase 3.5: Determine Output Types ---
            styling = await self._phase3_5_determine_output_types(toc_entries)

            # Report per-file progress for styling detection
            if sess_id and toc_entries:
                for i, entry in enumerate(toc_entries, start=1):
                    pct = 60 + int((i / len(toc_entries)) * 20)  # 60-80%
                    SessionLifecycle.update_progress(
                        project_id=self.project_id,
                        session_id=sess_id,
                        progress=pct,
                        current_phase=f"Determining output type for {entry['filename']} ({i}/{len(toc_entries)})",
                    )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="3.5 Determine Output Types", status="ok")
            result = Phase3Result(
                document_tree=doc_tree,
                table_of_contents=toc_entries,
                fields=fields_list,
                dependency_dag=dag,
                styling_rules=styling,
            )

        # Persist to JSON file
        if sess_id:
            SessionLifecycle.update_progress(
                project_id=self.project_id, session_id=sess_id, progress=90, current_phase="Saving analysis results"
            )
        output_file = self._save_phase3_result(result)
        result.output_file = output_file

        if sess_id:
            SessionLifecycle.update_progress(
                project_id=self.project_id,
                session_id=sess_id, progress=100, status="complete",
                current_phase=f"Phase 3 complete — {len(result.table_of_contents)} sections analyzed",
            )
            SessionLifecycle.log_stage_complete(project_id=self.project_id, session_id=sess_id, stage="Phase 3 Complete", status="ok")

        return result

    # =========================================================================
    # LLM call wrapper — uses llm_api_handler.llm_request for all LLM calls
    # =========================================================================

    async def _llm_call(
        self,
        system_prompt_name: str,
        user_content: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_TOKEN,
        temperature: float = DEFAULT_LLM_TEMPERATURE,
    ) -> Optional[str]:
        """Single-shot LLM call via llm_api_handler with retry, backoff, and model fallback.

        Mirrors the pattern in MemoryManagementAgent: resolves the model name,
        passes a system prompt and user message, and lets the SDK handle
        retries (exponential backoff on 429/5xx, empty-content detection,
        auto JSON correction, and fallback chains).
        """
        result = await llm_request(
            model=model,
            system_prompt=self.prompt_engine.render(system_prompt_name),
            messages=[{"role": "user", "content": user_content}],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=DEFAULT_TIMEOUT,
            fallback_chain=[DEFAULT_MODEL],
            response_format="json"
        )
        return result

    # =========================================================================
    # Helpers
    # =========================================================================
    # SAVE RESULT
    def _save_phase3_result(self, result: Phase3Result) -> str:
        """Persist Phase3Result to a JSON file and return the file path."""
        from system_config import get_project_phase3_dir
        details_dir = get_project_phase3_dir(self.project_id)
        filepath = details_dir / f"phase3_{self.project_id}.json"
        filepath.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
        return str(filepath)

    # READ CONTENT OF THE FILE
    def _read_file_content(self, filename: str) -> str:
        """Read a template file, with caching."""
        if filename not in self._section_content_cache:
            fpath = self.project_template_dir / filename
            if fpath.exists():
                self._section_content_cache[filename] = fpath.read_text(encoding="utf-8")
        return self._section_content_cache.get(filename, "")

    # BUILD TEMPLATE CONTENT
    def _build_template_context(self, toc_entries: list[dict]) -> str:
        """Build combined context string of all template files for 3.1."""
        parts = []
        for entry in toc_entries:
            content = self._read_file_content(entry["filename"])
            parts.append(f"=== FILE: {entry['filename']} (Section {entry['section_number']}) ===\n\n{content}")
        return "\n\n".join(parts)

    # BUILD SECTION CONTEXT
    def _build_sections_context(self, md_files: list[Path]) -> str:
        """Build context string for section identification (3.2)."""
        parts = []
        for file_data_item in md_files:
            preview = file_data_item.read_text(encoding="utf-8")
            parts.append(f"=== FILE: {file_data_item.name} ===\n\n{preview}")
        return "\n\n".join(parts)

    def _build_dag_context(self, toc_entries: list[dict]) -> str:
        """Build context string for dependency DAG (3.4)."""
        parts = [f"Template sections:\n"]
        for entry in toc_entries:
            parts.append(f"  Section {entry['section_number']}: {entry['filename']} ({entry['title']})")
        return "\n".join(parts)

    # =========================================================================
    # Sub-phase 3.2: Identify Sections → Table of Contents
    # (Needed first — all other sub-phases depend on section list)
    # =========================================================================

    async def _phase3_2_identify_sections(self) -> list[dict]:
        """Find all headers, chapters, appendices -> Table of Contents.

        Priority: LLM enrichment > filename regex heuristic fallback.
        """
        md_files = sorted(
            [file_data_item for file_data_item in self.project_template_dir.iterdir()
             if file_data_item.is_file() and file_data_item.suffix.lower() == ".md"],
            key=lambda file_data_item: file_data_item.name,
        )
        if not md_files:
            return []

        self.context_buffer_data = self._build_sections_context(md_files)

        # LLM call
        result = await self._llm_call(
            system_prompt_name="section_identification",
            user_content=self.context_buffer_data,
        )
        if result:
            try:
                parsed = json.loads(result)
                entries = parsed if isinstance(parsed, list) else parsed.get("sections", [])
                valid_entries = [entry_data for entry_data in entries if isinstance(entry_data, dict)]
                if valid_entries:
                    return valid_entries
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.2] LLM JSON parse failed, using fallback")

        # default_fallback: regex filename parser
        return self._phase3_2_default_fallback(md_files)

    def _phase3_2_default_fallback(self, md_files: list[Path]) -> list[dict]:
        """Regex filename parser — NN_name.md -> section_number, title, level."""
        entries = []
        for f in md_files:
            m = re.match(r"^(\d{2})_(.+)\.md$", f.name)
            section_num = int(m.group(1)) if m else 0
            title_raw = f.stem.replace("_", " ").title()
            content = f.read_text(encoding="utf-8")
            first_h = re.search(r'^(#{1,6})\s', content, re.MULTILINE)
            level = len(first_h.group(1)) if first_h else 2
            entries.append({
                "filename": f.name,
                "title": title_raw,
                "section_number": section_num,
                "level": level,
            })
        return sorted(entries, key=lambda e: (e["section_number"], e["filename"]))

    # =========================================================================
    # Sub-phase 3.1: Parse Template -> Document Tree
    # =========================================================================

    async def _phase3_1_parse_template(self, toc_entries: list[dict]) -> list[DocumentTreeNode]:
        """Convert raw template files into nested DocumentTreeNode structure."""
        context = self._build_template_context(toc_entries)

        # LLM call
        result = await self._llm_call(
            system_prompt_name="document_tree_parsing",
            user_content=context,
        )
        if result:
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list):
                    return [DocumentTreeNode(**parsed_node_item) for parsed_node_item in parsed]
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.1] LLM JSON parse failed, using fallback")

        # default_fallback: regex-based heading parser
        return self._phase3_1_default_fallback(toc_entries)

    # FALLBACK PARSE TEMPLATE
    def _phase3_1_default_fallback(self, toc_entries: list[dict]) -> list[DocumentTreeNode]:
        """Regex-based heading parser — no LLM needed."""
        tree = []
        for entry in toc_entries:
            content = self._read_file_content(entry["filename"])
            headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
            subsections = []
            for level_str, heading_text in headings:
                level = len(level_str)
                heading_text = re.sub(r'[*_`]', '', heading_text).strip()
                subsections.append(DocumentTreeNode(
                    heading=heading_text,
                    level=level,
                    filename=entry["filename"],
                    section_number=entry["section_number"],
                ))
            tree.append(DocumentTreeNode(
                heading=entry["title"],
                level=1,
                filename=entry["filename"],
                subsections=subsections,
                section_number=entry["section_number"],
            ))
        return tree

    # =========================================================================
    # Sub-phase 3.3: Identify Required Fields
    # =========================================================================

    async def _phase3_3_identify_fields(self, toc_entries: list[dict]) -> FieldsList:
        """Find all {{PLACEHOLDERS}}, blank tables, and inferred fields.

        Returns fields grouped by filename: {filename: [field_dict, ...]}
        """
        fields_by_file: dict[str, list[dict]] = {}

        for entry in toc_entries:
            filename = entry["filename"]
            content = self._read_file_content(filename)
            section_title = entry["title"]

            file_fields: list[dict] = []

            # Pass 1: LLM for explicit placeholders {{...}} and <...>
            explicit = await self._extract_explicit_placeholders_as_dicts(content, filename, section_title)
            file_fields.extend(explicit)

            # Pass 2: vague template -> LLM inference when no explicit placeholders found
            if not explicit:
                inferred = await self._execute_identify_fields_as_dicts(content, filename, section_title)
                file_fields.extend(inferred)

            # Pass 3: detect blank tables
            blank_tables = await self._detect_blank_tables_as_dicts(content, filename, section_title)
            file_fields.extend(blank_tables)

            # Deduplicate by field name — keep first occurrence
            seen: set[str] = set()
            deduped: list[dict] = []
            for f in file_fields:
                name = f.get("name", "")
                if name not in seen:
                    seen.add(name)
                    deduped.append(f)
            file_fields = deduped

            if file_fields:
                fields_by_file[filename] = file_fields

        return FieldsList(fields_by_file=fields_by_file)

    async def _extract_explicit_placeholders_as_dicts(self, content: str, filename: str, title: str) -> list[dict]:
        """Extract placeholders using LLM/regex, return dict list."""
        return await self._extract_explicit_placeholders(content, filename, title)

    async def _execute_identify_fields_as_dicts(self, content: str, filename: str, title: str) -> list[dict]:
        """Infer fields using LLM/regex, return dict list."""
        return await self._execute_identify_fields(content, filename, title)

    async def _detect_blank_tables_as_dicts(self, content: str, filename: str, title: str) -> list[dict]:
        """Detect blank tables using LLM/regex, return dict list."""
        return await self._detect_blank_tables(content, filename, title)

    # EXTRACT PLACEHOLDER DATA ITEM
    async def _extract_explicit_placeholders(self, content: str, filename: str, title: str) -> list[dict]:
        """Extract {{PLACEHOLDER}} and <...> markers using LLM, with regex fallback."""
        result = await self._llm_call(
            system_prompt_name="explicit_placeholder_extraction",
            user_content=f"Section: {title}\nFile: {filename}\n\nContent:\n{content}",
        )
        if result:
            try:
                parsed = json.loads(result)
                fields_data = parsed if isinstance(parsed, list) else parsed.get("fields", [])
                if fields_data:
                    return [dict(
                        name=field_data_item["name"],
                        location=field_data_item.get("location", filename),
                        field_type="placeholder",
                        placeholder_value=field_data_item["name"],
                        inferred_from=None,
                    ) for field_data_item in fields_data]
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.3] LLM placeholder extraction JSON parse failed, using fallback")

        # default_fallback: regex-based extraction
        return self._extract_explicit_placeholders_regex(content, filename, title)

    # FALLBACK EXTRACT PLACEHOLDER DATA ITEM
    def _extract_explicit_placeholders_regex(self, content: str, filename: str, title: str) -> list[Field]:
        """Regex fallback for extracting {{PLACEHOLDER}} and <...> markers."""
        fields = []
        location = f"{filename}"
        for pattern in [r'\{\{([^}]+)\}\}', r'<([^>]+)>']:
            for m in re.finditer(pattern, content):
                val = m.group(1).strip()
                if val and val not in ("N.A", "NA", "n.a"):
                    fields.append(dict(
                        name=val,
                        location=location,
                        field_type="placeholder",
                        placeholder_value=val,
                        inferred_from=None,
                    ))
        return fields
    
    # EXECUTE IDENTIFY FIELDS
    async def _execute_identify_fields(self, content: str, filename: str, title: str) -> list[dict]:
        """LLM inference for sections with no explicit {{...}} placeholders."""
        result = await self._llm_call(
            system_prompt_name="semantic_field_inference",
            user_content=f"Section: {title}\nFile: {filename}\n\nContent:\n{content}",
        )
        if result:
            try:
                parsed = json.loads(result)
                field_names = parsed if isinstance(parsed, list) else parsed.get("fields", [])
                if field_names:
                    return [dict(
                        name=str(n),
                        location=f"{filename} -> {title}",
                        field_type="inferred",
                        placeholder_value=None,
                        inferred_from=title,
                    ) for n in field_names]
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.3] LLM inference JSON parse failed, using fallback")

        # default_fallback: extract sub-headers as fields
        return self._phase3_3_default_fallback(content, filename, title)
    
    # DETECT BLANK TABLES
    async def _detect_blank_tables(self, content: str, filename: str, title: str) -> list[dict]:
        """Detect empty table rows using LLM, with regex fallback."""
        result = await self._llm_call(
            system_prompt_name="blank_table_detection",
            user_content=f"Section: {title}\nFile: {filename}\n\nContent:\n{content}",
        )
        if result:
            try:
                parsed = json.loads(result)
                fields_data = parsed if isinstance(parsed, list) else parsed.get("fields", [])
                if fields_data:
                    return [dict(
                        name=field_data_item["name"],
                        location=field_data_item.get("location", f"{filename} -> table"),
                        field_type="blank_table",
                        placeholder_value=None,
                        inferred_from=None,
                    ) for field_data_item in fields_data]
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.3] LLM blank table JSON parse failed, using fallback")

        # default_fallback: regex-based detection
        return self._detect_blank_tables_regex(content, filename, title)

    # FALLBACK DETECT BLANK TABLES
    def _detect_blank_tables_regex(self, content: str, filename: str, title: str) -> list[dict]:
        """Regex fallback for detecting empty table rows."""
        fields = []
        lines = content.split("\n")
        in_table = False
        expected_cols = 0

        for i, line in enumerate(lines):
            if re.match(r'^\|.*\|$', line):
                if not in_table:
                    expected_cols = len(line.split("|")) - 2
                    in_table = True
                elif "----" in line or "---" in line:
                    pass  # separator row
                else:
                    actual_cols = len(line.split("|")) - 2
                    if actual_cols == expected_cols:
                        cells = [c.strip() for c in line.split("|")[1:-1]]
                        if all(c == "" for c in cells):
                            fields.append(dict(
                                name=f"blank_table_row_{i+1}",
                                location=f"{filename} -> table row {i+1}",
                                field_type="blank_table",
                                placeholder_value=None,
                                inferred_from=None,
                            ))
            else:
                in_table = False

        return fields
    
    # FLALBACK IDENTIFY FIELDS
    def _phase3_3_default_fallback(self, content: str, filename: str, title: str) -> list[dict]:
            """Fallback: extract H2+ sub-headers as inferred fields."""
            fields = []
            for m in re.finditer(r'^(#{2,6})\s+(.+)$', content, re.MULTILINE):
                name = re.sub(r'[*_`]', '', m.group(2)).strip()
                if name:
                    fields.append(dict(
                        name=name,
                        location=f"{filename} -> header",
                        field_type="inferred",
                        placeholder_value=None,
                        inferred_from=title,
                    ))
            return fields

    # =========================================================================
    # Sub-phase 3.4: Build Dependency DAG
    # =========================================================================

    async def _phase3_4_build_dependency_dag(self, toc_entries: list[dict]) -> dict[str, list[str]]:
        """Determine which sections must be generated before others."""
        context = self._build_dag_context(toc_entries)

        # LLM call for cross-section dependency refinement
        result = await self._llm_call(
            system_prompt_name="dependency_dag_builder",
            user_content=context,
        )
        if result:
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    # LLM may wrap the DAG under a "refined_dependencies" key
                    dag_data: dict[str, list[str]] = parsed.get(
                        "refined_dependencies", parsed
                    )
                    if isinstance(dag_data, dict):
                        return dag_data
            except (json.JSONDecodeError, ValueError):
                log.warning("[Phase 3.4] LLM JSON parse failed, using fallback")

        # default_fallback: numeric ordering
        return self._phase3_4_default_fallback(toc_entries)

    # FALLBACK BUILD DEPENDENCY GRAPH
    def _phase3_4_default_fallback(self, toc_entries: list[dict]) -> dict[str, list[str]]:
        """Numeric ordering: section N depends on all sections M where M < N."""
        entries = sorted(toc_entries, key=lambda e: e["section_number"])
        dag: dict[str, list[str]] = {}
        for entry in entries:
            deps = [e["filename"] for e in entries
                    if e["section_number"] < entry["section_number"]]
            if deps:
                dag[entry["filename"]] = deps
        return dag

    # =========================================================================
    # Sub-phase 3.5: Determine Output Types
    # =========================================================================
    async def _phase3_5_determine_output_types(self, toc_entries: list[dict]) -> dict[str, list[dict]]:
        """Determine output format per subsection, grouped by filename.

        Returns {"FileName.md": [rule_dict, ...]} — same structure as fields_by_file.
        """
        rules_by_file: dict[str, list[dict]] = {}

        for entry in toc_entries:
            filename = entry["filename"]
            content = self._read_file_content(filename)
            file_rules: list[dict] = []

            # LLM call for per-subsection analysis
            result = await self._llm_call(
                system_prompt_name="styling_rules_determiner",
                user_content=(
                    f"File: {filename} (Section {entry['section_number']})\n"
                    f"Title: {entry['title']}\n\nContent:\n{content}"
                ),
            )
            if result:
                try:
                    parsed = json.loads(result)
                    rules_data = parsed if isinstance(parsed, list) else parsed.get("styling_rules", [])
                    if rules_data:
                        file_rules.extend(rules_data)
                        if file_rules:
                            rules_by_file[filename] = file_rules
                        continue
                except (json.JSONDecodeError, ValueError):
                    log.warning("[Phase 3.5] LLM JSON parse failed, using fallback")

            # default_fallback — heuristic per-subsection
            fallback_rules = self._phase3_5_heuristic_fallback(filename, content, entry["title"])
            if fallback_rules:
                file_rules.extend(fallback_rules)
                rules_by_file[filename] = file_rules

        return rules_by_file

    # FALLBACK BUILD OUTPUT TYPES
    def _phase3_5_heuristic_fallback(self, filename: str, content: str, title: str) -> list[dict]:
        """Regex-based per-subsection heuristic fallback."""
        rules: list[dict] = []

        # Split content by ## headings
        subsection_pattern = re.compile(r'^##\s+(.+)$', re.MULTILINE)
        subsections = list(subsection_pattern.finditer(content))

        if not subsections:
            # No ## headings — treat whole file as one subsection
            rules.append(self._heuristic_rule_for_text(content, filename, title))
        else:
            for idx, match in enumerate(subsections):
                subsection_name = re.sub(r'[*_`]', '', match.group(1)).strip()
                start = match.end()
                end = subsections[idx + 1].start() if idx + 1 < len(subsections) else len(content)
                subsection_content = content[start:end]

                rules.append(self._heuristic_rule_for_text(subsection_content, filename, subsection_name))

        return rules

    # DETERMINE OUTPUT TYPE FALLBACK
    def _heuristic_rule_for_text(self, text: str, filename: str, section_name: str) -> dict:
        """Compute a single StylingRule from raw text using regex heuristics."""
        table_count = len(re.findall(r'^\|.*\|$', text, re.MULTILINE)) // 3
        has_diagrams = bool(re.search(r'(?:mermaid|block.?diagram|figure)', text, re.IGNORECASE))
        has_lists = bool(re.search(r'^\s*[-*]\s', text, re.MULTILINE))
        has_paragraphs = bool(re.sub(r'^[#*\|`>\-\s]+$', '', text, flags=re.MULTILINE).strip())

        types = []
        if has_paragraphs:
            types.append("paragraphs")
        if table_count > 0:
            types.append("tables")
        if has_lists:
            types.append("lists")
        if has_diagrams:
            types.append("diagrams")

        if len(types) > 1:
            output_type = "mixed"
        elif types:
            output_type = types[0].rstrip("s")
        else:
            output_type = "paragraph"

        return {
            "section": filename,
            "subsection": section_name,
            "output_type": output_type,
            "needs_tables": table_count > 0,
            "needs_paragraphs": has_paragraphs,
            "needs_diagrams": has_diagrams,
            "table_count": table_count,
        }
