# ArchTech Memory & Knowledge Management System — Complete Implementation Plan

## Context

Your ArchTech V5 backend processes PDFs through an 8-stage pipeline to extract requirements. Currently there is no memory layer — every upload is independent, nothing persists across requests, and users have no way to query or explore their extracted data through conversation.

Claude Code manages memory through a three-tier system:
1. **Session memory** — auto-summarizes long conversations into a file (handles context window overflow)
2. **User memory** — typed memories (`user`, `feedback`, `project`, `reference`) stored as `.md` files with frontmatter, indexed by `MEMORY.md`
3. **Project memory** — per-project knowledge base with compaction thresholds

This plan builds an equivalent for ArchTech: **per-project knowledge base** (equivalent to Claude Code's session memory), **per-user memory** (typed memories like Claude Code's memdir), and a **query API** (equivalent to Claude Code's memory recall), all integrated with your existing extraction pipeline.

---

## Claude Code vs ArchTech: Direct Mapping

| Claude Code Concept | ArchTech Equivalent | Key Difference |
|---|---|---|
| `~/.claude/projects/<slug>/memory/` | `backend/memory/projects/<project_id>/` | Same pattern, Python backend |
| Session memory (`session_memory.md`) | `knowledge_base/all_requirements.json` | Text vs JSON |
| `MEMORY.md` index (200 lines / 25KB cap) | `MEMORY.md` index (same 200 lines / 25KB cap) | **Direct port** |
| Typed memories (user, feedback, project, reference) | Same 4 types in `user_memory/<user_id>/memories/*.md` | **Direct port** |
| Forked agent extraction | Synchronous extraction after Stage 8 | Forked agent vs Python function |
| Token threshold (10K-40K) | Doc count threshold (default 10) | Tokens vs doc count |
| CLI interaction (interactive) | HTTP API (REST endpoints) | CLI vs HTTP |
| Lazy loading (read index first) | Lazy loading (read index first) | **Direct port** |
| Per-project isolation | Per-project isolation | **Direct port** |
| Path validation (rejects `../`, root, UNC, null bytes) | Same validation in Python | **Direct port** |

---

## Directory Structure

```
/home/devusr/Mukesh/ArchTech_V5/Backend/backend/
├── memory/                                    # Root memory directory
│   └── projects/                              # Per-project memory (Claude Code's ~/.claude/projects/ equivalent)
│       └── <project_id>/                      # e.g., batch_2e49b875
│           ├── MEMORY.md                      # Entry-point index (max 200 lines / 25KB)
│           ├── knowledge_base/                # Aggregated knowledge (Claude Code's session_memory.md equivalent)
│           │   ├── all_requirements.json      # Union of all doc reqs across all documents
│           │   ├── category_stats.json        # Count per category
│           │   ├── high_confidence.json       # Filtered view (confidence >= 0.7)
│           │   └── compaction_index.json      # Tracks last compaction point (Claude Code's lastSummarizedMessageId equivalent)
│           ├── extracted_docs/                # Per-document requirement files
│           │   ├── doc_A_requirements.json
│           │   ├── doc_B_requirements.json
│           │   └── doc_C_requirements.json
│           ├── session_memory/                # Per-session notes (Claude Code's session memory)
│           │   └── 2026-05-25_143022.md       # Auto-summarized session notes
│           ├── session_logs/                  # Per-extraction session logs
│           │   └── 2026-05-25_143022.log
│           └── config.json                    # Project settings + compaction thresholds
├── user_memory/                               # Per-user persistent memories (Claude Code's memdir equivalent)
│   └── <user_id>/
│       ├── MEMORY.md                          # User's index of memories
│       └── memories/                          # Individual memory files
│           ├── user_role.md                   # Type: user
│           ├── project_context.md             # Type: project
│           ├── feedback_style.md              # Type: feedback
│           └── external_links.md              # Type: reference
└── Memory_Management/                            # New module
    ├── __init__.py
    ├── project_memory.py                      # Knowledge base, compaction, search
    ├── user_memory.py                         # User memory read/write/MEMORY.md
    ├── query_engine.py                        # Search/filter API backend
    ├── conversation.py                        # Chat history per project
    └── helpers.py                             # Truncation, validation, utils
```

---

## Phase 1: Helpers & Utilities (Foundation)

### 1.1 `Memory_Management/helpers.py`

**Purpose:** Common utilities shared across project and user memory. Ported directly from Claude Code's `memdir/memdir.py` and `memdir/paths.py`.

**Functions (ported directly from Claude Code):**

```python
def truncate_content(content: str, max_lines: int = 200, max_bytes: int = 25000) -> dict
    # Truncates to both line AND byte limits
    # Exact same logic as Claude Code's truncateEntrypointContent()
    # Returns {"content": truncated, "was_line_truncated": bool, "was_byte_truncated": bool}

def validate_memory_path(path: str) -> str | None
    # Security validation: rejects relative paths, root paths, UNC paths, null bytes
    # Exact same logic as Claude Code's validateMemoryPath()
    # Returns normalized path or None if invalid

def ensure_directory(dir_path: str) -> None
    # Idempotent directory creation (already exists → no-op)
    # Exact same pattern as Claude Code's ensureMemoryDirExists()

def append_to_md_index(filepath: str, entry: str) -> None
    # Appends a line to a markdown index file
    # Example: appends "- [name] description → type" to MEMORY.md
```

---

## Phase 2: Core — Project Memory & Knowledge Base

### 2.1 `Memory_Management/project_memory.py`

**Purpose:** Manage per-project knowledge base with compaction, search, and auto-summaries. This is the **equivalent of Claude Code's session memory + compaction system**.

**Functions:**

```python
def get_project_memory_dir(project_id: str) -> str
    # Returns: /home/devusr/Mukesh/ArchTech_V5/Backend/backend/memory/projects/<project_id>/
    # Auto-creates all subdirectories if they don't exist (idempotent)
    # Security: validates no path traversal via ../

def save_extracted_requirements(project_id: str, doc_name: str, requirements: list[dict]) -> None
    # Saves to extracted_docs/<doc_name>_requirements.json
    # Updates compaction_index.json: {"docs": [{"doc": "doc_A.pdf", "reqs": 47, "status": "pending"}]}

def load_extracted_requirements(project_id: str, doc_name: str) -> list[dict] | None
    # Returns requirements for a specific doc, or None if not found

def generate_session_summary(project_id: str, doc_name: str, requirements: list[dict]) -> str
    # Generates a condensed summary of extracted requirements
    # Format: "[doc_name.pdf] extracted N requirements: K Hardware, M Software, ..."
    # Writes to session_memory/<timestamp>.md
    # Equivalent to Claude Code's session memory extraction (background forked agent)

def add_to_knowledge_base(project_id: str, requirements: list[dict]) -> None
    # Merges new reqs into knowledge_base/all_requirements.json
    # Deduplicates by text similarity (rapidfuzz token_sort_ratio > 90%)
    # Updates knowledge_base/category_stats.json (e.g., {"Hardware/Power": 12, "Software/Driver": 5})
    # Updates knowledge_base/high_confidence.json (confidence >= 0.7)
    # Updates compaction_index.json to mark doc as "compacted"

def get_all_requirements(project_id: str) -> list[dict]
    # Returns all requirements from ALL documents in the project

def search_requirements(project_id: str, filters: dict) -> list[dict]
    # Supports filters: category, sub_category, min_confidence, doc_name, keyword, has_unit, priority
    # Example: {"category": "Hardware", "min_confidence": 0.7, "keyword": "FPGA"}
    # Returns matching requirements with their source document

def get_category_distribution(project_id: str) -> dict
    # Returns category counts: {"Hardware/Power": 12, "Software/Driver": 5, ...}

def get_extraction_stats(project_id: str) -> dict
    # Returns: {"total_docs": 3, "total_reqs": 89, "last_processed": "2026-05-25T14:30:22Z",
    #           "categories": {"Hardware/Power": 12, ...}, "avg_confidence": 0.82}

def needs_compaction(project_id: str) -> bool
    # Checks compaction_index.json: if more than N docs are "pending"
    # Returns True when knowledge base should be compacted
    # Threshold: configurable in config.json (default: 10 docs)

def compact_project_memory(project_id: str) -> dict
    # Merges all "pending" docs into knowledge base
    # Updates compaction_index.json to mark all as "compacted"
    # Generates session summary for the batch
    # Equivalent to Claude Code's auto-compaction after session memory extraction
```

**Compaction Flow (equivalent to Claude Code's session memory compaction):**

```
Before compaction:
  compaction_index.json:
    {
      "docs": [
        {"doc": "doc_A.pdf", "reqs": 47, "status": "pending"},
        {"doc": "doc_B.pdf", "reqs": 52, "status": "pending"},
        {"doc": "doc_C.pdf", "reqs": 38, "status": "pending"}
      ],
      "pending_count": 3,
      "threshold": 10
    }

When threshold exceeded (>= 10 docs pending):
  1. generate_session_summary() → writes session_memory/2026-05-25_143022.md
  2. add_to_knowledge_base() → merges all 3 docs into all_requirements.json
  3. compact_project_memory() → updates status to "compacted"
  4. Result: knowledge_base/ has aggregated data, per-doc files still exist for source tracking
```

**Integration with extraction pipeline:**
```python
# After Stage 8 dedup completes in PipelineCoordinator.run():
from Memory_Management.project_memory import save_extracted_requirements, generate_session_summary, add_to_knowledge_base

save_extracted_requirements(self.project_id, doc_name, dedup_result)
generate_session_summary(self.project_id, doc_name, dedup_result)
add_to_knowledge_base(self.project_id, dedup_result)
```

---

## Phase 3: Core — User Memory System

### 3.1 `Memory_Management/user_memory.py`

**Purpose:** Per-user persistent memories inspired by Claude Code's memdir system. Four typed memories stored as `.md` files with YAML frontmatter, indexed by `MEMORY.md`.

**Memory types (same as Claude Code):**

| Type | What it stores | Example |
|---|---|---|
| `user` | User's role, preferences, expertise level | "User is a senior FPGA engineer, prefers terse responses" |
| `feedback` | User corrections and approvals | "User said 'don't use Sonnet for this, use Haiku' — save for cost reasons" |
| `project` | Project context not derivable from code | "This project targets Xilinx Kintex UltraScale+, deadline 2026-08-01" |
| `reference` | Pointers to external systems | "Requirements tracked in JIRA project ARCH-2026" |

**Frontmatter format per file:**
```yaml
---
name: user_role
description: "User's role and technical background"
type: user
---

<content>
```

**Functions:**

```python
def get_user_memory_dir(user_id: str) -> str
    # Returns: /home/devusr/Mukesh/ArchTech_V5/Backend/backend/user_memory/<user_id>/
    # Auto-creates directory if needed

def save_user_memory(user_id: str, name: str, content: str, memory_type: str, description: str) -> None
    # Creates/overwrites user_memory/<user_id>/memories/<name>.md
    # Writes frontmatter + content
    # Updates MEMORY.md index with entry

def read_user_memory(user_id: str, name: str) -> dict | None
    # Returns {"content": ..., "type": ..., "description": ...} or None

def delete_user_memory(user_id: str, name: str) -> None
    # Removes .md file and updates MEMORY.md index

def load_all_user_memories(user_id: str) -> list[dict]
    # Reads MEMORY.md, resolves each entry, returns all memories with content
    # Truncated to 200 lines / 25KB (same cap as Claude Code)

def search_user_memories(user_id: str, query: str) -> list[dict]
    # Searches memory content for query string
    # Returns matching memories with snippet

def get_memory_index(user_id: str) -> str
    # Reads and returns the raw MEMORY.md content (for API response)
```

**How MEMORY.md index works (Claude Code pattern):**

Each line is a compact reference:
```markdown
- [user_role] User's role and technical background → user
- [project_context] Project context and targets → project
- [feedback_style] User feedback on response style → feedback
```

The agent/system reads this index first, then loads specific files as needed.

---

## Phase 4: Query Engine & Conversation

### 4.1 `Memory_Management/query_engine.py`

**Purpose:** Unified search/filter across project knowledge base and user memories. The backend for API queries like "what hardware requirements were extracted?".

**Functions:**

```python
def query_project(project_id: str, query: str, user_id: str | None = None) -> dict
    """
    Main query function. Handles:
    1. Parse query intent (search, list, filter, count, summarize)
    2. Load relevant memories (user preferences, project context)
    3. Search knowledge base with filters derived from query
    4. Return structured response + optionally LLM-generated summary

    Examples:
      "what hardware requirements were extracted?"
        → Returns filtered reqs with category=Hardware

      "how many requirements total?"
        → Returns {"total": 89, "by_category": {"Hardware/Power": 12, ...}}

      "show high-confidence FPGA specs"
        → Returns reqs where (category=Hardware/FPGA) AND (confidence >= 0.7)

      "what do you know about this project?"
        → Returns project memories + extraction stats
    """

def search_requirements_knowledge(project_id: str, term: str) -> list[dict]
    # Searches text, keywords, category fields of all requirements
    # Fuzzy match on text, exact match on category/sub_category/keywords

def get_related_requirements(req: dict, project_id: str, limit: int = 5) -> list[dict]
    # Finds semantically/syntactically similar requirements via rapidfuzz
    # Uses the same matching logic as Stage 8 Dedup (token_sort_ratio)
```

### 4.2 `Memory_Management/conversation.py`

**Purpose:** Store user ↔ system chat history per project for context.

**Functions:**

```python
def get_conversation_path(project_id: str, user_id: str) -> str
    # Returns: memory/<project_id>/conversation_<user_id>.jsonl

def add_message(project_id: str, user_id: str, role: str, content: str, metadata: dict | None = None) -> None
    # Appends JSONL line: {"role": "user", "content": "...", "timestamp": "2026-05-25T14:30:22Z"}

def get_conversation(project_id: str, user_id: str, last_n: int = 20) -> list[dict]
    # Returns last N messages from conversation

def clear_conversation(project_id: str, user_id: str) -> None
    # Deletes the conversation file
```

**Conversation history format (`*.jsonl`):**
```jsonl
{"role": "user", "content": "What hardware requirements were extracted?", "timestamp": "2026-05-25T14:30:22Z", "metadata": {"project_id": "batch_abc123", "user_id": "user_001"}}
{"role": "assistant", "content": "23 hardware requirements extracted: 8 Power, 5 FPGA, 5 Memory, 5 Interface", "timestamp": "2026-05-25T14:30:23Z", "metadata": {"response_time_ms": 245, "reqs_shown": 23}}
{"role": "user", "content": "Show me the FPGA ones", "timestamp": "2026-05-25T14:31:00Z"}
{"role": "assistant", "content": "Here are the 5 FPGA requirements...", "timestamp": "2026-05-25T14:31:01Z", "metadata": {"reqs_shown": 5}}
```

---

## Phase 5: API Integration

### 5.1 New API Endpoints

All endpoints require `project_id` in the path. `user_id` is optional for project queries but required for user memory operations.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/{project_id}/query` | Required | Query the project knowledge base |
| `GET` | `/api/{project_id}/requirements` | Required | List/filter extracted requirements |
| `GET` | `/api/{project_id}/stats` | Required | Get extraction statistics |
| `GET` | `/api/{project_id}/documents` | Required | List all processed documents |
| `GET` | `/api/{project_id}/documents/{doc_name}` | Required | Get requirements for a specific document |
| `POST` | `/api/{project_id}/extract` | Required | Trigger document extraction |
| `POST` | `/api/user/{user_id}/memory` | Required | Save a user memory |
| `GET` | `/api/user/{user_id}/memory` | Required | List all user memories |
| `GET` | `/api/user/{user_id}/memory/{name}` | Required | Read a specific user memory |
| `DELETE`| `/api/user/{user_id}/memory/{name}` | Required | Delete a user memory |
| `GET` | `/api/{project_id}/conversation` | Required | Get conversation history |
| `POST` | `/api/{project_id}/conversation` | Required | Add message to conversation |
| `DELETE`| `/api/{project_id}/conversation` | Required | Clear conversation |
| `POST` | `/api/{project_id}/extract/summary` | Required | Get LLM-generated summary of extraction |

### 5.2 Query Endpoint (`POST /api/{project_id}/query`)

**Request body:**
```json
{
  "query": "What hardware requirements were extracted?",
  "filters": {"category": "Hardware", "min_confidence": 0.7},
  "format": "structured",
  "user_id": "user_001",
  "llm_summary": false
}
```

**Response:**
```json
{
  "query": "What hardware requirements were extracted?",
  "total_matches": 23,
  "results": [
    {"id": "HAR-0001", "category": "Hardware/Power", "text": "...", "confidence": 0.85, "source": "doc_A.pdf"},
    ...
  ],
  "stats": {"avg_confidence": 0.82, "categories": {"Power": 8, "FPGA": 5, "Memory": 5, "Interface": 5}}
}
```

### 5.3 Integration with Extraction Pipeline

**File: `backend/extraction_event_loop.py` — `PipelineCoordinator.run()`**

After Stage 8 dedup completes, add:
```python
from Memory_Management.project_memory import save_extracted_requirements, generate_session_summary, add_to_knowledge_base

# After dedup result:
save_extracted_requirements(self.project_id, doc_name, dedup_result)
generate_session_summary(self.project_id, doc_name, dedup_result)
add_to_knowledge_base(self.project_id, dedup_result)
```

**File: `backend/main.py` — FastAPI route handler**

Extract `project_id` from the upload path and pass to extraction loop:
```python
# Route: POST /api/{project_id}/extract
# The project_id from URL path is passed to the extraction loop
results = extraction_loop.run_sync(pdf_path, doc_type, project_id=project_id)
```

---

## Files to Create (6 new files)

| File | Lines | Purpose |
|---|---|---|
| `Memory_Management/__init__.py` | ~30 | Package init, exports public API |
| `Memory_Management/project_memory.py` | ~200 | Per-project doc tracking, knowledge base, search, compaction |
| `Memory_Management/user_memory.py` | ~180 | User memory read/write/MEMORY.md (typed memories) |
| `Memory_Management/query_engine.py` | ~150 | Unified query/search across project + user memory |
| `Memory_Management/conversation.py` | ~80 | Chat history JSONL per project/user |
| `Memory_Management/helpers.py` | ~100 | Truncation, validation, directory creation |

## Files to Modify (2 existing files)

| File | Lines changed | What changes |
|---|---|---|
| `backend/extraction_event_loop.py` | ~10 | Add `Memory_Management.project_memory.save_extracted_requirements()` and `add_to_knowledge_base()` after Stage 8 |
| `backend/main.py` | ~15 | Extract `project_id` from URL path, pass to extraction loop, wire new API endpoints |

---

## Order of Implementation

1. **helpers.py** first — foundation (truncation, validation, mkdir)
2. **project_memory.py** second — core project data storage + compaction
3. **user_memory.py** third — user memory system
4. **conversation.py** fourth — chat history
5. **query_engine.py** fifth — search/filter API backend
6. **API endpoints** sixth — wire up FastAPI routes
7. **Extraction integration** seventh — connect to `PipelineCoordinator`

---

## Verification

1. **Unit tests** — write tests for `helpers.py` (truncation at 200 lines/25KB), `project_memory.py` (save/load/search/compaction), `user_memory.py` (read/write/delete MEMORY.md)
2. **Integration test** — run extraction on test PDF → verify `memory/projects/<id>/` has MEMORY.md, extracted_docs/, knowledge_base/
3. **API test** — POST to `/api/{id}/query` with "hardware requirements" → verify correct filtered results returned
4. **End-to-end** — upload doc A → extract → query "hardware reqs" → upload doc B → extract → query again → verify aggregated results include both docs
5. **User memory test** — POST memory via `/api/user/{id}/memory` → GET back → verify frontmatter + index
