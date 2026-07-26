# Plan: Phase 3 — Template Understanding Implementation

## Context

The architecture document defines Phase 3 (Template Understanding) as a 5-sub-phase pipeline that must perfectly understand an empty template before generating content. Currently, the equivalent logic exists as Stages 1-3 inside `TemplateAnalysisAgent`, but it's tightly coupled to the full 11-stage `execute_generation_plan()` pipeline and lacks handling for the "Vague Template Problem" (sections with headers but no explicit placeholders).

The **Frontend** (`TemplatePanel.jsx`) already shows section list, content editor, generation console, and toolbar. It currently has NO UI for Phase 3-specific outputs (document tree, variables list, dependency DAG, styling rules). Phase 3 should be visible and inspectable before hitting "Generate."

**Goal:** Extract Phase 3 into a standalone, independently callable agent with a clean output format, fix the vague template gap, create missing infrastructure (`DocumentValidatorAgent`, new prompts), and wire a frontend "Analyze" flow.

---

## Current State Mapping

| Phase 3 Sub-Phase | Current Backend Code | Status |
|---|---|---|
| **3.1 Parse Template** | `analyze_template_structure()` reads .md files, extracts heading info | EXISTS but no nested document tree output |
| **3.2 Identify Sections** | Section discovery via filename prefix + LLM purpose extraction | EXISTS, functional |
| **3.3 Identify Required Fields** | LLM extracts `{{...}}`/`<...>` placeholders | EXISTS but NO semantic inferencing for vague templates |
| **3.4 Build Dependency Graph** | `build_dependency_graph()` with LLM + heuristic fallback | EXISTS, functional |
| **3.5 Determine Output Types** | `output_type` field (text/tables/diagrams/etc.) | EXISTS, functional |

### Frontend Understanding

- `TemplatePanel.jsx` — Main orchestrator: loads sections, selects files, triggers generation
- `SectionList.jsx` — Left panel: file list with MEM indicator (green=generated, red=not)
- `SectionToolbar.jsx` — Top bar: Generate, Cancel, Console toggle, New section buttons
- `SectionContent.jsx` — Right panel: TiptapEditor for editing markdown
- `ConsoleTab.jsx` — Bottom panel: Shows 11 stage progress, tool calls, token usage
- `GenerationPanel.jsx` — Separate panel for generated SRS doc output
- `templateApi.js` — API client: fetchSections, fetchSectionContent, generateSections, cancelGeneration, fetchArchitecture, fetchGaps, validateDocument, executePlan

**Gap:** No UI element for running Phase 3 independently or viewing its structured results (document tree, fields, DAG, styling rules) before generation.

---

## Implementation Steps

### Step 1: Add Phase 3 Pydantic Models

**File:** `backend/Template_analysis/template_analysis_agent.py` (append after line 145)

Add these models:

```python
class DocumentTreeNode(BaseModel):
    heading: str
    level: int
    filename: str
    subsections: list["DocumentTreeNode"] = []

class Field(BaseModel):
    name: str
    location: str
    field_type: str   # "placeholder" | "inferred" | "blank_table"
    placeholder_value: str | None
    inferred_from: str | None

class FieldsList(BaseModel):
    fields: list[Field]

class StylingRule(BaseModel):
    section: str
    output_type: str
    needs_tables: bool
    needs_paragraphs: bool
    needs_diagrams: bool
    table_count: int

class Phase3Result(BaseModel):
    document_tree: list[DocumentTreeNode]
    table_of_contents: list[dict]
    fields: FieldsList
    dependency_dag: dict[str, list[str]]
    styling_rules: list[StylingRule]
```

Call `Phase3Result.model_rebuild()` after definition.

### Step 2: Create `TemplateAnalysisAgent` (Standalone Phase 3)

**File:** `backend/Template_analysis/template_analyzer_agent.py` (NEW, ~250 lines)

```python
class TemplateAnalysisAgent:
    run(target_sections=None)        # Orchestrator: runs 3.1-3.5 sequentially
    _parse_template()                # 3.1: Parse raw templates -> DocumentTreeNode list
    _identify_sections()             # 3.2: Identify -> TableOfContents dict
    _identify_fields()               # 3.3: Identify -> FieldsList (with vague template fix)
    _build_dependency_dag()          # 3.4: Build -> DependencyDAG dict
    _determine_output_types()        # 3.5: Determine -> StylingRule list
    _infer_vague_template_fields()   # Key: if section has 0 explicit placeholders,
                                     # call LLM with section header + content to infer expected fields
```

Each sub-phase follows **LLM → self-correction → heuristic fallback**. Reuses `QueryLoop`, `PromptEngine`, `registry`, and the `_clean_and_parse_json()` / `_self_correct_json()` methods (via shared utility logic).

Infrastructure wiring (`_init_infrastructure`, `_make_loop_kwargs`) mirrors the existing `TemplateAnalysisAgent` at lines 211-243.

### Step 3: Create New Prompt Files

Two new system prompts:

**File:** `backend/prompts/System_Prompts/template_analysis_prompts/semantic_field_inference.txt`
- Instructs LLM: "This section has no explicit placeholders. Based on the header and content, what fields/data should this section contain?"
- Output: `{"fields": [{"name": "...", "expected_format": "text|table|list"}]}`

**File:** `backend/prompts/System_Prompts/template_analysis_prompts/document_tree_parsing.txt`
- Instructs LLM: "Parse the heading hierarchy (H1-H6) from all template files into a nested document tree."
- Output: array of `DocumentTreeNode` objects

### Step 4: Create `TemplateValidatorAgent`

**File:** `backend/Template_analysis/template_validator_agent.py` (NEW, ~80 lines)

Thin wrapper agent fixing the broken import at `template_analysis_routes.py:443`. Saved alongside `template_analysis_agent.py` in the same folder.

```python
class TemplateValidatorAgent:
    def __init__(self, project_id):
    async def validate_document(self, target_sections=None) -> ValidationReport
    async def validate_section(self, section_name, filename, req_ids) -> ValidationReport
```

Delegates to `TemplateAnalysisAgent.validate_document()` — no duplicated logic.

**Also:** Update `template_analysis_routes.py:443` import from `Memory_Management.document_validator_agent` → `Template_analysis.template_validator_agent`.

### Step 5: Backend — Clean Unused Routes + Add Phase 3 Endpoints

**File:** `backend/Routes/template_analysis_routes.py` (modify)

**Remove unused routes** (not called from frontend, dead code):
- `GET /template-architecture/{project_id}` → 0 frontend callers
- `GET /template-gaps/{project_id}` → 0 frontend callers
- `POST /template-section/{project_id}/validate` → 0 frontend callers (validateDocument API func exists but never called)
- `POST /template-section/{project_id}/execute-plan` → 0 frontend callers (executePlan API func exists but never called)
- `PUT /template-section/{project_id}/{filename}` → 0 frontend callers (saveSectionContent imported in TemplatePanel but SectionContent receives empty `onContentChange={() => {}}`)

**Add new routes:**
```python
@router.get("/template-phase3/{project_id}")
async def get_phase3_result(project_id):
    """Run Phase 3 independently. Returns structured template analysis."""
    from Template_analysis.template_analyzer_agent import TemplateAnalysisAgent
    analyzer = TemplateAnalysisAgent(project_id)
    return (await analyzer.run()).model_dump()

@router.get("/template-phase3-status/{project_id}")
def get_phase3_status(project_id):
    """Check if Phase 3 results exist for this project."""
```

### Step 6: Backend — Wire Phase 3 into Existing Pipeline

**File:** `backend/Template_analysis/template_analysis_agent.py` (modify `execute_generation_plan()`)

After Stage 3 completes (~line 1605), save consolidated Phase 3 output to `output/template_details/{project_id}/phase3_result.json`. This makes Phase 3 data persistently available even when running through the full 11-stage pipeline.

### Step 7: Frontend — Clean Unused API Functions + Add Phase 3

**File:** `Frontend/src/api/templateApi.js` (modify)

**Remove unused exports** (0 frontend callers):
- `saveSectionContent` — imported in TemplatePanel but SectionContent passes `onContentChange={() => {}}`
- `fetchArchitecture` — 0 callers
- `fetchGaps` — 0 callers
- `validateDocument` — 0 callers
- `executePlan` — 0 callers

**Add new function:**
```javascript
export async function fetchPhase3Analysis(projectId) {
  return request(`/template-phase3/${projectId}`);
}
```

### Step 8: Frontend — Phase 3 Analysis in Console Tab

**File:** `Frontend/src/views/SoftwareWorkspace/ConsoleTab.jsx` (modify)

Add a new "Analyze" tab to the existing 3-tab console (Activity, Tools, Tokens). This tab shows Phase 3 results:

- **Document Tree**: Hierarchical nested list of sections/headings with expand/collapse
- **Variables/Fields**: Table listing all detected placeholders (blue) and inferred fields (amber/orange, color-coded differently to highlight semantic inference)
- **Dependency DAG**: Simple visual flow showing section → depends-on relationships (text-based arrows)
- **Styling Rules**: Table showing section → output_type (text/tables/diagrams)

The tab only appears when Phase 3 analysis data is available in the console's state.

### Step 8b: Frontend — "Analyze" Button in TemplatePanel

**File:** `Frontend/src/views/SoftwareWorkspace/TemplatePanel.jsx` (modify)

Add an **"Analyze" button** to the `SectionToolbar` alongside Generate/Cancel. This triggers `fetchPhase3Analysis(project.id)` and populates the Phase 3 tab in the console. Also adds a `phase3Data` state to `TemplatePanel` that flows down to `ConsoleTab`.

### Step 9: Frontend — Show Phase 3 Status in SectionList

**File:** `Frontend/src/views/SoftwareWorkspace/SectionList.jsx` (modify)

Add a small indicator on sections with inferred fields (no explicit placeholders) to show they've been analyzed. This connects Phase 3 findings directly to the section list UI.

---

## File Change Summary

| File | Action | Lines |
|---|---|---|
| `backend/Template_analysis/template_analysis_agent.py` | MODIFY | +80 (new models) |
| `backend/Template_analysis/template_analyzer_agent.py` | **NEW** | ~250 |
| `backend/Template_analysis/template_validator_agent.py` | **NEW** | ~80 |
| `backend/prompts/.../semantic_field_inference.txt` | **NEW** | ~100 |
| `backend/prompts/.../document_tree_parsing.txt` | **NEW** | ~100 |
| `backend/Routes/template_analysis_routes.py` | MODIFY | ~0 net (remove ~200 lines dead routes, add ~50 new Phase 3 endpoints) |
| `Frontend/src/api/templateApi.js` | MODIFY | +10 (new API function) |
| `Frontend/src/views/SoftwareWorkspace/TemplatePanel.jsx` | MODIFY | +40 (Analyze button + phase3Data state) |
| `Frontend/src/views/SoftwareWorkspace/ConsoleTab.jsx` | MODIFY | +80 (Phase 3 tab with results rendering) |
| `Frontend/src/views/SoftwareWorkspace/SectionToolbar.jsx` | MODIFY | +10 (Analyze button prop) |

---

## Verification Plan

### Backend
1. Run `python -c "from Template_analysis.template_analyzer_agent import TemplateAnalysisAgent; print('Import OK')"` — confirms new agent loads
2. Call `GET /template-phase3/{project_id}` with a known project (e.g., `Sample_1_1`) — verify Phase3Result has all 5 sub-fields populated
3. Verify vague template sections get inferred fields (check `fields` array for `field_type: "inferred"` entries)
4. Call `POST /template-section/{project_id}/validate` — confirm no import error (DocumentValidatorAgent fix)
5. Run `test_execute_generation_plan.py` — confirm existing 11-stage pipeline still works
6. Check `output/template_details/{project_id}/phase3_result.json` exists after running generate

### Frontend
7. Click "Analyze" button → "Analyze" tab appears in console with document tree, fields, DAG, styling rules
8. Inferred fields are color-coded amber to distinguish from explicit blue placeholders
9. Click "Generate" → verify existing flow still works, console shows Phase 3 stages alongside the 11 planned stages
