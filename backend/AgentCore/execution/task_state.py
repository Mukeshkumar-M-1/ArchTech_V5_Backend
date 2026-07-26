import enum
from typing import Any, Optional

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

_VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.KILLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED, TaskStatus.PENDING},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.KILLED: set(),
}

def can_transition(old: TaskStatus, new: TaskStatus) -> bool:
    """Check if a task can transition from the old status to the new status."""
    return new in _VALID_TRANSITIONS.get(old, set())

class TaskState:
    def __init__(self, task_id: str, description: str):
        self.id = task_id
        self.description = description
        self.status = TaskStatus.PENDING
        
    def transition(self, new_status: TaskStatus) -> None:
        if can_transition(self.status, new_status):
            self.status = new_status

class TaskStore(dict):
    """Lifecycle-managed store for tracking subagent tasks."""
    
    def __init__(self):
        super().__init__()
        self._states = {}
        
    def create_task(self, task_id: str, description: str = "") -> None:
        """Create a new task state in the store."""
        self._states[task_id] = TaskState(task_id, description)
        
    def get_task(self, task_id: str) -> Optional[TaskState]:
        return self._states.get(task_id)
