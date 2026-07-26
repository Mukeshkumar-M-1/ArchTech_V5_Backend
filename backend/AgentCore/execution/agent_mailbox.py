"""
AgentMailbox — Per-agent message delivery via file-based mailbox.

Phase 6: Each agent gets a mailbox where messages from parent agents
or other agents can be queued and later picked up.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

MAILBOX_DIR = os.path.join(os.path.dirname(__file__), "mailboxes")


@dataclass
class Mailbox:
    """A mailbox for a single agent."""

    agent_id: str
    messages: list[dict] = field(default_factory=list)

    def send(self, to: str, from_agent: str, message: str) -> bool:
        """Deliver a message to this mailbox.

        Args:
            to: Recipient agent ID.
            from_agent: Sender agent ID.
            message: Message body.

        Returns:
            True if message was delivered successfully.
        """
        entry = {
            "to": to,
            "from": from_agent,
            "message": message,
            "timestamp": time.time(),
        }
        self.messages.append(entry)
        log.info("[Mailbox] Delivered message to agent=%s from=%s", to, from_agent)
        return True


# Global registry: agent_id -> Mailbox
_mailboxes: dict[str, Mailbox] = {}
_lock = asyncio.Lock()


async def _ensure_mailbox(agent_id: str) -> Mailbox:
    """Ensure a mailbox exists for the given agent."""
    async with _lock:
        if agent_id not in _mailboxes:
            _mailboxes[agent_id] = Mailbox(agent_id=agent_id)
        return _mailboxes[agent_id]


def get_mailbox(agent_id: str) -> Mailbox:
    """Get or create a mailbox for the given agent ID.

    Args:
        agent_id: The agent's unique identifier.

    Returns:
        The Mailbox instance for this agent.
    """
    if agent_id not in _mailboxes:
        _mailboxes[agent_id] = Mailbox(agent_id=agent_id)
    return _mailboxes[agent_id]
