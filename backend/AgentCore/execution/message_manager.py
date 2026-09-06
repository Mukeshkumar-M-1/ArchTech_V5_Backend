"""
MessageManager — Tracks and emits agent progress events.

Phase 3: Provides per-agent messaging capabilities including
progress emission and context clearing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, List

log = logging.getLogger(__name__)


class MessageManager:
    """Manages per-agent messages and progress events."""

    def __init__(self) -> None:
        self._messages: list[dict] = []

    def emit_progress_event(
        self, content: str = "", tokens_in: int = 0, tokens_out: int = 0
    ) -> None:
        """Emit a progress update event.

        Args:
            content: Text content of the progress update.
            tokens_in: Number of input tokens for this turn.
            tokens_out: Number of output tokens for this turn.
        """
        event = {
            "type": "progress",
            "content": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        self._messages.append(event)
        log.info(
            "[MessageManager] Progress event: tokens_in=%d, tokens_out=%d, content_len=%d",
            tokens_in,
            tokens_out,
            len(content),
        )

    def clear_context(self) -> None:
        """Clear all messages in this agent's context."""
        count = len(self._messages)
        self._messages.clear()
        log.info("[MessageManager] Cleared %d messages", count)

# ─── SSE Chat Message Manager ──────────────────────────────────────────────────
class SSEChatMessageManager:
    def __init__(self, chat_event_queue: asyncio.Queue):
        self.chat_event_queue = chat_event_queue

    def emit_progress_event(self, content):
        if content:
            log.info("[SSEChatMessageManager] emit_progress_event: %d chars", len(content))
            self.chat_event_queue.put_nowait({"type": "text_delta", "content": content})

    def emit_tool_use_start(self, tool_call_id, name, input_args):
        log.info("[SSEChatMessageManager] emit_tool_use_start: %s %s", tool_call_id, name)
        self.chat_event_queue.put_nowait({
            "type": "tool_use_start",
            "tool_call_id": tool_call_id,
            "name": name,
            "input": input_args,
        })

    def emit_tool_interaction_request(self, tool_call_id, ui_type, options, prompt, title=""):
        self.chat_event_queue.put_nowait({
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
        log.info("[SSEChatMessageManager] emit_tool_use_complete: %s", tool_call_id)
        self.chat_event_queue.put_nowait({
            "type": "tool_use_complete",
            "tool_call_id": tool_call_id,
            "output": output,
        })


# ─── SSE Generation Message Manager ─────────────────────────────────────────────
class SSEGenerationMessageManager:
    """Unified message manager for document generation SSE events.

    Consolidates tool events (turn_start, tool_started, tool_finished),
    mission/section lifecycle events, and chunk data into a single
    asyncio.Queue. Emitted events are consumed by manager.stream().
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()

    # ── helper ──

    def _safe_put(self, event: dict) -> None:
        try:
            self._queue.put_nowait(event)
        except Exception:
            pass

    # ── turn / tool events (from ExecutionEngine) ──

    def emit_turn_start(self, turn: int, task_id: str) -> None:
        self._safe_put({"type": "turn_start", "turn": turn, "task_id": task_id})

    def emit_tool_started(
        self,
        tool_name: str,
        tool_call_id: str,
        input_args: Any,
        section_heading: str,
        task_id: str = "",
    ) -> None:
        self._safe_put({
            "type": "tool_started",
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "input": input_args,
            "section_heading": section_heading,
            "task_id": task_id,
        })

    def emit_tool_finished(
        self,
        tool_name: str,
        tool_call_id: str,
        is_error: bool,
        output: str,
        duration_ms: float,
        section_heading: str,
        task_id: str = "",
    ) -> None:
        self._safe_put({
            "type": "tool_finished",
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "is_error": is_error,
            "output": output,
            "duration_ms": duration_ms,
            "section_heading": section_heading,
            "task_id": task_id,
        })

    # ── mission / section lifecycle events (from orchestrator) ──

    def emit_mission_started(self, total_tasks: int, project_id: str) -> None:
        self._safe_put({
            "type": "mission_started",
            "total_tasks": total_tasks,
            "project_id": project_id,
        })

    def emit_gen_start(self, section_count: int, document_version: int) -> None:
        self._safe_put({
            "type": "gen_start",
            "section_count": section_count,
            "document_version": document_version,
        })

    def emit_paused(self, reason: str) -> None:
        self._safe_put({"type": "paused", "reason": reason})

    def emit_section_start(
        self,
        section_number: str,
        heading: str,
        section_current: int,
        section_total: int,
    ) -> None:
        self._safe_put({
            "type": "section_start",
            "section_number": section_number,
            "section_heading": heading,
            "section_current": section_current,
            "section_total": section_total,
        })

    def emit_progress(
        self,
        progress: int,
        section_current: int,
        section_total: int,
    ) -> None:
        self._safe_put({
            "type": "progress",
            "progress": progress,
            "section_current": section_current,
            "section_total": section_total,
        })
    
    def emit_section_phase(self, section_heading) -> None:
        self._safe_put({
            "type": "section_phase",
            "section_heading": section_heading
        })

    def emit_section_chunk(self, section_number: str, content: str) -> None:
        self._safe_put({
            "type": "section_chunk",
            "section_number": section_number,
            "content": content,
        })

    def emit_section_complete(
        self,
        section_number: str,
        heading: str,
        headings_parsed: List[dict],
        tools_used: List[Any],
    ) -> None:
        self._safe_put({
            "type": "section_complete",
            "section_number": section_number,
            "heading": heading,
            "headings_parsed": headings_parsed,
            "tools_used": tools_used,
        })

    def emit_tool_interaction_request(
        self,
        tool_call_id: str,
        tool_name: str,
        input_args: dict,        
        section_heading: str,
        task_id: str = "",

    ) -> None:
        """Emit an interaction request SSE event (RequestUserInput / ProposeContentEdit)."""
        self._safe_put({
            "type": "tool_interaction_request",
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "input": input_args,
            "status": "awaiting_input",
            "task_id": task_id,
            "section_heading": section_heading
        })

    def emit_task_failed(self, error: str) -> None:
        self._safe_put({"type": "task_failed", "error": error})

    def emit_gen_complete(
        self,
        total_sections: int,
        document_version: int,
        document_length: int,
    ) -> None:
        self._safe_put({
            "type": "gen_complete",
            "total_sections": total_sections,
            "document_version": document_version,
            "document_length": document_length,
        })

    def emit_error(self, error: str) -> None:
        self._safe_put({"type": "gen_error", "error": error})

    # ── streaming helpers ──

    async def done(self) -> None:
        """Signal completion by putting a None sentinel."""
        self._queue.put_nowait(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Yield formatted SSE strings until completion sentinel."""
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

