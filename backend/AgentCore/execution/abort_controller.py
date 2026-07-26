"""
Abort Controller Hierarchy — Parent→child abort chain.

Mirrors CCB's AbortController pattern with child-linked abort propagation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)


# ── AbortSignal ─────────────────────────────────────────────────────────

@dataclass
class AbortSignal:
    """Immutable signal representing an abort state."""
    is_aborted: bool = False
    reason: str | None = None
    _callbacks: list[Callable] = field(default_factory=list)

    def on_abort(self, callback: Callable) -> None:
        """Register a callback to fire when the signal is aborted.

        Args:
            callback: Callable to invoke with the abort reason.
        """
        self._callbacks.append(callback)
        if self.is_aborted:
            callback(self.reason)

    def _fire(self) -> None:
        """Fire all abort callbacks with the stored reason."""
        for cb in self._callbacks:
            try:
                cb(self.reason)
            except Exception as e:
                log.warning(f"Abort callback error: {e}")


# ── AbortController ─────────────────────────────────────────────────────

class AbortController:
    """Controller for cancelling async operations.

    Supports parent→child hierarchy: child controllers abort when the
    parent aborts, but child abort does NOT affect the parent.
    """

    def __init__(self, parent: AbortController | None = None, agent_id: str | None = None) -> None:
        """Initialize the abort controller with an optional parent controller and agent ID.

        Args:
            parent: Parent AbortController for hierarchy propagation.
            agent_id: Optional agent identifier for tracking.
        """
        self._signal = AbortSignal()
        self._parent = parent
        self._id: str | None = None
        if agent_id is not None:
            self._id = agent_id

    @property
    def signal(self) -> AbortSignal:
        """The immutable AbortSignal representing this controller's state."""
        return self._signal

    @property
    def id(self) -> str | None:
        """The agent ID associated with this controller, if any."""
        return self._id

    def abort(self, reason: str = "cancelled") -> None:
        """Abort this controller and propagate to parent if linked.

        Args:
            reason: Explanation for the abort.
        """
        if self._signal.is_aborted:
            log.info("[AbortController] Already aborted, skipping")
            return
        self._signal.is_aborted = True
        self._signal.reason = reason
        log.info("[AbortController] %s: aborted (%s)", self.id or "unknown", reason)
        self._signal._fire()
        # Cascade to children via parent hierarchy

    def child(self) -> AbortController:
        """Create a child controller linked to this one.

        Returns:
            A new AbortController whose parent is this controller.
        """
        log.info("[AbortController] Creating child controller")
        return AbortController(parent=self)

    def __repr__(self) -> str:
        """Return a string representation of this controller's state."""
        status = "ABORTED" if self._signal.is_aborted else "active"
        return f"AbortController({self._id}, {status})"


# ── Hierarchy Manager ───────────────────────────────────────────────────

class _AbortHierarchy:
    """Singleton manager for abort controller parent-child relationships.

    Maintains a directed graph of controller IDs and their parent-child
    links, enabling cascade abort from any root.
    """

    def __init__(self) -> None:
        """Initialize the hierarchy manager."""
        self._children: dict[str, set[str]] = {}  # parent_id -> {child_ids}
        self._controllers: dict[str, AbortController] = {}  # id -> AbortController
        self._lock: Any = None
        log.info("[_AbortHierarchy] Initialized")

    def _ensure_lock(self) -> None:
        """Create an asyncio.Lock if one doesn't exist yet."""
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()

    def register(self, parent_id: str, child_id: str, controller: AbortController | None = None) -> None:
        """Register a child controller under a parent in the hierarchy.

        Args:
            parent_id: The parent controller identifier.
            child_id: The child controller identifier.
            controller: Optional AbortController instance to register.
        """
        log.info("[_AbortHierarchy] register: parent=%s, child=%s", parent_id, child_id)
        self._ensure_lock()
        if parent_id not in self._children:
            self._children[parent_id] = set()
        self._children[parent_id].add(child_id)
        if controller is not None:
            self._controllers[child_id] = controller

    def abort_tree(self, root_id: str, reason: str = "parent cancelled") -> None:
        """Abort root controller and all descendants recursively.

        Args:
            root_id: The controller ID to start aborting from.
            reason: The reason for aborting.
        """
        log.info("[_AbortHierarchy] abort_tree: root=%s, reason=%s", root_id, reason)
        self._ensure_lock()
        # Ensure task store is initialized
        get_task_store()
        visited: set[str] = set()
        queue: list[str] = [root_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            # Abort this controller
            state = _task_store.get_task(current)
            if state is not None:
                from AgentCore.execution.task_state import TaskStatus
                state.transition(TaskStatus.KILLED)
            # Queue children
            for child_id in self._children.get(current, set()):
                queue.append(child_id)
        # Abort the controllers themselves (not just via signals)
        for cid in visited:
            ctrl = self._controllers.get(cid)
            if ctrl and not ctrl.signal.is_aborted:
                ctrl.abort(reason)
            # Also abort any child controllers directly
            for child_id in self._children.get(cid, set()):
                child_ctrl = self._controllers.get(child_id)
                if child_ctrl and not child_ctrl.signal.is_aborted:
                    child_ctrl.abort(reason)
        log.info(f"[AbortHierarchy] Tree rooted at {root_id} aborted ({reason})")

    def cleanup(self, controller_id: str) -> None:
        """Remove a controller from the hierarchy and clean up references.

        Args:
            controller_id: The controller ID to remove.
        """
        log.info("[_AbortHierarchy] cleanup: controller=%s", controller_id)
        self._ensure_lock()
        self._children.pop(controller_id, None)
        self._controllers.pop(controller_id, None)
        # Remove from parent's child list
        for parent_id, children in self._children.items():
            children.discard(controller_id)

    def abort_all(self, reason: str = "system shutdown") -> None:
        """Abort all active controllers in the hierarchy."""
        log.info("[_AbortHierarchy] abort_all: reason=%s", reason)
        self._ensure_lock()
        for cid, ctrl in self._controllers.items():
            if not ctrl.signal.is_aborted:
                ctrl.abort(reason)
        # Force cleanup of tasks
        if _task_store is not None:
            from AgentCore.execution.task_state import TaskStatus
            for task_id in list(_task_store._tasks.keys()):
                state = _task_store.get_task(task_id)
                if state and state.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED):
                    state.transition(TaskStatus.KILLED)


# Module-level singleton
_hierarchy = _AbortHierarchy()

# We need access to task store — resolve lazily
_task_store: Any = None


def get_hierarchy() -> _AbortHierarchy:
    """Get the global abort hierarchy singleton.

    Returns:
        The module-level _AbortHierarchy instance.
    """
    return _hierarchy


def get_task_store():
    """Get the task store, initializing it lazily if needed.

    Returns:
        The task store instance for abort hierarchy integration.
    """
    global _task_store
    if _task_store is None:
        from AgentCore.execution.builtins.tasks import get_store
        _task_store = get_store()
    return _task_store
