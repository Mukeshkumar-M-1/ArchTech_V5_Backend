# Plan: Template Parsing Agent Routes

## Context

The `template_parsing_routes.py` file exists but is empty. It needs to be populated with endpoints that let the frontend browse, view, edit, create, and LLM-generate SRS document template sections per project. Projects store their own copy of templates under `output/templates/{project_id}/Topic_Template/`, synced on first access from the shared source at `Document_Section/SRS_Section/Topic_Template/`.

## Files to Modify

1. **`/backend/Routes/template_parsing_routes.py`** — Create full route file (currently empty)
2. **`/backend/main.py`** — Add import and `include_router` call

## Existing Patterns to Reuse

- **Route pattern**: `APIRouter()` with `prefix=""`, same as `memory_management_routes.py` and `requirement_extraction_routes.py`
- **Progress tracking**: `template_progress_store: dict[str, dict]` + background task pattern
- **Background tasks**: `_background_tasks: set[asyncio.Task]` with `task.add_done_callback(_background_tasks.discard)`
- **Path traversal protection**: Resolve absolute paths, verify target starts with project base dir
- **Error handling**: `HTTPException` (404/403/500), plain dict responses
- **LLM integration**: Delegate to `ContentKnowledgeAgent.generate_document()` from `/backend/Memory_Management/content_knowledge_agent.py`
- **Pydantic models**: One model per request/response shape

## Endpoints

### 1. GET `/template-sections/{project_id}` — List sections
- Lists all `.md` files in the project's Topic_Template directory
- Auto-syncs from shared source if project directory is empty/missing
- Returns metadata: filename, path, section_number, title, is_generated
- Returns sorted list by section number

### 2. GET `/template-section/{project_id}/{filename:path}` — View file
- Returns `{filename, path, content}` for the specified markdown file
- Path traversal protection (403), file-not-found (404), dir check (404), extension check (404)

### 3. PUT/POST `/template-section/{project_id}/{filename:path}` — Update file
- Accepts `{"content": "..."}` in request body
- Writes content to the project-specific file
- Same path validation as GET

### 4. DELETE `/template-section/{project_id}/{filename:path}` — Delete file
- Deletes only from the project-specific directory (never from shared source)
- Path traversal protection, not-found handling

### 5. POST `/template-section/{project_id}/generate` — LLM-generate section(s)
- Accepts `{"filename": "01_introduction.md"|null, "requirement_ids": [...]}`
- If `filename` is null, generates all sections
- If `requirement_ids` is empty, loads all from `requirements.json`
- Runs as a background async task with progress tracking
- Uses `ContentKnowledgeAgent.generate_document()` internally
- Progress stored in `template_progress_store`

### 6. POST `/template-section/{project_id}/create` — Create new file
- Accepts `{"filename": "my_new_section"}`
- Auto-assigns next available section number (01_, 02_, etc.)
- Creates file with a basic heading placeholder
- Collision handling: appends `_1`, `_2`, etc.

### 7. GET `/template-progress/{project_id}` — Progress polling
- Returns progress store entry for the project's generation task
- States: idle, running, complete, error

## Helper Functions

| Function | Purpose |
|----------|---------|
| `_sync_project_templates(project_id)` | Copy shared templates to project dir on first access |
| `_parse_section_metadata(filename)` | Parse `01_introduction.md` -> `(1, "Introduction")` |
| `_next_section_number(proj_dir)` | Scan for max section number, return next `NN_` |
| `_sanitize_filename(user_input)` | Strip path components, ensure `.md` extension |
| `_resolve_file_path(project_id, filename)` | Resolve + validate path with traversal protection |

## main.py Changes

Add two lines:
```python
from Routes.template_parsing_routes import router as template_parsing_router
```
```python
app.include_router(template_parsing_router, prefix="")
```

## Verification

1. Start server — no import errors
2. `GET /template-sections/Sample_1_1` for a new project — returns 10 standard files, copies them to `output/templates/Sample_1_1/Topic_Template/`
3. `GET /template-section/Sample_1_1/01_introduction.md` — returns full markdown content
4. `PUT /template-section/Sample_1_1/01_introduction.md` with new content — verify change persists on re-GET
5. `POST /template-section/Sample_1_1/create` with `{"filename": "my_section"}` — returns `08_my_section.md`
6. `POST /template-section/Sample_1_1/generate` — poll `/template-progress/Sample_1_1` for progress transition idle->running->complete
7. `GET /template-section/Sample_1_1/../../../etc/passwd` — returns HTTP 403
8. `DELETE /template-section/Sample_1_1/08_my_section.md` — succeeds, shared source untouched
