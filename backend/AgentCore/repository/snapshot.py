"""
Repository Snapshot Management

Provides deterministic tracking of the codebase state at a specific point in time.
This guarantees that indexes and reasoning don't silently drift if the underlying
files change mid-execution.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import uuid

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileMetadata:
    """Immutable metadata for a single file in the snapshot."""
    path: str
    size_bytes: int
    last_modified: float
    sha256_hash: str


@dataclass
class RepositorySnapshot:
    """An immutable record of the repository state at a point in time."""
    snapshot_id: str
    root_path: str
    timestamp: float
    files: Dict[str, FileMetadata] = field(default_factory=dict)
    
    def get_file(self, rel_path: str) -> Optional[FileMetadata]:
        return self.files.get(rel_path)


class SnapshotManager:
    """Generates and manages versioned snapshots of the repository."""

    # Default directories to ignore when building a snapshot
    IGNORE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", "build", "dist"}
    # Default file extensions to include
    INCLUDE_EXTS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".ts", ".js", ".html", ".css"}

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self._current_snapshot: Optional[RepositorySnapshot] = None
        log.info(f"[SnapshotManager] Initialized for root: {self.root_path}")

    def create_snapshot(self) -> RepositorySnapshot:
        """Walks the repository and generates a deterministic snapshot of its current state."""
        log.info("[SnapshotManager] Generating new repository snapshot...")
        start_time = time.time()
        
        files_meta: Dict[str, FileMetadata] = {}
        
        # Traverse the directory tree
        for path in self.root_path.rglob("*"):
            if not path.is_file():
                continue
                
            # Skip ignored directories
            if any(part in self.IGNORE_DIRS for part in path.parts):
                continue
                
            # Only index specific extensions (or files without extensions like Dockerfile)
            if path.suffix not in self.INCLUDE_EXTS and path.suffix != "":
                continue

            rel_path = path.relative_to(self.root_path).as_posix()
            
            try:
                stat = path.stat()
                file_hash = self._compute_hash(path)
                
                files_meta[rel_path] = FileMetadata(
                    path=rel_path,
                    size_bytes=stat.st_size,
                    last_modified=stat.st_mtime,
                    sha256_hash=file_hash
                )
            except Exception as e:
                log.warning(f"[SnapshotManager] Failed to read {rel_path}: {e}")

        snapshot = RepositorySnapshot(
            snapshot_id=str(uuid.uuid4()),
            root_path=str(self.root_path),
            timestamp=time.time(),
            files=files_meta
        )
        
        self._current_snapshot = snapshot
        duration = time.time() - start_time
        log.info(f"[SnapshotManager] Created snapshot '{snapshot.snapshot_id}' with {len(files_meta)} files in {duration:.2f}s.")
        
        return snapshot

    def get_current_snapshot(self) -> Optional[RepositorySnapshot]:
        """Returns the most recently created snapshot."""
        return self._current_snapshot

    def _compute_hash(self, file_path: Path) -> str:
        """Compute the SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
