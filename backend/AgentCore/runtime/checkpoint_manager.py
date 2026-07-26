"""
Checkpoint Manager

Manages the saving and restoring of complete runtime state snapshots.
Ensures deterministic resumption by saving journal offsets and pending events.
"""

import logging
import json
import uuid
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger(__name__)

@dataclass
class Checkpoint:
    checkpoint_id: str
    version: str
    runtime_state: str
    reasoning_state: Dict[str, Any]
    memory_snapshot: Dict[str, Any]
    journal_offset: int
    pending_events: List[Dict[str, Any]] = field(default_factory=list)

class CheckpointManager:
    def __init__(self, storage_dir: str = ".checkpoints"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"[CheckpointManager] Initialized at {self.storage_dir.absolute()}")

    def save_checkpoint(self, state_snapshot: Checkpoint) -> str:
        filepath = self.storage_dir / f"{state_snapshot.checkpoint_id}.json"
        
        with open(filepath, 'w') as f:
            json.dump(asdict(state_snapshot), f, indent=2)
            
        log.info(f"[CheckpointManager] Saved checkpoint {state_snapshot.checkpoint_id}")
        return str(filepath)

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        filepath = self.storage_dir / f"{checkpoint_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found.")
            
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        log.info(f"[CheckpointManager] Loaded checkpoint {checkpoint_id}")
        return Checkpoint(**data)
