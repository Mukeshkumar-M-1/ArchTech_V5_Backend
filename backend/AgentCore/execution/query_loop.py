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
from .message_manager import SSEChatMessageManager
from .context_compaction import ContextCompactPipeline
from .session_memory import SessionMemoryExtractor, SessionMemoryCache, CompactSummary
from .system_prompt import SystemPromptManager
from .tool_registry import registry, get_tool_definition, get_selected_tool_definition
from .tool_executor import ToolExecutor
from .abort_controller import get_hierarchy

log = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 20
DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_MODEL_OPUS = "opus46"
DEFAULT_FALLBACK_CHAIN_MODEL = ["opus46"]
DEFAULT_TOKENS = 4096
DEFAULT_TEMP = 0.1
DEFAULT_TOOL_CONCURRENCY = 1
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_SLEEP_TIME = 10
DEFAULT_COMPACT_TOKEN_BUDGET = 100_000

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
        fallback_chain: list[str] = DEFAULT_FALLBACK_CHAIN_MODEL,
        abort_controller: Any = None,
        session_id: str | None = None,
        compact_token_budget: int = DEFAULT_COMPACT_TOKEN_BUDGET,
        permission_checker: Any = None,
        streaming_enabled: bool = False,
        project_id: str | None = None,
        context_injector: Any = None,
        observation_manager: Any = None,
        decision_manager: Any = None,
        transcript_writer: Any = None,
        message_manager: SSEChatMessageManager | None = None,
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
        self._compaction = ContextCompactPipeline(token_budget=compact_token_budget)
        self._memory_extractor = SessionMemoryExtractor()
        self._memory_cache = SessionMemoryCache(self._project_id)
        self._memory_adapter = CompactSummary(self._memory_cache)
        self._system_prompt_manager = SystemPromptManager()
        self._tool_definition = get_tool_definition()
        self._turn = 0
        self._last_progress_time = 0
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

    # HANDLE LLM LOOP
    async def run(
        self,
        initial_messages: list[dict],
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
        log.info("[QueryLoop] run: %d messages, %d max turns, model=%s", len(initial_messages), self.max_turns, model)
        self._awaiting_input = False
        self._interaction_tool_call_id = None
        final_text = ""

        try:
            for _ in range(self.max_turns):
                self._turn += 1
                log.info(f"\n\n ===== TURN {self._turn} =====")

                # HANDLE ABORT SIGNAL
                if self.abort_controller and self.abort_controller.signal.is_aborted:
                    log.info("[QueryLoop] Aborted at [Turn: %d]", self._turn)
                    break

                # BUILD CUSTOM SYSTEM PROMPT
                if system_prompt:
                    system_prompt_message = system_prompt
                else:
                    current_tool_definitions = []
                    if tools:
                        current_tool_definitions = get_selected_tool_definition(tools_list=tools)
                    else:
                        current_tool_definitions = self._tool_definition
                        
                    system_prompt_blocks = self._system_prompt_manager.build(
                        tool_definitions=current_tool_definitions,
                    )
                    system_prompt_message = "\n".join(
                        block_item.content for block_item in system_prompt_blocks if block_item.content
                    )

                # BUILD API MESSAGE
                api_messages = initial_messages + self._message_history

                # HANDLE LLM API CALL
                assistant_reply = await self._LLM_api_call(
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

                # HANDLE LLM RESPONSE PARSER
                final_text, tool_calls = self._parse_response(assistant_reply)
                log.info(f"[QueryLoop] Turn {self._turn}: API response received, text_len={len(final_text)}, tool_calls_count={len(tool_calls)}")
                
                # VALIDATE LLM RESULT AND TOOL CALLS
                if not final_text.strip() and not tool_calls:
                    continue
                
                # HANDLE LLM ASSISTANT MESSAGE HISTORY (MESSAGE, TOOL CALLS)
                assistant_msg = {"role": "assistant", "content": final_text}
                if tool_calls:
                    native_tool_calls = []
                    for tool_call_item in tool_calls:
                        native_tool_calls.append({
                            "id": tool_call_item["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call_item["name"],
                                "arguments": json.dumps(tool_call_item["input"])
                            }
                        })
                    assistant_msg["tool_calls"] = native_tool_calls
                self._message_history.append(assistant_msg)

                # HANDLE LLM ASSISTANT MESSAGE HISTORY (TOOLS RESULT)
                tool_results = []
                if tool_calls:
                    tool_results = await self._execute_tools(llm_tool_calls=tool_calls, tools_list=tools)
                    for tool_index, tool_call_item in enumerate(tool_calls):
                        if tool_index < len(tool_results):
                            executed_tool_result = tool_results[tool_index]
                            self._message_history.append({
                                "role": "tool",
                                "tool_call_id": tool_call_item.get("id", ""),
                                "name": tool_call_item.get("name", ""),
                                "content": executed_tool_result.get("content", "")
                            })
                    log.info(f"[QueryLoop] Turn {self._turn} complete, {len(tool_calls)} tools executed")

                # HANDLE LLM USER INTERACTION
                if self._awaiting_input:
                    log.info(f"[QueryLoop] Paused at turn {self._turn} awaiting user input")
                    updated_message_history: list[dict] = []

                    for message_item in self._message_history:
                        if not (isinstance(message_item.get("content"), str)) and message_item.get("content", "").startswith("__AWAITING_USER_INPUT__") and not message_item.get("tool_calls"):
                            updated_message_history.append(message_item)
                    self._message_history = updated_message_history

                    return {
                        "_status": "awaiting_input",
                        "_turn": self._turn,
                        "_tool_call_id": self._interaction_tool_call_id,
                    }

                # Text-only response (no tool calls) is the final answer —
                # stop looping so we don't re-prompt the model with its own reply.
                if not tool_calls:
                    break

            # HANDLE LOOP END
            log.info(f"[QueryLoop] Loop finished after [{self._turn}] turns")

            # HANDLE EMIT PROCESS MESSAGE
            if not self._streaming_enabled and self.message_manager and final_text:
                try:
                    self.message_manager.emit_progress_event(final_text)
                except Exception as exception:
                    log.info(f"[QueryLoop] Exception occured at loop run : {exception}")
                    pass
        except Exception as exception:
            log.error(f"[QueryLoop] Error: {exception}", exc_info=True)
            final_text = f"Error: {type(exception).__name__}: {exception}"

        return final_text

    # HANDLE SETUP USER MESSAGE
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

    # API CALL DESIDER FOR (STREAMING | CHAT_COMPLETION)
    async def _LLM_api_call(
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
                messages, system_prompt, tool_definitions, model, max_tokens, temperature
            )

        # COMPLETE API CALLING
        return await self._LLM_chatcomplete_call(
            messages=messages, system_prompt=system_prompt,
            tools=tool_definitions, model=model, max_tokens=max_tokens,
            temperature=temperature, response_format=api_response_format
        )

    # HANDLE NON-STREAMING API CALLING
    async def _LLM_chatcomplete_call(
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

        # Primary LLM model
        primary_model = model

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
        log.info(f"[QueryLoop] Turn {self._turn}: Message : {content}")
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

    # HANDLE API STREAMING CALLING
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
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        handler = StreamingLLMHandler(primary_model)
        collected_text = ""

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
                        )
                    self._last_progress_time = current_time

                if "token" in event:
                    collected_text += event["token"]
                elif event.get("type") == "done" or event.get("done"):
                    break
        except _asyncio.CancelledError:
            log.info("[QueryLoop] Streaming cancelled at turn %d", self._turn)

        if self.message_manager:
            self.message_manager.emit_progress_event(
                content=collected_text[-500:],
            )
            
        return collected_text

    # HANDLE LLM RESPONSE FORMAT TYPE
    def _get_response_format_type(self, response_str: str) -> dict:
        format_map = {
            "text": {"type": "text"},
            "json": {"type": "json_object"},
        }
        return format_map.get(response_str, {"type": "text"})

    # PARSER FOR LLM RESPONSE MESSAGE
    def _parse_response(
        self,
        assistant_reply: Optional[Any]
    ) -> tuple[str, list[dict]]:
        """Parse LLM API response into (text, tool_calls).

        Handles both streaming and non-streaming responses.
        Streaming returns a raw string. Non-streaming returns a
        ChatCompletion object with choices.
        """
        assistant_tool_calls = []
        assistant_text_message = "" 

        # VALIDATE ASSISTANT MESSAGE
        if assistant_reply is None:
            log.warning("[QueryLoop] Parse response: assistant_reply is None")
            return "", []
        
        # VALIDATE ERROR ASSISTANT MESSAGE
        if isinstance(assistant_reply, dict) and "error" in assistant_reply:
            log.warning(f"[QueryLoop] Parse response: error in assistant_reply: {assistant_reply['error']}")
            return "", []

        # VALIDATE ASSISTANT MESSAGE (TEXT REPLY)
        if isinstance(assistant_reply, str):
            assistant_text_message = assistant_reply
            log.info("[QueryLoop] [TEXT_PARSED] Parsed string response: %d chars", len(assistant_text_message))
            assistant_tool_calls.extend(self._parse_message_text_tool_calls(text_content=assistant_text_message))
            return assistant_text_message, assistant_tool_calls

        # VALIDATE ASSISTANT MESSAGE (TOOL CALL)
        if hasattr(assistant_reply, "choices") and assistant_reply.choices:
            llm_message_choice = assistant_reply.choices[0]
            llm_message = llm_message_choice.message

            # LLM TEXT MESSAGE
            if llm_message.content:
                assistant_text_message = llm_message.content

            # LLM TOOL CALLS
            if llm_message.tool_calls:
                for tool_call_item in llm_message.tool_calls:
                    if hasattr(tool_call_item.function, "name") and hasattr(tool_call_item.function, "arguments"):
                        assistant_tool_calls.append({
                            "id": tool_call_item.id,
                            "name": tool_call_item.function.name,
                            "input": json.loads(tool_call_item.function.arguments),
                        })

            # FALLBACK: PARSING LLM TEXT MESSAGE
            if not assistant_tool_calls and assistant_text_message:
                assistant_tool_calls.extend(self._parse_message_text_tool_calls(text_content=assistant_text_message))

            log.info(f"[QueryLoop] [TEXT_WITH_TOOL_PARSED] Parsed response: [{len(assistant_text_message)} chars], Parsed Tool Calls: [{len(assistant_tool_calls)}]")
            return assistant_text_message, assistant_tool_calls

        # DEFAULT RESPONSE  
        return "", []

    # HANDLE TOOL PARSING FOR TEXT FROM MESSAGE
    def _parse_message_text_tool_calls(self, text_content: str) -> list[dict]:
        """Parse tool calls from LLM text output using ```tool_code fenced blocks."""
        import json
        import re
        import uuid

        parsed_tool_calls: list[dict] = []
        tool_code_pattern = re.compile(r"```tool_code\s*\n(.*?)\n```", re.DOTALL)
        for pattern_item in tool_code_pattern.finditer(text_content):
            tool_code_block = pattern_item.group(1).strip()
            if ":" not in tool_code_block:
                continue

            tool_name_and_args = tool_code_block.split(":", 1)
            tool_name = tool_name_and_args[0].strip()
            tool_args_string = tool_name_and_args[1].strip()

            tool_arguments: dict[str, Any] = {}
            if tool_args_string.startswith("{") and tool_args_string.endswith("}"):
                try:
                    tool_arguments = json.loads(tool_args_string)
                except json.JSONDecodeError:
                    tool_arguments = self._parse_message_tool_args(tool_name, tool_args_string)
            else:
                tool_arguments = self._parse_message_tool_args(tool_name, tool_args_string)

            parsed_tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:10]}",
                "name": tool_name,
                "input": tool_arguments,
            })
        return parsed_tool_calls

    # HANDLE TOOL ARGUMENT PARSING FOR TEXT FROM MESSAGE
    def _parse_message_tool_args(self, tool_name: str, tool_args_string: str) -> dict:
        """Map a bare string argument to a tool's first expected property."""
        tool_definition = registry.get(tool_name)
        if not tool_definition or not tool_definition.input_schema or not tool_definition.input_schema.get("properties"):
            return {"args": tool_args_string}
        first_property = list(tool_definition.input_schema["properties"].keys())[0]
        return {first_property: tool_args_string}

    # TOOL CALL EXECUTION WITH PERMISSION CHECK AND HOOKS
    async def _execute_tools(
        self,
        llm_tool_calls: list[dict],
        tools_list: list[Any] | dict | None,
    ) -> list[dict]:
        """Execute tool calls with permission check, hooks, and structured results."""

        # BUILD TOOL DEFINITION BY NAME
        tool_definitions_by_name: dict[str, Any] = {}

        # VALIDATE TOOL LIST
        if isinstance(tools_list, dict):
            tool_definitions_by_name = tools_list
        elif isinstance(tools_list, list):
            for tool_entry in tools_list:
                if isinstance(tool_entry, dict):
                    tool_definitions_by_name[tool_entry.name] = tool_entry
                else:
                    tool_definitions_by_name[tool_entry.name] = tool_entry

        # TOOL EXECUTOR HANDLER
        tool_executor = ToolExecutor(permission_checker=self._permission_checker)

        # TOOL EXECUTION RESULT LIST
        tool_execution_results: list[dict] = []

        for tool_call_item in llm_tool_calls:
            tool_call_id = tool_call_item["id"]
            tool_name = tool_call_item["name"]
            tool_definition = tool_definitions_by_name.get(tool_name)
            tool_call_args = tool_call_item["input"]

            # VALIDATE TOOL DEFINITION
            if tool_definition is None:
                tool_execution_results.append({
                    "tool_call_id": tool_call_id,
                    "content": f"Error: Unknown tool: {tool_name}",
                    "is_error": True,
                })
                continue

            # VALIDATE TOOL ARGUMENTS
            if tool_call_args is None:
                tool_execution_results.append({
                    "tool_call_id": tool_call_id,
                    "content": f"Error: Invalid tool arguments: {tool_call_args}",
                    "is_error": True
                })
                continue

            # BLOCK REDUNDANT FILE READS
            if tool_name == "FileRead" and isinstance(tool_call_args, dict) and "file_path" in tool_call_args:
                file_path = tool_call_args["file_path"]
                if file_path in self._executed_tools:
                    tool_execution_results.append({
                        "tool_call_id": tool_call_id,
                        "content": f"System Warning: You already read this file '{file_path}' in a previous turn. Please check your conversation history or scratchpad instead of reading it again.",
                        "is_error": True
                    })
                    continue
                else:
                    self._executed_tools.add(file_path)

            # HANDLE EMIT TOOL START STATUS
            if self.message_manager:
                try:
                    self.message_manager.emit_tool_use_start(tool_call_id, tool_name, tool_call_args)
                except Exception as exception:
                    log.info(f"[QueryLoop] Exception occur in message_manager: {exception}")
                    pass

            execution_result = await tool_executor.execute(tool=tool_definition, tool_call_id=tool_call_id, args=tool_call_args)
            tool_output = execution_result.content

            # HANDLE USER INTERACTION TOOL STATUS
            if tool_output and tool_output.startswith("__AWAITING_USER_INPUT__"):
                self._awaiting_input = True
                self._interaction_tool_call_id = tool_call_id
                log.info("[QueryLoop] RequestUserInput triggered — pausing for user input")
                if self.message_manager:
                    try:
                        interaction_payload = tool_output.split("__AWAITING_USER_INPUT__", 1)[1]
                        try:
                            interaction_data = json.loads(interaction_payload)
                        except (json.JSONDecodeError, ValueError):
                            interaction_data = None

                        if isinstance(interaction_data, dict):
                            interaction_prompt = interaction_data.get("prompt", "")
                            interaction_ui_type = interaction_data.get("ui_type", "select")
                            interaction_options = interaction_data.get("options", [])
                            interaction_title = interaction_data.get("title", "")
                        else:
                            log.info(f"[QueryLoop] Interaction default data initialized")
                            interaction_prompt = "Please select an option" 
                            interaction_ui_type = "select"
                            interaction_options = []
                            interaction_title = ""
                            
                    except Exception as exception:
                        log.info(f"[QueryLoop] Interaction default data initialized: {exception}")
                        interaction_prompt = "Please select an option" 
                        interaction_ui_type = "select"
                        interaction_options = []
                        interaction_title = ""

                    try:
                        self.message_manager.emit_tool_interaction_request(
                            tool_call_id=tool_call_id, 
                            ui_type=interaction_ui_type, 
                            options=interaction_options, 
                            prompt=interaction_prompt, 
                            title=interaction_title
                        )
                    except Exception as exception:
                        log.info(f"[QueryLoop] Exception occured at emit tool interaction : {exception}")
                        pass  
                # Still append the marker as the tool result so the LLM sees it was called
                tool_execution_results.append({
                    "tool_call_id": tool_call_id,
                    "content": tool_output,
                    "is_error": False,
                    "_is_interactive": True,
                })
                continue

            tool_execution_results.append({
                "tool_call_id": execution_result.tool_call_id,
                "content": tool_output,
                "is_error": execution_result.is_error,
            })

            # HANDLE EMIT TOOL COMPLETE STATUS
            if self.message_manager:
                try:
                    self.message_manager.emit_tool_use_complete(tool_call_id, tool_output)
                except Exception as exception:
                    log.info(f"[QueryLoop] Exception occured at emit tool complete: {exception}")
                    pass

        return tool_execution_results
