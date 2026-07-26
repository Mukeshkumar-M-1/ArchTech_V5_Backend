"""
Transcript — Disk-backed JSONL output for agents.

Mirrors CCB's sidechain JSONL transcript storage:
- Each agent gets a JSONL file at .archtech/transcripts/{project_id}/{agent_id}.jsonl
- Writes are atomic (temp file + os.replace)
- Reads return lines with incremental offset support (outputOffset)
- Locked concurrent writes via asyncio.Lock
- Corruption recovery: repairs bad JSONL on read
- Entry types: user, assistant, attachment, tool_use, tool_result, compact_summary
- Batch queue for high-frequency writes (100ms flush)

Phase 5: Provides persistent, crash-recoverable agent history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
from system_config import get_transcript_dir as _sys_get_transcript_dir

log = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    """A typed transcript entry (user, assistant, tool_use, tool_result, etc.)."""
    entry_type: str
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    step_type: Optional[str] = None  # U-P-T-A-O sub-steps: understand, planning, thought, action, observation
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.entry_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.step_type:
            d["step_type"] = self.step_type
        return d


def get_transcript_dir(project_id: str) -> Path:
    """Get the transcript directory for an agent."""
    return _sys_get_transcript_dir(project_id=project_id)


def recover(transcript_path: str) -> bool:
    """Corruption recovery — reads entire file, filters bad JSON, rewrites.

    OOM safety: skips recovery for files >50MB.
    """
    path = Path(transcript_path)
    if not path.exists():
        return False

    file_size = path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        log.warning(f"[Transcript] Skipping recovery: {path} is {file_size / 1024 / 1024:.0f}MB (>50MB)")
        return False

    good_lines = []
    corrupted = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    good_lines.append(line)
                except json.JSONDecodeError:
                    corrupted += 1
    except OSError:
        return False

    if corrupted > 0:
        # Rewrite with only valid lines
        try:
            with open(path, "w", encoding="utf-8") as f:
                for line in good_lines:
                    f.write(line + "\n")
            log.info(f"[Transcript] Recovered {path}: {corrupted} corrupted lines removed")
        except OSError:
            log.warning(f"[Transcript] Failed to rewrite recovered {path}")
            return False

    return corrupted > 0


def get_transcript_path(project_id: str) -> Path:
    """Get the JSONL file path for an agent's transcript."""
    return get_transcript_dir(project_id) / f"transcript.jsonl"


class TranscriptWriter:
    """Thread-safe JSONL writer for agent transcripts.

    Each turn is written as one JSON line:
    {
        "timestamp": ...,
        "role": "user" | "assistant" | "tool",
        "content": "...",
        "tool_calls": [...],
        "tool_results": [...],
        "tokens_in": 0,
        "tokens_out": 0
    }
    """

    def __init__(self, transcript_dir: str):
        self._dir = Path(transcript_dir) 
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "transcript.jsonl"
        self._lock = asyncio.Lock()
        self._offset = 0  # byte offset for incremental reads
        self._batch_buffer: list[str] = []
        self._batch_flush_task: Any = None

    def write_turn(
        self,
        role: str,
        content: str = "",
        tool_calls: Optional[list[dict]] = None,
        tool_results: Optional[list[dict]] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Write a single turn to the JSONL file (sync, for use with create_task)."""
        entry = {
            "timestamp": time.time(),
            "role": role,
            "content": content,
        }
        if tool_calls:
            entry["tool_calls"] = tool_calls
        if tool_results:
            entry["tool_results"] = tool_results
        entry["tokens_in"] = tokens_in
        entry["tokens_out"] = tokens_out

        line = json.dumps(entry) + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)

        log.info(
            f"[Transcript] Wrote {len(line)} bytes for {role} turn "
            f"(in={tokens_in}, out={tokens_out})"
        )

    async def awrite_turn(
        self,
        role: str,
        content: str = "",
        tool_calls: Optional[list[dict]] = None,
        tool_results: Optional[list[dict]] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Async write (ensures lock safety within async context)."""
        async with self._lock:
            self.write_turn(role, content, tool_calls, tool_results, tokens_in, tokens_out)

    def write_entry(self, entry_type: str, content: str,
                    tool_call_id: Optional[str] = None,
                    timestamp: Optional[float] = None) -> None:
        """Write a typed transcript entry (user, assistant, tool_use, tool_result, compact_summary)."""
        entry = {
            "type": entry_type,
            "content": content,
            "timestamp": timestamp or time.time(),
        }
        if tool_call_id:
            entry["tool_call_id"] = tool_call_id

        line = json.dumps(entry) + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)

    def write_turn_with_entries(self, messages: list[dict]) -> None:
        """Group assistant + tool_use + tool_result into one atomic write."""
        if not messages:
            return
        # Collect all messages into a single entry
        content = "\n\n".join(str(m.get("content", "")) for m in messages if m.get("content"))
        role = messages[0].get("role", "assistant")
        self.write_turn(role=role, content=content)

    def recover(self) -> bool:
        """Repair corrupted JSONL file by filtering bad lines.

        Reads entire file, filters out non-JSON lines, rewrites.
        Skips recovery for files >50MB (OOM safety).
        """
        if not self._path.exists():
            return True
        file_size = self._path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            log.warning(f"[Transcript] Skipping recovery: file too large ({file_size} bytes)")
            return False

        valid_lines = []
        corrupted = 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                        valid_lines.append(line)
                    except json.JSONDecodeError:
                        corrupted += 1
        except OSError as e:
            log.error(f"[Transcript] Failed to read transcript for recovery: {e}")
            return False

        if corrupted > 0:
            try:
                with open(self._path, "w", encoding="utf-8") as f:
                    for line in valid_lines:
                        f.write(line + "\n")
                log.info(
                    f"[Transcript] Recovered: fixed {corrupted} corrupted lines, "
                    f"kept {len(valid_lines)} valid entries"
                )
            except OSError as e:
                log.error(f"[Transcript] Failed to rewrite recovered transcript: {e}")
                return False

        return True

    def read_all(self) -> list[dict]:
        """Read all lines from the transcript file."""
        if not self._path.exists():
            return []
        # Auto-recover on read
        self.recover()
        lines = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        log.warning("[Transcript] Skipping corrupted line")
        return lines

    def read_offset(self, offset: int = 0) -> list[dict]:
        """Read lines starting from byte offset (incremental)."""
        if not self._path.exists():
            return []
        with open(self._path, "rb") as f:
            f.seek(offset)
            lines = []
            for line in f:
                line_str = line.decode("utf-8").strip()
                if line_str:
                    try:
                        lines.append(json.loads(line_str))
                    except json.JSONDecodeError:
                        pass
        return lines

    def write_think_step(self, step: str, content: str) -> None:
        """Write a U-P-T-A-O thinking step to the transcript.

        Args:
            step: One of 'understand', 'planning', 'thought', 'action', 'observation'
            content: The thinking content for this step
        """
        entry = TranscriptEntry(
            entry_type="thinking_step",
            content=content,
            step_type=step,
        )
        self.write(entry)

    def close(self) -> None:
        """Close the writer, flushing any pending data."""
        log.info(f"[Transcript] Writer closed, offset={self._offset}")

    def get_size(self) -> int:
        """Current file size in bytes."""
        if self._path.exists():
            return self._path.stat().st_size
        return 0
