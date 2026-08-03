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
    from AgentCore import QueryLoop, SessionLifecycle
    from AgentCore.execution.registry import registry

    # Setup session
    record = SessionLifecycle._load(session_id, project_id)
    if not record:
        record = SessionLifecycle.create(project_path="", entrypoint="chat", kind="interactive", project_id=project_id)
        session_id = record.session_id

    yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id}, default=str)}\n\n"

    event_queue = asyncio.Queue()

    class SSEMessageManager:
        def emit_progress_event(self, content, tokens_in, tokens_out):
            if content:
                log.info("[Chat] emit_progress_event: %d chars", len(content))
                event_queue.put_nowait({"type": "text_delta", "content": content})

        def emit_tool_use_start(self, tool_call_id, name, input_args):
            log.info("[Chat] emit_tool_use_start: %s %s", tool_call_id, name)
            event_queue.put_nowait({
                "type": "tool_use_start",
                "tool_call_id": tool_call_id,
                "name": name,
                "input": input_args,
            })

        def emit_tool_interaction_request(self, tool_call_id, ui_type, options, prompt, title=""):
            event_queue.put_nowait({
                "type": "tool_interaction_request",
                "tool_call_id": tool_call_id,
                "name": "RequestUserInput",
                "input": {"prompt": prompt, "ui_type": ui_type, "options": options, "title": title},
                "status": "awaiting_input",
                "ui_type": ui_type,
                "options": options,
                "prompt": prompt,
            })

        def emit_tool_use_complete(self, tool_call_id, output):
            log.info("[Chat] emit_tool_use_complete: %s", tool_call_id)
            event_queue.put_nowait({
                "type": "tool_use_complete",
                "tool_call_id": tool_call_id,
                "output": output,
            })

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
                # Clear history so only user response (appended by set_user_response) is visible.
                # This prevents re-execution of RequestUserInput and resets the conversation
                # to continue from the user's selection.
                loop._message_history.clear()
                loop._executed_tools.clear()
                event_queue.put_nowait({"type": "turn_start", "turn": 1})
            # Restrict available tools in chat mode to a specific set of 5 tools
            allowed_tools = {"FileRead", "Bash", "Glob", "Search", "ProposeContentEdit"}
            available_tools = [t for t in registry._tools.values() if t.name in allowed_tools]
            run_messages = [{"role": "user", "content": user_message}]
            
            # Chat-specific system prompt to heavily bias the LLM toward using the ProposeContentEdit tool
            chat_system_prompt = (
                "You are ArchTech AI, an advanced engineering assistant operating within the ArchTech IDE Chat Panel.\n"
                "Your primary role is to help the user write, review, and edit technical documentation (such as SRS).\n"
                "CRITICAL INSTRUCTION: If the user provides text blocks from their editor (labeled as EDITOR CONTEXT) "
                "and asks you to modify, rewrite, rephrase, or update them, you MUST use the `ProposeContentEdit` tool "
                "to submit your proposed changes. Do NOT output the edited text directly in your conversational response "
                "because the user relies on the tool's UI to review the diff."
            )
            
            final_result = await loop.run(
                messages=run_messages,
                tools=available_tools,
                system_prompt=chat_system_prompt
            )
            if isinstance(final_result, dict) and final_result.get("_status") == "awaiting_input":
                # Parse the awaiting input details from the marker in message history
                tc_id = final_result.get("_tool_call_id", "")
                _pending_interactions[session_id]["loop"] = loop
                _pending_interactions[session_id]["tool_call_id"] = tc_id
                _pending_interactions[session_id]["resumed"] = False
                event_queue.put_nowait({"type": "interaction_paused", "session_id": session_id, "tool_call_id": tc_id})
            else:
                event_queue.put_nowait({"type": "turn_complete", "turn": 1})
                event_queue.put_nowait({"type": "done", "content": final_result})
                # Clear stale interaction state from any previous turn
                _pending_interactions[session_id]["tool_call_id"] = None
                _pending_interactions[session_id]["resumed"] = False
        except Exception as e:
            log.error(f"[Chat] Loop execution error: {e}", exc_info=True)
            event_queue.put_nowait({"type": "error", "message": str(e)})
            # Clear stale interaction state on error
            _pending_interactions[session_id]["tool_call_id"] = None
            _pending_interactions[session_id]["resumed"] = False

    # Run the query loop in a background task
    loop = QueryLoop(
        session_id=session_id,
        project_id=project_id,
        streaming_enabled=False,
        message_manager=SSEMessageManager(),
        max_turns=5,
    )

    _pending_interactions[session_id]["loop"] = loop

    task = asyncio.create_task(run_loop())

    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                yield f"data: {json.dumps(event, default=str)}\n\n"

                # Drain any events that arrived while we processed
                while not event_queue.empty():
                    try:
                        evt = event_queue.get_nowait()
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
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
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
    message = body.get("message", "").strip()

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    if context_blocks:
        blocks_text = "\n\n".join([
            f"Section: {b.get('section', 'Unknown')} (v{b.get('version', '1')}) | Block Number: {b.get('blockNumber', 'Unknown')}\n"
            f"Text:\n{b.get('text', '')}"
            for b in context_blocks
        ])
        
        # Explicit instruction to force the LLM to use the tool
        instruction = (
            "The user has selected the following text blocks from their editor. "
            "If the user asks you to modify, rephrase, rewrite, or update this content, "
            "you MUST use the `ProposeContentEdit` tool to propose the changes. "
            "CRITICAL: The `original_text` argument MUST EXACTLY MATCH the text in the context block below, character-for-character. Do not alter spacing, punctuation, or capitalization of the original text when passing it to the tool, otherwise the replacement will fail. "
            "Do NOT just output the raw edited text in your chat response."
        )
        
        message = (
            f"--- EDITOR CONTEXT ---\n"
            f"{instruction}\n\n"
            f"{blocks_text}\n"
            f"----------------------\n\n"
            f"User Query: {message}"
        )

    return StreamingResponse(
        _chat_stream(session_id, message, project_id),
        media_type="text/event-stream",
    )


@router.get("/chat/messages/{session_id}")
async def get_chat_messages(session_id: str, project_id: str = "default"):
    """Fetch conversation history for a session."""
    from AgentCore import SessionLifecycle, SessionMemoryCache
    
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
async def list_chat_sessions(project_id: str = "default"):
    """List all active chat sessions."""
    from AgentCore import SessionLifecycle
    
    # Discover all sessions for the project
    active = SessionLifecycle.discover_active(project_id)
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
