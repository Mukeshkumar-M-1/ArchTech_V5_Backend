"""
QueryLoop — The multi-turn inference loop.

MIRRORED FROM CCB'S query() LOOP IN query.ts:
- while(true): model -> tool_use -> execute -> tool_result -> model -> ...
- Stops when the model returns text only (no tool calls)
- Tool results (including errors) are fed back to the model each turn
- Error recovery at each level (API retry, model fallback, tool error feedback)
- Context compaction keeps conversation within token budget (fallback for legacy)
- Session memory for auto-compact reuse
- Streaming API integration with progress events

LAYER 5 INTEGRATION: wires query_guard, compaction, session_memory,
system_prompt, progress, permission, and streaming into a single loop.

ARCHITECTURAL NOTE (Layer 2 fix — State-First):
The original design accumulated conversation messages every turn, causing the
context to grow to 57K+ tokens and trigger proxy timeouts. The new pattern:

    StateManager (source of truth) -> ContextBuilder (fresh prompt every turn)
    -> LLM -> ObservationExtractor (structured state updates) -> StateManager.update()

The conversation list is only used as an intermediate buffer. After each turn,
the state is extracted and the conversation is effectively discarded (only
the compacted state is used for the next prompt). Compaction still exists as
a safety net, but the primary mechanism is state-first.
"""

from __future__ import annotations

import asyncio as _asyncio
import json
import logging
import time
from typing import Any, Optional
from .compaction import CompactPipeline
from .session_memory import SessionMemoryExtractor, SessionMemoryCache, CompactSummary
from .system_prompt import SystemPromptManager
from .registry import registry, get_tool_definition
from .executor import ToolExecutor
from .ptao_orchestrator import (
    PTAOPromptBuilder,
    PTAOResponseParser,
    PTAOValidator,
    PTAOObservationFormatter,
    PTAOState,
)
from .abort_controller import get_hierarchy

log = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 100
DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_MODEL_OPUS = "opus46"
DEFAULT_FALLBACK_CHAIN_MODEL = ["opus46"]
DEFAULT_TOKENS = 4096
DEFAULT_TEMP = 0.1
DEFAULT_TOOL_CONCURRENCY = 1
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_SLEEP_TIME = 10
DEFAULT_COMPACT_TOKEN_BUDGET = 100_000
DEFAULT_SESSION_ID = "default"


class QueryLoop:
    """Main multi-turn inference loop for agentic task execution.

    Runs the PTAO reasoning cycle (Understand -> Plan -> Thought -> Action -> Observation)
    until the model returns a final text response or the turn limit is reached.

    Integrates compaction, session memory, system prompt management,
    permission checking, and streaming output.

    State-first architecture:
        The conversation is an intermediate buffer, not the source of truth.
        StateManager holds the actual state. ContextBuilder rebuilds a fresh
        prompt every turn from state (bounded, never growing).
    """

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        timeout: int = DEFAULT_TIMEOUT,
        fallback_chain: list[str] | None = None,
        abort_controller: Any = None,
        session_id: str = DEFAULT_SESSION_ID,
        compact_token_budget: int = DEFAULT_COMPACT_TOKEN_BUDGET,
        permission_checker: Any = None,
        streaming_enabled: bool = False,
        project_id: str | None = None,
        context_injector: Any = None,
        observation_manager: Any = None,
        decision_manager: Any = None,
        transcript_writer: Any = None,
        message_manager: Any = None,
    ) -> None:
        self._project_id = project_id or ""
        self.max_turns = max_turns
        self.timeout = timeout
        self.fallback_chain = fallback_chain or []
        self.abort_controller = abort_controller
        self._session_id = session_id
        self._compact_token_budget = compact_token_budget
        self._permission_checker = permission_checker
        self._streaming_enabled = streaming_enabled
        self._compaction = CompactPipeline(token_budget=compact_token_budget)
        self._memory_extractor = SessionMemoryExtractor()
        self._memory_cache = SessionMemoryCache(self._project_id)
        self._memory_adapter = CompactSummary(self._memory_cache)
        self._system_prompt_manager = SystemPromptManager()
        self._tool_definition = get_tool_definition()
        self._turn = 0
        self._last_progress_time = 0
        self._ptao_state = PTAOState()
        self._executed_tools: set[str] = set()
        self._context_injector = context_injector
        self._observation_manager = observation_manager
        self._decision_manager = decision_manager
        self._transcript_writer = transcript_writer
        self.message_manager = message_manager
        self.token_tracker = None

        # Sliding window history for native tool calls
        self._message_history: list[dict] = []
        self._max_history_turns = 5

        # Pause/resume state for user input interactions
        self._awaiting_input: bool = False
        self._interaction_tool_call_id: str | None = None
        self._user_response: Any = None

        # Wire session memory into compaction
        self._compaction.set_summarize_fn(
            lambda msgs: self._memory_adapter.get_summary(
                self._session_id, msgs, legacy_fn=None
            )
        )

    def set_section_context(self, section_number: str, section_heading: str, goal: str) -> None:
        pass

    def update_template_and_knowledge(self, template: str = "", knowledge: str = "") -> None:
        pass

    async def run(
        self,
        messages: list[dict],
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        model: str = DEFAULT_MODEL_OPUS,
        max_tokens: int = DEFAULT_TOKENS,
        temperature: float = DEFAULT_TEMP,
        response_format: str = "text"
    ) -> str | dict:
        """Run the multi-turn agentic inference loop.

        The loop runs LLM calls, tool execution, compaction, and session memory
        extraction until the model returns text-only output or max turns reached.

        State-first flow:
            1. State is read from StateManager
            2. ContextBuilder builds a FRESH prompt (never from conversation)
            3. LLM is called
            4. ObservationExtractor converts response to structured state updates
            5. State is updated — conversation is discarded
            6. Repeat

        Args:
            messages: Initial conversation messages (legacy — state is primary).
            tools: List of tools available for execution.
            system_prompt: Optional override for the system prompt.
            model: Model name for the LLM call.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature for the LLM.
            response_format: Expected response format ("text" or "json").

        Returns:
            The final text output from the agent.
        """
        log.info("[QueryLoop] run: %d messages, %d max turns, model=%s", len(messages), self.max_turns, model)

        # Reset pause/resume state so stale values from a previous run() call don't bleed through
        self._awaiting_input = False
        self._interaction_tool_call_id = None

        try:
            for _ in range(self.max_turns):
                self._turn += 1
                log.info(f"\n\n ===== TURN {self._turn} =====")

                # Check abort signal
                if self.abort_controller and self.abort_controller.signal.is_aborted:
                    log.info("[QueryLoop] Aborted at turn %d", self._turn)
                    break

                # Build system prompt
                if system_prompt:
                    system_prompt_message = system_prompt
                else:
                    session_memory = self._memory_cache.load(self._session_id)
                    
                    # Convert the provided tools list to definitions for the system prompt
                    current_tool_defs = []
                    if tools is not None:
                        for tool in tools:
                            if isinstance(tool, dict):
                                current_tool_defs.append(tool)
                            else:
                                current_tool_defs.append({
                                    "type": "function",
                                    "function": {
                                        "name": tool.name,
                                        "description": tool.get_description(),
                                        "parameters": tool.input_schema,
                                    }
                                })
                    else:
                        # Fallback to all tools if none specified
                        current_tool_defs = self._tool_definition
                        
                    system_blocks = self._system_prompt_manager.build(
                        tool_definitions=current_tool_defs,
                        custom_system_prompt=system_prompt,
                        session_memory=session_memory,
                    )
                    system_prompt_message = "\n".join(
                        block_item.content for block_item in system_blocks if block_item.content
                    )

                api_messages = messages + self._message_history

                assistant_reply = await self._call_api(
                    messages=api_messages,
                    system_prompt=system_prompt_message,
                    tools=tools,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=response_format
                )

                # HANDLE ERROR RESPONSE
                if isinstance(assistant_reply, dict) and "error" in assistant_reply:
                    return f"API error: {assistant_reply['error']}"

                final_text, tool_calls = self._parse_response(assistant_reply)
                log.info(f"[QueryLoop] Turn {self._turn}: API response received, text_len={len(final_text)}, tool_calls_count={len(tool_calls)}")

                # Append assistant response to history
                assistant_msg = {"role": "assistant", "content": final_text}
                if tool_calls:
                    native_tool_calls = []
                    for tc in tool_calls:
                        native_tool_calls.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["input"])
                            }
                        })
                    assistant_msg["tool_calls"] = native_tool_calls
                self._message_history.append(assistant_msg)

                if not final_text.strip() and not tool_calls:
                    continue

                if not tool_calls and final_text.strip():
                    log.info(f"[QueryLoop] Turn {self._turn}: SECTION COMPLETED ({len(final_text)} chars)")
                    break
                tool_results = []
                if tool_calls:
                    tool_results = await self._execute_tools(tool_calls, tools)
                    for idx, tc in enumerate(tool_calls):
                        if idx < len(tool_results):
                            result = tool_results[idx]
                            self._message_history.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", ""),
                                "name": tc.get("name", ""),
                                "content": result.get("content", "")
                            })
                log.info(f"[QueryLoop] Turn {self._turn} complete, {len(tool_calls)} tools executed")

                # Check if a tool requested user input — pause the loop
                # When _awaiting_input, skip appending tool results to _message_history.
                # This prevents re-execution of RequestUserInput on resume.
                if self._awaiting_input:
                    log.info(f"[QueryLoop] Paused at turn {self._turn} awaiting user input")
                    # Clear the assistant message we just appended so the LLM
                    # starts fresh from the user response appended by set_user_response
                    self._message_history.pop()
                    return {
                        "_status": "awaiting_input",
                        "_turn": self._turn,
                        "_tool_call_id": self._interaction_tool_call_id,
                    }

                if self._transcript_writer:
                    self._transcript_writer.write_turn(
                        role="assistant",
                        content=final_text,
                        tool_calls=tool_calls,
                        tool_results=tool_results
                    )

                # Truncate history if it gets too long (Sliding Window)
                while len(self._message_history) > self._max_history_turns * 2:
                    self._message_history.pop(0)
                while self._message_history and self._message_history[0].get("role") == "tool":
                    self._message_history.pop(0)

            # End of loop
            log.info(f"[QueryLoop] Loop finished after {self._turn} turns")
            self._compaction.reset_failures()

        except Exception as exception:
            log.error(f"[QueryLoop] Error: {exception}", exc_info=True)
            final_text = f"Error: {type(exception).__name__}: {exception}"

        return final_text if 'final_text' in dir() else ""

    def set_user_response(self, tool_call_id: str, response: Any) -> None:
        """Set the user's response after a RequestUserInput pause.

        Appends the response as a tool result message so the next turn
        picks up where we left off.

        Args:
            tool_call_id: The tool call ID that triggered the pause.
            response: The user's selection (str or list[str]).
        """
        self._interaction_tool_call_id = tool_call_id
        self._user_response = response
        # Append as a tool result message — the next run() turn will see it
        self._message_history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps({"user_selection": response, "status": "completed"}),
            "_is_interactive": True,
        })
        self._awaiting_input = False
        log.info("[QueryLoop] User response set for tool %s, resuming", tool_call_id)

    # API CALL DESIDER FOR (STREAMING | FALLBACK)
    async def _call_api(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[Any],
        model: str,
        max_tokens: int,
        temperature: float,
        response_format: dict,
    ) -> str:
        """API call with fallback chain. Uses streaming if enabled."""

        # Build definitions only for the tools explicitly provided to this run
        tool_definitions = []
        if tools:
            for tool in tools:
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.get_description(),
                        "parameters": tool.input_schema,
                    },
                })
        log.info(f"[QueryLoop] Built {len(tool_definitions)} tool definitions for API call")

        # Do NOT send response_format when tools are available.
        # response_format:"text" tells the model to produce text-only output,
        # which suppresses tool call generation entirely.
        api_response_format = response_format if not tool_definitions else None

        # STREAMING CALLING
        if self._streaming_enabled:
            return await self._LLM_stream_call(
                messages, system_prompt, tool_definitions if tool_definitions else None, model, max_tokens, temperature
            )

        # FALLBACK CALLING
        return await self._LLM_call_with_fallback(
            messages=messages, system_prompt=system_prompt,
            tools=tool_definitions if tool_definitions else None, model=model, max_tokens=max_tokens,
            temperature=temperature, response_format=api_response_format
        )

    # NON-STREAMING API CALLING
    async def _LLM_call_with_fallback(
        self,
        messages,
        system_prompt,
        tools,
        model,
        max_tokens,
        temperature,
        response_format=None,
    ) -> Any:
        """API call with fallback chain. Handles streaming vs non-streaming."""
        from llm_api_handler import (
            _retry_with_backoff,
            _call_with_model_fallback,
            _resolve_model_name,
            MAX_RETRIES,
            MAX_RETRIES_ON_EMPTY,
        )

        primary_model = _resolve_model_name(model)

        # Format system prompt for API messages
        api_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        def api_call(active_client):
            # NEVER send response_format when tools are available — it blocks tool call generation
            api_format = response_format if not tools else None
            return active_client.chat.completions.create(
                model=primary_model,
                messages=api_messages,
                tools=tools,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=api_format,
            )

        content, success = await _retry_with_backoff(
            api_call=api_call,
            model=primary_model,
            max_retries=MAX_RETRIES,
            max_retries_on_empty=MAX_RETRIES_ON_EMPTY

        )
        log.info(f"[QueryLoop] Turn {self._turn}: API call completed, success={success}, tool_calls={'Yes' if content and hasattr(content, 'choices') and content.choices[0].message.tool_calls else 'No'}")

        if success and content:
            # Tool calls returned as raw response — record usage and return
            self.token_tracker and self.token_tracker.record_turn(
                turn_number=self._turn,
                tokens_in=content.usage.prompt_tokens if hasattr(content, "usage") else 0,
                tokens_out=content.usage.completion_tokens if hasattr(content, "usage") else 0,
            )
            return content

        log.warning(
            f"[QueryLoop] Primary model {primary_model} exhausted all retries, "
            f"trying fallback chain: {self.fallback_chain}"
        )

        # Try fallback chain
        fallback_content = await _call_with_model_fallback(
            fallback_models=self.fallback_chain,
            messages=api_messages,
            max_tokens=max_tokens,
            max_retries=MAX_RETRIES,
            max_retries_on_empty=MAX_RETRIES_ON_EMPTY,
            temperature=temperature,
        )

        if fallback_content:
            self.token_tracker and self.token_tracker.record_turn(
                turn_number=self._turn,
                tokens_in=fallback_content.usage.prompt_tokens if hasattr(fallback_content, "usage") else 0,
                tokens_out=fallback_content.usage.completion_tokens if hasattr(fallback_content, "usage") else 0,
            )
            return fallback_content

        return "Error: API call failed — all models exhausted retries"

    # API STREAMING CALLING
    async def _LLM_stream_call(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[Any],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Streaming API call with progress events."""
        from llm_api_handler import (
            StreamingLLMHandler,
            _resolve_model_name,
        )

        primary_model = _resolve_model_name(model)

        # Format messages for API
        api_messages = [
            # {"role": "system", "content": system_prompt},
            *messages,
        ]

        handler = StreamingLLMHandler(primary_model)

        collected_text = ""
        total_tokens_in = 0
        total_tokens_out = 0

        try:
            async for event in handler.stream(
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            ):
                # Update progress
                current_time = time.time()
                if current_time - self._last_progress_time >= 0.5:
                    if self.message_manager:
                        self.message_manager.emit_progress_event(
                            content=collected_text[-500:] if collected_text else "",
                            tokens_in=total_tokens_in,
                            tokens_out=total_tokens_out,
                        )
                    self._last_progress_time = current_time

                if "token" in event:
                    collected_text += event["token"]
                    total_tokens_out += len(event["token"]) // 4  # Rough estimate
                elif event.get("type") == "done" or event.get("done"):
                    break
        except _asyncio.CancelledError:
            log.info("[QueryLoop] Streaming cancelled at turn %d", self._turn)

        if self.message_manager:
            self.message_manager.emit_progress_event(
                content=collected_text[-500:],
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
            )

        # Record token usage
        self.token_tracker and self.token_tracker.record_turn(
            turn_number=self._turn,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )

        return collected_text

    # HANDLE LLM RESPONSE FORMAT TYPE
    def _get_response_format_type(self, response_str: str) -> dict:
        format_map = {
            "text": {"type": "text"},
            "json": {"type": "json_object"},
        }
        return format_map.get(response_str, {"type": "text"})

    # PARSER FOR LLM API RESPONSE
    def _parse_response(
        self,
        assistant_reply: Optional[Any]
    ) -> tuple[str, list[dict]]:
        """Parse LLM API response into (text, tool_calls).

        Handles both streaming and non-streaming responses.
        Streaming returns a raw string. Non-streaming returns a
        ChatCompletion object with choices.
        """
        tool_calls = []
        final_text = ""

        if assistant_reply is None:
            log.warning("[QueryLoop] Parse response: assistant_reply is None")
            return "", []

        if isinstance(assistant_reply, dict) and "error" in assistant_reply:
            log.warning(f"[QueryLoop] Parse response: error in assistant_reply: {assistant_reply['error']}")
            return "", []

        # Check if it's a raw string (streaming mode)
        if isinstance(assistant_reply, str):
            final_text = assistant_reply
            log.info("[QueryLoop] Parsed string response: %d chars", len(final_text))
            tool_calls.extend(self._parse_text_tool_calls(final_text))
            return final_text, tool_calls

        # Check if it has choices (ChatCompletion object)
        if hasattr(assistant_reply, "choices") and assistant_reply.choices:
            choice = assistant_reply.choices[0]
            message = choice.message

            # Text content
            if message.content:
                final_text = message.content

            # Tool calls
            if message.tool_calls:
                for tc in message.tool_calls:
                    if hasattr(tc.function, "name") and hasattr(tc.function, "arguments"):
                        tool_calls.append({
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments),
                        })

            # FALLBACK: Parse text blocks if no native tool calls were found
            if not tool_calls and final_text:
                tool_calls.extend(self._parse_text_tool_calls(final_text))

            log.info(f"[QueryLoop] Parsed response: {len(final_text)} chars, {len(tool_calls)} tool calls")
            return final_text, tool_calls

        # Unexpected type — log and return empty
        log.warning(f"[QueryLoop] Unhandled response type: {type(assistant_reply).__name__}")
        return "", []

    def _parse_text_tool_calls(self, text: str) -> list[dict]:
        tool_calls = []
        import re
        import json
        import uuid
        
        pattern = re.compile(r"```tool_code\s*\n(.*?)\n```", re.DOTALL)
        for match in pattern.finditer(text):
            block = match.group(1).strip()
            if ":" in block:
                parts = block.split(":", 1)
                tool_name = parts[0].strip()
                args_str = parts[1].strip()
                
                tool_input = {}
                if args_str.startswith("{") and args_str.endswith("}"):
                    try:
                        tool_input = json.loads(args_str)
                    except json.JSONDecodeError:
                        tool_input = self._map_string_to_tool_arg(tool_name, args_str)
                else:
                    tool_input = self._map_string_to_tool_arg(tool_name, args_str)
                    
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:10]}",
                    "name": tool_name,
                    "input": tool_input
                })
        return tool_calls
        
    def _map_string_to_tool_arg(self, tool_name: str, args_str: str) -> dict:
        tool_def = registry.get(tool_name)
        if not tool_def or not tool_def.input_schema or not tool_def.input_schema.get("properties"):
            return {"args": args_str}
        first_prop = list(tool_def.input_schema["properties"].keys())[0]
        return {first_prop: args_str}

    # TOOL CALL EXECUTION WITH PERMISSION CHECK AND HOOKS
    async def _execute_tools(
        self,
        tool_calls: list[dict],
        tools: list[Any] | dict | None,
    ) -> list[dict]:
        """Execute tool calls with permission check, hooks, and structured results."""

        # Build lookup: name -> tool def (handles both list and dict of tools)
        tool_map = {}
        if isinstance(tools, dict):
            tool_map = tools
        elif isinstance(tools, list):
            for tool_item in tools:
                if isinstance(tool_item, dict):
                    tool_map[tool_item.name] = tool_item
                else:
                    tool_map[tool_item.name] = tool_item

        executor = ToolExecutor(permission_checker=self._permission_checker)
        results = []

        for tool_call_item in tool_calls:
            tool_id = tool_call_item["id"]
            tool_name = tool_call_item["name"]
            tool_description = tool_map.get(tool_name)
            tool_arguments = tool_call_item["input"]


            # VALIDATE TOOL DESCRIPTION
            if tool_description is None:
                results.append({
                    "tool_call_id": tool_id,
                    "content": f"Error: Unknown tool: {tool_name}",
                    "is_error": True,
                })
                continue

            # VALIDATE TOOL ARGUMENTS
            if tool_arguments is None:
                results.append({
                    "tool_call_id": tool_id,
                    "content": f"Error: Invalid Tool arguments: {tool_arguments}",
                    "is_error": True
                })
                continue

            # BLOCK REDUNDANT FILE READS
            if tool_name == "FileRead" and isinstance(tool_arguments, dict) and "file_path" in tool_arguments:
                file_path = tool_arguments["file_path"]
                if file_path in self._executed_tools:
                    results.append({
                        "tool_call_id": tool_id,
                        "content": f"System Warning: You already read this file '{file_path}' in a previous turn. Please check your conversation history or scratchpad instead of reading it again.",
                        "is_error": True
                    })
                    continue
                else:
                    self._executed_tools.add(file_path)

            result = await executor.execute(tool=tool_description, tool_call_id=tool_id, args=tool_arguments)
            content = result.content

            # Detect RequestUserInput awaiting-input marker
            if content and content.startswith("__AWAITING_USER_INPUT__|"):
                self._awaiting_input = True
                self._interaction_tool_call_id = tool_id
                log.info("[QueryLoop] RequestUserInput triggered — pausing for user input")
                # Parse the interaction details and emit SSE events via message_manager
                if self.message_manager:
                    try:
                        _, prompt, ui_type, options_json, title = content.split("|", 4)
                        options = json.loads(options_json)
                    except Exception:
                        prompt, ui_type, options, title = "Please select an option", "select", [], ""
                    try:
                        self.message_manager.emit_tool_use_start(tool_id, tool_name, tool_arguments)
                        self.message_manager.emit_tool_interaction_request(tool_id, ui_type, options, prompt, title)
                    except Exception:
                        pass  # SSE events are best-effort
                # Still append the marker as the tool result so the LLM sees it was called
                results.append({
                    "tool_call_id": tool_id,
                    "content": content,
                    "is_error": False,
                    "_is_interactive": True,
                })
                continue

            results.append({
                "tool_call_id": result.tool_call_id,
                "content": content,
                "is_error": result.is_error,
            })

        return results
