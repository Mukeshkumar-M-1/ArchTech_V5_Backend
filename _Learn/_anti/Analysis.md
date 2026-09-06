# Backend Tools Architecture Analysis

This document provides a comprehensive analysis of the flow and functions within the `backend/tools/` directory, which orchestrates multi-agent tool execution, memory management, and subagent delegation.

## 1. High-Level Execution Flow
The system uses a persistent, reactive loop to interface with the LLM, validate tool requests, and manage concurrency.

*   **`query_loop.py` (QueryLoop)**: The core inference engine. It sends messages to the LLM, parses `tool_use` requests, delegates them to the `Executor`, and streams results (via `streaming_api.py`) back to the user. It handles auto-compaction when token limits are reached.
*   **`query_guard.py` (QueryGuard)**: A state machine (`idle` → `dispatching` → `running` → `requires_action`) that ensures only one LLM query runs per session concurrently.
*   **`executor.py` (ToolExecutor)**: Validates incoming LLM tool calls against schemas defined in `models.py`, checks execution permissions, and formats exceptions into structural tool results that the LLM can understand.
*   **`registry.py` (ToolRegistry)**: A centralized registry containing `ToolDefinition` objects (schemas, safety flags, and execution callbacks) for every available tool.
*   **`concurrency.py` (ConcurrencyManager)**: Partitions a list of LLM tool calls into batches. "Concurrency safe" tools (e.g., `FileRead`, `Glob`) are executed in parallel, while unsafe tools (e.g., `Bash`, `FileWrite`) are run serially.

## 2. Context Isolation & Subagent Orchestration
To prevent state leakage between concurrently running agents (like a planner and an explorer), the system uses context-based isolation.

*   **`context_isolation.py`**: Uses Python `contextvars` to provide isolated execution contexts (`AgentContext`). Each agent gets its own message manager, token tracker, and task store.
*   **`agent_spawner.py` (AgentSpawner)**: The orchestration layer for subagents. It creates isolated `AgentContext`s, initializes the appropriate system prompt for the subagent type (`explore`, `plan`, `general-purpose`), and manages the lifecycle of the child agent.
*   **`agent_cleanup.py` (AgentCleaner)**: Responsible for rigorous teardown. When an agent finishes or crashes, this module cancels running `asyncio` tasks, closes transcript writers, and clears token trackers.
*   **`abort_controller.py`**: Implements a hierarchical cancellation system (similar to JavaScript's `AbortController`). If a parent agent is stopped, the signal cascades to all child agents.
*   **`agent_mailbox.py` (MailboxManager)**: A file-based message passing system (`.jsonl` with `fcntl` locks) allowing concurrent agents to send asynchronous messages (e.g., `shutdown_request`, `text`) to one another.

## 3. Session, Memory, and Token Management
The system heavily optimizes context windows to prevent the LLM from running out of tokens during long, multi-step coding sessions.

*   **`compaction.py` (CompactPipeline)**: A three-tier pipeline that runs every turn to manage the context window:
    1.  **SnipCompact**: Truncates large file contents from old tool results if the message count exceeds 30.
    2.  **MicroCompact**: Replaces very old tool results with placeholders, preserving only the most recent context.
    3.  **AutoCompact**: An emergency fallback that summarizes older conversations when the token budget is exceeded.
*   **`session_memory.py` (SessionMemoryExtractor)**: Scans each conversation turn to extract reusable facts (file paths, function names, key decisions). This "cached memory" is injected during `AutoCompact` to preserve critical context without making an extra LLM summarizing call.
*   **`message_manager.py` (MessageManager)**: Normalizes incoming/outgoing messages and prepends the dynamically built system prompt.
*   **`session_manager.py` & `chat_sessions.py`**: Manages the persistence of sessions. It uses PID files to track active CLI agents and JSON/JSONL files to store complete chat transcripts and metadata under `.Archtech/<project_id>/`.
*   **`system_prompt.py` (SystemPromptManager)**: Assembles the system prompt dynamically using cached static blocks (rules, tools) and dynamic blocks (git status, session memory, current MCP instructions).
*   **`token_tracker.py`**: A thread-safe accumulator that tracks input, output, and total token usage across API turns.

## 4. Error Recovery & Governance
*   **`error_recovery.py` (ErrorRecovery)**: Implements robust failure handling:
    *   **API Retry**: Exponential backoff for rate limits and timeouts.
    *   **Model Fallback**: Automatically downgrades models (e.g., Opus → Sonnet) if the primary model returns a 529 Overloaded error.
    *   **Output Token Recovery**: If the LLM hits its output token limit mid-thought, it injects a system message instructing the LLM to continue exactly where it left off without apologizing.
*   **`permission.py` (PermissionChecker)**: Enforces `PermissionMode` (`FULL_AUTO`, `REQUIRE_PROMPT`, `SKIP`). Safe tools are auto-allowed, while destructive tools require user consent.

## 5. Built-in Tools (`backend/tools/builtins/`)
The tools provided to the LLM, registered via `models.py` Pydantic schemas:

### File System & Search
*   **`file_read.py` / `file_write.py` / `file_edit.py`**: Standard file operations. `FileRead` handles massive files by truncating them to 100k characters. `FileWrite` uses atomic temporary files. `FileEdit` does precise line-range replacements.
*   **`glob.py`**: Fast directory traversal and pattern matching (`**/*.py`) returning files sorted by modification time.
*   **`search.py`**: Regex content search across the codebase (emulating `ripgrep`).

### Execution & Agentic Tools
*   **`bash.py`**: Executes shell commands via `asyncio.create_subprocess_shell`. Includes timeouts and safety warnings against using it for file editing.
*   **`agent.py`**: The LLM-facing tool to invoke `AgentSpawner`.
*   **`send_message.py`**: Uses `agent_mailbox.py` to send messages to other agents.
*   **`skill.py`**: Dynamically loads markdown-based instruction files (`SKILL.md`) from the `.claude/skills` directory, allowing domain-specific capabilities to be injected into the prompt.

### Task Tracking (The Todo System)
A comprehensive task management system to help the agent track multi-step goals.
*   **`task_state.py` & `tasks.py`**: Defines the lifecycle (`PENDING` → `RUNNING` → `COMPLETED`/`FAILED`/`KILLED`) and holds the global (or context-isolated) `TaskStore`.
*   **`task_create.py`, `task_update.py`, `task_get.py`, `task_list.py`**: Tools for the LLM to create, update dependencies (blocking tasks), and view the project board.
*   **`task_output.py`**: Retrieves the output of completed tasks or polls running background agents.
*   **`task_stop.py`**: Sends a kill signal to running background `asyncio` tasks.
*   **`todo_write.py`**: A simpler, flat-list task tracker (v1 implementation) used for linear steps.
