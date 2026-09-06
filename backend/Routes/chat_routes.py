"""
Chat routes — FastAPI endpoints for the agentic chat.

POST /chat/send     — Main streaming endpoint (SSE)
GET  /chat/messages/{session_id} — Fetch conversation history
GET  /chat/sessions  — List active sessions
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from AgentCore.execution.message_manager import SSEChatMessageManager

log = logging.getLogger(__name__)

router = APIRouter()

# Pending interactions: session_id -> {loop, tool_call_id, resumed, messages}
_pending_interactions: dict[str, dict] = {}

# ─── Request models ──────────────────────────────────────────────────

class ChatSendRequest:
    def __init__(self, *, session_id: Optional[str] = None, message: str, project_id: Optional[str] = None):
        self.session_id = session_id
        self.message = message
        self.project_id = project_id

# ─── Streaming endpoint ──────────────────────────────────────────────
async def _chat_stream(
    session_id: str,
    user_message: str,
    project_id: str,
) -> AsyncGenerator[str, None]:
    """Core streaming logic — runs the AgentCore QueryLoop and yields SSE events."""
    from AgentCore import QueryLoop, ChatSessionManager
    from AgentCore.execution.tool_registry import registry

    # Setup session
    from system_config import load_project_settings
    chat_model = (load_project_settings(project_id) or {}).get("default_model")

    record = ChatSessionManager._load(session_id, project_id)

    # setup chatQueue
    chat_event_queue = asyncio.Queue()

    if not record:
        record = ChatSessionManager.create(project_path="", entrypoint="chat", kind="interactive", project_id=project_id)
        session_id = record.session_id

    yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id}, default=str)}\n\n"

    # Store pending interactions for /chat/interact endpoint
    global _pending_interactions
    if session_id not in _pending_interactions:
        _pending_interactions[session_id] = {}

    _pending_interactions[session_id]["loop"] = None
    _pending_interactions[session_id]["tool_call_id"] = None
    _pending_interactions[session_id]["resumed"] = False

    async def run_loop(resume=False):
        try:
            if resume:
                # Remove all stale __AWAITING_USER_INPUT__ markers AND the assistant
                # message that contained the tool calls. Keeping the assistant message
                # with unresolved tool_calls causes the LLM to replay those tools.
                # The user response tool result from set_user_response provides
                # sufficient context for the LLM to continue.
                loop._message_history = [
                    m for m in loop._message_history
                    if not (isinstance(m.get("content"), str) and m.get("content", "").startswith("__AWAITING_USER_INPUT__"))
                    and not m.get("tool_calls")
                ]
                loop._executed_tools.clear()
                chat_event_queue.put_nowait({"type": "turn_start", "turn": loop._turn})
            # Restrict available tools in chat mode to a specific set of tools
            allowed_tools = {"FileRead", "Bash", "Glob", "Search", "ProposeContentEdit", "RequestUserInput"}
            available_tools = [tool_item for tool_item in registry._tools.values() if tool_item.name in allowed_tools]
            run_messages = [{"role": "user", "content": user_message}]
            
            # Chat-specific system prompt to heavily bias the LLM toward using the ProposeContentEdit tool
            chat_system_prompt = (
                "You are ArchTech AI, an advanced engineering assistant operating within the ArchTech IDE Chat Panel.\n"
                "Your primary role is to help the user write, review, and edit technical documentation (such as SRS).\n"
                "CRITICAL INSTRUCTION: \n"
                "If the user provides text blocks from their editor (labeled as EDITOR CONTEXT) "
                "and asks you to modify, rewrite, rephrase, or update them, you MUST use the `ProposeContentEdit` tool "
                "to submit your proposed changes. Do NOT output the edited text directly in your conversational response "
                "because the user relies on the tool's UI to review the diff.\n\n"
                "TOOL PRIORITY RULE (READ THIS FIRST):\n"
                "When EDITOR CONTEXT is provided and the user asks to modify/rewrite/rephrase/update:\n"
                "→ ALWAYS use `ProposeContentEdit`. Do NOT ask the user for options or choices.\n"
                "→ `RequestUserInput` is NEVER appropriate for rephrase/rewrite/modify requests on editor content.\n\n"
                "\n"
                "INTERACTION INSTRUCTION: Use the `RequestUserInput` tool ONLY when the user asks for help filling in missing document fields or makes a selection between options.\n"
                "\n"
                "**When to use RequestUserInput:**\n"
                "- The user asks to fill {{placeholder}} values and no context data exists\n"
                "- The user explicitly asks you to choose between options (e.g., 'Which section should I update?')\n"
                "\n"
                "**When NOT to use RequestUserInput:**\n"
                "- Any query involving editor context — use ProposeContentEdit instead\n"
                "- General questions (explain, summarize, check grammar, give opinion)\n"
                "- Conversational or informational requests\n"
                "- You can directly answer from the provided information\n\n"
                "\n"
                "Decision flow (follow in order):\n"
                "1. Does the user provide editor context AND ask to modify/rewrite/rephrase? → Use `ProposeContentEdit`\n"
                "2. Does the user ask to fill placeholder values or choose between options? → Use `RequestUserInput`\n"
                "3. Does the user ask to read, open, or show the content of a specific file at a known path? → Use `FileRead` (pass the path) and report the content\n"
                "4. Does the user ask to find files by name or pattern (e.g. 'all .md files', 'where is X.py')? → Use `Glob`\n"
                "5. Does the user ask to search for text/content across files (e.g. 'find usages of Y')? → Use `Search`\n"
                "6. Does the user ask to run a command or perform a shell operation? → Use `Bash`\n"
                "7. Any other query → Answer directly without tools\n"
                "Note: If you do not know the exact path, use `Glob` or `Search` to locate the file first, then `FileRead` to read it.\n\n"
                "Available interaction types:\n"
                "1. **select** — When the user should pick ONE option from a dropdown list (2-8 options).\n"
                "   Example: 'Which section should we update?' with options like ['Introduction', 'Scope', 'Requirements'].\n"
                "2. **radio** — When the user should pick ONE option from a visible list (2-8 options).\n"
                "   Example: 'How would you like to proceed?' with options like ['Continue', 'Skip', 'Revise'].\n"
                "3. **checkbox** — When the user should pick MULTIPLE options from a list (2-8 options).\n"
                "   Example: 'Which requirements should be added?' with options like ['Authentication', 'Logging', 'Caching'].\n"
                "4. **text** — When you need a free-form text response from the user (pass empty list for options).\n"
                "   Example: 'Describe the intended behavior in your own words.'\n\n"
                "Interaction guidelines:\n"
                "- Use `select` when the list is short and a single choice is needed\n"
                "- Use `radio` when you want all options visible for a single choice\n"
                "- Use `checkbox` when multiple selections are valid\n"
                "- Use `text` when the user needs to provide details, explanations, or custom input\n"
                "- Always provide 2-8 clear, specific options (avoid vague choices)\n"
                "- The user's response is returned to you as a string you can use in subsequent reasoning\n"
                "- NEVER bundle multiple questions into a single prompt — ask ONE at a time"
            )
            
            final_result = await loop.run(
                initial_messages=run_messages,
                tools=available_tools,
                system_prompt=chat_system_prompt,
                model=chat_model
            )
            if isinstance(final_result, dict) and final_result.get("_status") == "awaiting_input":
                # Parse the awaiting input details from the marker in message history
                tc_id = final_result.get("_tool_call_id", "")
                _pending_interactions[session_id]["loop"] = loop
                _pending_interactions[session_id]["tool_call_id"] = tc_id
                _pending_interactions[session_id]["resumed"] = False
                chat_event_queue.put_nowait({"type": "interaction_paused", "session_id": session_id, "tool_call_id": tc_id})
            else:
                chat_event_queue.put_nowait({"type": "turn_complete", "turn": 1})
                chat_event_queue.put_nowait({"type": "done", "content": final_result})
                # Clear stale interaction state from any previous turn
                _pending_interactions[session_id]["tool_call_id"] = None
                _pending_interactions[session_id]["resumed"] = False
        except Exception as exception:
            log.error(f"[Chat] Loop execution error: {exception}", exc_info=True)
            chat_event_queue.put_nowait({"type": "error", "message": str(exception)})
            # Clear stale interaction state on error
            _pending_interactions[session_id]["tool_call_id"] = None
            _pending_interactions[session_id]["resumed"] = False

    # Run the query loop in a background task
    loop = QueryLoop(
        session_id=session_id,
        project_id=project_id,
        streaming_enabled=False,
        message_manager=SSEChatMessageManager(chat_event_queue=chat_event_queue),
        max_turns=5,
    )

    _pending_interactions[session_id]["loop"] = loop

    task = asyncio.create_task(run_loop())

    try:
        while True:
            try:
                event = await asyncio.wait_for(chat_event_queue.get(), timeout=0.5)
                yield f"data: {json.dumps(event, default=str)}\n\n"

                # Drain any events that arrived while we processed
                while not chat_event_queue.empty():
                    try:
                        evt = chat_event_queue.get_nowait()
                        yield f"data: {json.dumps(evt, default=str)}\n\n"
                    except asyncio.QueueEmpty:
                        break

                if event["type"] in ("done", "error", "interaction_paused"):
                    break

            except asyncio.TimeoutError:
                if task.done():
                    break
    finally:
        if not task.done():
            task.cancel()

    # Handle resume: only wait for interaction if the loop was actually paused
    pending = _pending_interactions.get(session_id, {})
    if pending.get("tool_call_id") and not pending.get("resumed", False):
        log.info(f"[Chat] Waiting for user interaction on session {session_id}")
        waited = 0
        while waited < 300:
            if _pending_interactions.get(session_id, {}).get("resumed"):
                break
            await asyncio.sleep(0.5)
            waited += 0.5

        if pending.get("tool_call_id") and session_id in _pending_interactions:
            await run_loop(resume=True)
            try:
                while True:
                    event = await asyncio.wait_for(chat_event_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    if event["type"] in ("done", "error", "interaction_paused"):
                        break
            except asyncio.TimeoutError:
                pass
    else:
        log.info(f"[Chat] Loop finished normally for session {session_id}, no interaction needed")

    # Final fallback if task exited abruptly
    if task.done() and task.exception():
        exc = task.exception()
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, default=str)}\n\n"


@router.post("/chat/send")
async def chat_send(request: Request):
    """Main streaming endpoint — runs the agentic loop and streams back events."""
    body = await request.json()
    session_id = body.get("session_id", "")
    project_id = body.get("project_id", "")
    user_message = ""
    """
    context_block = {
        "text": "Document InformationDetailsDocument TitleTBD for DP-XMC-5049Document ReferenceTBD-TBD-TBD-TBD-SRS-TBDVersion NumberTBDVersion Date2024-05-22Prepared ByName: TBDDocument Review ByName: TBDTechnical Review ByName: TBDProcess Review ByName: TBDApproved ByName: Design Review Board",
        "blockNumber": 1,
        "preview": "Document InformationDetailsDocument TitleTBD for DP-XMC-5049Document ReferenceTB",
        "section": "01_project_table.md",
        "version": 12
    }
    """
    context_blocks = body.get("context_blocks")
    context_message = body.get("message", "").strip()

    if not context_message:
        raise HTTPException(status_code=400, detail="message is required")

    if context_blocks:
        blocks_text = "\n\n".join([
            f"Section: {block_item.get('section', '')} (v{block_item.get('version', '')}) | Block Number: {block_item.get('blockNumber', '')}\n"
            f"Text:\n{block_item.get('markdown', '')}"
            for block_item in context_blocks
        ])
        
        # Explicit instruction to force the LLM to use the tool
        user_instruction = (
            "The user has selected the following text blocks from their editor. "
            "If the user asks you to modify, rephrase, rewrite, or update this content, "
            "you MUST use the `ProposeContentEdit` tool to propose the changes. "
            "CRITICAL: The `original_text` argument MUST EXACTLY MATCH the text in the context block below, character-for-character. Do not alter spacing, punctuation, or capitalization of the original text when passing it to the tool, otherwise the replacement will fail. "
            "Do NOT just output the raw edited text in your chat response."
        )
        
        user_message = (
            f"--- EDITOR CONTEXT ---\n"
            f"{user_instruction}\n\n"
            f"{blocks_text}\n"
            f"----------------------\n\n"
            f"User Query: {context_message}"
        )
    else:
        user_message = context_message

    return StreamingResponse(
        _chat_stream(session_id=session_id, user_message=user_message, project_id=project_id),
        media_type="text/event-stream",
    )


@router.get("/chat/messages/{session_id}")
async def get_chat_messages(session_id: str, project_id: str = "default"):
    """Fetch conversation history for a session."""
    from AgentCore import SessionMemoryCache
    
    # Try to extract the project ID from query params or assume default
    cache = SessionMemoryCache(project_id)
    memory = cache.load(session_id)
    
    # Format for UI
    messages = []
    if memory and memory.interactions:
        for interaction in memory.interactions:
            messages.append({
                "role": "user",
                "content": interaction.input,
                "timestamp": interaction.timestamp
            })
            messages.append({
                "role": "assistant",
                "content": interaction.output,
                "timestamp": interaction.timestamp
            })
            
    return messages


@router.get("/chat/sessions")
async def list_chat_sessions(project_id: str = None):
    """List all active chat sessions."""
    from AgentCore import ChatSessionManager

    # Discover all sessions for the project
    active = ChatSessionManager.discover_active(project_id)
    return [record.to_dict() for record in active]


@router.post("/chat/interact")
async def chat_interact(request: Request):
    """Receive user response for a pending RequestUserInput interaction.

    Marks the session as resumed so the SSE stream in _chat_stream continues.
    Also handles persistence for accepted content edits.
    """
    from system_config import get_project_generated_document_output_dir
    body = await request.json()
    session_id = body.get("session_id")
    tool_call_id = body.get("tool_call_id")
    response = body.get("response")  # str for select/radio, list for checkbox

    if not session_id or not tool_call_id or response is None:
        raise HTTPException(
            status_code=400,
            detail="session_id, tool_call_id, and response are required",
        )

    pending = _pending_interactions.get(session_id)
    if not pending:
        return {"status": "error", "message": "No pending interaction for this session"}

    loop_instance = pending.get("loop")
    if not loop_instance:
        return {"status": "error", "message": "Loop not available"}

    # We do NOT persist content edits to disk here anymore.
    # The frontend's Tiptap editor listens for 'apply-content-edit-accept',
    # updates its markdown state, and then natively triggers the 
    # 'updateSectionContent' (PUT /template-section/...) API, which correctly
    # updates the JSON AST and handles versioning.

    # Set the user response on the loop
    loop_instance.set_user_response(tool_call_id, response)
    # Mark as resumed so _chat_stream wakes up
    pending["resumed"] = True

    log.info("[Chat] User interaction received for session %s, tool %s", session_id, tool_call_id)
    return {"status": "resumed"}
