# LLM-Based Dependency Graph with OpenAI Function Calling

## Context

The current `build_dependency_graph()` uses overly aggressive heuristics — every section depends on all previous sections. We'll replace it with an LLM call that uses **OpenAI function calling** so the LLM can request knowledge file reads itself.

## Architecture

The `llm_api_handler.py` uses `AsyncOpenAI` client with `chat.completions.create()`. OpenAI's API supports a `tools` parameter — we pass a function definition, the LLM can emit a `tool_calls` response, and we execute the function locally then send results back to continue the conversation.

## Files to Modify

1. **`backend/prompts/System_Prompts/template_analysis_prompts/dependency_graph.txt`** — new system prompt
2. **`backend/Memory_Management/document_architect_agent.py`** — new `build_dependency_graph()` with tool calling
3. **`backend/Memory_Management/test_architect_agent.py`** — add `await`
4. **`backend/Routes/template_parsing_routes.py`** — update async callers

## Step-by-Step

### Step 1: Add function-calling support to `llm_api_handler.py`

**File**: `llm_api_handler.py`

Add a new function `llm_request_with_tools()` after the existing `llm_request()` and `llm_request_with_correction()` functions (~line 558):

```python
async def llm_request_with_tools(
    model: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
    max_tokens: int = DEFAULT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: float = DEFAULT_TIMEOUT,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    LLM request with OpenAI function calling support.
    
    - Sends function/tool definitions in the request
    - If LLM responds with tool_calls, executes them locally
    - Sends tool results back and gets the final answer
    - Returns the final content string
    
    tools: list of tool dicts with {type: 'function', function: {...}}
    """
    resolved_model = _resolve_model_name(model)
    client = _get_client()

    full_messages = list(messages)
    if system_prompt:
        full_messages.insert(0, {"role": "system", "content": system_prompt})

    max_tool_rounds = 5  # Limit tool calling rounds to prevent infinite loops
    
    for _ in range(max_tool_rounds):
        def api_call():
            return client.chat.completions.create(
                model=resolved_model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=DEFAULT_TOP_P,
                timeout=timeout,
                stream=False,
                tools=tools,
            )

        content, success = await _retry_with_backoff(
            api_call, resolved_model,
            max_retries=MAX_RETRIES,
            max_retries_on_empty=MAX_RETRIES_ON_EMPTY,
        )

        if not success or not content:
            return None

        # Check if LLM wants to call a tool
        # In OpenAI's response, tool_calls are on the message object
        import openai
        choice = None
        # Re-extract from the raw response would be needed here
        # For now, we need to capture the raw response
```

Wait — this needs refinement. The current `_retry_with_backoff` only returns `content` string, not the raw response. We need to modify the flow to handle tool_calls. Let me design this more carefully.

### Revised approach: Add a new API function

Add `llm_request_with_tool_calls()` to `llm_api_handler.py` that captures the raw response and handles tool calls:

```python
async def llm_request_with_tool_calls(
    model: str,
    messages: List[Dict[str, str]],
    tool_callables: Dict[str, Callable],
    max_tokens: int = DEFAULT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: float = DEFAULT_TIMEOUT,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    LLM request with OpenAI function/tool calling.
    
    Args:
        tool_callables: dict mapping tool names to async callable functions.
            When the LLM calls a tool, this dict provides the implementation.
            Each callable takes (tool_name: str, arguments: str) -> str.
    """
    resolved_model = _resolve_model_name(model)
    client = _get_client()

    full_messages = list(messages)
    if system_prompt:
        full_messages.insert(0, {"role": "system", "content": system_prompt})

    # Build tool definitions (same shape for all rounds)
    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"Read the content of a knowledge or template file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The full file path to read.",
                        },
                    },
                    "required": ["file_path"],
                },
            },
        }
        for name in tool_callables
    ]

    max_rounds = 5
    for _ in range(max_rounds):
        response = await client.chat.completions.create(
            model=resolved_model,
            messages=full_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=DEFAULT_TOP_P,
            timeout=timeout,
            stream=False,
            tools=tool_defs,
        )
        
        choice = response.choices[0]
        message = choice.message
        
        # Check for tool_calls
        if message.tool_calls:
            # Execute each tool call
            for tc in message.tool_calls:
                func_name = tc.function.name
                args_str = tc.function.arguments
                
                # Parse args and call the function
                try:
                    args = json.loads(args_str)
                    file_path = args.get("file_path", "")
                    result = await tool_callables[func_name](func_name, file_path)
                except Exception as e:
                    result = f"Error: {e}"
                
                # Send tool result back
                full_messages.append(message)  # assistant message with tool_calls
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            # Continue loop — LLM will use the tool results
            continue
        
        # No tool_calls — this is the final answer
        if message.content:
            return message.content

    return None
```

### Step 2: Create `dependency_graph.txt` prompt

**File**: `backend/prompts/System_Prompts/template_analysis_prompts/dependency_graph.txt`

```
# @version: 1.0
# @category: system
# @template: false

You are an SRS document structure analyst. Determine which document
sections must be generated before others based on content analysis.

AVAILABLE TOOLS:
- read_file: Read the content of a knowledge file from the project.
  Call this tool to read files before making dependency decisions.
  Read overview.md, relationships.md, categories/*.md files.

RULES:
- Read the knowledge files first to understand what data each section produces
- A section A depends on section B only if A needs data that B produces
- Do NOT add dependencies just because B comes before A
- Return only real, content-based dependencies

OUTPUT:
Return ONLY valid JSON after reading the relevant files:
{
  "dependencies": {
    "01_file.md": [],
    "02_file.md": ["01_file.md"],
    ...
  }
}
```

### Step 3: Rewrite `build_dependency_graph()` in `TemplateAnalysisAgent`

**File**: `document_architect_agent.py` (replace lines ~368–427)

```python
async def build_dependency_graph(
    self, section_map: SectionMap | None = None
) -> DependencyGraph:
    """Determine dependencies using LLM with tool-based file reading."""
    if section_map is None:
        section_map = self.build_section_map(self._cached_structure)

    # Build tool callables — the LLM can request file reads
    async def _read_file_tool(name: str, file_path: str) -> str:
        """Tool implementation for reading knowledge files."""
        try:
            target = Path(file_path)
            if not target.exists():
                # Try relative to knowledge dir
                target = self.knowledge_dir / Path(file_path).name
            if not target.exists():
                return f"File not found: {file_path}"
            content = target.read_text(encoding="utf-8")
            # Truncate if too large
            if len(content) > 4000:
                content = content[:4000] + "\n...(truncated)"
            return content
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    tool_callables = {"read_file": _read_file_tool}

    # Section summary for the LLM
    sections_summary = ""
    for fname, info in section_map.sections.items():
        sections_summary += (
            f"- {fname} (section {info.section_number})\n"
            f"  required_data: {info.required_data}\n"
        )

    system_prompt = self._PROMPT_ENGINE.render("dependency_graph")
    user_prompt = (
        "Analyze these sections and determine generation dependencies.\n"
        f"First, read the knowledge files to understand what each produces.\n\n"
        f"Sections:\n{sections_summary}"
    )

    result_text = await llm_request_with_tool_calls(
        model="opus46",
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tool_callables=tool_callables,
        max_tokens=2048,
        temperature=0.0,
    )

    if result_text:
        try:
            parsed = json.loads(result_text.strip())
            deps = parsed.get("dependencies", {})
            # Ensure all sections represented
            for fname in section_map.sections:
                if fname not in deps:
                    deps[fname] = []
            return DependencyGraph(graph=deps)
        except (json.JSONDecodeError, AttributeError):
            log.warning("[DocArchitect] LLM returned invalid JSON for dependency graph, falling back.")

    # Fallback: simple section-number ordering
    graph = {}
    items = list(section_map.sections.items())
    for i, (fname, info) in enumerate(items):
        deps = []
        for j in range(i):
            if items[j][1].section_number < info.section_number:
                deps.append(items[j][0])
        graph[fname] = deps
    return DependencyGraph(graph=graph)
```

### Step 4: Update all callers

**`document_architect_agent.py`**:
- `execute_generation_plan()` line ~757: `dep_graph = await self.build_dependency_graph(section_map)`
- `validate_document()` line ~697: `dep_graph = await self.build_dependency_graph(self.build_section_map())`
  - Change `validate_document()` to `async def`
  - Line ~767: `validation_plan = await self.validate_document()`

**`template_parsing_routes.py`**:
- `get_template_architecture()` line ~394: `dep_graph = await architect.build_dependency_graph(...)`

**`test_architect_agent.py`**:
- Line 54: `dep_graph = await agent.build_dependency_graph(section_map)`

### Step 5: Verify

```bash
python -m py_compile backend/Memory_Management/document_architect_agent.py \
    backend/Routes/template_parsing_routes.py \
    backend/Memory_Management/test_architect_agent.py \
    backend/llm_api_handler.py
python -m Memory_Management.test_architect_agent
```
