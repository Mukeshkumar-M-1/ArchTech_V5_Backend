# `chat.completions.create()` — Complete Parameter Reference

All parameters come from `AsyncOpenAI` (OpenAI Python SDK) and are sent to any OpenAI-compatible endpoint.

---

## Required Parameters

### `model`
**Type:** `str | ChatModel`
**Required:** Yes
**Description:** Which model to use.

```python
client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "hello"}],
)
# Options: claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5
```

### `messages`
**Type:** `Iterable[ChatCompletionMessageParam]`
**Required:** Yes
**Description:** Conversation history. Each item has `role` and `content`.

```python
client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "Multiply by 3?"},
    ],
)
```

---

## Core Behavior Parameters

### `max_tokens`
**Type:** `int`
**Default:** None (model default)
**Description:** Maximum tokens in the response. Controls response length.

```python
# Short answer: 20 tokens
# Detailed article: 4096 tokens
client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "Say hello"}],
    max_tokens=10,  # Only 10 tokens of output allowed
)
```

### `max_completion_tokens`
**Type:** `int`
**Description:** Alternative/alias for `max_tokens`. Sets upper bound including visible output and internal reasoning tokens.

```python
# Limits ONLY visible output
max_tokens=500

# Limits ALL tokens (visible + reasoning)
max_completion_tokens=500
```

### `temperature`
**Type:** `float`
**Range:** 0.0 — 2.0
**Default:** 1.0
**Description:** Sampling randomness. Lower = more deterministic. Higher = more creative.

```python
0.0  # Always same output, most predictable
0.1  # Very deterministic (our default for code/tasks)
0.7  # Balanced
1.0  # Default randomness
1.5  # More varied
2.0  # Maximum creativity (may produce nonsense)
```

### `top_p`
**Type:** `float`
**Range:** 0.0 — 1.0
**Default:** 1.0
**Description:** Nucleus sampling. Only considers tokens with cumulative probability mass <= top_p.

```python
0.1  # Only top 10% most likely tokens
0.5  # Top 50% most likely tokens
1.0  # All tokens (same as temperature=1.0)
```

**Note:** Don't use `temperature` and `top_p` together — pick one.

---

## Response Format

### `response_format`
**Type:** `dict`
**Description:** Control the output format.

```python
# Text output (default)
{"type": "text"}

# JSON mode (LLM guarantees valid JSON)
{"type": "json_object"}

# Structured output (Pydantic schema)
{
    "type": "json_schema",
    "json_schema": {
        "name": "user_data",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"]
        }
    }
}
```

---

## Output Control

### `stop`
**Type:** `str | List[str]`
**Description:** Stop generating when these sequences appear.

```python
# Single stop sequence
stop="\n\n"

# Multiple stop sequences
stop=["\n", "---", "END"]

# Model stops at first matching sequence
```

### `n` [Not working]
**Type:** `int`
**Default:** 1
**Description:** Generate N completions per request. Each counts toward cost.

```python
n=1   # One completion (default)
n=3   # Three completions, check response.choices[0], [1], [2]
```

### `presence_penalty`
**Type:** `float`
**Range:** -2.0 — 2.0
**Default:** 0.0
**Description:** Penalize tokens based on whether they appear anywhere in the text so far. Positive = encourages new topics.

```python
-1.0  # Repeats existing content
 0.0  # No effect (default)
+0.5  # Encourages talking about new topics
+2.0  # Strongly avoids repeating existing content
```

### `frequency_penalty`
**Type:** `float`
**Range:** -2.0 — 2.0
**Default:** 0.0
**Description:** Penalize tokens based on how often they appear so far. Positive = reduces repetition.

```python
-1.0  # Repeats existing tokens
 0.0  # No effect (default)
+0.5  # Reduces repetition
+2.0  # Strongly avoids repeated tokens
```

---

## Streaming

### `stream`
**Type:** `bool`
**Default:** False
**Description:** Enable streaming. True = events arrive as tokens are generated.

```python
# Non-streaming: wait for full response
response = await client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "hello"}],
    stream=False,  # ← default
)
print(response.choices[0].message.content)

# Streaming: events arrive in real-time
response = await client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "hello"}],
    stream=True,
)
async for chunk in response:
    if chunk.choices:
        print(chunk.choices[0].delta.content, end="")
```

### `stream_options`
**Type:** `dict`
**Description:** Streaming-specific settings.

```python
stream_options={"include_usage": True}
# With include_usage, the final chunk contains token usage data
```

---

## Tools / Function Calling

### `tools`
**Type:** `Iterable[ChatCompletionToolUnionParam]`
**Description:** List of tools the model can call.

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search files by pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
]

response = await client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "Find all .py files in project"}],
    tools=tools,
)
# response.choices[0].message.tool_calls contains the tool call details
```

### `tool_choice`
**Type:** `str | dict`
**Description:** Control which tool the model uses.

```python
"auto"  # Model decides (default when tools are present)
"none"  # Model never calls tools (default when no tools)
"required"  # Model MUST call at least one tool
{"type": "function", "function": {"name": "get_weather"}}  # Force specific tool
```

### `parallel_tool_calls`
**Type:** `bool`
**Default:** True
**Description:** Allow model to call multiple tools in parallel.

```python
parallel_tool_calls=True   # Model can call get_weather AND search_files simultaneously
parallel_tool_calls=False  # Model calls tools one at a time
```

---

## Debugging & Control

### `logprobs`
**Type:** `bool`
**Description:** Return log probabilities of output tokens.

```python
response = await client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "hello"}],
    logprobs=True,
)
response.choices[0].logprobs.content[0].logprob  # Log prob of first token
```

### `top_logprobs`
**Type:** `int`
**Description:** Return N most likely tokens per position (requires `logprobs=True`).

```python
response = await client.chat.completions.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "hello"}],
    logprobs=True,
    top_logprobs=5,  # Show 5 most likely tokens at each position
)
```

### `logit_bias`
**Type:** `Dict[str, int]`
**Description:** Modify likelihood of specific tokens (-100 to +100).

```python
# Bias token 1234 toward appearing, discourage token 5678
logit_bias={"1234": 50, "5678": -100}
```

### `seed`
**Type:** `int`
**Description:** Deterministic sampling. Same seed + same params = same output.

```python
seed=42  # Attempted deterministic output
```

### `service_tier`
**Type:** `str`
**Description:** Processing priority.

```python
"auto"    # Use project default (default)
"flex"    # Use flex credits if available
"scale"   # Scale tier if available
"priority"
"default"
```

---

## Caching & Monitoring

### `prompt_cache_key`
**Type:** `str`
**Description:** Cache key for prompt caching. Similar requests with same key get cached responses.

```python
prompt_cache_key="my_project_v1"
# OpenAI caches response for requests with matching cache key
```

### `prompt_cache_retention`
**Type:** `str`
**Description:** Cache duration.

```python
"in_memory"   # Keep in memory (default)
"24h"         # Extended retention for 24 hours
```

### `user`
**Type:** `str`
**Description:** End-user identifier. Used for abuse detection and debugging. Replaced by `safety_identifier`.

```python
user="user_12345"
```

### `safety_identifier`
**Type:** `str`
**Description:** Stable user identifier for safety monitoring. Hash usernames to avoid sending PII.

```python
safety_identifier="hashed_user_abc123"
```

### `metadata`
**Type:** `dict`
**Description:** Custom key-value pairs (max 16 pairs, key ≤ 64 chars, value ≤ 512 chars).

```python
metadata={
    "project": "archtech",
    "session": "default",
    "version": "3.0",
}
```

---

## Advanced

### `response_format` (JSON)
**Type:** `dict`
**Description:** Force JSON output.

```python
# Older JSON mode
response_format={"type": "json_object"}

# Structured output with Pydantic
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "extracted_data",
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        }
    }
}
```

### `store`
**Type:** `bool`
**Description:** Store output for distillation/evals.

```python
store=True   # Store for model distillation
store=False  # Don't store (default)
```

### `verbosity`
**Type:** `str`
**Description:** Response verbosity level.

```python
"low"   # Concise responses
"medium"  # Default
"high"  # Detailed responses
```

### `reasoning_effort`
**Type:** `str`
**Description:** Effort level for reasoning models.

```python
"low"   # Fast, less thorough reasoning
"medium"  # Balanced
"high"  # Deep reasoning (more tokens, longer)
```

### `modalities`
**Type:** `List[str]`
**Description:** Output types.

```python
["text"]              # Text only (default)
["text", "audio"]     # Text + audio (requires audio param)
```

### `audio`
**Type:** `dict`
**Description:** Audio output config (requires `modalities=["text", "audio"]`).

```python
audio={"voice": "alloy", "format": "mp3"}
```

### `web_search_options`
**Type:** `dict`
**Description:** Enable web search tool.

```python
web_search_options={"search_at_publication_time": True}
```

### `prediction`
**Type:** `dict`
**Description:** Predicted output content for regeneration scenarios.

```python
prediction={
    "type": "content",
    "content": "The existing file content to regenerate..."
}
```

---

## HTTP-Level Options

### `timeout`
**Type:** `float`
**Description:** Request timeout in seconds.

```python
timeout=120.0  # 2 minute timeout
```

### `extra_headers`
**Type:** `dict`
**Description:** Add custom HTTP headers.

```python
extra_headers={"X-Custom-Header": "value"}
```

### `extra_query`
**Type:** `dict`
**Description:** Add query parameters to URL.

```python
extra_query={"custom_param": "value"}
```

### `extra_body`
**Type:** `dict`
**Description:** Add properties to the request body not available via kwargs.

```python
extra_body={"custom_property": "value"}
```

---

## Quick Reference — Most Used Parameters

| Parameter | Our Default | Typical Range |
|-----------|------------|---------------|
| `model` | `"claude-opus-4-6"` | opus/sonnet/haiku |
| `messages` | `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]` | - |
| `max_tokens` | `4096` | 10 — 128000 |
| `temperature` | `0.1` | 0.0 — 2.0 |
| `top_p` | `0.1` | 0.0 — 1.0 |
| `timeout` | `120.0` | 5.0 — 300.0 |
| `stream` | `False` | True/False |
| `tools` | `[]` | - |
| `stop` | `None` | - |
| `presence_penalty` | `0.0` | -2.0 — 2.0 |
| `frequency_penalty` | `0.0` | -2.0 — 2.0 |
