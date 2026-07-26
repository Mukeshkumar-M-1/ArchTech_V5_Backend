# Backend Tools System — Complete Bug & Issues Report

## Context

This is the `backend/tools/` package — a tool orchestration layer for LLM-powered agentic loops, powering the Template Analysis pipeline. Below is an exhaustive list of every bug, issue, and gap found across all files.

---

## A. CRITICAL BUGS (Will crash or produce wrong behavior at runtime)

### 1. `agent_spawner.py:275` — Wrong class name import
```python
from .abort_controller import AbortControllerHierarchy
```
The class in `abort_controller.py` is named `_AbortHierarchy`, **not** `AbortControllerHierarchy`. This import will raise `ImportError` at runtime, breaking all background agent spawning.

### 2. `agent_spawner.py:281-282` — `global _task_counter` undefined
```python
global _task_counter
_task_counter += 1
```
`_task_counter` is defined in `builtins/tasks.py`, not in `agent_spawner.py`'s module scope. `global _task_counter` declares it in the spawner's module, where it doesn't exist. This raises `UnboundLocalError` at runtime.

### 3. `task_create.py:24,37` — TaskState created but immediately overwritten by plain dict
```python
store.create_task(task_id, description=description or subject)  # Creates TaskState
...
store[task_id] = task  # Overwrites with plain dict {"id": ..., "subject": ...}
```
`TaskStore.create_task()` correctly creates a `TaskState` with lifecycle management. But immediately after, a plain `dict` is assigned to the same key, overwriting the `TaskState`. All lifecycle features (`created_at`, `ttl_seconds`, `retain_flag`, `transition()`) are dead code for every task.

### 4. `task_update.py:49-58` — Status transition enforcement is non-functional
```python
task_state = store.get_task(taskId)  # Returns None (tasks are dicts, not TaskState)
if task_state:  # Never true
    target = _STATUS_MAP.get(status.lower(), TaskStatus.RUNNING)
    if not can_transition(task_state.status, target):  # Dead code
```
Because tasks are stored as dicts (bug #3), `store.get_task()` always returns `None`. The `can_transition()` validation is never reached, so invalid transitions like `pending -> completed` silently succeed.

### 5. `task_update.py:59` — Task state transition and dict update are not synchronized
Even if bug #4 were fixed, line 58 calls `task_state.transition(target)` on the TaskState from the store, but line 59 does `task["status"] = status` on the dict. The two stores would diverge.

### 6. `task_stop.py:33-34` — Potential `None` task, `AttributeError` on `.cancel()`
```python
task = running_tasks[task_id]
task.cancel()  # If task is None (placeholder from agent_spawner.py:284), raises AttributeError
```
Due to bug #2, the placeholder `None` stored at line 284 of `agent_spawner.py` may never be replaced with the real task, causing a crash.

### 7. `query_loop.py:420-523` (`_execute_parallel`) — Parallel execution is completely broken
Multiple bugs in this method:
- **`run_until_complete` in running event loop** (line 489): `loop.run_until_complete(bg_task)` called inside an already-running event loop raises `RuntimeError`.
- **Closure variable capture** (line 471-481): `_run_safe` is defined inside a `for batch in batches:` loop, and the closure captures `batch`, `safe_in_batch`, and `tool_calls` by reference — all will have their final values when the async function executes.
- **Incorrect batch iteration** (line 468): `for t in batch if t.is_concurrency_safe` — `batch` is a `Batch` dataclass with `.blocks`, not an iterable of tool definitions. This will either fail or silently skip all tools.
- **Sync method calling async** (line 483): `_execute_parallel` is a sync method (`def _execute_parallel`, not `async def`) but it creates async tasks inside it.
- **Duplicate message appending** (line 498-502): Parallel results are appended to `full_messages`, but the serial path at lines 507-520 also appends. Results may be added twice.
- **Unused `safe_tools` and `unsafe_tools`** (lines 435-436): Computed but never used.

### 8. `search.py:39` — ReDoS vulnerability
```python
found = re.findall(pattern, content, re.IGNORECASE)
```
User-supplied `pattern` is passed directly to `re.findall()` with no validation, timeout, or escaping. A crafted regex like `(?:(a+)+)b` causes catastrophic backtracking, DoS-ing the entire process.

### 9. `agent_spawner.py:332` — `get_mailbox()` called without required `agent_id` argument
```python
mailbox = get_mailbox()  # Missing agent_id argument
```
`get_mailbox(agent_id)` requires `agent_id`. This silently fails due to the try/except wrapper, so agent mailbox registration never works.

### 10. `task_output.py:32-45` — Iterates ALL running tasks regardless of `task_id`
```python
for key, async_task in running_tasks.items():  # Ignores task_id entirely
```
The tool is supposed to retrieve output for a specific `task_id`, but it iterates over all running tasks and returns the first completed one it finds — regardless of whether it matches the requested task ID.

### 11. `tasks.py` — Three global mutable dicts with no synchronization
```python
_next_id = 1                           # No lock; race on concurrent ID generation
_running_tasks: dict[str, asyncio.Task] = {}  # No lock; race on concurrent access
_task_counter = 0                     # No lock; race on concurrent access
```
All accessed by potentially concurrent async tool calls without any locks. Race conditions on ID generation and task registry are certain under concurrency.

---

## B. HIGH SEVERITY BUGS

### 12. `file_write.py:24` — Non-atomic writes; crash produces corrupt files
```python
path.write_text(content, encoding="utf-8")
```
If the process crashes mid-write, the file is corrupted. Should use temp file + `os.replace()`.

### 13. `file_write.py:19` — No path traversal validation
The LLM could be tricked into writing to any system path (`/etc/passwd`, etc.). No `cwd` restriction or allowlist.

### 14. `bash.py:22` — Command injection via `subprocess_shell`
```python
proc = await asyncio.create_subprocess_shell(command, ...)
```
Command passed directly to `/bin/sh -c`. No input sanitization.

### 15. `bash.py:29-31` — Zombie process risk on timeout
```python
proc.kill()  # No await proc.wait()
```
Process is killed but never waited on. Zombie processes could accumulate.

### 16. `glob.py:34` — `path.match()` has wrong semantics
```python
files = [f for f in files if f.match(glob)]
```
`PurePath.match()` matches from the path tail, not the full path. `f.match("src/**/*.py")` will NOT work as documented.

### 17. `search.py:32` — Hardcoded `*.py` extension
The tool claims to be "built on ripgrep" with glob filtering, but only searches `.py` files. The glob parameter (line 34) is a post-filter that still only matches Python files.

### 18. `search.py:48-55` — Double file read in content mode
Files are read once to find matches (line 38), then read again in content mode (line 50) — this time reading ALL files, not just matched ones.

### 19. `todo_write.py:15,20` — Lost-update race on shared `_todo_state`
```python
_todo_state: dict[str, list[dict]] = {}  # No lock
```
Multiple concurrent `TodoWrite` calls for the same session will silently overwrite each other.

### 20. `todo_write.py:24-33` — Validation uses `assert` (stripped with `python -O`)
```python
assert len(todo) == 3  # Invalid in optimized Python
```
Production runs with `-O` will silently allow corrupted todo data.

### 21. `task_state.py:94-99` — `_ensure_lock()` is dead code
The `TaskStore` declares an `asyncio.Lock` but `_ensure_lock()` is never called. Claims thread safety but provides none.

### 22. `abort_controller.py:67` — Logging uses wrong variable
```python
log.info(f"[AbortController] {self._id or self._id or 'unknown'}: aborted ({reason})")
```
`self._id or self._id` — should be `self.id or 'unknown'`. The property `self.id` exists; accessing `self._id` directly bypasses it and may be `None` when the property would return a default.

### 23. `abort_controller.py:114` — `_task_store` may be `None` in `abort_tree`
```python
state = _task_store.get_task(current)  # _task_store is None if get_task_store() never called
```
`_task_store` is module-level `None`, lazily initialized via `get_task_store()`. In `abort_tree()`, `_task_store.get_task()` is called directly without ensuring initialization, causing `AttributeError`.

### 24. `agent.py:54-57` — Fragile background task key matching
```python
for key, t in list(running.items()):
    if key.startswith("background_"):
        running[agent_id] = t
        del running[key]
        break
```
Moves the first matching `background_*` task to `agent_id`, regardless of which agent spawned it. Race condition when multiple agents are launched concurrently.

### 25. `agent.py:66` — Potential `TypeError` on `None` content
```python
return result.content + usage  # If result.content is None, TypeError
```
`AgentResult.content` is typed as `str` but line 57 of `AgentResult.to_tool_result_block()` uses `self.content + "\n\n" + usage` which would fail if content is `None`.

### 26. `file_edit.py:26` — `target_file` parameter accepted but ignored
```python
def _execute(file_path: str, target_file: str, range: dict, ...):
    path = Path(file_path)  # target_file never used
```
Dead parameter. If callers pass `target_file` as keyword arg, it silently absorbs into `**kwargs`.

### 27. `file_edit.py:43-44` — No range validation; defaults can be destructive
```python
start_line = max(1, range.get("start_line", 1))  # Missing start defaults to 1
end_line = range.get("end_line", len(lines))     # Missing end defaults to entire file
```
Missing `end_line` silently deletes the entire rest of the file.

### 28. `file_edit.py:49,52` — Line ending corruption
```python
lines = path.read_text(...).splitlines()  # Splits \r\n
path.write_text("\n".join(new_lines), ...)  # Writes \n
```
Windows files get their CRLF line endings silently converted to LF.

---

## C. MEDIUM SEVERITY ISSUES

### 29. `session.py:90-91` — Session ID collision
```python
raw = f"{project_id}:{key}:{int(time.time())}"  # Second-granularity timestamp
```
Two sessions created within the same second for the same project and sections produce identical IDs.

### 30. `session.py:150-154` — Non-atomic session file writes
```python
info._path.write_text(json.dumps(data, indent=2, default=str), ...)
```
Crash during write corrupts session files. No temp file + `os.replace` pattern.

### 31. `session.py:157-166` — `update_session()` loads, modifies in memory, saves — no locking
```python
info = load_session(session_id)  # Read from disk
# ... modify attributes ...
_save_session(info)              # Write back to disk
```
Two concurrent updates will overwrite each other (classic read-modify-write race).

### 32. `session.py:169-186` — `log_tool_call()` has same race condition
Each call loads, modifies, and saves — concurrent calls race.

### 33. `transcript.py` — `MAX_TRANSCRIPT_SIZE` defined but never enforced
No file rotation or size check exists.

### 34. `transcript.py` — Sync/async write split is confusing
`write_turn()` is sync (no lock), `awrite_turn()` is async (lock-protected). If multiple callers use `write_turn()`, there's no protection.

### 35. `message_manager.py:71-72` — Char count is not token count
```python
self.current_size += len(content)  # Characters, not tokens
```
Could significantly misestimate context budget for multilingual or emoji-heavy content.

### 36. `message_manager.py:77` — `trim()` mutates the original message list
```python
msg["content"] = msg["content"][:truncate_to]  # Modifies in-place
```
Caller's original messages list is mutated unexpectedly.

### 37. `message_manager.py:93` — `collapse_context()` hardcodes "last 2 exchanges"
Not configurable. May lose too much or too little context.

### 38. `skill.py:17` — `_invoked_skills` list is never cleared (memory leak)
```python
_invoked_skills: list[str] = []
```
Grows unboundedly across the agent's lifetime.

### 39. `skill.py:20` — No skill name sanitization
Path is built directly from user input. Skill name `../../../etc` could read arbitrary files.

### 40. `error_recovery.py` — `_try_fallback_model` does raw API call
Bypasses all abstractions, hardcodes 300s timeout and 4096 max_tokens.

### 41. `error_recovery.py` — `handle_tool_error` instantiates `ToolExecutor` per call
Should be passed as dependency or reused.

### 42. `executor.py` — `_get_pydantic_model()` has hardcoded tool->model map
Adding a new tool requires updating both the tool definition AND this map.

### 43. `agent_mailbox.py:108-118` — Lock files not cleaned up on error
The `.lock` file from `fcntl.lockf()` is never explicitly removed. Stale lock files accumulate.

### 44. `agent_spawner.py:233-249` — Exception traceback lost
```python
except Exception as error:
    return AgentResult(content=f"Subagent error: {type(error).__name__}: {error}")
```
Original traceback is discarded. Debugging is extremely difficult.

### 45. `task_update.py:75` — `task["metadata"]` None semantics wrong
```python
task["metadata"].update(...)  # If metadata is None, crashes
```
Line 35 sets `metadata: {}` as default in task_create, but if someone manipulates the store directly, this line can crash.

### 46. `task_list.py:41` — Unhandled KeyError on `t['id']`
If a task dict in the store is missing the `id` key, `task_list.py:41` raises `KeyError`.

### 47. `task_stop.py:29` — Transition failure silently ignored
```python
state.transition(TaskStatus.KILLED)  # Return value ignored
```
If task is already terminal, transition fails silently.

### 48. `task_stop.py:36` — `task.result()` blocks indefinitely
```python
task.result()  # If task isn't cancelled yet (race), this blocks
```
The task was just `cancel()`ed but may not have actually stopped yet.

### 49. `task_output.py:55` — 10-minute potential block
Default timeout is 30000ms (30 seconds), but if the API passes a large timeout value, this could block for a very long time.

### 50. `task_stop.py:41-52` — Dead code path for `running_` prefix
The `"running_"` prefix key path (lines 41-52) is a legacy that should no longer be reachable since `agent.py` moves tasks from `background_*` to `agent_id` keys.

---

## D. LOW SEVERITY / CODE QUALITY

### 51. `__init__.py:50-52` — No duplicate registration check
If `builtins` is imported twice, every tool gets registered twice.

### 52. `file_read.py:29-30` — Truncated content has no error distinction
Returns content + `"..."` without flagging it as truncated error.

### 53. `file_read.py:60` — `is_concurrency_safe=True` potentially incorrect
Concurrent reads of a file being written may return partial content.

### 54. `glob.py:29` — No truncation notice
"showing 100 of N results" is never indicated.

### 55. `search.py:53` — No line truncation in content mode
A single extremely long line could produce massive output.

### 56. `search.py:25` — Misleading error when `path=None`
Returns `"Error: Path is not a directory: None"` when no path was provided.

### 57. `models.py:73-74` — `addBlocks`/`addBlockedBy` typed as bare `list`
No validation that referenced task IDs actually exist.

### 58. `task_get.py:28` — Runtime import of `time`
`time` is imported inside the function instead of at module level.

### 59. `query_loop.py:83` — `id(self)` as controller ID
Uses Python object identity, which is non-deterministic and not useful for debugging/logging.

### 60. `query_loop.py:390` — Method named `EXCECUTE` (typo)
`def _EXCECUTE_SINGLE` / `def _EXCECUTE_PARALLEL` — typo in method naming comment.

### 61. `task_state.py:152` — TTL uses `created_at` not `updated_at`
A task frequently updated may be evicted earlier than expected.

### 62. `todo_write.py:15` — Session state never evicted
Old session IDs accumulate in `_todo_state` with no cleanup.

### 63. `agent_spawner.py:207` — Sync spawn doesn't set project_id
`_spawn_sync` passes `project_id=project_id` but the transcript path resolution may not work without it.

---

## Summary Counts

| Severity | Count |
|----------|-------|
| Critical (crash / wrong behavior) | 11 |
| High (data corruption / security / race) | 17 |
| Medium (functional issues) | 22 |
| Low (code quality) | 13 |
| **Total** | **63** |

---

## Verification Plan

1. **Run existing tests**: `python backend/tools/test_tools.py` — will likely fail on bugs #1, #2, #7, #9
2. **Fix import bugs (#1, #2)**: Rename `_AbortHierarchy` or create alias; move `_task_counter` to correct module scope
3. **Fix TaskState overwrite (#3, #4, #5)**: Remove dict overwrite in `task_create.py`; fix `task_update.py` to update `TaskState` objects
4. **Fix parallel execution (#7)**: Rewrite `_execute_parallel` as proper `async def`, fix closure captures, use `asyncio.gather` directly
5. **Fix ReDoS (#8)**: Add `re` timeout or pattern validation in `search.py`
6. **Fix TaskOutput (#10)**: Match `task_id` specifically instead of iterating all tasks
7. **Add concurrency protection (#11)**: Add `asyncio.Lock` around `_task_store`, `_running_tasks`, `_next_id`
8. **Make file writes atomic**: Use temp file + `os.replace` in `file_write.py` and `session.py`
9. **Add path validation**: Restrict file operations to project directory in `file_write.py`
10. **Fix mailbox call (#9)**: Pass `agent_id` to `get_mailbox()`
11. **Run full integration**: Re-run `test_tools.py` and verify no crashes
