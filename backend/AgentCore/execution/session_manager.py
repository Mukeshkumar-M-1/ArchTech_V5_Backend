"""
Session Manager — Session lifecycle per CCB specification.

CCB session management (state.ts, sessionStorage.ts, concurrentSessions.ts):
1. Session Creation: random UUID, PID file written, transcript path set
2. Session State Machine: idle -> running -> idle, requires_action for tool waiting
3. Transcript Storage: JSONL entries at ~/.claude/projects/<path>/<id>.jsonl
4. Session Resume: load latest non-terminal session
5. Session Clear: new UUID, parent_session_id set, old file untouched
6. Session Discovery: PID files for active, project directories for history

Uses .archtech/ directory (not ~/.claude/) as specified.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from system_config import get_session_transcript_dir, get_project_transcript_dir, get_chat_session_dir, _ROOT_FOLDER_NAME
from uuid import uuid4

log = logging.getLogger(__name__)



# ─── Per-project session directory cache ─────────────────────────────
_dir_cache: dict[str, tuple[Path, Path]] = {}

def _get_dir_cache(project_id: str) -> tuple[Path, Path]:
    """Return (sessions_dir, projects_dir) for project_id, cached."""
    pid = (project_id)
    if pid not in _dir_cache:
        _dir_cache[pid] = (get_chat_session_dir(pid), get_project_transcript_dir(pid))
    return _dir_cache[pid]


@dataclass
class SessionRecord:
    """A session record matching CCB's concurrentSessions.ts structure.
    Extended with generation-tracking fields for template generation."""
    session_id: str
    pid: int
    cwd: str
    started_at: float
    kind: str = "interactive"
    entrypoint: str = "cli"
    transcript_path: str = ""
    status: str = "idle"  # idle | running | complete | error | cancelled
    parent_session_id: str | None = None
    project_id: str = ""
    target_sections: list[str] | None = None
    current_stage: int = 0
    progress: int = 0
    current_phase: str = ""
    stage_logs: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    understanding: list[str] = field(default_factory=list)
    planning: list[str] = field(default_factory=list)
    action: list[dict] = field(default_factory=list)
    conversation: dict = field(default_factory=lambda: {"user": [], "assistant": []})
    error: str | None = None
    _path: Path = field(default=None, repr=False)  # internal

    def to_dict(self) -> dict:
        dict_data = {
            "pid": self.pid,
            "sessionId": self.session_id,
            "cwd": self.cwd,
            "startedAt": self.started_at,
            "kind": self.kind,
            "entrypoint": self.entrypoint,
            "transcriptPath": self.transcript_path,
            "status": self.status,
            "parentSessionId": self.parent_session_id,
        }
        if self.project_id:
            dict_data["projectId"] = self.project_id
        if self.target_sections is not None:
            dict_data["targetSections"] = self.target_sections
        if self.current_stage:
            dict_data["currentStage"] = self.current_stage
        if self.progress:
            dict_data["progress"] = self.progress
        if self.current_phase:
            dict_data["currentPhase"] = self.current_phase
        if self.stage_logs:
            dict_data["stageLogs"] = self.stage_logs
        if self.tool_calls:
            dict_data["toolCalls"] = self.tool_calls
        if self.understanding:
            dict_data["understanding"] = self.understanding
        if self.planning:
            dict_data["planning"] = self.planning
        if self.action:
            dict_data["action"] = self.action
        if self.conversation and (self.conversation.get("user") or self.conversation.get("assistant")):
            dict_data["conversation"] = self.conversation
        if self.error:
            dict_data["error"] = self.error
        return dict_data

    @classmethod
    def from_dict(cls, data: dict) -> SessionRecord:
        record = cls(
            session_id=data["sessionId"],
            pid=data.get("pid", os.getpid()),
            cwd=data.get("cwd", ""),
            started_at=data.get("startedAt", time.time()),
            kind=data.get("kind", "interactive"),
            entrypoint=data.get("entrypoint", "cli"),
            transcript_path=data.get("transcriptPath", ""),
            status=data.get("status", "idle"),
            parent_session_id=data.get("parentSessionId"),
            project_id=data.get("projectId", ""),
            target_sections=data.get("targetSections"),
            current_stage=data.get("currentStage", 0),
            progress=data.get("progress", 0),
            current_phase=data.get("currentPhase", ""),
            stage_logs=data.get("stageLogs", []),
            tool_calls=data.get("toolCalls", []),
            understanding=data.get("understanding", []),
            planning=data.get("planning", []),
            action=data.get("action", []),
            conversation=data.get("conversation", {"user": [], "assistant": []}),
            error=data.get("error"),
        )
        record._path = Path(data.get("_path", ""))
        return record

    def _save(self) -> None:
        """Atomically save this session record to disk."""
        path = self._path
        if not path or not path.exists():
            return
        import tempfile
        parent = path.parent
        fd, tmp = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


class SessionLifecycle:
    """Manages session creation, resume, clear, and discovery."""

    @staticmethod
    def create(project_path: str, entrypoint: str = "cli", kind: str = "interactive", project_id: str = "") -> SessionRecord:
        """Create a new session, writing PID file and transcript path.

        Mirrors CCB state.ts:269 — getInitialState() calls randomUUID() to create sessionId.

        :param project_id: Project identifier. Directories are scoped under .Archtech/{project_id}/.
        """
        session_id = f"chat_{project_id}"
        now = time.time()
        cwd = os.getcwd()

        # Resolve per-project directories
        sessions_dir, projects_dir = _get_dir_cache(project_id)

        # Write session file: .ArchTech/{project_id}/chat_sessions/<session_id>.json
        sessions_dir.mkdir(parents=True, exist_ok=True)
        pid_file = sessions_dir / f"{session_id}.json"
        record = SessionRecord(
            session_id=session_id,
            pid=os.getpid(),
            cwd=cwd,
            started_at=now,
            kind=kind,
            entrypoint=entrypoint,
            transcript_path="",  # set below
        )

        # Determine transcript path: .archtech/{project_id}/projects/{sanitized-project-path}/{sessionId}.jsonl
        sanitized = project_path.replace("/", "_").replace("\\", "_")
        transcript_dir = projects_dir / sanitized
        transcript_dir.mkdir(parents=True, exist_ok=True)
        record.transcript_path = str(transcript_dir / f"{session_id}.jsonl")

        # Write session metadata file
        pid_file.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

        # Create empty transcript file
        Path(record.transcript_path).touch()

        log.info(
            f"[SessionLifecycle] Created session {session_id} "
            f"project={project_path} transcript={record.transcript_path}"
        )
        return record

    @staticmethod
    def resume(project_path: str, project_id: str = "") -> Optional[SessionRecord]:
        """Resume the latest active (non-terminal) session for a project.

        Mirrors CCB sessionStorage.ts:loadTranscriptFile() — finds latest non-terminal session.
        """
        _, projects_dir = _get_dir_cache(project_id)
        sanitized = project_path.replace("/", "_").replace("\\", "_")
        project_dir = projects_dir / sanitized
        if not project_dir.exists():
            return None

        # Find latest non-terminal session
        latest = None
        latest_time = 0.0
        sessions_dir, _ = _get_dir_cache(project_id)
        for transcript_file in project_dir.glob("*.jsonl"):
            try:
                mtime = transcript_file.stat().st_mtime
                # Check if there's a corresponding session in sessions dir
                for pid_file in sessions_dir.glob("*.json"):
                    try:
                        data = json.loads(pid_file.read_text(encoding="utf-8"))
                        if data.get("sessionId") == transcript_file.stem:
                            if data.get("status") in ("idle", "running") and mtime > latest_time:
                                latest_time = mtime
                                record = SessionRecord.from_dict({
                                    **data,
                                    "transcriptPath": str(transcript_file),
                                })
                                latest = record
                    except (json.JSONDecodeError, OSError):
                        continue
            except OSError:
                continue

        if latest:
            log.info(f"[SessionLifecycle] Resumed session {latest.session_id} from {latest.transcript_path}")
        return latest

    @staticmethod
    def clear(session_id: str, project_path: str, project_id: str = "") -> bool:
        """Clear current session and create a new one with parent_session_id set.

        Mirrors CCB: new UUID, parentSessionId set, old file untouched.
        """
        sessions_dir, projects_dir = _get_dir_cache(project_id)
        sanitized = project_path.replace("/", "_").replace("\\", "_")
        project_dir = projects_dir / sanitized

        # Find old session record
        old_record = None
        for transcript_file in project_dir.glob(f"{session_id}.jsonl"):
            # Try to find PID file
            for pid_file in sessions_dir.glob("*.json"):
                try:
                    data = json.loads(pid_file.read_text(encoding="utf-8"))
                    if data.get("sessionId") == session_id:
                        old_record = SessionRecord.from_dict({**data, "transcriptPath": str(transcript_file)})
                        break
                except (json.JSONDecodeError, OSError):
                    continue
            if old_record:
                break

        if old_record is None:
            log.warning(f"[SessionLifecycle] Session {session_id} not found for clear")
            return False

        # Create new session with parent_session_id
        new_record = SessionLifecycle.create(
            project_path=project_path,
            entrypoint=old_record.entrypoint,
            kind=old_record.kind,
            project_id=project_id,
        )
        new_record.parent_session_id = session_id
        new_record.status = "idle"

        # Update session file with parent_session_id
        pid_file = sessions_dir / f"{session_id}.json"
        if pid_file.exists():
            data = json.loads(pid_file.read_text(encoding="utf-8"))
            data["parentSessionId"] = session_id
            pid_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        log.info(
            f"[SessionLifecycle] Cleared session {session_id}, "
            f"created new session {new_record.session_id} with parent={session_id}"
        )
        return True

    @staticmethod
    def discover_active(project_id: str = "") -> list[SessionRecord]:
        """Discover all active sessions via PID files.

        Mirrors CCB concurrentSessions.ts:59 — reads .archtech/sessions/<PID>.json.
        If project_id is provided, only returns sessions for that project.
        If not, returns ALL active sessions across all projects.
        """
        sessions = []
        # If project_id given, only check that project; otherwise scan all
        if project_id:
            targets = [project_id]
        else:
            # Collect all known project dirs from .Archtech/
            archtech_dir = Path(__file__).resolve().parent.parent.parent / _ROOT_FOLDER_NAME
            if archtech_dir.exists():
                targets = [d.name for d in archtech_dir.iterdir() if d.is_dir() and d.name not in {"sessions", "None"}]
            else:
                return sessions
        seen_ids = set()
        for pid in targets:
            sessions_dir, _ = _get_dir_cache(pid)
            if not sessions_dir.exists():
                continue
            for pid_file in sessions_dir.glob("*.json"):
                try:
                    data = json.loads(pid_file.read_text(encoding="utf-8"))
                    sid = data.get("sessionId", "")
                    if sid in seen_ids:
                        continue
                    # Verify process is alive (best-effort check)
                    pid_check = data.get("pid", 0)
                    is_alive = False
                    try:
                        os.kill(pid_check, 0)
                        is_alive = True
                    except (OSError, ProcessLookupError):
                        is_alive = False
                    if not is_alive:
                        continue
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                except (json.JSONDecodeError, OSError):
                    continue
        seen_ids = set()
        for pid in targets:
            sessions_dir, _ = _get_dir_cache(pid)
            if not sessions_dir.exists():
                continue
            for pid_file in sessions_dir.glob("*.json"):
                try:
                    data = json.loads(pid_file.read_text(encoding="utf-8"))
                    sid = data.get("sessionId", "")
                    if sid in seen_ids:
                        continue
                    # Verify process is alive (best-effort check)
                    pid_check = data.get("pid", 0)
                    is_alive = False
                    try:
                        os.kill(pid_check, 0)
                        is_alive = True
                    except (OSError, ProcessLookupError):
                        pass
                    if is_alive:
                        seen_ids.add(sid)
                        sessions.append(SessionRecord.from_dict(data))
                except (json.JSONDecodeError, OSError):
                    continue
        return sessions

    @staticmethod
    def discover_history(project_path: str, project_id: str = "") -> list[SessionRecord]:
        """Discover all sessions for a project from transcript directory.

        Mirrors CCB sessionStorage.ts — reads project transcript directory for history.
        """
        _, projects_dir = _get_dir_cache(project_id)
        sanitized = project_path.replace("/", "_").replace("\\", "_")
        project_dir = projects_dir / sanitized
        records = []
        if not project_dir.exists():
            return records
        for transcript_file in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            records.append(
                SessionRecord(
                    session_id=transcript_file.stem,
                    pid=os.getpid(),
                    cwd="",
                    started_at=transcript_file.stat().st_mtime,
                    transcript_path=str(transcript_file),
                    status="history",
                )
            )
        return records

    # ------------------------------------------------------------------
    # Generation session helpers (replaces session.py functionality)
    # ------------------------------------------------------------------

    @staticmethod
    def create_generation(project_id: str, target_sections: list[str] | None = None) -> SessionRecord:
        """Create a session for a generation task. Stores in .Archtech/{project_id}/sessions/."""
        import hashlib
        if target_sections:
            key = ":".join(target_sections)
        else:
            key = "*"
        now_ns = time.time_ns()
        pid = os.getpid()
        raw = f"{project_id}:{key}:{now_ns}:{pid}"
        session_id = "sess-" + hashlib.md5(raw.encode()).hexdigest()[:10]

        sessions_dir = get_chat_session_dir(project_id=project_id)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        record = SessionRecord(
            session_id=session_id,
            pid=pid,
            cwd=os.getcwd(),
            started_at=time.time(),
            kind="generation",
            entrypoint="cli",
            status="running",
            project_id=project_id,
            target_sections=target_sections,
            _path=sessions_dir / f"{session_id}.json",
        )

        record._path.write_text(json.dumps(record.to_dict(), indent=2, default=str), encoding="utf-8")
        log.info(f"[SessionLifecycle] Created generation session={session_id} project={project_id}")
        return record

    @staticmethod
    def _load(session_id: str, project_id: str) -> Optional[SessionRecord]:
        """Load a session record by ID.
        Scans all project session dirs under .Archtech/{project}/sessions/.

        Args:
            session_id: The session identifier to load.
            project_id: Current project ID

        Returns:
            SessionRecord if found, None otherwise.
        """
        current_pid = project_id
        candidates: list[tuple[dict, Path]] = []
        if current_pid:
            # Fast path: check the current project first
            sessions_dir = get_chat_session_dir(current_pid)
            for session_file in sessions_dir.glob("*.json"):
                try:
                    data = json.loads(session_file.read_text(encoding="utf-8"))
                    if data.get("sessionId") == session_id:
                        candidates.append((data, session_file))
                except (json.JSONDecodeError, OSError, ValueError):
                    continue
        # Fallback: scan all project session dirs
        archtech_dir = Path(__file__).resolve().parent.parent.parent / _ROOT_FOLDER_NAME
        if not archtech_dir.exists():
            if not candidates:
                return None
        else:
            for project_dir in archtech_dir.iterdir():
                if not project_dir.is_dir() or project_dir.name in {"sessions", "chat_sessions", "None"}:
                    continue
                pid = project_dir.name
                sessions_dir = get_chat_session_dir(pid)
                if not sessions_dir.exists():
                    continue
                for session_file in sessions_dir.glob("*.json"):
                    try:
                        data = json.loads(session_file.read_text(encoding="utf-8"))
                        if data.get("sessionId") == session_id:
                            candidates.append((data, session_file))
                    except (json.JSONDecodeError, OSError, ValueError):
                        continue
        if not candidates:
            return None
        # Try to parse candidates; use the first one that succeeds
        for data, session_file in candidates:
            try:
                record = SessionRecord.from_dict({**data, "_path": str(session_file)})
                return record
            except (KeyError, ValueError):
                continue
        return None

    @staticmethod
    def update_progress(project_id: str, session_id: str, current_stage: int | None = None,
                        progress: int | None = None, current_phase: str | None = None,
                        status: str | None = None, error: str | None = None) -> Optional[SessionRecord]:
        """Update generation progress fields on a session."""
        rec = SessionLifecycle._load(session_id=session_id, project_id=project_id)
        if rec is None:
            return None
        if current_stage is not None:
            rec.current_stage = current_stage
        if progress is not None:
            rec.progress = progress
        if current_phase is not None:
            rec.current_phase = current_phase
        if status is not None:
            rec.status = status
        if error is not None:
            rec.error = error
        rec._save()
        return rec

    @staticmethod
    def log_stage_complete(project_id: str, session_id: str, stage: str, status: str = "ok",
                           duration_ms: float = 0, tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Record a stage completion in the session's stage_logs."""
        rec = SessionLifecycle._load(session_id=session_id, project_id=project_id)
        if rec is None:
            return
        rec.stage_logs.append({
            "stage": stage,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        rec._save()

    @staticmethod
    def log_tool_call(session_id: str, tool_name: str, status: str = "ok",
                      tokens_in: int = 0, tokens_out: int = 0, duration_ms: float = 0) -> None:
        """Record a tool call in the session's tool_calls."""
        rec = SessionLifecycle._load(session_id)
        if rec is None:
            return
        rec.tool_calls.append({
            "tool_name": tool_name,
            "status": status,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": round(duration_ms, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        rec._save()

    @staticmethod
    def find_active(project_id: str) -> Optional[SessionRecord]:
        """Find the latest active (non-terminal) session for a project."""
        sessions_dir = get_chat_session_dir(project_id=project_id)
        if not sessions_dir.exists():
            return None
        for session_file in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                if data.get("status") in ("running", "idle"):
                    rec = SessionRecord.from_dict({**data, "_path": str(session_file)})
                    return rec
            except (json.JSONDecodeError, OSError):
                continue
        return None

    @staticmethod
    def cancel(session_id: str, project_id: str) -> bool:
        """Cancel a session."""
        rec = SessionLifecycle._load(session_id=session_id, project_id=project_id)
        if rec is None:
            return False
        rec.status = "cancelled"
        rec._save()
        log.info(f"[SessionLifecycle] Cancelled: {session_id}")
        return True

    @staticmethod
    def find_latest(project_id: str) -> Optional[SessionRecord]:
        """Find the most recent session for a project, regardless of status."""
        sessions_dir = get_chat_session_dir(project_id=project_id)
        if not sessions_dir.exists():
            return None
        for session_file in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                rec = SessionRecord.from_dict({**data, "_path": str(session_file)})
                return rec
            except (json.JSONDecodeError, OSError):
                continue
        return None

    @staticmethod
    def get_progress(project_id: str) -> dict:
        """Get the latest session's progress for a project (including terminal states)."""
        import datetime as _dt
        rec = SessionLifecycle.find_latest(project_id)
        if rec is None:
            return {"status": "idle", "progress": 0}
        total_calls = len(rec.tool_calls)
        total_in = sum(c.get("tokens_in", 0) for c in rec.tool_calls)
        total_out = sum(c.get("tokens_out", 0) for c in rec.tool_calls)
        total_duration = sum(s.get("duration_ms", 0) for s in rec.stage_logs)
        elapsed = 0
        if rec.started_at:
            elapsed = round((datetime.now(timezone.utc) - _dt.datetime.fromtimestamp(rec.started_at, tz=_dt.timezone.utc)).total_seconds())
        return {
            "status": rec.status,
            "progress": rec.progress,
            "phase": rec.current_phase,
            "session_id": rec.session_id,
            "tool_calls_count": total_calls,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_duration_ms": total_duration,
            "elapsed_seconds": elapsed,
            "stage_logs": rec.stage_logs,
            "tool_calls": rec.tool_calls,
        }
