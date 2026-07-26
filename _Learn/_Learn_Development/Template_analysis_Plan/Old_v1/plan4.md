# Plan: Template Parsing Routes + TemplateAnalysisAgent

## Context

The `template_parsing_routes.py` file exists but is empty. It needs:
1. A new **TemplateAnalysisAgent** — the central orchestration agent that analyzes templates, builds generation plans, detects gaps, manages dependencies, and validates document completeness. It does NOT write content itself.
2. **7 API endpoints** for the frontend to browse, view, edit, create, and generate template sections.

Projects store templates at `output/templates/{project_id}/Topic_Template/`, synced from shared source at `Document_Section/SRS_Section/Topic_Template/`.

## Files to Create/Modify

1. **`/backend/Memory_Management/document_architect_agent.py`** — NEW: TemplateAnalysisAgent class
2. **`/backend/Routes/template_parsing_routes.py`** — Create full route file (currently empty)
3. **`/backend/main.py`** — Add import and `include_router` call

---

## Part 1: TemplateAnalysisAgent

**Location:** `/backend/Memory_Management/document_architect_agent.py`

### Responsibility Summary
The architect is a **planning/analysis-only agent**. It produces JSON plans. It does NOT write sections, retrieve memory directly, or generate content.

### Responsibility Summary
A **post-generation validator** — runs AFTER ContentKnowledgeAgent generates a section.
Combines **structural checks** (rule-based, ~100% accurate) + **semantic checks** (LLM-based, ~85-90% accurate).

### Two-Phase Validation Flow
```
1. Structural check (rule-based, fast)
   ├── Headings match template structure
   ├── No empty sections
   ├── All <PLACEHOLDER> resolved
   ├── Tables/lists formatted correctly
   └── → Pass or Fail

2. Semantic check (LLM-based, only if structural passes)
   ├── Read generated content + relevant memory files
   ├── Check: accuracy against source memory (no hallucination)
   ├── Check: correct requirement references
   └── → Pass or Fail with specific issues
```

### Core Methods

| Method | Returns | Purpose |
|--------|---------|---------|
| `analyze_template_structure()` | `DocumentStructure` | Parse template files, identify sections, extract placeholders, build hierarchy |
| `build_section_map()` | `SectionMap` | For each section: purpose, output_type, required data from memory, dependencies |
| `build_dependency_graph()` | `DependencyGraph` | Section ordering based on content dependencies |
| `plan_retrieval(section)` | `RetrievalPlan` | Which memory files to load for a given section (avoids loading everything) |
| `analyze_gaps(project_id, section)` | `GapAnalysis` | Compare what's in the template vs. what's in memory/requirements |
| `generate_questions(gaps)` | `QuestionPlan` | Convert missing info into precise questions for the user |
| `select_generation_strategy(section, purpose, output_type)` | `GenerationStrategy` | Decide how to generate a section (agent, model, format) |
| `validate_document(project_id)` | `ValidationReport` | Check completeness, unresolved placeholders, conflicts, dependency satisfaction |
| `build_traceability_map(project_id)` | `TraceabilityMap` | Track source of every statement |
| `build_assembly_plan(project_id)` | `AssemblyPlan` | Final document order for combining sections |
| `execute_generation_plan(project_id, section)` | `dict` | Execute the plan by coordinating ContentKnowledgeAgent for writing |

| Method | Returns | Purpose |
|--------|---------|---------|
| `validate_structure(section, filename)` | `ValidationResult` | Rule-based: headings, placeholders, tables, emptiness |
| `validate_semantics(section, filename, req_ids)` | `ValidationResult` | LLM-based: reads content + memory, checks accuracy |
| `validate_section(section, filename, req_ids)` | `ValidationResult` | Runs structural → semantic (only if structural passes) |
| `validate_document()` | `ValidationReport` | Runs all sections, aggregates results |

### Data Models (Pydantic)

```python
class SectionInfo(BaseModel):
    name: str              # "Introduction"
    filename: str          # "01_introduction.md"
    section_number: int    # 1
    purpose: str           # "Provide overview and context"
    output_type: str       # "text_with_tables"
    placeholders: list[str] # ["<PROJECT NAME>", "<VERSION NO>"]
    required_data: list[str] # ["project_overview", "scope_summary"]
    dependencies: list[str] # []

class DocumentStructure(BaseModel):
    project_id: str
    sections: list[SectionInfo]
    section_order: list[str]

class SectionMap(BaseModel):
    sections: dict[str, SectionInfo]

class DependencyGraph(BaseModel):
    graph: dict[str, list[str]]  # section -> [sections it depends on]

class RetrievalPlan(BaseModel):
    section: str
    memory_files: list[str]      # which .md files in knowledge/ to load
    requirement_ids: list[str]   # which requirements to reference

class Gap(BaseModel):
    section: str
    missing_data: list[str]
    severity: str  # "critical" | "warning" | "info"

class GapAnalysis(BaseModel):
    gaps: list[Gap]
    is_complete: bool

class Question(BaseModel):
    section: str
    question: str
    expected_source: str  # "user_input" | "memory" | "requirements"
    priority: str  # "high" | "medium" | "low"

class QuestionPlan(BaseModel):
    questions: list[Question]

class GenerationStrategy(BaseModel):
    section: str
    generator: str       # "content_knowledge_agent" | "manual" | "llm_fill_placeholders"
    model: str           # "opus46" (always)
    format: str          # "markdown" | "tables" | "requirements_list"
    dependencies: list[str]

class ValidationReport(BaseModel):
    is_valid: bool
    checks: dict[str, bool]  # section -> passed/not_passed
    issues: list[str]
    unresolved_placeholders: list[str]
    conflicts: list[str]

class TraceabilityEntry(BaseModel):
    section: str
    statement_index: int
    source_type: str   # "memory" | "requirement" | "user_input" | "template"
    source_ref: str    # file path or requirement ID

class AssemblyPlan(BaseModel):
    section_order: list[str]
    merge_strategy: str  # "sequential" | "parallel"

class ExecutionPlan(BaseModel):
    structure: DocumentStructure
    dependency_graph: DependencyGraph
    retrieval_plans: dict[str, RetrievalPlan]
    gap_analysis: GapAnalysis
    question_plan: QuestionPlan
    generation_strategies: dict[str, GenerationStrategy]
    validation_plan: ValidationReport
    assembly_plan: AssemblyPlan
    traceability_map: TraceabilityMap
```

### Key Implementation Details

- **Template parsing**: Reads `.md` files, extracts `<PLACEHOLDER>` patterns via regex, parses headings to determine section purpose
- **Purpose classification**: Uses a small prompt-based classification (via `llm_request`) or a hardcoded mapping for SRS sections
- **Memory planning**: Reads from `output/memory/{project_id}/knowledge/` directory, determines which knowledge files are relevant
- **Dependency rules**: Hardcoded for SRS sections (e.g., `02_overall` depends on `01_introduction`, `04_functional` depends on `01_introduction` + `02_overall`, etc.)
- **Validation**: Checks for empty sections, unresolved `<...>` placeholders, inconsistent section counts
- **LLM calls**: Only uses `llm_request` for classification and gap analysis questions — structural parsing is rule-based

---

## Part 1.5: DocumentValidatorAgent

**Location:** `/backend/Memory_Management/document_validator_agent.py`

### Responsibility Summary
A **post-generation validator** — runs AFTER ContentKnowledgeAgent generates a section.
Combines **structural checks** (rule-based, ~100% accurate) + **semantic checks** (LLM-based, ~85-90% accurate).

### Two-Phase Validation Flow
```
1. Structural check (rule-based, fast)
   ├── Headings match template structure
   ├── No empty sections
   ├── All <PLACEHOLDER> resolved
   ├── Tables/lists formatted correctly
   └── → Pass or Fail

2. Semantic check (LLM-based, only if structural passes)
   ├── Read generated content + relevant memory files
   ├── Check: accuracy against source memory (no hallucination)
   ├── Check: correct requirement references
   └── → Pass or Fail with specific issues
```

### LLM Call
- **Model:** `opus46`, **Max tokens:** 2048, **Temperature:** 0.1
- **Only calls LLM for sections that pass structural checks**
- **Prompt:** Shows generated section + relevant memory snippets + template expectations
- **Returns JSON:** structural_passed, semantic_passed, issues list, suggestions

---

## Part 2: Template Parsing Routes

### Endpoints

#### 1. GET `/template-sections/{project_id}` — List sections
- Lists all `.md` files in the project's Topic_Template directory
- Auto-syncs from shared source if project directory is empty/missing
- Returns metadata: filename, path, section_number, title, is_generated
- Returns sorted list by section number

#### 2. GET `/template-section/{project_id}/{filename:path}` — View file
- Returns `{filename, path, content}` for the specified markdown file
- Path traversal protection (403), file-not-found (404), dir check (404), extension check (404)

#### 3. PUT/POST `/template-section/{project_id}/{filename:path}` — Update file
- Accepts `{"content": "..."}` in request body
- Writes content to the project-specific file
- Same path validation as GET

#### 4. DELETE `/template-section/{project_id}/{filename:path}` — Delete file
- Deletes only from the project-specific directory (never from shared source)
- Path traversal protection, not-found handling

#### 5. POST `/template-section/{project_id}/generate` — LLM-generate section(s)
- Accepts `{"filename": "01_introduction.md"|null, "requirement_ids": [...]}`
- If `filename` is null, generates all sections (respecting dependency order)
- If `requirement_ids` is empty, loads all from `requirements.json`
- **Uses TemplateAnalysisAgent to build an ExecutionPlan first**, then executes
- **After each section generation, DocumentValidatorAgent validates** (structural → semantic)
- **On validation failure: auto-regenerate up to 2 times** per section before marking as failed
- Runs as a background async task with progress tracking
- Progress stored in `template_progress_store`

#### 6. POST `/template-section/{project_id}/create` — Create new file
- Accepts `{"filename": "my_new_section"}`
- Auto-assigns next available section number (01_, 02_, etc.)
- Creates file with a basic heading placeholder
- Collision handling: appends `_1`, `_2`, etc.

#### 7. GET `/template-progress/{project_id}` — Progress polling
- Returns progress store entry for the project's generation task
- States: idle, running, complete, error

#### 8. GET `/template-architecture/{project_id}` — Analyze document structure
- **New endpoint**: Runs TemplateAnalysisAgent to analyze the document
- Returns: DocumentStructure, dependency graph, gaps, questions
- Pure analysis — no writing, just planning

#### 9. GET `/template-gaps/{project_id}` — Gap analysis
- **New endpoint**: Returns GapAnalysis for the entire document
- Lists missing data, severity, and generates questions

#### 10. POST `/template-section/{project_id}/validate` — Validate document
- **New endpoint**: Runs DocumentValidatorAgent for full validation
- Two-phase: structural (rule-based) → semantic (LLM-based)
- Returns ValidationResult per section + ValidationReport aggregate

#### 11. POST `/template-section/{project_id}/execute-plan` — Execute generation plan
- **New endpoint**: Uses the TemplateAnalysisAgent's ExecutionPlan to orchestrate LLM generation
- Respects dependency order (generates Introduction before Functional Requirements)
- Builds traceability map as it goes

---

## Helper Functions (Route-level)

| Function | Purpose |
|----------|---------|
| `_sync_project_templates(project_id)` | Copy shared templates to project dir on first access |
| `_parse_section_metadata(filename)` | Parse `01_introduction.md` -> `(1, "Introduction")` |
| `_next_section_number(proj_dir)` | Scan for max section number, return next `NN_` |
| `_sanitize_filename(user_input)` | Strip path components, ensure `.md` extension |
| `_resolve_file_path(project_id, filename)` | Resolve + validate path with traversal protection |

---

## main.py Changes

```python
from Routes.template_parsing_routes import router as template_parsing_router
app.include_router(template_parsing_router, prefix="")
```

---

## Verification

1. Start server — no import errors
2. `GET /template-sections/{project_id}` for a new project — returns 10 standard files, copies them to `output/templates/{project_id}/Topic_Template/`
3. `GET /template-section/{project_id}/01_introduction.md` — returns full markdown content
4. `PUT /template-section/{project_id}/01_introduction.md` with new content — verify change persists
5. `POST /template-section/{project_id}/create` with `{"filename": "my_section"}` — returns `08_my_section.md`
6. `POST /template-section/{project_id}/generate` — poll progress idle->running->complete
7. `GET /template-architecture/{project_id}` — returns DocumentStructure with sections, placeholders, purpose classification
8. `GET /template-gaps/{project_id}` — returns GapAnalysis with missing data
9. `POST /template-section/{project_id}/validate` — returns ValidationReport
10. `GET /template-section/{project_id}/../../../etc/passwd` — returns HTTP 403
11. `DELETE /template-section/{project_id}/08_my_section.md` — succeeds, shared source untouched
