# Plan: Add Missing Tool Prompts to Backend Agent System

## Context

The backend at `/home/devusr/Mukesh/ArchTech_V5/Backend/backend/tools/builtins/` has 5 tool implementations (FileRead, FileWrite, FileEdit, Bash, Agent), but their descriptions/prompts are **short and incomplete** compared to Claude Code CLI's `prompt.ts` files. The user wants to check all 9 tool prompts against the CCB source and update any that are missing or inadequate.

## Audit: CCB vs Backend Prompts

| Tool | CCB prompt.ts exists? | Backend has prompt? | Backend prompt quality | Action needed |
|------|----------------------|---------------------|----------------------|---------------|
| **FileRead** | Yes (detailed, ~250 chars) | Yes (1 line, short) | Short/incomplete | **UPDATE** — copy full CCB prompt |
| **FileWrite** | Yes (detailed, ~200 chars) | Yes (1 line, short) | Short/incomplete | **UPDATE** — copy full CCB prompt |
| **FileEdit** | Yes (detailed, ~300 chars) | Yes (1 line, short) | Short/incomplete | **UPDATE** — copy full CCB prompt |
| **Glob** | Yes (~200 chars) | **NO** file exists | N/A | **CREATE** file + prompt |
| **Grep** | Yes (~300 chars) | **NO** file exists | N/A | **CREATE** file + prompt |
| **Bash** | Yes (very long, ~370 lines) | Yes (short desc) | Short/incomplete | **UPDATE** — copy full CCB prompt |
| **Agent** | Yes (~280 lines) | Yes (1 line, short) | Short/incomplete | **UPDATE** — copy key parts of CCB prompt |
| **TodoWrite** | Yes (~180 lines) | **NO** file exists | N/A | **CREATE** file + prompt |
| **Skill** | Yes (~220 lines) | **NO** file exists | N/A | **CREATE** file + prompt |

## Summary
- **3 tools need full prompt replacement**: FileRead, FileWrite, FileEdit (current prompts are 1-liners)
- **1 tool needs major prompt expansion**: Bash (currently short, CCB has 370 lines)
- **1 tool needs partial prompt update**: Agent (currently 1 line, CCB has 280 lines)
- **4 tools need new files**: Glob, Grep, TodoWrite, Skill

---

## Step 1: Update Prompts for Existing Tools

### 1a. FileRead — Replace short description with CCB prompt

**File:** `builtins/file_read.py`

Current:
```python
description="Read the complete contents of a text file..."
```

Replace with full CCB prompt (from `FileReadTool/prompt.ts`):
```
Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine.
- The file_path parameter must be an absolute path
- By default, it reads up to 2000 lines
- You can specify offset and limit for targeted reads
- Results are returned using cat -n format with line numbers
- This tool can read images (PNG, JPG, etc) — presented visually
- This tool can read PDF files (.pdf) — for large PDFs (>10 pages), provide the pages parameter
- This tool can read Jupyter notebooks (.ipynb) — returns all cells with outputs
- If you read a file that exists but has empty contents you will receive a warning
```

### 1b. FileWrite — Replace short description with CCB prompt

**File:** `builtins/file_write.py`

Replace with:
```
Writes a file to the local filesystem.
- This tool will overwrite the existing file if there is one
- If this is an existing file, you MUST use the Read tool first to read the file's contents
- Prefer the Edit tool for modifying existing files — it only sends the diff
- NEVER create documentation files (*.md) or README files unless explicitly requested
- Only use emojis if the user explicitly requests it
```

### 1c. FileEdit — Replace short description with CCB prompt

**File:** `builtins/file_edit.py`

Replace with:
```
Performs exact string replacements in files.
- You must use the Read tool at least once before editing — this tool will error if you did not read the file first
- When editing text from Read tool output, preserve the exact indentation after the line number prefix
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it
- The edit will FAIL if old_string is not unique in the file. Either provide a larger string with more context or use replace_all
- Use replace_all for replacing and renaming strings across the file
```

### 1d. Bash — Replace short description with CCB prompt

**File:** `builtins/bash.py`

Replace with key sections from CCB `BashTool/prompt.ts`:
```
Executes a given bash command and returns its output.
- Avoid using this tool to run `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands. Use the appropriate dedicated tool instead.
- File search: Use Glob (NOT find or ls)
- Content search: Use Grep (NOT grep or rg)
- Read files: Use Read (NOT cat/head/tail)
- Edit files: Use Edit (NOT sed/awk)
- Write files: Use Write (NOT echo >/cat <<EOF)
- Always quote file paths with spaces in double quotes
- Try to maintain current working directory by using absolute paths (avoid cd)
- You may specify an optional timeout in milliseconds (up to 600000ms / 10 minutes)
- You can use run_in_background to run commands asynchronously
- When issuing multiple commands: parallel independent commands, chain dependent ones with &&
- For git commands: NEVER skip hooks, NEVER run destructive commands without explicit request, create NEW commits (not amend)
```

### 1e. Agent — Replace short description with CCB prompt

**File:** `builtins/agent.py`

Replace with key sections from CCB `AgentTool/prompt.ts`:
```
Launch a new agent to handle complex, multi-step tasks autonomously.
Each agent type has specific capabilities and tools available to it.
- Specify subagent_type: general-purpose, explore, or plan
- When NOT to use: Use Read for specific file paths, Glob/Grep for searching, Read for 2-3 specific files
- Always include a short description (3-5 words)
- You can run agents in the background using run_in_background — you will be notified when it completes
- Foreground (default): use when you need results before proceeding
- Background: use when you have independent work to do in parallel
- To continue a previously spawned agent, use SendMessage with the agent's ID
- The agent's outputs should generally be trusted
- Clearly tell the agent whether to write code or just do research
- Launch multiple agents concurrently whenever possible for parallel tasks
```

---

## Step 2: Create New Tool Files with CCB Prompts

### 2a. Glob Tool

**File:** `builtins/glob.py` (NEW)

```python
Glob = ToolDefinition(
    name="Glob",
    description="""Fast file pattern matching tool that works with any codebase size.
Supports glob patterns like "**/*.js" or "src/**/*.ts".
Returns matching file paths sorted by modification time.
Use this tool when you need to find files by name patterns.
When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead.""",
    input_schema=GlobInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2b. Search (Grep) Tool

**File:** `builtins/search.py` (NEW)

```python
Search = ToolDefinition(
    name="Search",
    description="""A powerful search tool built on ripgrep.

ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command.
- Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
- Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter
- Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts
- Use Agent tool for open-ended searches requiring multiple rounds
- Pattern syntax uses ripgrep — literal braces need escaping (use \`interface\\{\\}\` to find \`interface{}\` in Go code)
- Multiline matching: default is single-line only. For cross-line patterns, use multiline: true""",
    input_schema=GrepInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2c. TodoWrite Tool

**File:** `builtins/todo_write.py` (NEW)

```python
TodoWrite = ToolDefinition(
    name="TodoWrite",
    description="""Use this tool to create and manage a structured task list for your current coding session.

## When to Use:
1. Complex multi-step tasks (3+ steps)
2. Non-trivial and complex tasks requiring planning
3. User explicitly requests todo list
4. User provides multiple tasks (numbered or comma-separated)
5. After receiving new instructions

## When NOT to Use:
1. Single straightforward task
2. Trivial task with no organizational benefit
3. Task completable in less than 3 trivial steps
4. Purely conversational

## Task States: pending, in_progress, completed
- Exactly ONE task must be in_progress at a time
- Update status in real-time as you work
- Mark tasks complete IMMEDIATELY after finishing
- Provide both content (imperative) and activeForm (present continuous)""",
    input_schema=TodoWriteInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

### 2d. Skill Tool

**File:** `builtins/skill.py` (NEW)

```python
Skill = ToolDefinition(
    name="Skill",
    description="""Execute a skill within the main conversation.

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.

When users reference a slash command or "/<something>" (e.g., "/commit", "/review-pr"), they are referring to a skill. Use this tool to invoke it.

How to invoke:
- skill: "pdf" - invoke the pdf skill
- skill: "commit", args: "-m 'Fix bug'" - invoke with arguments
- skill: "review-pr", args: "123" - invoke with arguments

Important:
- Available skills are listed in system-reminder messages
- When a skill matches, this is a BLOCKING REQUIREMENT: invoke the Skill tool BEFORE any other response
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running
- Do not use for built-in CLI commands (/help, /clear, etc.)
- If you see a <command-name> tag, the skill is ALREADY loaded — follow instructions instead of calling again""",
    input_schema=SkillInput.model_json_schema(),
    execute=_execute,
    is_concurrency_safe=True,
)
```

---

## Step 3: Register Everything

**`builtins/__init__.py`** — Add Glob, Search, TodoWrite, Skill imports and auto-registration.

## Step 4: Update Executor Model Map

**`executor.py`** — Add Glob, Search, TodoWrite, Skill to `_get_pydantic_model`.

## Verification

1. All 9 tools now have detailed prompts matching CCB prompt.ts content
2. `registry.build_tool_defs()` returns full prompts for all tools
3. Unit tests pass
