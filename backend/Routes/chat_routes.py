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

log = logging.getLogger("Routes.chat_routes")

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

    queue = asyncio.Queue()
    tool_queue = asyncio.Queue()

    class SSEMessageManager:
        def emit_progress_event(self, content, tokens_in, tokens_out):
            if content:
                queue.put_nowait({"type": "text_delta", "content": content})

        def emit_tool_use_start(self, tool_call_id, name, input_args):
            tool_queue.put_nowait({
                "type": "tool_use_start",
                "tool_call_id": tool_call_id,
                "name": name,
                "input": input_args,
            })

        def emit_tool_interaction_request(self, tool_call_id, ui_type, options, prompt, title=""):
            tool_queue.put_nowait({
                "type": "tool_interaction_request",
                "tool_call_id": tool_call_id,
                "name": "RequestUserInput",
                "input": {"prompt": prompt, "ui_type": ui_type, "options": options, "title": title},
                "status": "awaiting_input",
            })

        def emit_tool_use_complete(self, tool_call_id, output):
            tool_queue.put_nowait({
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
                queue.put_nowait({"type": "turn_start", "turn": 1})
            available_tools = [] # list(registry._tools.values())
            run_messages = [{"role": "user", "content": user_message}]
            final_result = await loop.run(
                messages=run_messages,
                tools=available_tools,
            )
            if isinstance(final_result, dict) and final_result.get("_status") == "awaiting_input":
                # Parse the awaiting input details from the marker in message history
                tc_id = final_result.get("_tool_call_id", "")
                _pending_interactions[session_id]["loop"] = loop
                _pending_interactions[session_id]["tool_call_id"] = tc_id
                _pending_interactions[session_id]["resumed"] = False
                queue.put_nowait({"type": "interaction_paused", "session_id": session_id, "tool_call_id": tc_id})
            else:
                queue.put_nowait({"type": "turn_complete", "turn": 1})
                queue.put_nowait({"type": "done", "content": final_result})
                # Clear stale interaction state from any previous turn
                _pending_interactions[session_id]["tool_call_id"] = None
                _pending_interactions[session_id]["resumed"] = False
        except Exception as e:
            log.error(f"[Chat] Loop execution error: {e}", exc_info=True)
            queue.put_nowait({"type": "error", "message": str(e)})
            # Clear stale interaction state on error
            _pending_interactions[session_id]["tool_call_id"] = None
            _pending_interactions[session_id]["resumed"] = False

    # Run the query loop in a background task
    loop = QueryLoop(
        session_id=session_id,
        project_id=project_id,
        streaming_enabled=True,
        message_manager=SSEMessageManager(),
        max_turns=5,
    )

    _pending_interactions[session_id]["loop"] = loop

    task = asyncio.create_task(run_loop())

    try:
        while True:
            # Drain tool queue first (higher priority)
            while not tool_queue.empty():
                try:
                    event = tool_queue.get_nowait()
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.QueueEmpty:
                    break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {json.dumps(event, default=str)}\n\n"

                if event["type"] in ("done", "error", "interaction_paused"):
                    break

            except asyncio.TimeoutError:
                if task.done():
                    break
    finally:
        if not task.done():
            task.cancel()

    # Drain remaining tool events
    while not tool_queue.empty():
        try:
            event = tool_queue.get_nowait()
            yield f"data: {json.dumps(event, default=str)}\n\n"
        except asyncio.QueueEmpty:
            break

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
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
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
    session_id = body.get("session_id")
    message = body.get("message", "").strip()
    project_id = body.get("project_id", "default")

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

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
    """
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

    # Set the user response on the loop
    loop_instance.set_user_response(tool_call_id, response)
    # Mark as resumed so _chat_stream wakes up
    pending["resumed"] = True

    log.info("[Chat] User interaction received for session %s, tool %s", session_id, tool_call_id)
    return {"status": "resumed"}
