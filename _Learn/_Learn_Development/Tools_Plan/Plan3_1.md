# Fix: Subagent Not Spawning — Empty Response + Tool Calls Handling

## Problem
The LLM subagent never spawns sub-agents or uses tools. Two bugs prevent this:

1. **`_retry_with_backoff` treats `tool_calls` responses as empty** — When the LLM responds with tool calls, `message.content` is `None`. The function checks only `content`, sees `None`, and retries 10 times before exhausting. Even though `_retry_call` (with its own budget) returns the raw response correctly, the unnecessary retries add latency and the empty response handling masks valid tool-call responses.

2. **`_call_with_fallback` discards `_retry_with_backoff` result** — It calls `_retry_with_backoff`, gets `content` (a string, not the raw response), then discards it and calls `_retry_call` with a fresh budget. This double-retry wastes attempts and `_retry_with_backoff` never preserves tool_calls.

3. **Subagent test didn't pass tools to spawn** — The test called `spawner.spawn()` without `tools=all_tools`.

4. **Relative import error** — `query_loop.py:218` uses `from llm_api_handler import ...` which fails when run from outside `backend/`. Same in `error_recovery.py:206`.

## Fixes

### 1. `backend/llm_api_handler.py` — Fix `_retry_with_backoff` to handle tool_calls

**Lines 168-182:** After extracting content, check for tool_calls before treating as empty:

```python
response = await api_call()
message = response.choices[0].message

if message.tool_calls:
    return response, True  # Tool calls are a valid response

content = message.content
if content is not None and content.strip():
    return content, True

# Only then treat as empty and retry
```

### 2. `backend/tools/query_loop.py` — Fix `_call_with_fallback` to not double-retry

**Lines 235-254:** Remove the dead `_retry_with_backoff` call since `_retry_call` handles retries properly and preserves raw response objects:

```python
async def _call_with_fallback(self, messages, tool_defs, model, max_tokens, temperature):
    from llm_api_handler import _get_client, _resolve_model_name
    
    client = _get_client()
    resolved = _resolve_model_name(model)

    try:
        return await self._retry_call(client, resolved, messages, tool_defs, max_tokens, temperature)
    except Exception as e:
        log.error(f"[QueryLoop] Primary model {resolved} failed: {e}")

    if self.fallback_chain:
        for fallback in self.fallback_chain:
            try:
                response = await self._retry_call(client, _resolve_model_name(fallback), ...)
                if response is not None:
                    return response
            except Exception as e:
                log.warning(f"[QueryLoop] Fallback {fallback} failed: {e}")

    return None
```

### 3. `backend/tools/builtins/agent.py` — Ensure tools are always passed to subagent

The `_execute` function already does `all_tools = tool_registry.get_all()` and passes `tools=all_tools`. No change needed beyond verifying it works.

### 4. `backend/tools/test_tools.py` — Pass tools to spawn in test

The user already updated the test to pass `tools=all_tools`. No change needed.

## Verification
- Run `py_venv/bin/python ./backend/tools/test_tools.py`
- Subagent should see 5 tools (not 0)
- Subagent should be able to call FileRead, Bash, and Agent tools
