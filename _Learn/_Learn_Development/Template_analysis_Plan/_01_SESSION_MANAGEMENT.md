# Session Manager — Complete Documentation

## Overview

`session_manager.py` is the unified session management system. It handles both **interactive chat sessions** and **template generation tasks** from a single `SessionLifecycle` class backed by `SessionRecord` dataclass. All session data is stored in `.Archtech/{project_id}/sessions/`.

## File Storage

```
.Archtech/{project_id}/
├── sessions/
│   ├── {PID}.json                    ← Interactive chat session PID file
│   ├── sess-{project_id}-{hash}.json ← Generation task session
│   └── {session_id}.json             ← Interactive session record
└── projects/{sanitized-path}/
    └── {session_id}.jsonl            ← Conversation transcript
```

---

## SessionRecord Dataclass

The single data model used for all sessions (chat + generation).

### Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `session_id` | `str` | — | Unique session identifier |
| `pid` | `int` | — | Process ID that owns this session |
| `cwd` | `str` | — | Working directory when session was created |
| `started_at` | `float` | — | Unix timestamp of creation |
| `kind` | `str` | `"interactive"` | `"interactive"` for chat, `"generation"` for template tasks |
| `entrypoint` | `str` | `"cli"` | How the session was created |
| `transcript_path` | `str` | `""` | Path to `.jsonl` conversation transcript |
| `status` | `str` | `"idle"` | `"idle" \| "running" \| "complete" \| "error" \| "cancelled"` |
| `parent_session_id` | `str \| None` | `None` | Links to previous session after clear/reset |
| `project_id` | `str` | `""` | Project identifier (generation tasks only) |
| `target_sections` | `list[str] \| None` | `None` | Which sections to generate |
| `current_stage` | `int` | `0` | Current stage in 11-stage pipeline (generation) |
| `progress` | `int` | `0` | Progress percentage (generation) |
| `current_phase` | `str` | `""` | Human-readable phase name (generation) |
| `stage_logs` | `list[dict]` | `[]` | Records of completed stages |
| `tool_calls` | `list[dict]` | `[]` | Records of LLM tool invocations |
| `error` | `str \| None` | `None` | Error message if status is `"error"` |
| `_path` | `Path` | `None` | Internal — path to this record's JSON file on disk |

### Methods

#### `to_dict() -> dict`

Converts the record to a dictionary for JSON serialization. Omits `None` and empty fields for clean output.

**Example output:**
```json
{
  "pid": 12345,
  "sessionId": "sess-proj-4f8e2d",
  "cwd": "/home/dev/Mukesh/ArchTech_V5",
  "startedAt": 1719000000.0,
  "kind": "generation",
  "entrypoint": "cli",
  "status": "running",
  "projectId": "proj",
  "targetSections": null,
  "currentStage": 5,
  "progress": 45,
  "currentPhase": "Stage 5/11 - Gap Analysis",
  "stageLogs": [{"stage": "01_structure", "status": "ok", ...}],
  "toolCalls": [{"tool_name": "FileRead", "status": "ok", ...}],
  "error": null
}
```

#### `from_dict(data: dict) -> SessionRecord`

Factory method — reconstructs a `SessionRecord` from a dictionary (e.g., loaded from disk).

#### `_save()`

Atomically writes the record to its `_path` on disk using temp file + `os.replace` to prevent corruption on crash.

---

## SessionLifecycle Class

### Interactive Chat Methods

#### `create(project_path, entrypoint="cli", kind="interactive", project_id="") -> SessionRecord`

Creates a new interactive chat session.

| Step | Action |
|------|--------|
| 1 | Generate UUID-based `session_id` (12 hex chars) |
| 2 | Resolve `sessions_dir` and `projects_dir` from project config |
| 3 | Write PID file: `.Archtech/{project_id}/sessions/{PID}.json` |
| 4 | Determine transcript path: `.Archtech/{project_id}/projects/{sanitized}/` |
| 5 | Touch empty transcript `.jsonl` file |

**Returns:** `SessionRecord` with `status="idle"`, `transcript_path` set.

**Called by:** Chat routes when a new conversation starts.

---

#### `resume(project_path, project_id="") -> Optional[SessionRecord]`

Finds the latest active (non-terminal) session for a project to continue.

| Step | Action |
|------|--------|
| 1 | Scan `.jsonl` transcript files in project directory |
| 2 | For each transcript, check if a matching PID file exists |
| 3 | Verify PID file status is `"idle"` or `"running"` |
| 4 | Return the one with most recent mtime |

**Returns:** `SessionRecord` for the latest active session, or `None`.

**Called by:** When a user reconnects to an ongoing conversation.

---

#### `clear(session_id, project_path, project_id="") -> bool`

Clears the current session and creates a new one with `parent_session_id` set.

| Step | Action |
|------|--------|
| 1 | Find the old session record by matching session_id |
| 2 | Create a new session via `SessionLifecycle.create()` |
| 3 | Set `new_record.parent_session_id = session_id` |
| 4 | Update PID file with `parentSessionId` |

**Returns:** `True` on success, `False` if old session not found.

**Called by:** User requests a new chat session (clears context but preserves history).

---

#### `discover_active(project_id="") -> list[SessionRecord]`

Lists all currently active sessions across all projects (or a specific project).

| Step | Action |
|------|--------|
| 1 | Scan `.Archtech/` directories |
| 2 | Read PID files, verify process is still alive via `os.kill(pid, 0)` |
| 3 | Deduplicate by session_id |

**Returns:** `list[SessionRecord]` of all alive sessions.

**Called by:** IDE sidebar showing active conversations.

---

#### `discover_history(project_path, project_id="") -> list[SessionRecord]`

Lists all past sessions from transcript files.

| Step | Action |
|------|--------|
| 1 | Scan `.jsonl` files in project directory |
| 2 | Sort by mtime, newest first |

**Returns:** `list[SessionRecord]` with `status="history"`.

**Called by:** Session history dropdown in the UI.

---

### Generation Task Methods

#### `create_generation(project_id, target_sections=None) -> SessionRecord`

Creates a session for a template generation task.

| Step | Action |
|------|--------|
| 1 | Generate session_id: `"sess-" + MD5(project_id:key:nanoseconds:pid)[:10]` |
| 2 | Resolve session dir: `.Archtech/{project_id}/sessions/` |
| 3 | Create `SessionRecord` with `kind="generation"`, `status="running"` |
| 4 | Write JSON file directly to `.Archtech/{project_id}/sessions/{session_id}.json` |

**Returns:** `SessionRecord` with the session_id needed for tracking.

**Called by:** `POST /template-section/{project_id}/generate` route.

---

#### `update_progress(session_id, current_stage=None, progress=None, current_phase=None, status=None, error=None) -> Optional[SessionRecord]`

Updates generation state on a session record.

| Step | Action |
|------|--------|
| 1 | Load session via `_load()` |
| 2 | Set any non-None fields on the record |
| 3 | Call `record._save()` for atomic write |

**Params:**
- `current_stage` — which of 11 stages we're on (1-11)
- `progress` — percentage 0-100
- `current_phase` — human-readable like `"Stage 5/11 - Gap Analysis"`
- `status` — `"running"`, `"complete"`, `"error"`, `"cancelled"`
- `error` — error message string

**Returns:** Updated `SessionRecord`, or `None` if session not found.

**Called by:** Every stage in `execute_generation_plan()` and the generate route success/error handlers.

---

#### `log_stage_complete(session_id, stage, status="ok", duration_ms=0, tokens_in=0, tokens_out=0) -> None`

Records that a pipeline stage completed.

| Step | Action |
|------|--------|
| 1 | Load session via `_load()` |
| 2 | Append `{stage, status, duration_ms, tokens_in, tokens_out, timestamp}` to `stage_logs` |
| 3 | Save session |

**Params:**
- `session_id` — the generation session
- `stage` — stage identifier like `"01_structure"`, `"02_section_map"`
- `status` — `"ok"` or `"error"`
- `duration_ms` — how long the stage took
- `tokens_in` / `tokens_out` — LLM token counts

**Called by:** Each of the 11 stages in `template_analysis_agent.py`.

---

#### `log_tool_call(session_id, tool_name, status="ok", tokens_in=0, tokens_out=0, duration_ms=0) -> None`

Records an LLM tool invocation.

| Step | Action |
|------|--------|
| 1 | Load session via `_load()` |
| 2 | Append `{tool_name, status, tokens_in, tokens_out, duration_ms, timestamp}` to `tool_calls` |
| 3 | Save session |

**Params:**
- `tool_name` — name of the tool (e.g., `"FileRead"`, `"Bash"`)
- `status` — `"ok"`, `"error"`, `"cancelled"`
- `tokens_in` / `tokens_out` — token counts for this tool call
- `duration_ms` — how long the call took

**Called by:** LLM query loop when tools are invoked during generation.

---

#### `find_active(project_id) -> Optional[SessionRecord]`

Finds the latest non-terminal session for a project.

| Step | Action |
|------|--------|
| 1 | Scan `.Archtech/{project_id}/sessions/*.json` |
| 2 | Sort by mtime, newest first |
| 3 | Return first one with `status` in `("running", "idle")` |

**Returns:** `SessionRecord` or `None` if no active session.

**Called by:** Cancel route (`_find_session_file` replacement), progress endpoint.

---

#### `cancel(session_id) -> bool`

Marks a session as cancelled.

| Step | Action |
|------|--------|
| 1 | Load session via `_load()` |
| 2 | Set `status = "cancelled"` |
| 3 | Save session |

**Returns:** `True` on success, `False` if session not found.

**Called by:** `POST /template-section/{project_id}/cancel` route.

---

#### `get_progress(project_id) -> dict`

Returns formatted progress data for the frontend ConsoleTab.

| Step | Action |
|------|--------|
| 1 | Call `find_active(project_id)` to get the latest session |
| 2 | If no session, return `{"status": "idle", "progress": 0}` |
| 3 | Calculate totals: `total_calls`, `total_tokens_in`, `total_tokens_out`, `total_duration` |
| 4 | Calculate `elapsed_seconds` from `started_at` |

**Returns:**
```json
{
  "status": "running",
  "progress": 45,
  "phase": "Stage 5/11 - Gap Analysis",
  "session_id": "sess-proj-4f8e2d",
  "tool_calls_count": 23,
  "total_tokens_in": 145000,
  "total_tokens_out": 89000,
  "total_duration_ms": 18400,
  "elapsed_seconds": 22,
  "stage_logs": [{"stage": "01_structure", "status": "ok", ...}],
  "tool_calls": [{"tool_name": "FileRead", "status": "ok", ...}]
}
```

**Called by:** `GET /template-progress/{project_id}` endpoint (polling every 1.5s).

---

#### `_load(session_id) -> Optional[SessionRecord]`

Internal helper — loads a session by ID by scanning all project session directories.

| Step | Action |
|------|--------|
| 1 | Scan `.Archtech/{project_id}/sessions/*.json` for all projects |
| 2 | Match by `sessionId` field |
| 3 | Return `SessionRecord.from_dict()` with `_path` set |

**Note:** Called internally by `update_progress`, `log_stage_complete`, `log_tool_call`, `find_active`, `cancel`, `get_progress`.

---

## Data Flow Diagram

### Interactive Chat Session

```
User starts new chat
    │
    ▼
SessionLifecycle.create()
    │ → Writes PID file + empty transcript
    ▼
User sends messages → LLM responds
    │
    ▼
SessionLifecycle.resume() (on reconnect)
    │ → Finds latest non-terminal session
    ▼
User clears chat
    │
    ▼
SessionLifecycle.clear()
    │ → Creates new session, links via parent_session_id
```

### Template Generation Session

```
User clicks "Generate"
    │
    ▼
SessionLifecycle.create_generation()
    │ → Writes sess-{hash}.json to sessions/
    ▼
TemplateAnalysisAgent.execute_generation_plan() (11 stages)
    │
    ├── Each stage calls:
    │     SessionLifecycle.log_stage_complete(stage, ...)
    │     SessionLifecycle.update_progress(current_stage=N, progress=X, ...)
    │
    ▼
SessionLifecycle.update_progress(status="complete", progress=100, ...)
    │
    ▼
Frontend polls:
SessionLifecycle.get_progress(project_id)
    │ → Returns dict with status, progress, stage_logs, tool_calls
```

---

## File: session_memory.py

Separate module — extracts reusable facts from conversation transcripts.

### SessionMemoryExtractor

Scans messages with regex patterns to extract:

| Field | Pattern | Extracts From |
|-------|---------|---------------|
| `files` | `"/[^\s']+"` or `"./[^\s']+"` | User and assistant messages |
| `decisions` | `"decided|choose|selected|use|should use"` | Assistant text messages |
| `code_changes` | `"def \w+"`, `"class \w+"`, diff markers | Tool results and assistant |

**Returns:** `{"files": [...], "decisions": [...], "code_changes": [...]}`

### SessionMemoryCache

| Method | Storage Path | Purpose |
|--------|-------------|---------|
| `save(session_id, memory)` | `.Archtech/{project_id}/sessions/{session_id}.json` | Write extracted memory to disk |
| `load(session_id)` | Same | Read memory from disk |
| `clear(session_id)` | Same | Delete memory file |
| `update(session_id, delta)` | Same | Merge new facts, deduplicate |

### CompactSummary

| Method | Purpose |
|--------|---------|
| `get_summary(session_id, old_messages, legacy_fn)` | Returns formatted memory string OR falls back to LLM call |

**Why this matters:** If session memory exists, compaction is free (disk read). If not, it triggers an LLM call to generate a summary — which costs tokens.

---

## Quick Reference: When Each Method Is Called

| Method | Called From | Trigger |
|--------|-------------|---------|
| `create()` | Chat routes | New conversation starts |
| `resume()` | Chat routes | User reconnects |
| `clear()` | Chat routes | User requests new session |
| `discover_active()` | IDE sidebar | Show active conversations |
| `discover_history()` | History panel | Show past sessions |
| `create_generation()` | `/generate` route | User clicks "Generate" |
| `update_progress()` | Each pipeline stage, error handlers | Stage completes, success, or error |
| `log_stage_complete()` | 11 stages in `execute_generation_plan()` | Each stage finishes |
| `log_tool_call()` | LLM query loop | Each tool invocation completes |
| `find_active()` | Cancel route, progress endpoint | Find latest running session |
| `cancel()` | `/cancel` route | User clicks cancel |
| `get_progress()` | `/template-progress` endpoint | Frontend polls every 1.5s |
| `extract()` | After each chat turn | Conversation memory extraction |
| `save()` | After `extract()` | Cache memory to disk |
| `get_summary()` | Auto-compaction | Compress old conversation context |
