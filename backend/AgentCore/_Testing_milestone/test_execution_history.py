"""
Tests for bounded context management: ExecutionTurn, ExecutionStore, ContextManager.
"""

import pytest
from AgentCore.core.execution_history import (
    ContextConfig,
    ContextManager,
    ExecutionStore,
    ExecutionTurn,
    OldTurnSummary,
    TurnFacts,
)


def _make_assistant_msg(tool_ids=None):
    """Build a minimal assistant message with optional tool_calls."""
    msg = {"role": "assistant", "content": "thinking...", "tool_calls": []}
    if tool_ids:
        for i, tid in enumerate(tool_ids):
            msg["tool_calls"].append({
                "id": tid,
                "type": "function",
                "function": {"name": f"tool_{i}", "arguments": "{}"},
            })
    return msg


def _make_tool_msg(tool_call_id, name="tool_0", content="ok"):
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }


class TestExecutionTurn:
    def test_complete_turn(self):
        """2 tool_calls + 2 matching results → is_complete=True"""
        assistant = _make_assistant_msg(["call_1", "call_2"])
        tools = [_make_tool_msg("call_1"), _make_tool_msg("call_2")]
        turn = ExecutionTurn.from_flat_messages(
            turn_number=1,
            assistant_msg=assistant,
            tool_msgs=tools,
            tool_meta=[],
        )
        assert turn.is_complete is True

    def test_incomplete_turn_missing_result(self):
        """2 tool_calls + 1 result → is_complete=False"""
        assistant = _make_assistant_msg(["call_1", "call_2"])
        tools = [_make_tool_msg("call_1")]
        turn = ExecutionTurn.from_flat_messages(
            turn_number=1,
            assistant_msg=assistant,
            tool_msgs=tools,
            tool_meta=[],
        )
        assert turn.is_complete is False

    def test_no_tool_calls_incomplete(self):
        """No tool_calls → is_complete=False (no work done)"""
        assistant = _make_assistant_msg()
        turn = ExecutionTurn.from_flat_messages(
            turn_number=1,
            assistant_msg=assistant,
            tool_msgs=[],
            tool_meta=[],
        )
        assert turn.is_complete is False

    def test_frozen_dataclass(self):
        """Frozen dataclass prevents mutation."""
        turn = ExecutionTurn(
            turn_number=1,
            assistant_message={},
            tool_messages=[],
            tool_metadata=[],
            is_complete=True,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            turn.turn_number = 2


class TestExecutionStore:
    def test_sliding_window(self):
        """5 turns appended, config=3 → get_recent returns last 3."""
        config = ContextConfig(recent_turns=3)
        store = ExecutionStore(config=config)
        store.set_base_messages([{"role": "developer", "content": "dev"}, {"role": "user", "content": "user"}])
        for i in range(1, 6):
            assistant = _make_assistant_msg([f"call_{i}"])
            tools = [_make_tool_msg(f"call_{i}")]
            turn = ExecutionTurn.from_flat_messages(i, assistant, tools, [])
            store.append_turn(turn)
        recent = store.get_recent_turns()
        assert len(recent) == 3
        assert recent[0].turn_number == 3
        assert recent[2].turn_number == 5

    def test_get_all_turns(self):
        """5 turns → get_all returns all 5."""
        store = ExecutionStore(config=ContextConfig(recent_turns=3))
        for i in range(1, 6):
            assistant = _make_assistant_msg([f"call_{i}"])
            tools = [_make_tool_msg(f"call_{i}")]
            turn = ExecutionTurn.from_flat_messages(i, assistant, tools, [])
            store.append_turn(turn)
        assert len(store.get_all_turns()) == 5

    def test_incomplete_turn_excluded_from_recent(self):
        """Incomplete turns are not returned by get_recent_turns."""
        store = ExecutionStore(config=ContextConfig(recent_turns=3))
        # Turn 1: complete
        assistant = _make_assistant_msg(["call_1"])
        store.append_turn(ExecutionTurn.from_flat_messages(1, assistant, [_make_tool_msg("call_1")], []))
        # Turn 2: incomplete
        assistant = _make_assistant_msg(["call_2a", "call_2b"])
        store.append_turn(ExecutionTurn.from_flat_messages(2, assistant, [_make_tool_msg("call_2a")], []))
        # Turn 3: complete
        assistant = _make_assistant_msg(["call_3"])
        store.append_turn(ExecutionTurn.from_flat_messages(3, assistant, [_make_tool_msg("call_3")], []))
        recent = store.get_recent_turns()
        turn_numbers = [t.turn_number for t in recent]
        assert 2 not in turn_numbers
        assert 1 in turn_numbers
        assert 3 in turn_numbers


class TestContextManager:
    def test_bounded_context(self):
        """10 turns → context contains only base + recent 3 turns."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        store = ExecutionStore(config=config)
        store.set_base_messages([{"role": "developer", "content": "d"}, {"role": "user", "content": "u"}])
        for i in range(1, 11):
            assistant = _make_assistant_msg([f"call_{i}"])
            store.append_turn(ExecutionTurn.from_flat_messages(i, assistant, [_make_tool_msg(f"call_{i}")], []))
        cm = ContextManager(config=config)
        recent = store.get_recent_turns()
        ctx = cm.build_context(store.base_messages, recent)
        # Should be base(2) + 3 turns × (1 assistant + 1 tool) = 8
        assert len(ctx) == 8

    def test_first_turn_empty_store(self):
        """No prior turns → only base messages returned."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        cm = ContextManager(config=config)
        base = [{"role": "developer", "content": "d"}, {"role": "user", "content": "u"}]
        ctx = cm.build_context(base, [])
        assert len(ctx) == 2

    def test_orphan_tool_message_detected(self, caplog):
        """Tool message without matching assistant call → warning logged."""
        caplog.set_level("WARNING")
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        cm = ContextManager(config=config)
        base = [{"role": "developer", "content": "d"}]
        # Create a turn with mismatched IDs
        assistant = _make_assistant_msg(["call_real"])
        tool_msgs = [_make_tool_msg("call_real"), _make_tool_msg("call_orphan")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        cm.build_context(base, [turn])
        assert "Orphan tool message" in caplog.text

    def test_unmatched_tool_calls_detected(self, caplog):
        """Assistant tool_call without result → warning logged."""
        caplog.set_level("WARNING")
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        cm = ContextManager(config=config)
        base = [{"role": "developer", "content": "d"}]
        assistant = _make_assistant_msg(["call_1", "call_2"])
        tool_msgs = [_make_tool_msg("call_1")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=False)
        # Force incomplete turn through by building manually
        messages = list(base) + [assistant] + tool_msgs
        cm._validate_integrity(messages)
        assert "unmatched tool calls" in caplog.text

    def test_hard_cap_enforcement(self):
        """50+ messages, cap=30 → exactly 30 returned with base preserved."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        store = ExecutionStore(config=config)
        store.set_base_messages([{"role": "developer", "content": "d"}, {"role": "user", "content": "u"}])
        # Create turns with many tools each
        for i in range(1, 6):
            tool_ids = [f"call_{i}_1", f"call_{i}_2", f"call_{i}_3"]
            assistant = _make_assistant_msg(tool_ids)
            tools = [_make_tool_msg(tid) for tid in tool_ids]
            turn = ExecutionTurn.from_flat_messages(i, assistant, tools, [])
            store.append_turn(turn)
        cm = ContextManager(config=config)
        ctx = cm.build_context(store.base_messages, store.get_all_turns())
        assert len(ctx) <= 30
        assert ctx[0]["role"] == "developer"
        assert ctx[1]["role"] == "user"

    def test_large_tool_output_truncation(self):
        """10K-char tool output → truncated by CompactPipeline."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        cm = ContextManager(config=config)
        large_content = "X" * 10_000
        assistant = _make_assistant_msg(["call_big"])
        tool_msgs = [_make_tool_msg("call_big", content=large_content)]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        base = [{"role": "developer", "content": "d"}]
        ctx = cm.build_context(base, [turn])
        # The tool content in ctx should be truncated
        tool_result = [m for m in ctx if m.get("role") == "tool"][0]
        assert len(tool_result["content"]) < len(large_content)

    def test_context_stats(self):
        """get_context_stats returns correct counts."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        cm = ContextManager(config=config)
        messages = [
            {"role": "developer", "content": "dev"},
            {"role": "user", "content": "user"},
            {"role": "assistant", "content": "text", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "name": "t", "content": "ok"},
        ]
        stats = cm.get_context_stats(messages)
        assert stats["total_messages"] == 4
        assert stats["assistant_messages"] == 1
        assert stats["tool_messages"] == 1
        assert stats["tool_calls"] == 1

    def test_old_turn_summary_present(self):
        """4 complete turns → turn 1 summarized, turns 2-4 recent."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        store = ExecutionStore(config=config)
        store.set_base_messages([{"role": "developer", "content": "d"}, {"role": "user", "content": "u"}])
        for i in range(1, 5):
            assistant = _make_assistant_msg([f"call_{i}"])
            store.append_turn(ExecutionTurn.from_flat_messages(i, assistant, [_make_tool_msg(f"call_{i}", content=f"result_{i}")], []))
        cm = ContextManager(config=config)
        ctx = cm.build_context(store.base_messages, store.get_all_turns())
        # Summary is appended as a new user message: base(2) + 1 summary + 3 recent turns(6) = 9
        assert len(ctx) == 9
        # The summary should be a separate user message after base messages
        summary_msgs = [m for m in ctx if m.get("role") == "user" and "COMPLETED EXECUTION" in m.get("content", "")]
        assert len(summary_msgs) == 1
        user_msg = summary_msgs[0]
        assert "COMPLETED EXECUTION" in user_msg["content"]
        assert "Turn 1" in user_msg["content"]
        assert "tool_0" in user_msg["content"]
        # Turns 2-4 should NOT appear in summary
        assert "Turn 2" not in user_msg["content"]
        assert "Turn 3" not in user_msg["content"]
        assert "Turn 4" not in user_msg["content"]

    def test_no_summary_few_turns(self):
        """2 turns, window=3 → no old turns → no summary."""
        config = ContextConfig(recent_turns=3, max_context_messages=30)
        store = ExecutionStore(config=config)
        store.set_base_messages([{"role": "developer", "content": "d"}])
        for i in range(1, 3):
            assistant = _make_assistant_msg([f"call_{i}"])
            store.append_turn(ExecutionTurn.from_flat_messages(i, assistant, [_make_tool_msg(f"call_{i}")], []))
        cm = ContextManager(config=config)
        ctx = cm.build_context(store.base_messages, store.get_all_turns())
        # Base(1) + 2 turns(4) = 5, no summary
        summary_msgs = [m for m in ctx if m.get("role") == "user" and "COMPLETED" in str(m.get("content", ""))]
        assert len(summary_msgs) == 0

    def test_old_summary_with_tool_metadata(self):
        """Summary includes file paths from tool_input_argument metadata."""
        config = ContextConfig(recent_turns=2, max_context_messages=30)
        cm = ContextManager(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="/some/path/file.txt\nline content")]
        tool_meta = [{"tool_id": "call_1", "tool_input_argument": {"file_path": "/some/path/file.txt"}}]
        turn = ExecutionTurn.from_flat_messages(1, assistant, tool_msgs, tool_meta)
        base = [{"role": "developer", "content": "d"}]
        summary = cm._build_old_turn_summary([turn])
        assert "/some/path/file.txt" in summary

    def test_old_summary_with_error_tools(self):
        """Summary marks tools with error content as 'failed'."""
        config = ContextConfig(recent_turns=2, max_context_messages=30)
        cm = ContextManager(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="Error: file not found")]
        turn = ExecutionTurn.from_flat_messages(1, assistant, tool_msgs, [])
        summary = cm._build_old_turn_summary([turn])
        assert "failed" in summary
        assert "Error" not in summary.split("-")[0]  # error status, not raw output


class TestTurnFacts:
    def test_turn_facts_defaults(self):
        """TurnFacts initializes with empty lists."""
        facts = TurnFacts(turn_number=1)
        assert facts.key_findings == []
        assert facts.decisions == []
        assert facts.artifacts == []
        assert facts.errors == []
        assert facts.patterns == []

    def test_turn_facts_with_data(self):
        """TurnFacts stores all fields correctly."""
        facts = TurnFacts(
            turn_number=1,
            key_findings=["found X"],
            decisions=["chose Y"],
            artifacts=[{"path": "/a", "action": "read"}],
            errors=["error Z"],
            patterns=["pattern P"],
        )
        assert len(facts.key_findings) == 1
        assert len(facts.decisions) == 1
        assert len(facts.artifacts) == 1
        assert facts.artifacts[0]["action"] == "read"


class TestFormatTurnForExtraction:
    def test_truncates_large_output(self):
        """Large tool output truncated under max_chars."""
        config = ContextConfig()
        cm = ContextManager(config=config)
        large_content = "X" * 20_000
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content=large_content)]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        result = cm._format_turn_for_extraction(turn, max_chars=5000)
        assert len(result) <= 5000
        assert "TURN 1" in result
        assert "tool_0" in result

    def test_includes_key_args(self):
        """Key arguments extracted from tool_calls."""
        config = ContextConfig()
        cm = ContextManager(config=config)
        assistant = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "type": "function",
                "function": {
                    "name": "file_read",
                    "arguments": '{"file_path": "/src/main.py", "other": "value"}',
                },
            }],
        }
        tool_msgs = [_make_tool_msg("c1", name="file_read", content="def main(): pass")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        result = cm._format_turn_for_extraction(turn)
        assert "file_path" in result
        assert "/src/main.py" in result


class TestExtractFactsForTurn:
    @pytest.mark.asyncio
    async def test_caches_result(self):
        """Second call returns cached facts without LLM call."""
        config = ContextConfig(enable_llm_fact_extraction=True)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        # Pre-populate cache
        expected = TurnFacts(turn_number=1, key_findings=["cached fact"])
        store.facts_cache[1] = expected
        result = await cm.extract_facts_for_turn(turn, store)
        assert result is expected
        assert result.key_findings == ["cached fact"]

    @pytest.mark.asyncio
    async def test_graceful_llm_failure(self, monkeypatch):
        """LLM returns None → function returns None, no cache entry."""
        async def mock_llm_request(*args, **kwargs):
            return None
        monkeypatch.setattr("llm_api_handler.llm_request", mock_llm_request)
        config = ContextConfig(enable_llm_fact_extraction=True)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        result = await cm.extract_facts_for_turn(turn, store)
        assert result is None
        assert 1 not in store.facts_cache

    @pytest.mark.asyncio
    async def test_invalid_json(self, monkeypatch):
        """LLM returns invalid JSON → function returns None, no cache entry."""
        async def mock_llm_request(*args, **kwargs):
            return "not valid json {"
        monkeypatch.setattr("llm_api_handler.llm_request", mock_llm_request)
        config = ContextConfig(enable_llm_fact_extraction=True)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        result = await cm.extract_facts_for_turn(turn, store)
        assert result is None
        assert 1 not in store.facts_cache


class TestOldTurnSummaryEnhanced:
    def test_uses_llm_facts(self):
        """Cached facts produce LLM-enhanced summary."""
        config = ContextConfig(recent_turns=2)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        # Pre-populate cache with LLM facts
        store.facts_cache[1] = TurnFacts(
            turn_number=1,
            key_findings=["found test cases"],
            decisions=["chose structure"],
            artifacts=[{"path": "/src/main.py", "action": "read"}],
        )
        summary = cm.build_old_turn_summary_enhanced([turn], store)
        assert summary.is_llm_enhanced is True
        assert "found test cases" in summary.text
        assert "chose structure" in summary.text
        assert "/src/main.py" in summary.text
        assert summary.fact_counts["key_findings"] == 1
        assert summary.fact_counts["decisions"] == 1

    def test_mixed_fallback(self):
        """Some turns cached, some not → hybrid output."""
        config = ContextConfig(recent_turns=2)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        # Turn 1: has LLM facts
        assistant1 = _make_assistant_msg(["call_1"])
        tool1 = [_make_tool_msg("call_1", content="result1")]
        turn1 = ExecutionTurn(1, assistant1, tool1, [], is_complete=True)
        store.facts_cache[1] = TurnFacts(
            turn_number=1,
            key_findings=["fact1"],
        )
        # Turn 2: no LLM facts
        assistant2 = _make_assistant_msg(["call_2"])
        tool2 = [_make_tool_msg("call_2", content="result2")]
        turn2 = ExecutionTurn(2, assistant2, tool2, [], is_complete=True)
        summary = cm.build_old_turn_summary_enhanced([turn1, turn2], store)
        assert summary.is_llm_enhanced is True
        assert "fact1" in summary.text  # Turn 1 uses LLM
        assert "Turn 2" in summary.text  # Turn 2 uses programmatic
        assert "tool_0" in summary.text

    def test_all_fallback(self):
        """No cache → all programmatic."""
        config = ContextConfig(recent_turns=2)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        summary = cm.build_old_turn_summary_enhanced([turn], store)
        assert summary.is_llm_enhanced is False
        assert "Turn 1" in summary.text
        assert "tool_0" in summary.text

    def test_metadata_counts(self):
        """OldTurnSummary tracks fact counts correctly."""
        config = ContextConfig(recent_turns=2)
        cm = ContextManager(config=config)
        store = ExecutionStore(config=config)
        assistant = _make_assistant_msg(["call_1"])
        tool_msgs = [_make_tool_msg("call_1", content="result")]
        turn = ExecutionTurn(1, assistant, tool_msgs, [], is_complete=True)
        store.facts_cache[1] = TurnFacts(
            turn_number=1,
            key_findings=["f1", "f2"],
            decisions=["d1"],
        )
        summary = cm.build_old_turn_summary_enhanced([turn], store)
        assert summary.fact_counts["key_findings"] == 2
        assert summary.fact_counts["decisions"] == 1
        assert summary.turns_covered == [1]