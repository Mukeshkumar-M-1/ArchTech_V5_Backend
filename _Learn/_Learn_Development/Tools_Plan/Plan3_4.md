# Plan: Add 15 Tool Prompts to Match Claude Code CLI

## Context

The backend at `/home/devusr/Mukesh/ArchTech_V5/Backend/backend/tools/builtins/` has 5 tools (FileRead, FileWrite, FileEdit, Bash, Agent) with short descriptions. We need to:
1. **UPDATE** the 5 existing tools with full CCB-style prompts
2. **CREATE** 4 new basic tool files (Glob, Search, TodoWrite, Skill) with CCB prompts
3. **CREATE** 6 new V2 Task tools (TaskCreate, TaskUpdate, TaskList, TaskGet, TaskOutput, TaskStop) with CCB prompts

---

## Step 1: Update 5 Existing Tool Prompts

### 1a. `builtins/file_read.py` — Replace `description=`

```python
description=(
    "Reads a file from the local filesystem. You can access any file directly by using this tool. "
    "Assume this tool is able to read all files on the machine. If the User provides a path to a file "
    "assume that path is valid. It is okay to read a file that does not exist; an error will be returned.\n"
    "- The file_path parameter must be an absolute path, not a relative path\n"
    "- By default, it reads up to 2000 lines starting from the beginning of the file\n"
    "- When you already know which part of the file you need, only read that part\n"
    "- Results are returned using cat -n format, with line numbers starting at 1\n"
    "- This tool can read images (eg PNG, JPG, etc). When reading an image file the contents are "
    "presented visually as Claude Code is a multimodal LLM.\n"
    "- This tool can read PDF files (.pdf). For large PDFs (more than 10 pages), you MUST provide the "
    "pages parameter to read specific page ranges (e.g., pages: '1-5'). Maximum 20 pages per request.\n"
    "- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs.\n"
    "- This tool can only read files, not directories. To read a directory, use an ls command via the Bash tool.\n"
    "- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, "
    "ALWAYS use this tool to view the file at the path.\n"
    "- If you read a file that exists but has empty contents you will receive a system reminder warning."
)
```

### 1b. `builtins/file_write.py` — Replace `description=`

```python
description=(
    "Writes a file to the local filesystem.\n\n"
    "Usage:\n"
    "- This tool will overwrite the existing file if there is one at the provided path.\n"
    "- If this is an existing file, you MUST use the Read tool first to read the file's contents. "
    "This tool will fail if you did not read the file first.\n"
    "- Prefer the Edit tool for modifying existing files — it only sends the diff. "
    "Only use this tool to create new files or for complete rewrites.\n"
    "- NEVER create documentation files (*.md) or README files unless explicitly requested by the User.\n"
    "- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked."
)
```

### 1c. `builtins/file_edit.py` — Replace `description=`

```python
description=(
    "Performs exact string replacements in files.\n\n"
    "Usage:\n"
    "- You must use the Read tool at least once in the conversation before editing. "
    "This tool will error if you attempt an edit without reading the file.\n"
    "- When editing text from Read tool output, ensure you preserve the exact indentation "
    "(tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: "
    "spaces + line number + arrow. Everything after that is the actual file content to match. "
    "Never include any part of the line number prefix in the old_string or new_string.\n"
    "- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.\n"
    "- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.\n"
    "- The edit will FAIL if old_string is not unique in the file. Either provide a larger string "
    "with more surrounding context to make it unique or use replace_all to change every instance.\n"
    "- Use replace_all for replacing and renaming strings across the file. This parameter is useful "
    "if you want to rename a variable for instance."
)
```

### 1d. `builtins/bash.py` — Replace `description=`

```python
description=(
    "Executes a given bash command and returns its output.\n\n"
    "IMPORTANT: Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` "
    "commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. "
    "Instead, use the appropriate dedicated tool:\n"
    "- File search: Use Glob (NOT find or ls)\n"
    "- Content search: Use Search (NOT grep or rg)\n"
    "- Read files: Use Read (NOT cat/head/tail)\n"
    "- Edit files: Use Edit (NOT sed/awk)\n"
    "- Write files: Use Write (NOT echo >/cat <<EOF)\n"
    "- Communication: Output text directly (NOT echo/printf)\n\n"
    "Instructions:\n"
    "- If your command will create new directories or files, first run ls to verify the parent directory exists.\n"
    "- Always quote file paths that contain spaces with double quotes.\n"
    "- Try to maintain current working directory by using absolute paths and avoiding cd.\n"
    "- You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes).\n"
    "- You can use run_in_background to run commands asynchronously.\n"
    "- When issuing multiple commands: parallel independent commands, chain dependent ones with &&.\n"
    "- For git commands: NEVER skip hooks, NEVER run destructive commands without explicit request, "
    "create NEW commits (not amend).\n"
    "- Avoid unnecessary sleep commands — just run commands that can execute immediately."
)
```

### 1e. `builtins/agent.py` — Replace `description=`

```python
description=(
    "Launch a new agent to handle complex, multi-step tasks autonomously. "
    "Each agent type has specific capabilities and tools available to it.\n\n"
    "When using the Agent tool, specify a subagent_type: general-purpose, explore, or plan.\n\n"
    "When NOT to use:\n"
    "- If you want to read a specific file path, use the Read tool instead.\n"
    "- If you are searching for specific content, use Glob or Search instead.\n"
    "- If you are searching within 2-3 specific files, use the Read tool.\n\n"
    "Usage notes:\n"
    "- Always include a short description (3-5 words) summarizing what the agent will do.\n"
    "- You can run agents in the background using run_in_background — you will be automatically "
    "notified when it completes. Do NOT sleep, poll, or proactively check.\n"
    "- Foreground (default): use when you need the agent's results before proceeding.\n"
    "- Background: use when you have genuinely independent work to do in parallel.\n"
    "- Launch multiple agents concurrently whenever possible for parallel tasks.\n"
    "- The agent's outputs should generally be trusted.\n"
    "- Clearly tell the agent whether to write code or just do research.\n"
    "- If the agent description mentions that it should be used proactively, use it without being asked."
)
```

---

## Step 2: Create 4 New Basic Tool Files

### 2a. `builtins/glob.py` (NEW)

```python
Glob = ToolDefinition(
    name="Glob",
    description=(
        "Fast file pattern matching tool that works with any codebase size.\n"
        "Supports glob patterns like '**/*.js' or 'src/**/*.ts'.\n"
        "Returns matching file paths sorted by modification time.\n"
        "Use this tool when you need to find files by name patterns.\n"
        "When you are doing an open ended search that may require multiple rounds "
        "of globbing and grepping, use the Agent tool instead."
    ),
    input_schema=GlobInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2b. `builtins/search.py` (NEW)

```python
Search = ToolDefinition(
    name="Search",
    description=(
        "A powerful search tool built on ripgrep.\n\n"
        "ALWAYS use Search for search tasks. NEVER invoke `grep` or `rg` as a Bash command. "
        "The Search tool has been optimized for correct permissions and access.\n"
        "- Supports full regex syntax (e.g., 'log.*Error', 'function\\\\s+\\\\w+')\n"
        "- Filter files with glob parameter (e.g., '*.js', '**/*.tsx')\n"
        "- Output modes: 'content' shows matching lines, "
        "'files_with_matches' shows only file paths (default), "
        "'count' shows match counts\n"
        "- Use Agent tool for open-ended searches requiring multiple rounds\n"
        "- Pattern syntax uses ripgrep — literal braces need escaping "
        "(use 'interface\\\\{\\\\}' to find 'interface{}' in Go code)\n"
        "- Multiline matching: default is single-line only. "
        "For cross-line patterns, use multiline: true"
    ),
    input_schema=GrepInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2c. `builtins/todo_write.py` (NEW)

CCB V1 TodoWrite (in-memory, flat list) — simpler, matches existing backend architecture:

```python
TodoWrite = ToolDefinition(
    name="TodoWrite",
    description=(
        "Use this tool to create and manage a structured task list for your current coding session.\n\n"
        "## When to Use:\n"
        "1. Complex multi-step tasks (3+ distinct steps)\n"
        "2. Non-trivial and complex tasks requiring planning\n"
        "3. User explicitly requests todo list\n"
        "4. User provides multiple tasks (numbered or comma-separated)\n"
        "5. After receiving new instructions — immediately capture as todos\n"
        "6. When you start working — mark in_progress BEFORE beginning\n"
        "7. After completing — mark completed, add any new follow-up tasks\n\n"
        "## When NOT to Use:\n"
        "1. Single straightforward task\n"
        "2. Trivial task with no organizational benefit\n"
        "3. Task completable in less than 3 trivial steps\n"
        "4. Purely conversational or informational\n\n"
        "## Task States and Management:\n"
        "- States: pending, in_progress, completed\n"
        "- Exactly ONE task must be in_progress at a time\n"
        "- Update status in real-time as you work\n"
        "- Mark tasks complete IMMEDIATELY after finishing\n"
        "- ALWAYS provide both content (imperative form) "
        "and activeForm (present continuous form) for each task"
    ),
    input_schema=TodoWriteInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2d. `builtins/skill.py` (NEW)

```python
Skill = ToolDefinition(
    name="Skill",
    description=(
        "Execute a skill within the main conversation.\n\n"
        "When users ask you to perform tasks, check if any of the available skills match. "
        "Skills provide specialized capabilities and domain knowledge.\n\n"
        "When users reference a slash command or '/<something>' "
        "(e.g., '/commit', '/review-pr'), they are referring to a skill. "
        "Use this tool to invoke it.\n\n"
        "How to invoke:\n"
        "- skill: 'pdf' — invoke the pdf skill\n"
        "- skill: 'commit', args: '-m Fix bug' — invoke with arguments\n"
        "- skill: 'review-pr', args: '123' — invoke with arguments\n"
        "- skill: 'ms-office-suite:pdf' — invoke using fully qualified name\n\n"
        "Important:\n"
        "- Available skills are listed in system-reminder messages.\n"
        "- When a skill matches, this is a BLOCKING REQUIREMENT: "
        "invoke the Skill tool BEFORE generating any other response.\n"
        "- NEVER mention a skill without actually calling this tool.\n"
        "- Do not invoke a skill that is already running.\n"
        "- Do not use this tool for built-in CLI commands (/help, /clear, etc.).\n"
        "- If you see a <command-name> tag, the skill is ALREADY loaded — "
        "follow the instructions directly instead of calling again."
    ),
    input_schema=SkillInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

---

## Step 3: Create 6 V2 Task Management Tool Files

### 3a. `builtins/task_create.py` (NEW)

```python
TaskCreate = ToolDefinition(
    name="TaskCreate",
    description=(
        "Use this tool to create a structured task list for your current coding session.\n\n"
        "## When to Use:\n"
        "- Complex multi-step tasks (3+ distinct steps)\n"
        "- Non-trivial and complex tasks requiring planning\n"
        "- Plan mode — when using plan mode, create a task list to track the work\n"
        "- User explicitly requests todo list\n"
        "- User provides multiple tasks (numbered or comma-separated)\n"
        "- After receiving new instructions — immediately capture as tasks\n"
        "- When you start working — mark in_progress BEFORE beginning\n"
        "- After completing — mark completed, add new follow-up tasks\n\n"
        "## When NOT to Use:\n"
        "- Single straightforward task\n"
        "- Trivial task with no organizational benefit\n"
        "- Task completable in less than 3 trivial steps\n"
        "- Purely conversational or informational\n\n"
        "## Task Fields\n"
        "- **subject**: A brief, actionable title in imperative form "
        "(e.g., 'Fix authentication bug in login flow')\n"
        "- **description**: What needs to be done\n"
        "- **activeForm** (optional): Present continuous form shown in the spinner "
        "when in_progress (e.g., 'Fixing authentication bug')\n"
        "- All tasks are created with status 'pending'\n\n"
        "## Tips\n"
        "- Create tasks with clear, specific subjects that describe the outcome\n"
        "- After creating tasks, use TaskUpdate to set up dependencies (blocks/blockedBy)\n"
        "- Check TaskList first to avoid creating duplicate tasks"
    ),
    input_schema=TaskCreateInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=False,
)
```

**Input Schema:**
```python
class TaskCreateInput(BaseModel):
    subject: str = Field(..., description="Brief actionable title in imperative form")
    description: str = Field(..., description="What needs to be done")
    activeForm: Optional[str] = Field(None, description="Present continuous for spinner")
    metadata: Optional[dict] = Field(None, description="Arbitrary metadata")
```

### 3b. `builtins/task_update.py` (NEW)

```python
TaskUpdate = ToolDefinition(
    name="TaskUpdate",
    description=(
        "Use this tool to update a task in the task list.\n\n"
        "## When to Use:\n"
        "**Mark tasks as resolved:**\n"
        "- When you have completed the work described in a task\n"
        "- When a task is no longer needed or has been superseded\n"
        "- Always mark your assigned tasks as resolved when you finish them\n"
        "- After resolving, call TaskList to find your next task\n"
        "- ONLY mark a task as completed when you have FULLY accomplished it\n"
        "- If you encounter errors, blockers, or cannot finish, keep the task as in_progress\n"
        "- When blocked, create a new task describing what needs to be resolved\n"
        "- Never mark completed if: tests failing, implementation partial, "
        "unresolved errors, missing files\n\n"
        "**Delete tasks:**\n"
        "- When a task is no longer relevant or was created in error\n"
        "- Setting status to 'deleted' permanently removes the task\n\n"
        "**Update task details:**\n"
        "- When requirements change or become clearer\n"
        "- When establishing dependencies between tasks\n\n"
        "## Fields You Can Update\n"
        "- **status**: pending, in_progress, completed, deleted\n"
        "- **subject**: New title (imperative form)\n"
        "- **description**: New description\n"
        "- **activeForm**: Present continuous for spinner\n"
        "- **owner**: Change task owner (agent name)\n"
        "- **metadata**: Merge metadata keys (null deletes key)\n"
        "- **addBlocks**: Mark tasks that cannot start until this completes\n"
        "- **addBlockedBy**: Mark tasks that must complete before this can start\n\n"
        "## Status Workflow\n"
        "pending → in_progress → completed | deleted\n\n"
        "## Staleness\n"
        "Make sure to read a task's latest state using TaskGet before updating it.\n\n"
        "## Examples\n"
        "json: {\"taskId\": \"1\", \"status\": \"in_progress\"}\n"
        "json: {\"taskId\": \"1\", \"status\": \"completed\"}\n"
        "json: {\"taskId\": \"1\", \"status\": \"deleted\"}\n"
        "json: {\"taskId\": \"1\", \"owner\": \"my-name\"}\n"
        "json: {\"taskId\": \"2\", \"addBlockedBy\": [\"1\"]}"
    ),
    input_schema=TaskUpdateInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=False,
)
```

**Input Schema:**
```python
class TaskUpdateInput(BaseModel):
    taskId: str = Field(..., description="Task ID to update")
    subject: Optional[str] = None
    description: Optional[str] = None
    activeForm: Optional[str] = None
    status: Optional[str] = Field(None, description="pending | in_progress | completed | deleted")
    addBlocks: Optional[list] = None
    addBlockedBy: Optional[list] = None
    owner: Optional[str] = None
    metadata: Optional[dict] = None
```

### 3c. `builtins/task_list.py` (NEW)

```python
TaskList = ToolDefinition(
    name="TaskList",
    description=(
        "Use this tool to list all tasks in the task list.\n\n"
        "## When to Use:\n"
        "- To see what tasks are available to work on (pending, no owner, not blocked)\n"
        "- To check overall progress on the project\n"
        "- To find tasks that are blocked and need dependencies resolved\n"
        "- Before assigning tasks to teammates, to see what's available\n"
        "- After completing a task, to check for newly unblocked work or claim the next task\n"
        "- Prefer working on tasks in ID order (lowest ID first) when multiple are available\n\n"
        "## Output\n"
        "Returns a summary of each task:\n"
        "- **id**: Task identifier (use with TaskGet, TaskUpdate)\n"
        "- **subject**: Brief description of the task\n"
        "- **status**: 'pending', 'in_progress', or 'completed'\n"
        "- **owner**: Agent ID if assigned, empty if available\n"
        "- **blockedBy**: List of open task IDs that must be resolved first\n"
        "\nUse TaskGet with a specific task ID to view full details."
    ),
    input_schema=TaskListInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,  # read-only
)
```

### 3d. `builtins/task_get.py` (NEW)

```python
TaskGet = ToolDefinition(
    name="TaskGet",
    description=(
        "Use this tool to retrieve a task by its ID from the task list.\n\n"
        "## When to Use:\n"
        "- When you need the full description and context before starting work on a task\n"
        "- To understand task dependencies (what it blocks, what blocks it)\n"
        "- After being assigned a task, to get complete requirements\n\n"
        "## Output\n"
        "Returns full task details:\n"
        "- **subject**: Task title\n"
        "- **description**: Detailed requirements and context\n"
        "- **status**: 'pending', 'in_progress', or 'completed'\n"
        "- **blocks**: Tasks waiting on this one to complete\n"
        "- **blockedBy**: Tasks that must complete before this one can start\n\n"
        "## Tips\n"
        "- After fetching a task, verify its blockedBy list is empty before beginning work.\n"
        "- Use TaskList to see all tasks in summary form."
    ),
    input_schema=TaskGetInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,  # read-only
)
```

**Input Schema:**
```python
class TaskGetInput(BaseModel):
    taskId: str = Field(..., description="The ID of the task to retrieve")
```

### 3e. `builtins/task_output.py` (NEW)

```python
TaskOutput = ToolDefinition(
    name="TaskOutput",
    description=(
        "- Retrieves output from a running or completed task (background shell, agent, or remote session)\n"
        "- Takes a task_id parameter identifying the task\n"
        "- Returns the task output along with status information\n"
        "- Use block=true (default) to wait for task completion\n"
        "- Use block=false for non-blocking check of current status\n"
        "- Task IDs can be found using the /tasks command\n"
        "- Works with all task types: background shells, async agents, and remote sessions"
    ),
    input_schema=TaskOutputInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

**Input Schema:**
```python
class TaskOutputInput(BaseModel):
    task_id: str = Field(..., description="The task ID to get output from")
    block: bool = Field(True, description="Whether to wait for completion")
    timeout: int = Field(30000, description="Max wait time in ms (0-600000)")
```

### 3f. `builtins/task_stop.py` (NEW)

```python
TaskStop = ToolDefinition(
    name="TaskStop",
    description=(
        "- Stops a running background task by its ID\n"
        "- Takes a task_id parameter identifying the task to stop\n"
        "- Returns a success or failure status\n"
        "- Use this tool when you need to terminate a long-running task"
    ),
    input_schema=TaskStopInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=False,
)
```

**Input Schema:**
```python
class TaskStopInput(BaseModel):
    task_id: Optional[str] = Field(None, description="The task ID to stop")
```

---

## Step 4: Add All Input Models

**File:** `models.py` — Append all new classes:

```python
class GlobInput(BaseModel):
    pattern: str = Field(..., description="Glob pattern like **/*.ts or src/**/*.py")
    path: Optional[str] = Field(None, description="Directory to search in (defaults to CWD)")

class GrepInput(BaseModel):
    pattern: str = Field(..., description="Regex pattern to search for")
    path: Optional[str] = Field(None, description="File or directory to search in")
    glob: Optional[str] = Field(None, description="Glob filter like *.js")
    output_mode: Optional[str] = Field("files_with_matches", description="content | files_with_matches | count")

class TodoWriteInput(BaseModel):
    todos: list[dict] = Field(..., description="Tasks with content, status, activeForm")

class SkillInput(BaseModel):
    skill: str = Field(..., description="Skill name (e.g., 'review', 'simplify')")
    args: Optional[str] = Field(None, description="Optional arguments")

class TaskCreateInput(BaseModel):
    subject: str = Field(..., description="Brief actionable title in imperative form")
    description: str = Field(..., description="What needs to be done")
    activeForm: Optional[str] = Field(None, description="Present continuous for spinner")
    metadata: Optional[dict] = Field(None, description="Arbitrary metadata")

class TaskUpdateInput(BaseModel):
    taskId: str = Field(..., description="Task ID to update")
    subject: Optional[str] = None
    description: Optional[str] = None
    activeForm: Optional[str] = None
    status: Optional[str] = Field(None, description="pending | in_progress | completed | deleted")
    addBlocks: Optional[list] = None
    addBlockedBy: Optional[list] = None
    owner: Optional[str] = None
    metadata: Optional[dict] = None

class TaskListInput(BaseModel):
    pass

class TaskGetInput(BaseModel):
    taskId: str = Field(..., description="The ID of the task to retrieve")

class TaskOutputInput(BaseModel):
    task_id: str = Field(..., description="The task ID to get output from")
    block: bool = Field(True, description="Whether to wait for completion")
    timeout: int = Field(30000, description="Max wait time in ms")

class TaskStopInput(BaseModel):
    task_id: Optional[str] = Field(None, description="The task ID to stop")
```

---

## Step 5: Register All New Tools

**File:** `builtins/__init__.py` — Add all imports and registration:

```python
from .glob import Glob
from .search import Search
from .todo_write import TodoWrite
from .skill import Skill
from .task_create import TaskCreate
from .task_update import TaskUpdate
from .task_list import TaskList
from .task_get import TaskGet
from .task_output import TaskOutput
from .task_stop import TaskStop

__all__ = [..., "Glob", "Search", "TodoWrite", "Skill",
           "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskOutput", "TaskStop"]

for _tool in [..., Glob, Search, TodoWrite, Skill,
             TaskCreate, TaskUpdate, TaskList, TaskGet, TaskOutput, TaskStop]:
    registry.register(_tool)
```

---

## Step 6: Update Executor Model Map

**File:** `executor.py` — Add all new tools:

```python
model_map = {
    ...
    "Glob": tool_models.GlobInput,
    "Search": tool_models.GrepInput,
    "TodoWrite": tool_models.TodoWriteInput,
    "Skill": tool_models.SkillInput,
    "TaskCreate": tool_models.TaskCreateInput,
    "TaskUpdate": tool_models.TaskUpdateInput,
    "TaskList": tool_models.TaskListInput,
    "TaskGet": tool_models.TaskGetInput,
    "TaskOutput": tool_models.TaskOutputInput,
    "TaskStop": tool_models.TaskStopInput,
}
```

---

## Files Modified / Created (16 total)

| File | Action |
|------|--------|
| `builtins/file_read.py` | UPDATE description |
| `builtins/file_write.py` | UPDATE description |
| `builtins/file_edit.py` | UPDATE description |
| `builtins/bash.py` | UPDATE description |
| `builtins/agent.py` | UPDATE description |
| `builtins/glob.py` | CREATE |
| `builtins/search.py` | CREATE |
| `builtins/todo_write.py` | CREATE |
| `builtins/skill.py` | CREATE |
| `builtins/task_create.py` | CREATE |
| `builtins/task_update.py` | CREATE |
| `builtins/task_list.py` | CREATE |
| `builtins/task_get.py` | CREATE |
| `builtins/task_output.py` | CREATE |
| `builtins/task_stop.py` | CREATE |
| `builtins/__init__.py` | UPDATE imports + registration |
| `models.py` | UPDATE add 10 new classes |
| `executor.py` | UPDATE model map |

---

## Task Memory Management (How Tasks Are Stored)

CCB manages task memory in **two systems** — V1 (TodoWrite) and V2 (TaskCreate/Update/...). Here's how each works:

### V1: TodoWrite — In-Memory, Flat List

**Storage:** `appState.todos` — a Python dict keyed by session/agent ID.

```python
# Internal state (equivalent of CCB's appState.todos)
todos_by_session: dict[str, list[dict]] = {
    "session_abc123": [
        {"content": "Fix auth bug", "status": "pending", "activeForm": "Fixing auth bug"},
        {"content": "Write tests", "status": "pending", "activeForm": "Writing tests"},
    ]
}
```

**How it works:**
1. **TodoWrite replaces the entire list atomically** — you pass the full updated list, it overwrites the old one
2. **Validation:** Each todo must have `content`, `status` (pending/in_progress/completed), `activeForm`
3. **Single in_progress rule:** Exactly one task must be `in_progress` at a time
4. **Auto-clear:** When all todos are completed, the entire list is cleared
5. **No persistence:** Lost on restart — lives only in memory
6. **No dependencies:** Flat list, no concept of blocks/blockedBy

**Prompt tells the agent:** "When you start working — mark in_progress BEFORE beginning", "Mark tasks complete IMMEDIATELY after finishing", "Exactly ONE task must be in_progress at a time."

---

### V2: TaskCreate/Update/List/Get/Output/Stop — File-Based, Graph-Based

**Storage:** Disk files under `~/.claude/tasks/` (JSON files with file locking).

```
~/.claude/tasks/
  session_abc123/
    task_001.json   ← {id, subject, description, status, blocks, blockedBy, owner, metadata}
    task_002.json
    task_003.json
    index.json      ← {list of task IDs, sorted by ID order}
```

**How each tool manages memory:**

| Tool | Memory Operation |
|------|-----------------|
| **TaskCreate** | Creates a new JSON file in `~/.claude/tasks/{session_id}/task_XXX.json`, appends ID to `index.json`, returns `{task: {id, subject}}`. Status defaults to `pending`. |
| **TaskGet** | Reads the specific task JSON file by ID, returns full details including `blocks` and `blockedBy` arrays. |
| **TaskList** | Reads `index.json`, loads each task file, returns summary: `{id, subject, status, owner, blockedBy}`. Sorted by ID order. |
| **TaskUpdate** | Reads task file, validates transition (`pending → in_progress → completed` or `deleted`), writes updated JSON, fires `taskCompleted` hooks if status changed to completed, fires `taskCreated` hooks if first creation. Can update: status, subject, description, owner, metadata, addBlocks, addBlockedBy. |
| **TaskOutput** | Reads the task's output file from disk (separate from task metadata). Supports `block=true` to wait, or `block=false` for non-blocking check. |
| **TaskStop** | Sends termination signal to the running subprocess/agent for the given task_id. |

**Key differences from V1:**

| Aspect | V1 (TodoWrite) | V2 (TaskCreate/Update) |
|--------|---------------|----------------------|
| Storage | In-memory `appState.todos` | JSON files on disk |
| Persistence | Lost on restart | Survives restarts |
| Structure | Flat list | Graph with `blocks`/`blockedBy` |
| Mutation | Atomic full-list replace | Individual CRUD operations |
| Ownership | No concept | Owner field for agent/team |
| Dependencies | None | Full dependency graph |
| Hooks | Verification nudge | `taskCreated`, `taskCompleted` hooks |
| Concurrency | Single-process only | File locking for multi-agent |
| Task lifecycle | Auto-cleared when all done | `deleted` status, tasks persist |

**V2 status workflow:** `pending → in_progress → completed` or `deleted`. The `deleted` status permanently removes the task from the active list but the file remains (for history).

**Task memory in the QueryLoop:** The `QueryLoop` (in `query_loop.py`) manages conversation messages through `MessageManager`, which handles token budgeting and context collapse. The task list (V1 or V2) is separate — it's stored in state and passed to `TodoWrite` or `TaskCreate` via tool calls, not embedded in conversation messages. The task list acts as an **external memory** that the LLM reads/writes via tool calls each turn.

---

## Verification

1. `python -c "from tools.registry import registry; print([t.name for t in registry.get_all()])"` → 15 tools
2. Each tool description matches CCB prompt.ts content
3. `python -m tools.test_tools` — all tests pass
4. `QueryLoop.run()` with all tools — end-to-end works
