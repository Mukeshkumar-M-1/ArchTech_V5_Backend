# Template Analysis Agent — Documentation

## Overview

The Template Analysis module provides a **Phase 3: Template Understanding** system that scans, parses, and analyzes markdown template documents for a given project. It produces a structured blueprint that downstream generation stages use to understand document hierarchy, required fields, section dependencies, and output formatting rules.

---

## Project Structure

```
backend/Template_analysis/
  template_analysis_agent.py      # Core agent — Phase 3 analysis
  template_validator_agent.py     # Structural validation agent
  test_template_analysis_routes.py # Test suite (pytest)
  _01_SESSION_MANAGEMENT.md       # Session management docs
```

```
backend/Routes/
  template_analysis_routes.py     # FastAPI route handlers (10 endpoints)
```

---

## Files — Classes & Methods

### 1. `template_analysis_agent.py`

#### Pydantic Models

| Model | Fields | Purpose |
|---|---|---|
| `DocumentTreeNode` | `heading`, `level` (1-6), `filename`, `subsections[]`, `section_number` | Represents a single node in the nested document tree |
| `Field` | `name`, `location`, `field_type` ("placeholder" \| "inferred" \| "blank_table"), `placeholder_value`, `inferred_from` | A detected or inferred required field in a template |
| `FieldsList` | `fields[]` | Container for a list of `Field` objects |
| `StylingRule` | `section`, `output_type` ("paragraph" \| "table" \| "list" \| "diagram" \| "mixed"), `needs_tables`, `needs_paragraphs`, `needs_diagrams`, `table_count` | Describes the output format for a given template section |
| `ValidationIssue` | `filename`, `severity` ("error" \| "warning"), `message`, `suggestion` | A single validation problem found in a template section |
| `ValidationReport` | `project_id`, `total_sections`, `valid_sections`, `issues[]`, `is_valid` | Full validation report for a project |
| `Phase3Result` | `document_tree[]`, `table_of_contents[]`, `fields` (FieldsList), `dependency_dag`, `styling_rules[]` | The complete output of Phase 3 analysis |

#### Class: `TemplateAnalysisAgent`

**Constructor:** `__init__(self, project_id: str)`
- Sets up the project template directory, source template directory, prompt engine, and output directory.

**`async def run(self) -> Phase3Result`** *(Public Entry Point)*
- Executes all 5 sub-phases in sequence:
  1. **Phase 3.2** — Identify sections (TOC) — *runs first since all others depend on it*
  2. **Phase 3.1** — Parse template into nested document tree
  3. **Phase 3.3** — Identify fields (placeholders, inferred, blank tables)
  4. **Phase 3.4** — Build dependency DAG (section ordering)
  5. **Phase 3.5** — Determine output types (styling rules per section)

**`async def _llm_call(self, system_prompt_name, user_content, model, max_tokens, temperature) -> str | None`**
- Wrapper around `QueryLoop` for all LLM calls. Handles retry, model fallback chain (Opus46 → Sonnet46 → Haiku45), auto-compaction, and session memory.

**Sub-Phase Methods:**

| Method | Priority Logic | Input | Output |
|---|---|---|---|
| `_phase3_2_identify_sections()` | LLM (`section_identification` prompt) → regex filename parser fallback | None (scans directory) | `list[dict]` — each dict: `filename`, `title`, `section_number`, `level` |
| `_phase3_1_parse_template(toc_entries)` | LLM (`document_tree_parsing` prompt) → regex heading parser fallback | `list[dict]` from 3.2 | `list[DocumentTreeNode]` — nested tree |
| `_phase3_3_identify_fields(toc_entries)` | 3 passes per section (see below) | `list[dict]` from 3.2 | `FieldsList` |
| `_phase3_4_build_dependency_dag(toc_entries)` | LLM (`dependency_dag_builder` prompt) → numeric ordering fallback | `list[dict]` from 3.2 | `dict[str, list[str]]` — adjacency list |
| `_phase3_5_determine_output_types(toc_entries)` | Heuristic pre-scan → LLM (`styling_rules_determiner` prompt) → heuristic fallback | `list[dict]` from 3.2 | `list[StylingRule]` |

**3 Passes for `_phase3_3_identify_fields`:**

| Pass | Method | Logic | Returns |
|---|---|---|---|
| 1 | `_extract_explicit_placeholders()` | Regex finds `{{...}}` and `<...>` markers | `list[Field]` with `field_type="placeholder"` |
| 2 | `_execute_identify_fields()` | LLM call (`semantic_field_inference` prompt) for sections without explicit placeholders; falls back to regex H2+ sub-header extraction | `list[Field]` with `field_type="inferred"` |
| 3 | `_detect_blank_tables()` | Regex detects empty markdown table rows `|   |   |` | `list[Field]` with `field_type="blank_table"` |

---

### 2. `template_validator_agent.py`

#### Class: `TemplateValidatorAgent`

**Constructor:** `__init__(self, project_id: str)`
- Sets up the project template directory.

**`async def validate_document(self, target_sections: list[str] | None = None) -> dict`**
- Validates all `.md` files (or a specified subset).
- Runs 3 checks per file:
  1. `_check_empty_sections()` — checks if content is empty/nearly empty after stripping markdown
  2. `_check_broken_tables()` — checks for table rows with mismatched column counts
  3. `_check_orphaned_placeholders()` — checks for cross-file references pointing to non-existent files
- **Output:** `dict` (from `ValidationReport.model_dump()`) with keys: `project_id`, `total_sections`, `valid_sections`, `issues[]`, `is_valid`

**`async def validate_section(self, section_name: str, filename: str, req_ids: list[str] | None = None) -> dict`**
- Validates a single section by delegating to `validate_document(target_sections=[filename])`.
- **Output:** Same dict format as above.

---

### 3. `test_template_analysis_routes.py`

#### Test Classes

| Class | What It Tests |
|---|---|
| `TestModuleImports` | Verifies all imports resolve (router, route models, agent classes, Phase3 models) |
| `TestRouteRegistration` | Verifies 10 routes exist with correct HTTP methods/paths |
| `TestSyncProjectTemplates` | Tests `_sync_project_templates` copies source templates without overwriting |
| `TestGetTemplateSections` | Tests `GET /template-sections/{project_id}` |
| `TestGetTemplateSection` | Tests `GET /template-section/{project_id}/{filename:path}` |
| `TestUpdateTemplateFile` | Tests `PUT /template-section/{project_id}/{filename:path}` |
| `TestCreateTemplateFile` | Tests `POST /template-section/{project_id}/create` |
| `TestDeleteTemplateFile` | Tests `DELETE /template-section/{project_id}/{filename:path}` |
| `TestGetTemplateProgress` | Tests `GET /template-progress/{project_id}` |
| `TestValidateTemplateDocument` | Tests `POST /template-section/{project_id}/validate` |
| `TestGetPhase3Result` | Tests `GET /template-phase3/{project_id}` returns all expected keys |
| `TestGetPhase3Status` | Tests `GET /template-phase3-status/{project_id}` |
| `TestPhase3Integration` | End-to-end tests running `TemplateAnalysisAgent` directly with real template files |

---

### 4. `backend/Routes/template_analysis_routes.py`

#### Pydantic Models

| Model | Fields | Purpose |
|---|---|---|
| `UpdateFileRequest` | `content: str` | Body for updating a template file |
| `CreateFileRequest` | `filename: str` | Body for creating a new template file |
| `GenerateRequest` | `filename: str | None = None` | Body for generation endpoint |
| `ValidateRequest` | `sections: list[str] | None = None` | Body for validation endpoint |

#### Helper Functions

| Function | Description |
|---|---|
| `_sync_project_templates(project_id)` | Copies source templates to project directory if missing |
| `_parse_section_metadata(filename)` | Parses `NN_name.md` into `(section_number, title)` |
| `_next_section_number(proj_dir)` | Finds next available section number |
| `_sanitize_filename(user_input)` | Sanitizes user input, ensures `.md` extension |
| `_resolve_file_path(project_id, filename)` | Resolves path with directory traversal protection |

#### 10 Route Endpoints

| # | Method | Endpoint | Description |
|---|---|---|---|
| 1 | `GET` | `/template-sections/{project_id}` | Lists all template sections (calls sync, reads `.md` files, returns list with `filename`, `path`, `section_number`, `title`, `is_generated`) |
| 2 | `GET` | `/template-section/{project_id}/{filename:path}` | Gets content of a single template file |
| 3 | `DELETE` | `/template-section/{project_id}/{filename:path}` | Deletes a template file |
| 4 | `POST` | `/template-section/{project_id}/cancel` | Cancels running generation via `SessionLifecycle.cancel` |
| 5 | `POST` | `/template-section/{project_id}/generate` | Starts LLM generation (creates session, spawns background `asyncio.Task`) |
| 6 | `POST` | `/template-section/{project_id}/create` | Creates a new template file with auto-assigned section numbering |
| 7 | `GET` | `/template-progress/{project_id}` | Returns session progress via `SessionLifecycle.get_progress` |
| 8 | `POST` | `/template-section/{project_id}/validate` | Runs `TemplateValidatorAgent.validate_document()` |
| 9 | `GET` | `/template-phase3/{project_id}` | Runs `TemplateAnalysisAgent.run()` and returns `Phase3Result.model_dump()` |
| 10 | `GET` | `/template-phase3-status/{project_id}` | Checks if Phase 3 results exist by looking for `phase3_*.json` files |

---

## End-to-End Flow

```
User Request
    |
    v
FastAPI Routes (Routes/template_analysis_routes.py)
    |
    +--- [File Management] → GET/PUT/DELETE/POST sections
    |
    +--- [Generate] ────> TemplateAnalysisAgent.run()
    |                      Background asyncio.Task
    |
    +--- [Validate] ────> TemplateValidatorAgent.validate_document()
    |                      Checks: empty sections, broken tables, orphaned refs
    |
    +--- [Phase 3] ─────> TemplateAnalysisAgent.run()
    |                      3.2 Identify Sections (TOC)
    |                      3.1 Parse Template (Document Tree)
    |                      3.3 Identify Fields (3 passes)
    |                      3.4 Build Dependency DAG
    |                      3.5 Determine Output Types
    |
    +--- [Progress] ────> SessionLifecycle.get_progress()
```

---

## Phase 3 Analysis — What Each Sub-Phase Does

### Phase 3.2: Identify Sections (TOC)
Scans the project template directory for all `.md` files. Uses LLM to assign section numbers, titles, and hierarchy levels. Falls back to regex parsing of filenames like `01_introduction.md`.

### Phase 3.1: Parse Template (Document Tree)
Converts raw markdown template files into a **nested hierarchical tree** by extracting headings (`#` through `######`) and their relationships. Uses LLM for accurate hierarchy; falls back to regex heading extraction.

### Phase 3.3: Identify Fields
Scans every section for **required input fields** across 3 passes:
1. **Explicit placeholders** — finds `{{variable_name}}` and `<variable_name>` markers via regex
2. **Inferred fields** — LLM analyzes section content to deduce required fields (e.g., a section titled "Claimant Details" implies fields like `name`, `address`, `dob`). Falls back to extracting H2+ sub-headers
3. **Blank tables** — finds empty markdown table structures (`|   |   |`) that need to be populated

### Phase 3.4: Build Dependency DAG
Determines the **section generation order** by identifying which sections reference or depend on others. Uses LLM for semantic dependency detection. Falls back to numeric ordering (section N depends on all sections M where M < N).

### Phase 3.5: Determine Output Types
Analyzes each section to determine its **output format** (paragraph, table, list, diagram, or mixed). Uses heuristic pre-scan (regex-based detection of tables, diagram keywords like `mermaid`, list markers) refined by LLM.

---

## Phase 3 Output — `Phase3Result`

The final output of `TemplateAnalysisAgent.run()` is a `Phase3Result` object with these 5 fields:

```json
{
  "document_tree": [
    {
      "heading": "Introduction",
      "level": 1,
      "filename": "01_introduction.md",
      "subsections": [],
      "section_number": 1
    }
  ],
  "table_of_contents": [
    { "filename": "01_introduction.md", "title": "Introduction", "section_number": 1, "level": 1 }
  ],
  "fields": {
    "fields": [
      {
        "name": "claimant_name",
        "location": "02_claimant_details.md",
        "field_type": "placeholder",
        "placeholder_value": "{{claimant_name}}",
        "inferred_from": null
      }
    ]
  },
  "dependency_dag": {
    "02_claimant_details.md": ["01_introduction.md"],
    "03_background.md": ["02_claimant_details.md"]
  },
  "styling_rules": [
    {
      "section": "02_claimant_details.md",
      "output_type": "table",
      "needs_tables": true,
      "needs_paragraphs": false,
      "needs_diagrams": false,
      "table_count": 1
    }
  ]
}
```

---

## Validation Output — `ValidationReport`

The output of `TemplateValidatorAgent.validate_document()` is a `ValidationReport` object:

```json
{
  "project_id": "proj_123",
  "total_sections": 5,
  "valid_sections": 4,
  "issues": [
    {
      "filename": "02_claimant_details.md",
      "severity": "error",
      "message": "Section is empty after stripping markdown",
      "suggestion": "Populate the section template with required content"
    }
  ],
  "is_valid": false
}
```
