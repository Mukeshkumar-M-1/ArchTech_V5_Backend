"""
Execution History — Bounded context management for the ExecutionEngine.

Separates full execution history (audit/debugging) from LLM context (bounded window).

    ExecutionStore (full history)
           │
           └── ContextManager (bounded context)
                   │
                   ├── Base messages (developer + user)
                   ├── Last N complete turns
                   └── CompactPipeline (large output truncation)
                   │
                   ▼
                  LLM
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
import json
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionTurn:
    """A complete turn of LLM interaction: one assistant response + all tool results."""
    turn_number: int
    assistant_message: Dict[str, Any]
    tool_messages: List[Dict[str, Any]]
    tool_metadata: List[Dict[str, Any]]
    is_complete: bool

    @staticmethod
    def from_flat_messages(
        turn_number: int,
        assistant_msg: Dict[str, Any],
        tool_msgs: List[Dict[str, Any]],
        tool_meta: List[Dict[str, Any]],
    ) -> ExecutionTurn:
        """Construct a turn and validate completeness."""
        tool_call_ids = {
            tc["id"] for tc in assistant_msg.get("tool_calls", [])
        }
        result_ids = {
            tm.get("tool_call_id") for tm in tool_msgs
        }
        is_complete = bool(tool_call_ids and tool_call_ids == result_ids)
        log.info(
            "[ExecutionTurn] Turn %d created: complete=%s, tool_calls=%d, tool_results=%d",
            turn_number, is_complete, len(tool_call_ids), len(result_ids),
        )
        return ExecutionTurn(
            turn_number=turn_number,
            assistant_message=assistant_msg,
            tool_messages=tool_msgs,
            tool_metadata=tool_meta,
            is_complete=is_complete,
        )


@dataclass
class TurnFacts:
    """Structured facts extracted from a single turn via LLM."""
    turn_number: int
    key_findings: List[str] = None
    decisions: List[str] = None
    artifacts: List[Dict[str, str]] = None
    errors: List[str] = None
    patterns: List[str] = None

    def __post_init__(self):
        if self.key_findings is None:
            self.key_findings = []
        if self.decisions is None:
            self.decisions = []
        if self.artifacts is None:
            self.artifacts = []
        if self.errors is None:
            self.errors = []
        if self.patterns is None:
            self.patterns = []


@dataclass
class OldTurnSummary:
    """Result of summarizing old turns (LLM-enhanced or programmatic)."""
    text: str
    is_llm_enhanced: bool
    turns_covered: List[int]
    fact_counts: Dict[str, int]


@dataclass(frozen=True)
class ContextConfig:
    """Configuration for bounded context building."""
    recent_turns: int = 3
    max_context_messages: int = 30
    enable_llm_fact_extraction: bool = True
    fact_extraction_model: str = "haiku45"


class ExecutionStore:
    """Stores execution history as discrete turns, separate from LLM context."""

    def __init__(self, config: Optional[ContextConfig] = None) -> None:
        self.config = config or ContextConfig()
        self.base_messages: List[Dict[str, Any]] = []
        self.turns: List[ExecutionTurn] = []
        self.facts_cache: Dict[int, TurnFacts] = {}

    def set_base_messages(self, messages: List[Dict[str, Any]]) -> None:
        self.base_messages = list(messages)
        log.info("[ExecutionStore] Base messages set: %d messages", len(messages))

    def append_turn(self, turn: ExecutionTurn) -> None:
        self.turns.append(turn)
        log.info(
            "[ExecutionStore] Turn %d appended (complete=%s, tools=%d, cached_facts=%s)",
            turn.turn_number,
            turn.is_complete,
            len(turn.tool_messages),
            turn.turn_number in self.facts_cache,
        )

    def get_recent_turns(self) -> List[ExecutionTurn]:
        """Return the last N complete turns."""
        if not self.config.recent_turns:
            return []
        complete_turns = [t for t in self.turns if t.is_complete]
        recent = list(complete_turns[-self.config.recent_turns:])
        log.info(
            "[ExecutionStore] Recent turns: %d of %d complete turns (window=%d)",
            len(recent), len(complete_turns), self.config.recent_turns,
        )
        return recent

    def get_all_turns(self) -> List[ExecutionTurn]:
        return list(self.turns)

    def turn_count(self) -> int:
        return len(self.turns)


class ContextManager:
    """Builds bounded LLM context from ExecutionStore data."""

    def __init__(
        self,
        config: ContextConfig,
        compact_token_budget: int = 100_000,
    ) -> None:
        self.config = config
        from AgentCore.execution.context_compaction import ContextCompactPipeline, ContextTokenEstimator
        self._compact_pipeline = ContextCompactPipeline(token_budget=compact_token_budget)
        self._TokenEstimator = ContextTokenEstimator
        log.info(
            "[ContextManager] Initialized: recent_turns=%d, max_context_messages=%d, "
            "llm_fact_extraction=%s, extraction_model=%s",
            config.recent_turns,
            config.max_context_messages,
            config.enable_llm_fact_extraction,
            config.fact_extraction_model,
        )

    def build_context(
        self,
        base_messages: List[Dict[str, Any]],
        execution_turns: List[ExecutionTurn],
        store: Optional[ExecutionStore] = None,
    ) -> List[Dict[str, Any]]:
        """Build the bounded message list for an LLM call."""
        messages = [copy.deepcopy(m) for m in base_messages]

        # Split all complete turns into old vs recent.
        # Include turns that have tool_messages even if is_complete=False —
        # e.g. a paused turn where we injected a user response.
        complete_turns = [t for t in execution_turns if t.is_complete or t.tool_messages]
        recent_turns = complete_turns[-self.config.recent_turns:] if self.config.recent_turns else []
        old_turns = complete_turns[:-len(recent_turns)]

        log.info(
            "[ContextManager] build_context: base=%d, complete=%d, old=%d, recent=%d",
            len(base_messages), len(complete_turns), len(old_turns), len(recent_turns),
        )

        # Append summary as a new user message (before recent turns)
        if old_turns:
            if store:
                summary_result = self.build_old_turn_summary_enhanced(old_turns, store)
            else:
                summary_result = OldTurnSummary(
                    text=self._build_old_turn_summary(old_turns),
                    is_llm_enhanced=False,
                    turns_covered=[t.turn_number for t in old_turns],
                    fact_counts={},
                )
            messages.append({"role": "user", "content": summary_result.text})
            log.info(
                "[ContextManager] Appended old-turn summary as new user message (turns=%s, summary_len=%d)",
                summary_result.turns_covered, len(summary_result.text),
            )
            if summary_result.is_llm_enhanced:
                log.info(
                    "[ContextManager] LLM-enhanced summary: %d findings, %d decisions",
                    summary_result.fact_counts.get("key_findings", 0),
                    summary_result.fact_counts.get("decisions", 0),
                )

        # Flatten recent complete turns
        for turn in recent_turns:
            messages.append(copy.deepcopy(turn.assistant_message))
            for tool_msg in turn.tool_messages:
                messages.append(copy.deepcopy(tool_msg))

        # Validate tool-call integrity (recent turns only)
        self._validate_integrity(messages)

        # Run compaction pipeline every turn (no-op when under threshold)
        pre_compaction_count = len(messages)
        messages, _ = self._compact_pipeline.run(messages)
        post_compaction_count = len(messages)
        if pre_compaction_count != post_compaction_count:
            log.info(
                "[ContextManager] Compaction: %d -> %d messages",
                pre_compaction_count, post_compaction_count,
            )

        # Enforce hard cap on total message count
        messages = self._enforce_hard_cap(messages, base_messages)

        log.info(
            "[ContextManager] Final context: %d messages (%d base + %d history)",
            len(messages), len(base_messages), len(messages) - len(base_messages),
        )

        return messages

    def _build_old_turn_summary(self, turns: List[ExecutionTurn]) -> str:
        """Create a programmatic summary of old (pruned) turns."""
        lines = [f"## COMPLETED EXECUTION (Turns {turns[0].turn_number}-{turns[-1].turn_number})"]
        for turn in turns:
            tool_names = [
                tc.get("function", {}).get("name", "unknown")
                for tc in turn.assistant_message.get("tool_calls", [])
            ]
            if not tool_names:
                log.info("[ContextManager] Turn %d has no tool calls, skipping in summary", turn.turn_number)
                continue
            lines.append(f"- Turn {turn.turn_number}: " + ", ".join(tool_names))
            for tool_result_msg in turn.tool_messages:
                tool_name = tool_result_msg.get("name", "unknown")
                tool_content = str(tool_result_msg.get("content", ""))
                is_tool_error = tool_content.startswith("Error")
                tool_status = "failed" if is_tool_error else "success"
                resolved_file_path = self._extract_file_path(tool_result_msg)
                tool_input_detail = self._extract_tool_input(turn, tool_result_msg)
                if resolved_file_path:
                    lines.append(f"  Tool '{tool_name}' ({tool_status}): {resolved_file_path}")
                elif tool_input_detail:
                    lines.append(f"  Tool '{tool_name}' ({tool_status}): {tool_input_detail}")
                else:
                    lines.append(f"  Tool '{tool_name}' ({tool_status}): {len(tool_content)} chars")
        summary_text = "\n".join(lines)
        log.info(
            "[ContextManager] Programmatic summary: %d lines, %d chars",
            len(lines), len(summary_text),
        )
        return summary_text

    @staticmethod
    def _extract_file_path(tool_result_msg: Dict[str, Any]) -> Optional[str]:
        """Extract a file path from tool output content."""
        from AgentCore.execution.context_compaction import ContextToolCompact
        return ContextToolCompact.extract_path(str(tool_result_msg.get("content", "")))

    @staticmethod
    def _extract_tool_input(turn: ExecutionTurn, tool_msg: Dict[str, Any]) -> Optional[str]:
        """Extract key input from the matching tool_metadata."""
        tool_call_id = tool_msg.get("tool_call_id", "")
        for metadata in turn.tool_metadata:
            if metadata.get("tool_id") == tool_call_id:
                tool_args = metadata.get("tool_input_argument", {})
                if isinstance(tool_args, dict):
                    for key in ("file_path", "path", "pattern", "query"):
                        if key in tool_args:
                            return str(tool_args[key])[:120]
        return None

    def _validate_integrity(self, messages: List[Dict[str, Any]]) -> None:
        """Ensure every assistant tool_call has a matching tool result."""
        pending: Dict[str, str] = {}
        for msg in messages:
            role = msg.get("role", "")
            if role == "assistant" and msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    tool_call_id = tool_call.get("id", "")
                    pending[tool_call_id] = tool_call.get("function", {}).get("name", "unknown")
            elif role == "tool":
                result_id = msg.get("tool_call_id", "")
                if result_id in pending:
                    del pending[result_id]
                else:
                    log.warning("[ContextManager] Orphan tool message id=%s", result_id)

        if pending:
            log.warning(
                "[ContextManager] %d unmatched tool calls: %s",
                len(pending), list(pending.keys()),
            )
        else:
            log.info("[ContextManager] Tool-call integrity validated: all calls have matching results")

    def _enforce_hard_cap(
        self,
        messages: List[Dict[str, Any]],
        base_messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Drop oldest history messages if total exceeds hard cap."""
        if len(messages) <= self.config.max_context_messages:
            return messages
        base_len = len(base_messages)
        history = messages[base_len:]
        allowed_history = self.config.max_context_messages - base_len
        if allowed_history <= 0:
            return list(messages[:base_len])
        dropped = len(history) - allowed_history
        log.info("[ContextManager] Hard cap: dropped %d history messages", dropped)
        return messages[:base_len] + history[-allowed_history:]

    def get_context_stats(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate context statistics for logging."""
        assistant_message_count = sum(1 for m in messages if m.get("role") == "assistant")
        tool_message_count = sum(1 for m in messages if m.get("role") == "tool")
        tool_calls_count = sum(
            len(m.get("tool_calls", []))
            for m in messages
            if m.get("role") == "assistant"
        )
        estimated_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_tokens = self._TokenEstimator.estimate(messages)
        stats = {
            "total_messages": len(messages),
            "assistant_messages": assistant_message_count,
            "tool_messages": tool_message_count,
            "tool_calls": tool_calls_count,
            "estimated_characters": estimated_chars,
            "estimated_tokens": estimated_tokens,
        }
        log.info(
            "[ContextManager] Context stats: %d messages (%d assistant, %d tool), "
            "%d tool calls, %d chars, %d tokens",
            stats["total_messages"],
            stats["assistant_messages"],
            stats["tool_messages"],
            stats["tool_calls"],
            stats["estimated_characters"],
            stats["estimated_tokens"],
        )
        return stats

    def _format_turn_for_extraction(self, turn: ExecutionTurn, max_chars: int = 5000) -> str:
        """Format turn data as structured text for fact extraction LLM call."""
        parts = [f"--- TURN {turn.turn_number} ---"]
        assistant_content = str(turn.assistant_message.get("content", ""))[:1000]
        if assistant_content:
            parts.append(f"Assistant thought: {assistant_content}")
        tool_calls = turn.assistant_message.get("tool_calls", [])
        for tool_call in tool_calls:
            tool_name = tool_call.get("function", {}).get("name", "unknown")
            argsJsonStr = tool_call.get("function", {}).get("arguments", "{}")
            if isinstance(argsJsonStr, str):
                try:
                    argsDict = json.loads(argsJsonStr)
                except (json.JSONDecodeError, TypeError):
                    argsDict = argsJsonStr
            else:
                argsDict = argsJsonStr
            if isinstance(argsDict, dict):
                keyInputArgs = {k: v for k, v in argsDict.items() if k in ("file_path", "path", "pattern", "query")}
            else:
                keyInputArgs = str(argsDict)[:300]
            parts.append(f"Tool call: {tool_name}({keyInputArgs})")
        remainingChars = max_chars - len("\n".join(parts)) - 200
        charsPerToolResult = max(200, (remainingChars - 200) // max(len(turn.tool_messages), 1))
        for tool_result_msg in turn.tool_messages:
            result_name = tool_result_msg.get("name", "unknown")
            result_content = str(tool_result_msg.get("content", ""))
            is_result_error = result_content.startswith("Error")
            result_status = "ERROR" if is_result_error else "OK"
            truncated_content = result_content[:charsPerToolResult]
            parts.append(f"Result [{result_status}] {result_name}: {truncated_content}")
        formatted_text = "\n".join(parts)
        was_truncated = len(formatted_text) > max_chars
        output_text = formatted_text[:max_chars]
        if was_truncated:
            log.info(
                "[ContextManager] Turn %d extraction input truncated: %d -> %d chars",
                turn.turn_number, len(formatted_text), max_chars,
            )
        return output_text

    async def extract_facts_for_turn(
        self,
        turn: ExecutionTurn,
        store: ExecutionStore,
        model: str = None,
        max_tokens: int = 2048,
    ) -> Optional[TurnFacts]:
        """Extract structured facts from a single turn via LLM. Cache in store."""
        if turn.turn_number in store.facts_cache:
            cached_facts = store.facts_cache[turn.turn_number]
            log.info(
                "[ContextManager] Turn %d fact extraction: cache hit (%d findings, %d decisions)",
                turn.turn_number,
                len(cached_facts.key_findings),
                len(cached_facts.decisions),
            )
            return cached_facts

        input_text = self._format_turn_for_extraction(turn)
        extraction_model = model or self.config.fact_extraction_model
        log.info(
            "[ContextManager] Turn %d fact extraction: calling %s with %d chars input",
            turn.turn_number, extraction_model, len(input_text),
        )

        system_prompt = (
            "You are a technical fact extractor. Analyze the given agent execution turn "
            "and extract structured facts. Output ONLY valid JSON matching this schema:\n"
            '{\n'
            '  "key_findings": ["concise factual statements about discoveries"],\n'
            '  "decisions": ["decisions made based on results"],\n'
            '  "artifacts": [{"path": "/file/path", "action": "created|modified|read|deleted"}],\n'
            '  "errors": ["error messages and resolutions"],\n'
            '  "patterns": ["code patterns or conventions observed"]\n'
            '}\n'
            "Rules: each item max 200 chars. Empty list if nothing to report. No preamble."
        )
        from llm_api_handler import llm_request
        llm_result = await llm_request(
            model=extraction_model,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": input_text}],
            max_tokens=max_tokens,
            temperature=0.1,
            timeout=15.0,
            response_format="json",
        )
        if llm_result is None:
            log.warning(
                "[ContextManager] Fact extraction LLM returned None for turn %d",
                turn.turn_number,
            )
            return None
        try:
            facts_data = json.loads(llm_result)
            extracted_facts = TurnFacts(
                turn_number=turn.turn_number,
                key_findings=facts_data.get("key_findings", []),
                decisions=facts_data.get("decisions", []),
                artifacts=facts_data.get("artifacts", []),
                errors=facts_data.get("errors", []),
                patterns=facts_data.get("patterns", []),
            )
            store.facts_cache[turn.turn_number] = extracted_facts
            log.info(
                "[ContextManager] Turn %d fact extraction: %d findings, %d decisions, %d artifacts, %d errors, %d patterns",
                turn.turn_number,
                len(extracted_facts.key_findings),
                len(extracted_facts.decisions),
                len(extracted_facts.artifacts),
                len(extracted_facts.errors),
                len(extracted_facts.patterns),
            )
            return extracted_facts
        except json.JSONDecodeError:
            log.warning(
                "[ContextManager] Invalid JSON from fact extraction for turn %d (raw=%s)",
                turn.turn_number, str(llm_result)[:200],
            )
            return None

    def build_old_turn_summary_enhanced(
        self,
        turns: List[ExecutionTurn],
        store: ExecutionStore,
    ) -> OldTurnSummary:
        """Build summary using cached LLM facts, falling back to programmatic per turn."""
        lines = [f"## COMPLETED EXECUTION (Turns {turns[0].turn_number}-{turns[-1].turn_number})"]
        hasLlmFacts = False
        total_findings = 0
        total_decisions = 0
        llm_turn_count = 0
        fallback_turn_count = 0

        for turn in turns:
            cached_facts = store.facts_cache.get(turn.turn_number)
            if cached_facts and any([
                cached_facts.key_findings,
                cached_facts.decisions,
                cached_facts.artifacts,
                cached_facts.errors,
                cached_facts.patterns,
            ]):
                hasLlmFacts = True
                llm_turn_count += 1
                lines.append(f"\n### Turn {turn.turn_number}")
                if cached_facts.key_findings:
                    total_findings += len(cached_facts.key_findings)
                    lines.append("Findings:")
                    for finding in cached_facts.key_findings:
                        lines.append(f"  - {finding}")
                if cached_facts.decisions:
                    total_decisions += len(cached_facts.decisions)
                    lines.append("Decisions:")
                    for decision in cached_facts.decisions:
                        lines.append(f"  - {decision}")
                if cached_facts.artifacts:
                    lines.append("Artifacts:")
                    for artifact in cached_facts.artifacts:
                        lines.append(f"  - [{artifact.get('action', '?')}] {artifact.get('path', '?')}")
                if cached_facts.errors:
                    lines.append("Errors/Resolutions:")
                    for errorItem in cached_facts.errors:
                        lines.append(f"  - {errorItem}")
                if cached_facts.patterns:
                    lines.append("Patterns:")
                    for pattern in cached_facts.patterns:
                        lines.append(f"  - {pattern}")
            else:
                fallback_turn_count += 1
                log.info(
                    "[ContextManager] Turn %d: no LLM facts available, using programmatic fallback",
                    turn.turn_number,
                )
                programmaticSummary = self._build_old_turn_summary([turn])
                lines.append(programmaticSummary)

        summary_text = "\n".join(lines)
        log.info(
            "[ContextManager] Enhanced summary: %d turns with LLM facts, %d fallbacks, total=%d turns, %d chars",
            llm_turn_count, fallback_turn_count, len(turns), len(summary_text),
        )

        return OldTurnSummary(
            text=summary_text,
            is_llm_enhanced=hasLlmFacts,
            turns_covered=[t.turn_number for t in turns],
            fact_counts={"key_findings": total_findings, "decisions": total_decisions},
        )