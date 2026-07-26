🏗️ API Routes Explained
Here are all 10 routes in template_analysis_routes.py:

1. GET /template-sections/{project_id} — List all sections
Scans the project's template directory, returns a sorted list of all .md template files with their section number, title, and whether they've been generated (no unresolved <> placeholders).

2. GET /template-section/{project_id}/{filename:path} — View a file
Returns the raw markdown content of a specific template file. Includes path traversal protection.

3. DELETE /template-section/{project_id}/{filename:path} — Delete a file
Removes a template file from the project directory. Returns 404 if file doesn't exist.

4. POST /template-section/{project_id}/cancel — Cancel generation
Stops a running LLM generation by canceling the session and aborting all child tasks in the abort hierarchy.

5. POST /template-section/{project_id}/generate — LLM-generate sections
The main route. Spawns a background async task that creates a TemplateAnalysisAgent, runs execute_generation_plan() (all 11 stages), and fills placeholders with LLM-generated content. Returns a session_id for polling progress.

6. POST /template-section/{project_id}/create — Create new section
Creates a new .md template file with auto-assigned section numbering (e.g., 08_new_section.md). Pre-fills with a header comment.

7. GET /template-progress/{project_id} — Progress polling
Returns real-time generation progress (status, current phase, sessions, tool calls, tokens) for the frontend console to display.

8. POST /template-section/{project_id}/validate — Validate document
Runs TemplateValidatorAgent to check all sections for structural issues (empty files, unresolved placeholders) and semantic problems.

9. GET /template-phase3/{project_id} — Phase 3 analysis
Runs TemplateAnalysisAgent.run() to independently analyze the template structure and return: document tree, table of contents, fields/placeholders, dependency DAG, and styling rules. This is the "Analyze" button in the UI.

10. GET /template-phase3-status/{project_id} — Check Phase 3 status
Returns whether Phase 3 results already exist in output/template_details/{project_id}/ (cached check, doesn't re-run).