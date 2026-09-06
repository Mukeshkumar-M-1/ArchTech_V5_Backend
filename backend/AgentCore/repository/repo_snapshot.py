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
from typing import Dict, List, Optional, Set
import uuid

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileMetadata:
    """Immutable metadata for a single file in the snapshot."""
    path: str
    size_bytes: int
    last_modified: float
    sha256_hash: str = ""


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
    DEFAULT_IGNORE_DIRS: Set[str] = {
        ".git", "__pycache__", "venv", ".venv", "node_modules",
        "build", "dist", "output_req_extracted", "transcripts",
    }

    # Default file extensions to include
    DEFAULT_INCLUDE_EXTS: Set[str] = {
        ".py", ".md", ".txt", ".json", ".yaml", ".yml",
        ".ts", ".js", ".html", ".css", ".jsonl",
    }

    def __init__(
        self,
        root_path: str,
        ignore_dirs: Optional[Set[str]] = None,
        include_exts: Optional[Set[str]] = None,
    ):
        self.root_path = Path(root_path).resolve()
        self.ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS
        self.include_exts = include_exts or self.DEFAULT_INCLUDE_EXTS
        self._current_snapshot: Optional[RepositorySnapshot] = None
        self._previous_snapshot: Optional[RepositorySnapshot] = None
        log.info(f"[SnapshotManager] Initialized for root: [{self.root_path}]")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file for change detection."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as file_handler:
                for chunk in iter(lambda: file_handler.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (OSError, IOError):
            return ""

    def create_snapshot(self, incremental: bool = False) -> RepositorySnapshot:
        """Walks the repository and generates a deterministic snapshot.

        When incremental=True and a previous snapshot exists, only files with
        changed hashes will be flagged during index rebuild.
        """
        log.info("[SnapshotManager] Generating new repository snapshot...")
        start_time = time.time()
        file_metadata: Dict[str, FileMetadata] = {}

        for file_path in self.root_path.rglob("*"):
            if not file_path.is_file():
                continue

            if any(segment in self.ignore_dirs for segment in file_path.parts):
                continue

            if file_path.suffix not in self.include_exts and file_path.suffix != "":
                continue

            relative_path = file_path.relative_to(self.root_path).as_posix()

            try:
                file_stat = file_path.stat()
                file_hash = self._compute_file_hash(file_path)
                file_metadata[relative_path] = FileMetadata(
                    path=relative_path,
                    size_bytes=file_stat.st_size,
                    last_modified=file_stat.st_mtime,
                    sha256_hash=file_hash,
                )
            except Exception as exception:
                log.warning(f"[SnapshotManager] Failed to read [{relative_path}]: [{exception}]")

        snapshot = RepositorySnapshot(
            snapshot_id=str(uuid.uuid4()),
            root_path=str(self.root_path),
            timestamp=time.time(),
            files=file_metadata,
        )

        if incremental:
            self._previous_snapshot = self._current_snapshot
        self._current_snapshot = snapshot

        duration = time.time() - start_time
        log.info(
            f"[SnapshotManager] Created snapshot '{snapshot.snapshot_id}' "
            f"with {len(file_metadata)} files in {duration:.2f}s."
        )

        return snapshot

    def get_current_snapshot(self) -> Optional[RepositorySnapshot]:
        """Returns the most recently created snapshot."""
        return self._current_snapshot

    def get_previous_snapshot(self) -> Optional[RepositorySnapshot]:
        """Returns the snapshot before the current one (for incremental comparison)."""
        return self._previous_snapshot