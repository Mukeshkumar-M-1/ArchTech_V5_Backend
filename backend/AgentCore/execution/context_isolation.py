"""
Context Isolation — Per-agent isolated state via contextvars.

Phase 3: Each spawned subagent gets its own isolated context containing
a task store, message manager, abort controller, transcript writer,
and token tracker. Context is set via async context manager so that
nested async calls always resolve to the correct per-agent state.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)

# Global context variables — one per async execution context
_context_var: contextvars.ContextVar[Optional["AgentContext"]] = contextvars.ContextVar("agent_context", default=None)


@dataclass
class AgentContext:
    """Holds per-agent isolated state (task store, messages, abort controller, etc).

    Attributes:
        agent_id: Unique identifier for this agent.
        task_store: TaskStore instance for this agent.
        message_manager: MessageManager instance for this agent.
        abort_controller: AbortController for this agent.
        transcript_writer: Optional transcript writer (Phase 5).
        token_tracker: Token usage tracker (Phase 9).
    """

    agent_id: str
    task_store: Any = None
    message_manager: Any = None
    abort_controller: Any = None
    transcript_writer: Any = None
    token_tracker: Any = None


class AgentContextManager:
    """Async context manager that installs an AgentContext into contextvars."""

    def __init__(self, context: AgentContext) -> None:
        self._context = context
        self._token: contextvars.Token | None = None

    async def __aenter__(self) -> "AgentContextManager":
        self._token = _context_var.set(self._context)
        log.info("[ContextIsolation] Activated context for agent=%s", self._context.agent_id)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            _context_var.reset(self._token)
        log.info("[ContextIsolation] Deactivated context for agent=%s", self._context.agent_id)


def get_context() -> Optional[AgentContext]:
    """Get the current isolated agent context, or None if not in an agent scope."""
    return _context_var.get()


def get_agent_id() -> Optional[str]:
    """Get the current agent ID from context, or None if not in an agent scope."""
    ctx = _context_var.get()
    return ctx.agent_id if ctx else None
