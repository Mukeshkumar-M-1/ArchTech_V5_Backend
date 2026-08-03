"""
ExecutionEngine - The runtime boundary for executing tasks.

Hides LLM turning, tool execution, and prompt assembly from the AgentKernel.
The Kernel says "Execute Task", and this engine handles the Turn -> Tool -> Turn loop,
emitting events along the way.
"""

import asyncio
import copy
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional
from .event_bus import EventBus
from .agent_state import AgentStateStore
from .execution_history import ContextConfig, ContextManager, ExecutionStore, ExecutionTurn
from AgentCore.execution.executor import ToolExecutor
from AgentCore.execution.registry import registry
from AgentCore.orchestration.contracts import TaskContract

log = logging.getLogger(__name__)

# Module-level tool event queue for SSE forwarding.
# Set by routes.py via set_tool_event_queue() before each generation request.
_tool_event_queue: Optional[asyncio.Queue] = None


def set_tool_event_queue(queue: Optional[asyncio.Queue]) -> None:
    """Set the global tool event queue for SSE forwarding."""
    global _tool_event_queue
    _tool_event_queue = queue


def get_tool_event_queue() -> Optional[asyncio.Queue]:
    """Get the current tool event queue (if any active generation)."""
    return _tool_event_queue

class ExecutionEngine:
    """Executes tasks by managing the LLM interaction loop and tool execution."""
    
    def __init__(self, event_bus: EventBus, agent_state_store: AgentStateStore, tool_executor: ToolExecutor):
        self.event_bus = event_bus
        self.agent_state_store = agent_state_store
        self.tool_executor = tool_executor
        log.info("[ExecutionEngine] Initialized.")

    async def execute_task(self, task_id: str, task_contract: TaskContract, tools: List[Any], max_turns: int = 10) -> str:
        """Run the execution loop for a specific task.
        
        Args:
            task_id: Identifier for the current task.
            user_context: The assembled prompt context for this task.
            tools: List of tools available to the LLM.
            max_turns: Maximum number of LLM turns before forcing an exit.
            
        Returns:
            The final textual result of the execution.
        """
        log.info(f"[ExecutionEngine] Starting execution Task=[{task_id}] with {len(tools)} tools.")
        
        self.agent_state_store.set_active_task(task_id)
        self.agent_state_store.update_state("EXECUTE")
        agent_version_data: Dict[str, List[Any]] = {}
        agent_turn_control: Dict[str, List[Any]] = {}
        agent_tool_control: Dict[str, Any] = {}
        if self.agent_state_store.agent_state.version_count == 0:
            self.agent_state_store.update_version_count()

        """
        ['project_id', 
        'section_number', 
        'section_heading', 'section_filename', 'section_subsection', 
        'section_dependency_data', 'section_template_content', 
        'knowledge_content', 'required_capabilities']
        """
        agent_context_data = task_contract.execution_context or {}
        task_section_heading = agent_context_data.get("section_heading", "")

        # Build user context message
        build_user_message = [
            f"Goal: {task_contract.goal}",
            "",
            "---",
            "## TEMPLATE CONTENT",
            str(agent_context_data.get('section_template_content', '')),
            "---",
            "## TEMPLATE SUB-SECTION HEADING",
            str(agent_context_data.get("section_subsection", "")),
            "---",
            "",
            "## KNOWLEDGE DATA",
            str(agent_context_data.get('knowledge_content', '')),
            "---",
        ]   
        build_user_message_context = "\n".join(build_user_message)

        # Build developer message
        build_developer_message = [
            "When generating the final section content, output ONLY the markdown content. "
            "Do NOT include any introductory sentences, explanations, summaries, or trailing text. "
            "The entire response must be the final section content alone — no preamble, no commentary.",
            "## ABSOLUTELY NO EXPLANATION TEXT",
            "Your response must start with the first heading of the section content and end with the last line of the section content.",
            "Do NOT include phrases like 'Here is the content', 'Now I have all the information', 'Key data extracted', 'Now generating the final output', or any similar commentary.",
            "Do NOT list extracted data or acronyms before the content.",
            "The response must contain ZERO text outside of the actual section content. Anything before the first heading or after the last table is a violation.",
            "## NO REQUIREMENT IDs",
            "Do NOT generate or include any requirement identifiers such as REQ-XXXX, HAR-XXXX, SOF-XXXX, GEN-XXXX, FUN-XXXX or any similar prefixed ID format in the output. If such IDs appear in the context or template, omit them entirely from the generated content.",
            "## TEMPLATE FORMAT",
            "\n\n",
            str(agent_context_data.get("section_template_content", "")),
            "\n\n",
        ]

        if agent_context_data.get("section_number") in ["06", "6"]:
            build_developer_message.extend([
                "## FUNCTIONAL REQUIREMENTS — TEST CASE GENERATION INSTRUCTIONS",
                "You are generating detailed functional requirements and test case specifications for Section 06. "
                "Use the provided Internal Memory Test Case Index and available file tools to dynamically build each structured sub-requirement.",
                "",
                "### CRITICAL STRUCTURAL & HEADING RULES",
                "1. **Parent Component Sections (`###` Level):**",
                "   - Create a `### 4.X.Y [Component Name]` heading for every major requirement (e.g., `### 4.3.3 EEPROM Test`).",
                "   - Include a parent table formatted as: `**Table 4.NN [Component Name]**` containing the primary Requirement ID and high-level description.",
                "",
                "2. **Individual Test Cases (`####` Level):**",
                "   - Create a separate `#### 4.X.Y.Z [Test Case Name]` subsection for EVERY individual test case defined in the test case files.",
                "   - **STRICT FORBIDDEN:** Do NOT condense, consolidate, or lump multiple test cases into single paragraphs or single tables.",
                "   - Use exact test case names from the source files — do NOT rename, hallucinate, or omit any test case.",
                "   - Include a dedicated table formatted as: `**Table 4.NN.Z [Test Case Name]**` containing its specific Sub-Requirement ID and description.",
                "",
                "3. **Table Column Standard:**",
                "   - Every table in this section MUST strictly adhere to this 2-column format:",
                "     `| Sub-Requirement ID | Requirement Description |`",
                "",
                "---",
                "### EXEMPLAR FORMAT",
                "Follow this exact markdown structure and syntax:",
                "",
                "```markdown",
                "### 4.3.3 EEPROM Test",
                "",
                "**Table 4.21 EEPROM Test**",
                "| Sub-Requirement ID | Requirement Description |",
                "|-------------------|-------------------------|",
                "| DPXMC5049_FW_EEPROM_03_03 | High-level summary of EEPROM hardware testing scope... |",
                "",
                "#### 4.3.3.1 Data Retention Test",
                "",
                "**Table 4.21.1 Data Retention Test**",
                "| Sub-Requirement ID | Requirement Description |",
                "|-------------------|-------------------------|",
                "| DPXMC5049_FW_EEPROM_03_03_01 | Qualifies authenticity and integrity of the memory device. A read operation shall be performed to verify the signature... |",
                "",
                "#### 4.3.3.2 Read/Write Test",
                "",
                "**Table 4.21.2 Read/Write Test**",
                "| Sub-Requirement ID | Requirement Description |",
                "|-------------------|-------------------------|",
                "| DPXMC5049_FW_EEPROM_03_03_02 | Validates read, write, and erase verification operations across designated memory banks... |",
                "```",
                "",
                "---",
                "### INTERNAL MEMORY — TEST CASE INDEX SOURCE DATA:",
                "\n",
                str(agent_context_data.get("internal_memory_content", "")),
                "\n---",
                "",
            ])
            # log.info(f"[Execution_engine] [Internal_Memory] : {agent_context_data.get("internal_memory_content", "")}")

        if agent_context_data.get("section_number") in ["09", "9"]:
            # Filter traceability_data to only include sections needed for the matrix
            try:
                trace_data = json.loads(agent_context_data.get("traceability_data", "[]"))
                trace_data = [section_item for section_item in trace_data if section_item.get("section_number") in ("06", "6")]
                filtered_traceability = "\n\n".join(section_item.get("generated_data", "") for section_item in trace_data)
            except Exception as exception:
                log.info(f"[Execution_engine] [section_09] Prompt build is not working : {exception}")
                filtered_traceability = ""

            build_developer_message.extend([
                "## SYSTEM INSTRUCTION: REQUIREMENTS TRACEABILITY MATRIX (RTM) GENERATOR",
                "You are an automated, deterministic requirements engineering processor. Your sole task is to construct a precise Requirements Traceability Matrix (RTM) as a Markdown table that maps SRS Requirement IDs to HRS Requirement IDs based strictly on provided data.",
                "",
                "### OUTPUT SCHEMA & FORMAT",
                "Produce EXACTLY one Markdown table following this structure with zero conversational fluff before or after:",
                "",
                "| S.No | SRS Requirement ID | HRS Requirement ID | SRS Section Reference |",
                "|------|-------------------|-------------------|----------------------|",
                "| 1 | DPXMC5049_TARGET_BRD_DETAILS_02_01 | DP-XMC-5049-HRS-001 | 2.1 |",
                "| 2 | DPXMC5049_FW_EEPROM_03_03 | DP-XMC-5049-HRS-003 | 3.3.1 |",
                "",
                "### MULTI-PASS EXTRACTION ALGORITHM",
                "Follow these passes sequentially to compile the table:",
                "",
                "#### Pass 1: Hierarchy & ID Harvest",
                "- Traverse `GENERATED SECTION DATA` sequentially line by line.",
                "- Track the current active section heading/number from Markdown headings (e.g., `### 4.3.3 EEPROM Test` -> `4.3.3`).",
                "- Extract ALL requirement IDs matching the pattern regex `DPXMC5049_[A-Za-z0-9_]+`.",
                "- Include both base IDs and all sub-requirement variants exactly as they appear in the source text.",
                "",
                "#### Pass 2: Mapping & Resolution",
                "For each extracted SRS Requirement ID, determine the HRS Requirement ID using this deterministic resolution hierarchy:",
                "1. **Exact Lookup:** Search `KNOWLEDGE DATA` for an explicit mapping to a `DP-XMC-5049-HRS-*` ID.",
                "2. **Structural Inference:** If no explicit lookup table entry exists, apply structural rule (e.g., `DPXMC5049_FW_EEPROM_03_03` maps to `DP-XMC-5049-HRS-003`).",
                "3. **Fallback:** If neither exact lookup nor structural pattern matches, set value to `TBD`.",
                "",
                "#### Pass 3: Deduplication, Sorting, & Indexing",
                "- Deduplicate entries so every distinct `SRS Requirement ID` appears in exactly ONE row.",
                "- Sort all rows primarily by `SRS Section Reference` (ascending numerical order), and secondarily by `SRS Requirement ID` alphabetically.",
                "- Assign continuous, sequential integer `S.No` starting at `1` (1, 2, 3...) with no gaps.",
                "",
                "### STRICT COMPLIANCE RULES",
                "1. **NO HALLUCINATIONS:** Only include IDs that explicitly exist in `GENERATED SECTION DATA`.",
                "2. **NO BLANK CELLS:** Every column must have a value (`TBD` if unmapped).",
                "3. **NO TEXT OUTSIDE TABLE:** Output only the requested Markdown table.",
                "",
                "---",
                "### GENERATED SECTION DATA (Source Data):",
                "",
                filtered_traceability,
                "---",
                "",
                "### KNOWLEDGE DATA (HRS Mapping Source):",
                str(agent_context_data.get("knowledge_content", "")),
                "---",
                "",
            ])
        # log.info(f"[Execution_engine] [Traciability_data] [section: {agent_context_data.get("section_number")}] : {str(agent_context_data.get("traceability_data", ""))} ")

        build_developer_message_context = "\n".join(build_developer_message)

        base_messages = [
            {"role": "developer", "content": build_developer_message_context},
            {"role": "user", "content": build_user_message_context},
        ]

        context_config = ContextConfig(recent_turns=3, max_context_messages=30)
        store = ExecutionStore(config=context_config)
        store.set_base_messages(base_messages)
        context_manager = ContextManager(config=context_config)

        for agent_turn in range(1, max_turns + 1):
            # Build bounded LLM context from store
            # ContextManager splits all turns into:
            #   old turns → programmatic summary
            #   recent N turns → full messages
            llm_messages = context_manager.build_context(
                base_messages=store.base_messages,
                execution_turns=store.get_all_turns(),
                store=store,
            )

            if not self.agent_state_store.increment_loop():
                log.warning("[ExecutionEngine] Loop budget exceeded. Halting execution.")
                return f"Error: Execution halted with max loop [{self.agent_state_store.agent_state.loop_count}/{self.agent_state_store.agent_state.max_loops}]"            
            
            # Emit Agent Turn status
            await self.event_bus.emit("TurnStarted", {
                "task_id": task_id,
                "turn": agent_turn,
            })

            # Emit SSE Tool Turn Status
            try:
                sse_tool_queue = get_tool_event_queue()
                if sse_tool_queue:
                    sse_tool_queue.put_nowait({
                        "type": "turn_start",
                        "turn": agent_turn,
                        "task_id": task_id,
                    })
            except Exception as exception:
                log.error(f"[ExecutionEngine] [Error] Tool Execution : {exception}")
                pass
            
            # Execute agent llm call
            try:
                log.info(f"[ExecutionEngine] [LLM_Message_list] roles: {[getattr(m, 'role', m.get('role', '?')) for m in llm_messages]}")
                agent_response_context, result_tool_calls = await self._simulate_or_call_llm(agent_turn=agent_turn, messages=llm_messages, tools=tools, custom_developer_message=build_developer_message_context)
                log.info(f"[ExecutionEngine] [LLM_Message] Tak ID: [{task_id}] \n LLM Message Input: [{len(llm_messages)}], Turn: [{agent_turn}], agent_response: [{len(agent_response_context)}]")

            except Exception as exception:
                log.error(f"[ExecutionEngine] LLM Call failed: {exception}", exc_info=True)
                return f"Error: LLM Call failed: {str(exception)}"
            
            # Agent Execution result
            if not result_tool_calls and agent_response_context is not None:
                agent_response_context = agent_response_context
                await self.event_bus.emit("TaskCompleted", {
                    "task_id": task_id,
                    "result": agent_response_context
                })
                agent_version_data.setdefault(f"version_v{self.agent_state_store.agent_state.version_count}", []).append({
                    "Data": copy.deepcopy(agent_turn_control),
                    "agent_generated_context": agent_response_context,
                })
                self.agent_state_store.agent_state.version_data = agent_version_data
                return agent_response_context
                
            # Agent Tool result
            if result_tool_calls:
                assistant_message = {"role": "assistant", "content": agent_response_context or "", "tool_calls": []}

                # Build Assistant message
                for tool_call_item in result_tool_calls:
                    assistant_message["tool_calls"].append({
                        "id": tool_call_item["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call_item["name"],
                            "arguments": json.dumps(tool_call_item["input"])
                        }
                    })

                # Execute tools
                tool_messages: List[Dict[str, Any]] = []
                tool_meta_list: List[Dict[str, Any]] = []
                for tool_call_item in result_tool_calls:
                    tool_name = tool_call_item["name"]
                    tool_call_id = tool_call_item["id"]
                    tool_arguments = tool_call_item["input"]

                    await self.event_bus.emit("ToolStarted", {
                        "tool_name": tool_name,
                        "tool_call_id": tool_call_id
                    })

                    # Emit SSE tool_started event for frontend progress layer
                    try:
                        sse_tool_queue = get_tool_event_queue()
                        if sse_tool_queue:
                            sse_tool_queue.put_nowait({
                                "type": "tool_started",
                                "tool_name": tool_name,
                                "tool_call_id": tool_call_id,
                                "input": tool_arguments,
                                "section": task_section_heading,
                            })
                    except Exception as exception:
                        log.error(f"[ExecutionEngine] Error in tool start: {exception}")
                        pass

                    tool_execution_start_time = time.monotonic()

                    # Execute tool via ToolExecutor
                    tool_output = ""
                    tool_execution_succeeded = True

                    if self.tool_executor:
                        tool_definition = registry.get(tool_name)
                        if tool_definition:
                            tool_execution_result = await self.tool_executor.execute(tool_definition, tool_call_id, tool_arguments)
                            tool_output = tool_execution_result.content
                            tool_execution_succeeded = not tool_execution_result.is_error
                        else:
                            tool_output = f"Error: Tool '{tool_name}' not found."
                            tool_execution_succeeded = False
                    else:
                        tool_output = f"Simulated result for {tool_name}"
                        tool_execution_succeeded = True

                    tool_execution_duration_ms = (time.monotonic() - tool_execution_start_time) * 1000

                    await self.event_bus.emit("ToolFinished", {
                        "tool_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "is_error": not tool_execution_succeeded,
                        "content_length": len(tool_output)
                    })

                    # Emit SSE tool_finished event for frontend progress layer
                    truncated_tool_output = (tool_output[:200] + "...") if len(tool_output) > 200 else tool_output
                    agent_tool_data = {
                        "tool_id": tool_call_id,
                        "tool_name": tool_name,
                        "tool_input_argument": tool_arguments,
                        "tool_output": truncated_tool_output,
                    }
                    try:
                        sse_tool_queue = get_tool_event_queue()
                        if sse_tool_queue:
                            sse_tool_queue.put_nowait({
                                "type": "tool_finished",
                                "tool_name": tool_name,
                                "tool_call_id": tool_call_id,
                                "is_error": not tool_execution_succeeded,
                                "output": truncated_tool_output,
                                "duration_ms": round(tool_execution_duration_ms, 1),
                                "section": task_section_heading,
                            })

                        agent_tool_control.setdefault(agent_turn, []).append(agent_tool_data)
                    except Exception as exception:
                        log.error(f"[ExecutionEngine] Error in tool finished: {exception}")
                        pass

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_output
                    }
                    tool_messages.append(tool_msg)
                    tool_meta_list.append(agent_tool_data)

                exec_turn = ExecutionTurn.from_flat_messages(
                    turn_number=agent_turn,
                    assistant_msg=assistant_message,
                    tool_msgs=tool_messages,
                    tool_meta=tool_meta_list,
                )
                store.append_turn(exec_turn)
                log.info(f"[ExecutionEngine] Turn {agent_turn} stored (complete={exec_turn.is_complete}, tools={len(tool_messages)})")

                # Eagerly extract facts for LLM-enhanced context
                if store.config.enable_llm_fact_extraction:
                    await context_manager.extract_facts_for_turn(exec_turn, store)

            agent_turn_control.setdefault(agent_turn, []).append({
                "turn_control": {str(agent_turn): copy.deepcopy(agent_tool_control.get(agent_turn, []))},
                "generated_context_turn": agent_response_context
            })
            await self.event_bus.emit("TurnCompleted", {
                "task_id": task_id,
                "turn": agent_turn,
                "tool_calls_count": len(result_tool_calls)
            })

            # Log context statistics
            stats = context_manager.get_context_stats(llm_messages)
            log.info(
                f"[ContextStats] turn={agent_turn} history={store.turn_count()} | "
                f"llm_msgs={stats['total_messages']} assistant={stats['assistant_messages']} "
                f"tool={stats['tool_messages']} tool_calls={stats['tool_calls']} "
                f"est_tokens={stats['estimated_tokens']}"
            )

        log.warning(f"[ExecutionEngine] Task '{task_id}' reached max turns ({max_turns}) without completing.")
        return "Error: Max turns reached without final answer."
    
    async def _simulate_or_call_llm(self, agent_turn: int, messages: List[Dict[str, Any]], tools: List[Any], custom_developer_message: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Calls the actual LLM API using the legacy QueryLoop's fallback and parsing logic.
        """
        from AgentCore.execution.query_loop import QueryLoop
        from AgentCore.execution.system_prompt import SystemPromptManager

        log.info(f"[ExecutionEngine] [Execute_LLM_Call] Turn: [{agent_turn}]")
        query_loop = QueryLoop(streaming_enabled=False, fallback_chain=["opus46"])
        
        tool_definitions = []
        if tools:
            for tool in tools:
                if isinstance(tool, str):
                    tool_def = registry.get(tool)
                    if not tool_def:
                        log.warning(f"Tool {tool} not found in registry")
                        continue
                    tool = tool_def
                    
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.get_description(),
                        "parameters": tool.input_schema,
                    },
                })
                
        system_prompt = SystemPromptManager()
        system_prompt_block = system_prompt.build(tool_definitions=tool_definitions)
        system_prompt_message = "\n".join(
            block_item.content for block_item in system_prompt_block if block_item.content
        )

        system_prompt_message += "\n" + custom_developer_message

        try:
            response = await query_loop._LLM_call_with_fallback(
                messages=messages,
                system_prompt=system_prompt_message,
                tools=tool_definitions if tool_definitions else None,
                model="opus46",
                max_tokens=32768,
                temperature=0.1
            )
            
            final_text, result_tool_calls = query_loop._parse_response(response)
            return final_text, result_tool_calls
            
        except Exception as exception:
            log.error(f"[ExecutionEngine] Real LLM Call failed: {exception}", exc_info=True)
            return f"Error: LLM Call failed: {str(exception)}", []

    def _clean_final_output(self, raw_llm_output: str) -> str:
        """Strip LLM preamble, code fences, and commentary from final document output."""
        if not raw_llm_output:
            return raw_llm_output

        cleaned_text = raw_llm_output

        # Remove markdown code fence wrapper (```markdown ... ``` or ``` ... ```)
        cleaned_text = re.sub(r"^```markdown\s*\n", "", cleaned_text, count=1)
        cleaned_text = re.sub(r"^```\s*\n", "", cleaned_text, count=1)
        cleaned_text = re.sub(r"\n```\s*$", "", cleaned_text, count=1)

        # Remove preamble: strip all lines before the first level-1 heading (#)
        first_heading_match = re.search(r"^#\s+\S", cleaned_text, re.MULTILINE)
        if first_heading_match:
            cleaned_text = cleaned_text[first_heading_match.start():]

        # Remove leading/trailing whitespace
        cleaned_text = cleaned_text.strip()

        return cleaned_text
