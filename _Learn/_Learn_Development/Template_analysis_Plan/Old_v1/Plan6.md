# TemplateAnalysisAgent: LLM → Self-Correction → Fallback Per Phase

## Context

`TemplateAnalysisAgent` orchestrates generic embedded document generation. The LLM frequently returns non-JSON output (bash commands, echoed template content) because:
- Prompt bug: missing newline concatenates `section_num` with next line
- No retry: `_self_correct_json` exists but is never called
- Type mismatch: `required_data` is `list[dict]` but heuristic produces `list[str]`
- LLM attention overwhelmed by large templates (133 lines of nested blocks)

**Root fix**: Add structured output + tool-based LLM with fallback to every phase.

**Three-tier pattern for every phase**:
1. **LLM** (primary): QueryLoop (max_turns=DEFAULT_MAX_TOOL_TURNS, i.e. 100), relevant prompt + tools
2. **self_correction** (secondary): If `_clean_and_parse_json` fails → retry LLM with correction via `_self_correct_json`
3. **default_fallback** (tertiary): Pure heuristic that produces structurally valid data, marked with `__source` field so the executor knows confidence

**Design decisions from user feedback**:
- All prompts are generic for embedded documents (not SRS-specific)
- All phases use tools (FileRead, Bash, Glob) to read from knowledge directory
- All 5 new prompts are production-ready
- Combined section data saved as separate per-section files, not one combined file

---

## Phase 1: analyze_template_structure — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `_analyze_template_file()` (lines 349-418)

### System Prompt (existing)
**File**: `template_analysis_prompts/template_analysis.txt` — defines JSON output with `required_data` as objects.

### LLM (primary)
1. QueryLoop (max_turns=DEFAULT_MAX_TOOL_TURNS=100), full tool registry
2. LLM uses tools to list/read knowledge files, analyzes template content
3. Returns JSON with `name`, `section_number`, `purpose`, `output_type`, `placeholders`, `required_data`

### Self-Correction (secondary — NEW wiring)
4. If `_clean_and_parse_json` fails → call `_self_correct_json(template_content, system_prompt)`
5. Retry LLM with correction prompt: "Your previous JSON response failed to parse. Fix formatting and return ONLY valid JSON."

### Default Fallback (tertiary — heuristic fix)
6. `_analyze_template_file_heuristic()` — pure code
7. **Fix required_data type**: produce `list[dict[str, Any]]`:
   ```python
   required_data.append({"file": data_key, "reason": f"Keyword match: {keyword}"})
   ```
8. **Fix user prompt**: `f"section_num: {section_num}\n"` (add missing newline, was concatenating "1Knowledge...")

---

## Phase 2: build_section_map — Pure Code (No Change)

**File**: `document_architect_agent.py`, `build_section_map()` (lines 462-475)

No changes. Pure dict construction from `DocumentStructure`.

---

## Phase 3: build_dependency_graph — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `build_dependency_graph()` + `_build_dependency_graph_heuristic()` (lines 494-573)

### System Prompt (existing)
**File**: `template_analysis_prompts/dependency_graph.txt`

### LLM (primary)
1. QueryLoop (max_turns=100) with FileRead tool
2. LLM uses tools to read knowledge files, understands what each section produces
3. Returns JSON `{"dependencies": {"01_file.md": [], "02_file.md": ["01_file.md"]}}`

### Self-Correction (secondary — NEW)
4. If `_clean_and_parse_json` fails → `_self_correct_json(section_summary, system_prompt)`

### Default Fallback (tertiary — section-number ordering)
5. `_build_dependency_graph_heuristic()` — every section depends on all earlier sections by number

---

## Phase 4: plan_retrieval — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `plan_retrieval()` + `_plan_retrieval_heuristic()` (lines 578-715)

### System Prompt (existing)
**File**: `template_analysis_prompts/retrieval_planning.txt`

### LLM (primary)
1. QueryLoop (max_turns=100) with list_files tool
2. LLM uses tools to list knowledge directories, maps `required_data` to actual file paths
3. Returns JSON `{"memory_files": [...], "requirement_ids": [...]}`

### Self-CorCorrection (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(section_summary, system_prompt)`

### Default Fallback (tertiary — string-key lookup)
5. `_plan_retrieval_heuristic()` — hardcoded mapping dict
6. **Fix**: handle `list[dict]` access — extract `.get("file")` from dict items

---

## Phase 5: analyze_gaps — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `analyze_gaps()` + `_analyze_gaps_heuristic()` (lines 720-826)

### System Prompt (existing)
**File**: `template_analysis_prompts/gap_analysis.txt`

### LLM (primary)
1. QueryLoop (max_turns=100) with list_files tool
2. LLM uses tools to verify knowledge directory contents, compares required_data against availability
3. Returns JSON `{"gaps": [...], "is_complete": bool}`

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(gaps_context, system_prompt)`

### Default Fallback (tertiary — file existence checks)
5. `_analyze_gaps_heuristic()` — direct file path checks
6. **Fix**: handle `list[dict]` access — extract `.get("file")` from dict items

---

## Phase 6: generate_questions — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `generate_questions()` (lines 831-842)

**Currently**: Pure code — iterates gaps → creates Question objects.

### NEW: Convert to LLM with fallback

### System Prompt (NEW file)
**File**: `template_analysis_prompts/question_generation.txt`
```
# @version: 1.0
# @category: system
# @template: false

You are a document question analyst. Given gap analysis results for a document section,
generate precise, actionable questions to fill the missing information.

## AVAILABLE TOOLS
Use FileRead or Bash tools to inspect the knowledge directory and related documents
to understand what information might already be available before asking the user.
Read relevant knowledge files to frame context-aware questions.

## WORKFLOW
1. List the knowledge directory to see what files exist
2. Read relevant knowledge files to check if information is already available
3. Generate questions only for genuinely missing data

## OUTPUT FORMAT

Return ONLY valid JSON with NO markdown code fences:
{
  "questions": [
    {
      "section": "section name",
      "question": "What is the operating environment for this system?",
      "expected_source": "user_input",
      "priority": "high"
    }
  ]
}

## FIELD RULES
- expected_source: "user_input" for critical gaps, "memory" for warnings/info
- priority: "high" for critical, "medium" for warning, "low" for info
- Questions should be specific and actionable based on the knowledge files examined
```

### LLM (primary)
1. QueryLoop (max_turns=100) with full tool registry
2. LLM reads knowledge files, generates targeted questions
3. Returns JSON `{"questions": [...]}`

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(gaps_context, system_prompt)`

### Default Fallback (tertiary — heuristic)
5. `_generate_questions_heuristic()` — convert each gap into a template question

---

## Phase 7: select_generation_strategy — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `select_generation_strategy()` (lines 847-876)

**Currently**: Pure code — returns `GenerationStrategy` with fixed model "opus46".

### NEW: Convert to LLM with fallback

### System Prompt (NEW file)
**File**: `template_analysis_prompts/generation_strategy.txt`
```
# @version: 1.0
# @category: system
# @template: false

You are a document generation strategist. Given a document section's purpose, context,
and data requirements, decide the best approach to generate its content.

## AVAILABLE TOOLS
Use FileRead or Bash tools to inspect the knowledge directory and understand what
data sources are available for this section before recommending a strategy.

## OUTPUT FORMAT

Return ONLY valid JSON with NO markdown code fences:
{
  "generator": "content_knowledge_agent",
  "model": "opus46",
  "format": "markdown",
  "dependencies": ["01_project_table.md"]
}

## CHOICES
- generator: "content_knowledge_agent" (default), "manual" (if section needs no external data), "llm_fill_placeholders" (if section has only placeholders)
- model: "opus46" (default), "sonnet46" (for lightweight sections)
- format: "markdown", "tables", "requirements_list", "text_with_tables"
```

### LLM (primary)
1. QueryLoop (max_turns=100) with tools to inspect knowledge
2. LLM reads knowledge files, selects optimal generation strategy
3. Returns JSON `{"generator", "model", "format", "dependencies"}`

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(section_context, system_prompt)`

### Default Fallback (tertiary — fixed strategy)
5. `_select_generation_strategy_heuristic()` — returns default

---

## Phase 8: build_retrieval_plans — Aggregation (Call Phase 4 per section)

**File**: `document_architect_agent.py`, `build_retrieval_plans()` (lines 881-889)

No changes. Iterates sections, calls `plan_retrieval()` for each. Phase 4 has its own LLM→self_correction→heuristic.

---

## Phase 9: build_gap_analysis — Aggregation (Call Phase 5 per section)

**File**: `document_architect_agent.py`, `build_gap_analysis()` (lines 894-923)

No changes. Iterates sections, calls `analyze_gaps()` for each. Phase 5 has its own LLM→self_correction→heuristic.

---

## Phase 10: validate_document — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `validate_document()` (lines 928-996)

**Currently**: Rule-based only — checks existence, emptiness, placeholders.

### Convert to LLM with fallback (LLM is primary)

### System Prompt (NEW file)
**File**: `template_analysis_prompts/document_validation.txt`
```
# @version: 1.0
# @category: system
# @template: false

You are a document validation analyst. Check generated document sections for
completeness, accuracy, and consistency against the knowledge base.

## AVAILABLE TOOLS
Use FileRead and Bash tools to:
1. List and read generated output files from the project's output directory
2. List and read knowledge files from the knowledge directory
3. Compare generated content against source knowledge

## VALIDATION CHECKS
1. No empty sections — every section has meaningful content
2. All placeholders resolved — no unresolved <...> or {{...}} patterns
3. Dependency order respected — dependent sections reference their dependencies
4. No contradictory statements between sections
5. Content matches source knowledge — no hallucination or fabrication

## OUTPUT FORMAT

Return ONLY valid JSON with NO markdown code fences:
{
  "is_valid": true,
  "checks": {"01_file.md": true, "02_file.md": false},
  "issues": ["Section 02_file.md is empty"],
  "unresolved_placeholders": ["02_file.md/<PROJECT-NAME>"],
  "conflicts": []
}
```

### LLM (primary)
1. QueryLoop (max_turns=100) with tools to read output + knowledge
2. LLM reads each generated section file + knowledge files for comparison
3. Returns JSON with validation results

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(validation_context, system_prompt)`

### Default Fallback (tertiary — rule-based)
5. Keep existing code as fallback: check file existence, emptiness, `<...>` placeholders

---

## Phase 11: build_traceability_map — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `build_traceability_map()` (lines 1001-1015)

**Currently**: Pure code — lists requirement files, creates `TraceabilityEntry`.

### System Prompt (NEW file)
**File**: `template_analysis_prompts/traceability.txt`
```
# @version: 1.0
# @category: system
# @template: false

You are a document traceability analyst. Map every statement in document sections
back to its source (knowledge file, requirement, user input, or template).

## AVAILABLE TOOLS
Use FileRead and Bash tools to:
1. List and read all knowledge files in the knowledge directory
2. List and read all requirement files in the requirements/ subdirectory
3. Read generated section files to understand what statements they contain

## OUTPUT FORMAT

Return ONLY valid JSON with NO markdown code fences:
{
  "entries": [
    {
      "section": "section name",
      "statement_index": 1,
      "source_type": "memory",
      "source_ref": "requirements/REQ-0001.md"
    }
  ]
}

## SOURCE TYPES
- "memory" — from knowledge directory files
- "requirement" — from requirements/ subdirectory
- "user_input" — from user-provided data
- "template" — from template definitions
```

### LLM (primary)
1. QueryLoop (max_turns=100) with tools to read all knowledge/requirements
2. LLM traces statements back to their source files
3. Returns JSON `{"entries": [...]}`

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(traceability_context, system_prompt)`

### Default Fallback (tertiary — requirement file listing)
5. `_build_traceability_map_heuristic()` — list all requirement .md files, create entries

---

## Phase 12: build_assembly_plan — LLM → self_correction → heuristic

**File**: `document_architect_agent.py`, `build_assembly_plan()` (lines 1020-1026)

**Currently**: Pure code — returns section_order + merge_strategy.

### System Prompt (NEW file)
**File**: `template_analysis_prompts/assembly_plan.txt`
```
# @version: 1.0
# @category: system
# @template: false

You are a document assembly strategist. Given the document section list and their
dependencies, determine the optimal merge and assembly strategy.

## AVAILABLE TOOLS
Use FileRead and Bash tools to inspect the knowledge directory and understand
the section structure before determining assembly strategy.

## OUTPUT FORMAT

Return ONLY valid JSON with NO markdown code fences:
{
  "section_order": ["01_file.md", "02_file.md", ...],
  "merge_strategy": "sequential"
}
```

### LLM (primary)
1. QueryLoop (max_turns=100) with tools to inspect knowledge
2. LLM confirms optimal section order and merge strategy
3. Returns JSON `{"section_order", "merge_strategy"}`

### Self-Correction (secondary — NEW)
4. If JSON parse fails → `_self_correct_json(assembly_context, system_prompt)`

### Default Fallback (tertiary — use dependency graph order)
5. `_build_assembly_plan_heuristic()` — use dependency graph topological sort

---

## Phase 13: execute_generation_plan — Orchestration + Per-Section Output Files

**File**: `document_architect_agent.py`, `execute_generation_plan()` (lines 1031-1129)

### LLM → self_correction → heuristic (applies to each sub-phase)
1. All 12 phases run in order with their own LLM→self_correction→heuristic
2. Each phase's result is cached in the `ExecutionPlan`

### NEW: Save per-section combined files for content generation
After all phases complete, create one separate file per section containing all
necessary data for `ContentKnowledgeAgent` to generate that section:

```python
for fname in assembly_plan.section_order:
    info = section_map.sections.get(fname)
    if not info:
        continue
    strategy = strategies.get(fname, {})
    retrieval = retrieval_plans.get(fname)
    
    # Save combined data for this section
    section_file = output_dir / f"{fname}_combined.md"
    section_file.write_text(f"""\
# Section: {info.name}
# File: {fname}
# Section Number: {info.section_number}

## Purpose
{info.purpose}

## Output Type
{info.output_type}

## Placeholders to Fill
{json.dumps(info.placeholders, indent=2)}

## Required Data
{json.dumps(info.required_data, indent=2)}

## Dependencies
{json.dumps(info.dependencies, indent=2)}

## Generation Strategy
- Generator: {strategy.get('generator', 'content_knowledge_agent')}
- Model: {strategy.get('model', 'opus46')}
- Format: {strategy.get('format', 'markdown')}

## Retrieved Memory Files
{json.dumps(retrieval.memory_files, indent=2) if retrieval else '[]'}

## Requirement IDs
{json.dumps(retrieval.requirement_ids, indent=2) if retrieval else '[]'}
""")
```

Each file (`01_project_table_combined.md`, `02_revision_history_combined.md`, etc.) is saved separately per section.

---

## New System Prompt Files to Create

| File | Purpose |
|------|---------|
| `question_generation.txt` | Generate questions from gap analysis |
| `generation_strategy.txt` | Select generation strategy per section |
| `document_validation.txt` | Validate generated sections (LLM primary) |
| `traceability.txt` | Map statements to source files |
| `assembly_plan.txt` | Confirm section order + merge strategy |

---

## Files to Modify

1. **`backend/Memory_Management/document_architect_agent.py`**:
   - Phase 1: Fix user prompt, wire `_self_correct_json`, fix heuristic `required_data` type
   - Phase 3: Wire `_self_correct_json` in `build_dependency_graph`
   - Phase 4: Wire `_self_correct_json`, fix heuristic dict access
   - Phase 5: Wire `_self_correct_json`, fix heuristic dict access
   - Phase 6: Convert to LLM with `_self_correct_json` + heuristic
   - Phase 7: Convert to LLM with `_self_correct_json` + heuristic
   - Phase 10: Convert to LLM with `_self_correct_json` + rule-based heuristic
   - Phase 11: Convert to LLM with `_self_correct_json` + heuristic
   - Phase 12: Convert to LLM with `_self_correct_json` + heuristic
   - Phase 13: Add per-section combined output file logic

2. **`backend/prompts/System_Prompts/template_analysis_prompts/`** — create 5 new prompt files

---

## Verification

```bash
python3 ./backend/Memory_Management/test_architect_agent.py
```

Expected: all template files parse successfully. Each phase logs which tier succeeded (LLM / self-corrected / heuristic). No Pydantic validation errors. Per-section combined files generated at execution time.
