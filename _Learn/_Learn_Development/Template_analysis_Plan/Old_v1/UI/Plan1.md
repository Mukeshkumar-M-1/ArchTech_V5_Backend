# TemplatePanel — Production Upgrade with Backend API Integration

## Context

The `TemplatePanel` UI is a fully functional local demo but has **zero integration** with the backend API. All 11 endpoints in `template_parsing_routes.py` are implemented but completely unwired. The UI uses inline styles instead of Tailwind CSS, the "Analyze" button has an empty handler, and no data is fetched from or saved to the backend.

**Goal:** Upgrade TemplatePanel to production-grade — Tailwind-only styles, full backend integration, proper error/loading states, JSDoc comments, and clean component architecture.

---

## Files to Modify

| File | Action |
|------|--------|
| `Frontend/src/api/templateApi.js` | **NEW** — All backend API calls |
| `Frontend/src/views/SoftwareWorkspace/TemplatePanel.jsx` | **REWRITE** — Orchestrator component |
| `Frontend/src/views/SoftwareWorkspace/SectionList.jsx` | **NEW** — Left sidebar file list |
| `Frontend/src/views/SoftwareWorkspace/SectionToolbar.jsx` | **NEW** — Top toolbar with view mode + actions |
| `Frontend/src/views/SoftwareWorkspace/SectionContent.jsx` | **NEW** — Editor/preview area |
| `Frontend/src/views/SoftwareWorkspace/ProgressOverlay.jsx` | **NEW** — Generation progress modal |
| `Frontend/src/views/SoftwareWorkspace/ErrorBanner.jsx` | **NEW** — Dismissible error banner |
| `Frontend/src/views/SoftwareWorkspace.jsx` | **MODIFY** — Remove local template state, simplify |
| `Frontend/src/views/SoftwareWorkspace/EditorPanel.jsx` | **MODIFY** — Simplify props |

---

## Step-by-Step Implementation

### Step 1: Create `Frontend/src/api/templateApi.js`

API utility module encapsulating all 11 backend calls. Reuses the existing `getApiUrl()` helper and `fetch` pattern.

- `request(url, options)` — shared fetch wrapper with JSON parsing + error throw on `!res.ok`
- `fetchSections(projectId)` — GET `/template-sections/{id}`
- `fetchSectionContent(projectId, filename)` — GET `/template-section/{id}/{filename}`
- `saveSectionContent(projectId, filename, content)` — PUT `/template-section/{id}/{filename}`
- `deleteSectionFile(projectId, filename)` — DELETE `/template-section/{id}/{filename}`
- `createSectionFile(projectId, filename)` — POST `/template-section/{id}/create`
- `generateSections(projectId, options)` — POST `/template-section/{id}/generate`
- `fetchProgress(projectId)` — GET `/template-progress/{id}`
- `fetchArchitecture(projectId)` — GET `/template-architecture/{id}`
- `fetchGaps(projectId)` — GET `/template-gaps/{id}`
- `validateDocument(projectId)` — POST `/template-section/{id}/validate`
- `executePlan(projectId, options)` — POST `/template-section/{id}/execute-plan`

Each function has JSDoc with `@param` and `@returns`.

### Step 2: Create `SectionList.jsx` — Left Sidebar

Renders the file list with Tailwind (no inline styles).

- **Props:** `sections`, `selectedFilename`, `onSelect`, `onDelete`, `onAddClick`, `loading`
- **Header:** "Document Template" label + `+` button
- **Each row:**
  - Selected: `bg-blue-50 border-blue-200` (uses `C.accentLight`)
  - Hover: `hover:bg-gray-50`
  - Section number badge: `text-[10px] font-mono`
  - Generated indicator: small green dot (`bg-green-500 w-1.5 h-1.5 rounded-full`)
  - Delete button: visible on hover, `text-gray-400 hover:text-red-600`
- **Loading state:** Spinner during initial fetch
- **Empty state:** "No sections available. Click + to create your first section."
- JSDoc on export function

### Step 3: Create `SectionToolbar.jsx` — Top Navigation

Top bar with view mode toggle + action buttons.

- **Props:** `selectedFilename`, `viewMode`, `onViewModeChange`, `onAnalyze`, `onGenerate`, `onValidate`, `isAnalyzing`, `isGenerating`, `isValidating`
- **Editor/Preview toggle:** Pill buttons with active state styling (white bg + shadow)
- **Analyze button:** `Brain` icon, triggers architecture analysis, shows spinner
- **Generate button:** Opens a mini choice dialog: "Generate selected section" or "Generate all sections"
- **Validate button:** Full document validation
- **Save button:** Manual save trigger (in addition to auto-save)
- All buttons disable during their respective operations with `animate-spin` loaders
- JSDoc on export function

### Step 4: Create `SectionContent.jsx` — Editor/Preview Area

Renders either the TiptapEditor or ReactMarkdown preview.

- **Props:** `content`, `viewMode`, `onContentChange`, `isSaving`
- **Editor mode:** Renders `TiptapEditor` with same props as current code
- **Preview mode:** Renders `ReactMarkdown` with prose classes
- **Saving indicator:** Bottom-right "Saving..." / "Saved" label
- **Empty state:** "No content available"
- JSDoc on export function

### Step 5: Create `ProgressOverlay.jsx` — Generation Progress Modal

Reuses the existing modal pattern (`fixed inset-0 z-[200]` + backdrop blur).

- **Props:** `progressData`, `onDismiss`
- **Progress bar:** `bg-blue-600` bar that fills based on progress percentage
- **Phase text:** Shows current phase from backend
- **Auto-dismiss:** When status becomes `complete` or `error`
- JSDoc on export function

### Step 6: Create `ErrorBanner.jsx` — Dismissible Error

- **Props:** `message`, `onDismiss`
- **Style:** `bg-red-50 border-red-100 text-red-700 px-4 py-2 rounded-lg flex items-center gap-2`
- **Dismissable** via X button

### Step 7: Rewrite `TemplatePanel.jsx` as Orchestrator

Becomes a thin component managing state and wiring sub-components.

**State management:**
- `sections` (array from API)
- `selectedFilename`
- `content`
- `viewMode`
- `isLoading`, `isSaving`, `isAnalyzing`, `isGenerating`, `isValidating`
- `progressData`, `error`, `showCreateModal`, `newName`

**Effects:**
1. **Mount:** `fetchSections(project.id)` → populate sections + auto-select first
2. **Selection change:** `fetchSectionContent(project.id, filename)` → load content
3. **Progress polling:** `setInterval(fetchProgress)` while generating (1.5s interval)
4. **Auto-save:** Debounced (800ms) `saveSectionContent` PUT call on content change

**Handlers:**
- `handleContentChange(newContent)` — updates state + debounced (800ms) auto-save via PUT call
- `handleSaveNow()` — explicit manual save via toolbar button
- `handleAnalyze()` — fetches architecture data, opens **detail modal/drawer** with structure, dependency graph, gap analysis results
- `handleGenerate(target)` — user chooses "selected section" or "all sections", triggers LLM generation, starts progress polling
- `handleValidate()` — runs validation, shows report in toast/overlay
- `handleCreateSection()` — calls API, refreshes section list
- `handleDeleteSection(filename)` — calls API, updates state

**JSDoc on export function** describing props and behavior.

### Step 8: Update `SoftwareWorkspace.jsx`

Remove all local template state (was ~20 lines of unnecessary management).

**Remove:**
- `useState` for: `templateFiles`, `selectedTemplate`, `templateViewMode`, `addModalOpen`, `newTemplateName`, `newTemplateContent`
- Functions: `handleAddTemplate`, `handleDeleteTemplate`, `getSelectedTemplateContent`, `setSelectedTemplateContent`
- `AddTemplateModal` inline component (now managed inside TemplatePanel)

**Change:**
- Pass `project` to `TemplatePanel` — the panel now manages its own state internally
- Simplify `EditorPanel` props (remove all template-specific props)

### Step 9: Update `EditorPanel.jsx`

Simplify to pass-through — TemplatePanel now handles its own state.

**Old props to remove:** `templateFiles`, `onSelectTemplate`, `onDeleteTemplate`, `onTemplateContentChange`, `templateContent`, `templateViewMode`, `onViewModeChange`

**New props:** `project`, `onSectionsChange`

### Step 10: Add JSDoc Comments

Final pass — add JSDoc to every exported function in every new/modified file:
- API functions: `@param`, `@returns`
- Components: `@param {Object} props` with typed descriptions for each prop
- Helper functions in templateApi.js

---

## Existing Patterns to Reuse

- **API calls:** `fetch(getApiUrl('/endpoint'), { method, headers, body })` from `utils/apiConfig.js`
- **Color tokens:** `C.accent`, `C.surface`, `C.accentLight` from `types.jsx`
- **Toast notifications:** `useToastStore().addToast(message, type)` from `store/toastStore.js`
- **Modal pattern:** `fixed inset-0 z-[200]` + `backdrop-blur-md` + `animate-in`
- **Loading:** `animate-spin` spinner + text
- **Icons:** `lucide-react` — `FileText`, `Brain`, `Loader2`, `CheckCircle2`, `AlertCircle`, `X`

---

## Verification

1. **Dev server:** `npm run dev` in Frontend/
2. **Check template sections load** from API on mount (verify network tab)
3. **Test file creation** via the `+` button
4. **Test file deletion** via the `x` button on hover
5. **Test editing** — make changes, wait 800ms, verify PUT call in network tab
6. **Test Editor/Preview toggle** — both modes render correctly
7. **Test Generate** — progress modal appears, polls backend, auto-dismisses
8. **Test Analyze** — architecture analysis runs, success toast shown
9. **Test Validate** — validation report displayed
10. **Check Tailwind only** — no inline `style` attributes for layout (dynamic values like progress bar width are fine)
11. **Check no regressions** in GenerationPanel or ChatPanel tabs
