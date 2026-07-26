"""
Session Memory — Extract, cache, and reuse conversation context.

Mirrors CCB's session memory extraction:
- After each turn, scan transcript for reusable facts
- Cache facts per session (write to .Archtech/<Project_id>/sessions/<session_id>/memory.json)
- Auto-compact reuses session memory instead of making another API call
- Saves both tokens and money vs legacy compact
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional
from system_config import get_session_transcript_dir

log = logging.getLogger(__name__)

class PTAOSectionExtractor:
    """Extract structured PTAO sections from conversation messages.

    Parses PTAO markers ([UNDERSTAND], [PLANNING], [ACTION]) from assistant
    text and links them with tool calls and tool results. Also extracts
    user/assistant conversation history.
    """

    STEP_PATTERNS = {
        "UNDERSTAND": re.compile(r'\[UNDERSTAND\]\s*\n?(.*?)(?=\n\[[A-Z]+\]|$)', re.DOTALL),
        "PLANNING": re.compile(r'\[PLANNING\]\s*\n?(.*?)(?=\n\[[A-Z]+\]|$)', re.DOTALL),
        "ACTION": re.compile(r'\[ACTION\]\s*\n?(.*?)(?=\n\[[A-Z]+\]|$)', re.DOTALL),
    }

    DECISION_PATTERN = re.compile(
        r'(?:decided|chosen|select|go with|will use|should use|opted for|prefer|using)',
        re.IGNORECASE,
    )

    FILE_PATH_PATTERN = re.compile(r"[\"']?(/[^\s'\"]+|\.\/[^\s'\"]+)[\"']?")

    def extract_from_messages(self, messages: list[dict]) -> dict:
        """Extract structured PTAO sections from conversation messages.

        Parses PTAO markers ([UNDERSTAND], [PLANNING], [ACTION]) from assistant
        text and links them with tool calls and tool results.

        Args:
            messages: List of conversation messages.

        Returns:
            Dict with structured PTAO data, decisions, and conversation history.
        """
        result = {
            "understanding": [],
            "planning": [],
            "action": [],
            "conversation": {"user": [], "assistant": []},
            "decisions": [],
        }

        assistant_turn = 0
        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = str(msg.get("content", ""))

            if role == "assistant" and content:
                assistant_turn += 1
                result["conversation"]["assistant"].append({
                    "turn": assistant_turn,
                    "full_text": content,
                })
                self._parse_ptao_steps(content, assistant_turn, result)

            elif role == "user":
                result["conversation"]["user"].append({
                    "turn": len(result["conversation"]["user"]) + 1,
                    "content": content,
                })

            elif role == "tool":
                self._link_tool_result(content, result)

        return result

    def _parse_ptao_steps(self, text: str, turn: int, result: dict):
        """Parse PTAO markers from assistant text and populate sections."""
        for step_name, pattern in self.STEP_PATTERNS.items():
            match = pattern.search(text)
            if match:
                step_content = match.group(1).strip()
                if step_name == "UNDERSTAND":
                    result["understanding"].append(step_content)
                elif step_name == "PLANNING":
                    result["planning"].append(step_content)
                elif step_name == "ACTION":
                    action_entry = {
                        "turn": turn,
                        "ptao_action": step_content,
                    }
                    result["action"].append(action_entry)

                # Extract decisions from PTAO steps
                if self.DECISION_PATTERN.search(step_content) and len(step_content) > 20:
                    sentence = step_content[:500]
                    if sentence not in result["decisions"]:
                        result["decisions"].append(sentence)

    def _link_tool_result(self, content: str, result: dict):
        """Link tool result to the latest action entry."""
        if not result["action"]:
            return
        # Find the latest action without a result
        for action in reversed(result["action"]):
            if "tool_result" not in action:
                action["tool_result"] = content.strip()
                break

    def extract_files(self, messages: list[dict]) -> list[str]:
        """Extract unique file paths from messages for cross-section shared memory.

        Args:
            messages: List of conversation messages to scan.

        Returns:
            List of unique file path strings found in recent messages.
        """
        """Extract unique file paths from messages (for cross-section shared memory)."""
        files = []
        seen = set()
        for msg in messages[-10:]:
            content = str(msg.get("content", ""))
            for path in self.FILE_PATH_PATTERN.findall(content):
                if path not in seen:
                    seen.add(path)
                    files.append(path)
        return files


class SessionMemoryExtractor:
    """Extract reusable facts from conversation messages.

    Uses PTAOSectionExtractor for PTAO reasoning, conversation history,
    and decisions. Extracts file paths for cross-section shared memory.
    Called after each turn (incremental — last turn only, not full transcript).
    """

    def __init__(self):
        """Initialize with a PTAO section extractor."""
        self._ptao = PTAOSectionExtractor()

    def extract(self, messages: list[dict], session_id: str) -> dict:
        """Extract reusable facts from the last turn's messages.

        Args:
            messages: List of conversation messages to extract from.
            session_id: The session identifier for cache key.

        Returns:
            Dict with files, understanding, planning, action, conversation, decisions.
        """
        """Extract reusable facts from the last turn's messages."""
        ptao = self._ptao.extract_from_messages(messages)
        files = self._ptao.extract_files(messages)

        memory = {
            "files": files,
            "understanding": ptao["understanding"],
            "planning": ptao["planning"],
            "action": ptao["action"],
            "conversation": ptao["conversation"],
            "decisions": ptao["decisions"],
        }
        return memory


class SessionMemoryCache:
    """Cache session memory for reuse during auto-compact.

    Stores memory in .Archtech/<Project_id>/sessions/<session_id>.json
    """

    def __init__(self, project_id: str):
        """Initialize session memory cache for a project.

        Args:
            project_id: The project identifier for directory scoping.
        """
        self._base = get_session_transcript_dir(project_id=project_id)

    def save(self, session_id: str, memory: dict) -> None:
        """Save extracted memory for a session to disk.

        Args:
            session_id: The session identifier.
            memory: Dict of extracted memory data.
        """
        mem_file = self._base / f"{session_id}.json"
        mem_file.write_text(json.dumps(memory, indent=2, default=str), encoding="utf-8")
        understanding_count = len(memory.get("understanding", []))
        decisions_count = len(memory.get("decisions", []))
        log.info(f"[SessionMemory] Saved memory for session {session_id}: {len(memory.get('files', []))} files, {understanding_count} understandings, {decisions_count} decisions")

    def load(self, session_id: str) -> Optional[dict]:
        """Load saved memory for a session from disk.

        Args:
            session_id: The session identifier.

        Returns:
            The loaded memory dict, or None if not found or corrupted.
        """
        mem_file = self._base / f"{session_id}.json"
        if not mem_file.exists():
            return None
        try:
            data = json.loads(mem_file.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def clear(self, session_id: str) -> None:
        """Remove cached memory for a session from disk.

        Args:
            session_id: The session identifier.
        """
        mem_file = self._base / f"{session_id}.json"
        mem_file.unlink(missing_ok=True)

    def update(self, session_id: str, delta: dict) -> dict:
        """Merge new memory delta with existing session memory.

        Args:
            session_id: The session identifier.
            delta: New memory data to merge.

        Returns:
            The updated memory dict after merging.
        """
        existing = self.load(session_id)
        if existing is None:
            existing = {
                "files": [],
                "understanding": [],
                "planning": [],
                "action": [],
                "conversation": {"user": [], "assistant": []},
                "decisions": [],
            }

        for key, values in delta.items():
            if key in ("files", "understanding", "planning", "decisions"):
                # Unique merge for scalar lists
                existing.setdefault(key, [])
                for item in values:
                    if item not in existing[key]:
                        existing[key].append(item)
            elif key == "action":
                # Append all action entries (turn-based, no duplicates)
                existing.setdefault(key, [])
                existing[key].extend(values)
            elif key == "conversation":
                # Append user/assistant turns
                conv = existing.setdefault(key, {"user": [], "assistant": []})
                for role in ("user", "assistant"):
                    conv.setdefault(role, [])
                    conv[role].extend(values.get(role, []))
            else:
                existing[key] = values

        self.save(session_id, existing)
        return existing


class CompactSummary:
    """Produces the compact summary string for auto-compact.

    Uses SessionMemoryCache first (session memory compact).
    Falls back to legacy summary_fn if no session memory exists.
    """

    def __init__(self, memory_cache: SessionMemoryCache):
        """Initialize with a session memory cache.

        Args:
            memory_cache: SessionMemoryCache instance for loading persisted memory.
        """
        self._cache = memory_cache

    def _first_last(self, items: list, n: int = 100) -> list:
        """Return first N items with last N if total exceeds 2N.

        Args:
            items: List of items to trim.
            n: Maximum number of items from each end.

        Returns:
            Trimmed list with omitted items indicator if necessary.
        """
        """Return first N items (or last N if total > 2N, with indicator)."""
        if len(items) <= n:
            return items
        if len(items) <= 2 * n:
            return items[:n] + ["... (last " + str(len(items) - n) + " items omitted)"] + items[-(len(items) - n):]
        return items[:n] + ["... (showing first " + str(n) + " of " + str(len(items)) + ")"] + items[-n:]

    def get_summary(self, session_id: str, old_messages: list[dict],
                    legacy_fn=None) -> Optional[str]:
        """Get a compact summary for auto-compact.

        Returns formatted session memory if available, otherwise None
        (triggers legacy fallback in compaction).
        """
        memory = self._cache.load(session_id)
        if memory and any(memory.values()):
            lines = []

            # --- Files ---
            files = memory.get("files", [])
            if files:
                lines.append(f"\n## Files ({len(files)} total):")
                for file_entry in self._first_last(files):
                    lines.append(f"  - {file_entry}")

            # --- Understanding (first 100, last 100) ---
            understanding = memory.get("understanding", [])
            if understanding:
                lines.append(f"\n## Understanding ({len(understanding)} total):")
                for understanding_item in self._first_last(understanding):
                    lines.append(f"  - {understanding_item[:300]}")

            # --- Planning (first 100, last 100) ---
            planning = memory.get("planning", [])
            if planning:
                lines.append(f"\n## Planning ({len(planning)} total):")
                for planning_item in self._first_last(planning):
                    lines.append(f"  - {planning_item[:300]}")

            # --- Actions (first 100, last 100) ---
            action = memory.get("action", [])
            if action:
                lines.append(f"\n## Actions ({len(action)} total):")
                for action_item in self._first_last(action):
                    if isinstance(action_item, dict):
                        tool_name = action_item.get("tool", "unknown")
                        ptao = action_item.get("ptao_action", "")[:300]
                        lines.append(f"  - [{tool_name}] {ptao}")
                    else:
                        lines.append(f"  - {str(action_item)[:300]}")

            # --- Conversation (first 100, last 100) ---
            conversation = memory.get("conversation", {})
            user_msgs = conversation.get("user", [])
            assistant_msgs = conversation.get("assistant", [])
            if user_msgs:
                lines.append(f"\n## User Messages ({len(user_msgs)} total):")
                for msg in self._first_last(user_msgs):
                    content = msg.get("content", str(msg))[:300] if isinstance(msg, dict) else str(msg)[:300]
                    lines.append(f"  - {content}")
            if assistant_msgs:
                lines.append(f"\n## Assistant Messages ({len(assistant_msgs)} total):")
                for msg in self._first_last(assistant_msgs):
                    content = msg.get("full_text", str(msg))[:300] if isinstance(msg, dict) else str(msg)[:300]
                    lines.append(f"  - {content}")

            # --- Decisions (first 100, last 100) ---
            decisions = memory.get("decisions", [])
            if decisions:
                lines.append(f"\n## Decisions ({len(decisions)} total):")
                for decision_item in self._first_last(decisions):
                    lines.append(f"  - {decision_item[:300]}")

            summary = "\n".join(lines)
            log.info(f"[CompactSummary] Using session memory for {session_id}")
            return summary

        if legacy_fn is not None:
            log.info(f"[CompactSummary] No session memory, using legacy function for {session_id}")
            try:
                return legacy_fn(old_messages)
            except Exception as e:
                log.warning(f"[CompactSummary] Legacy function failed: {e}")
                return None

        return None
