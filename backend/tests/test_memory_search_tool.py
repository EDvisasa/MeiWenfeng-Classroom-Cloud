import pytest
from backend.database import get_db_connection


def _seed_memory_data():
    """Insert deterministic journal and conversation records into the isolated test SQLite DB."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-1", "I2C 调试记录", "2026-10-15 20:10:00"),
        )
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-2", "SPI 时序对比", "2026-11-12 09:00:00"),
        )

        # Memory logs: active, summarized, archived
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                10,
                "2026-10-15 20:05:00",
                "完整记录：开漏输出模式下 I2C 总线上拉电阻计算公式与测试结论，标准 100kHz 模式确定采用 4.7k 欧姆上拉电阻。",
                "I2C 标准模式上拉电阻选型确定为 4.7kΩ。",
                1,
                "active",
                "sess-1",
            ),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                11,
                "2026-10-01 10:00:00",
                "旧日记：4.7k 早期草稿记录（已归档，不应再被召回）。",
                "已归档草稿 4.7k。",
                0,
                "archived",
                "sess-1",
            ),
        )

        # Chat messages across two sessions, including internal XML tags that must be stripped
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (101, "sess-1", "user", "板子 I2C 总是超时，是不是电阻选大了？", "2026-10-15 20:01:00"),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                102,
                "sess-1",
                "assistant",
                "<think>internal secret reasoning about resistor calculation</think>\n*我俯身看了看波形图。* “检查一下上拉电阻，之前约定标准模式焊 4.7k。”<monologue>幸好留了记录</monologue><property_update affection_delta=\"0\" />",
                "2026-10-15 20:02:00",
            ),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (103, "sess-2", "user", "今天开始看 SPI 时钟极性。", "2026-11-12 09:00:00"),
        )
        conn.commit()
    finally:
        conn.close()


def test_search_memory_tool_registration_and_keyword_preview():
    from backend.services.agent_tools import TOOL_REGISTRY

    _seed_memory_data()

    for tool_name in ("search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory"):
        assert tool_name in TOOL_REGISTRY
        assert TOOL_REGISTRY[tool_name].is_safe is True

    search_tool = TOOL_REGISTRY["search_memory"]
    search_schema = search_tool.parameters_schema
    search_props = search_schema.get("properties", {})
    assert "mode" not in search_props
    assert "record_id" not in search_props
    assert search_schema.get("required") == ["query"]
    for key in ("query", "target", "date_range", "start_date", "end_date", "limit"):
        assert key in search_props

    output = search_tool.execute({"query": "4.7k"})

    # Matches active journal (#10) and chat message (#102), excludes archived (#11)
    assert "journal #10" in output
    assert "conversation #102" in output
    assert "journal #11" not in output

    # Strips internal control tags from conversation preview
    assert "internal secret reasoning" not in output
    assert "<think>" not in output
    assert "<monologue>" not in output
    assert "<property_update" not in output


def test_timeline_date_filters_target_and_limit_ceiling():
    from datetime import datetime, timedelta
    from backend.services.agent_tools import TOOL_REGISTRY

    tool = TOOL_REGISTRY["get_memory_timeline"]
    tl_props = tool.parameters_schema.get("properties", {})
    assert "mode" not in tl_props
    assert "query" not in tl_props
    assert "record_id" not in tl_props
    for key in ("date_range", "start_date", "end_date", "target", "limit"):
        assert key in tl_props

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-tl", "时间线验证", "2026-10-15 20:00:00"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (20, "2026-09-28 12:00:00", "九月旧事", "九月总结", 1, "active", "sess-tl"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (21, "2026-10-05 14:00:00", "十月初回顾", "十月初记录", 1, "active", "sess-tl"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (22, "2026-10-14 20:05:00", "十月十四重点", "十月十四日记", 1, "active", "sess-tl"),
        )
        recent_ts = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (201, "sess-tl", "user", "最近两天讨论的 PWM 占空比公式", recent_ts),
        )
        for i in range(20):
            conn.execute(
                "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (100 + i, "2026-10-15 21:00:00", f"批量条数验证条目 #{i}", f"十月十五批量摘要 #{i}", 1, "active", "sess-tl"),
            )
        conn.commit()
    finally:
        conn.close()

    # timeline by month requires no query
    oct_out = tool.execute({"date_range": "2026-10", "target": "journals", "limit": 100})
    assert "十月十五" in oct_out
    assert "九月总结" not in oct_out
    assert "conversation #" not in oct_out
    # Hard limit ceiling = 15 bullets
    bullet_lines = [ln for ln in oct_out.splitlines() if ln.startswith("- [")]
    assert len(bullet_lines) == 15

    # exact date filter excludes 2026-10-05 and 2026-10-15
    exact_out = tool.execute({"date_range": "2026-10-14", "target": "journals", "limit": 50})
    assert "十月初记录" not in exact_out
    assert "十月十五" not in exact_out
    assert "journal #22" in exact_out

    # recent_7d captures recent conversation even with ISO 'T' timestamp
    recent_out = tool.execute({"date_range": "recent_7d", "target": "conversations"})
    assert "conversation #201" in recent_out
    assert "journal #" not in recent_out


def test_expand_full_journal_and_bounded_session_conversation():
    from backend.services.agent_tools import TOOL_REGISTRY

    tool = TOOL_REGISTRY["expand_memory"]
    expand_schema = tool.parameters_schema
    expand_props = expand_schema.get("properties", {})
    assert "mode" not in expand_props
    assert "query" not in expand_props
    assert set(expand_schema.get("required", [])) == {"source_type", "record_id"}
    for key in ("source_type", "record_id", "context_turns"):
        assert key in expand_props

    long_body = "【长篇完整复盘】" + ("A" * 240) + "，关键结论是 SPI Mode 0 在上升沿采样。"
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-a", "会话 A", "2026-11-10 10:00:00"),
        )
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-b", "会话 B", "2026-11-10 10:05:00"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (30, "2026-11-10 10:10:00", long_body, "SPI Mode 0 简要总结", 1, "active", "sess-a"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (31, "2026-11-01 09:00:00", "已归档秘密内容", "已归档摘要", 0, "archived", "sess-a"),
        )
        # Contiguous IDs across sess-a (301..304) and sess-b (305..306)
        msgs = [
            (301, "sess-a", "user", "最开始聊的寒暄话题", "2026-11-10 10:00:00"),
            (302, "sess-a", "assistant", "<think>secret</think>上一句提示：准备看时序图。", "2026-11-10 10:01:00"),
            (303, "sess-a", "user", "核心问题：CPOL=0 CPHA=0 是什么含义？", "2026-11-10 10:02:00"),
            (304, "sess-a", "assistant", "代表空闲低电平、第一个边沿采样。<monologue>记下了</monologue><property_update affection_delta=\"1\" />", "2026-11-10 10:03:00"),
            (305, "sess-b", "user", "跨会话绝不能泄漏的消息 305", "2026-11-10 10:05:00"),
            (306, "sess-b", "assistant", "跨会话绝不能泄漏的消息 306", "2026-11-10 10:06:00"),
        ]
        conn.executemany(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            msgs,
        )
        conn.commit()
    finally:
        conn.close()

    # Expand active journal yields full untruncated content
    journal_full = tool.execute({"source_type": "journal", "record_id": 30})
    assert "SPI Mode 0 简要总结" in journal_full
    assert "关键结论是 SPI Mode 0 在上升沿采样。" in journal_full

    # Archived journal cannot be expanded
    archived_out = tool.execute({"source_type": "journal", "record_id": 31})
    assert "已归档秘密内容" not in archived_out
    assert "No memory record found" in archived_out

    # Expand conversation strictly stays inside sess-a and strips control tags
    conv_out = tool.execute({
        "source_type": "conversation",
        "record_id": 303,
        "context_turns": 1,
    })
    assert "conversation #302" in conv_out
    assert "conversation #303" in conv_out
    assert "conversation #304" in conv_out
    assert "conversation #301" not in conv_out
    assert "跨会话绝不能泄漏的消息" not in conv_out
    assert "<think>" not in conv_out
    assert "<monologue>" not in conv_out
    assert "<property_update" not in conv_out

    # Even with huge context_turns=50, still stays within sess-a without bleeding into sess-b
    bounded_out = tool.execute({
        "source_type": "conversation",
        "record_id": 304,
        "context_turns": 50,
    })
    assert "conversation #301" in bounded_out
    assert "跨会话绝不能泄漏的消息" not in bounded_out


def test_empty_results_like_wildcard_escaping_and_objective_notices():
    from backend.services.agent_tools import TOOL_REGISTRY

    tool = TOOL_REGISTRY["search_memory"]
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status) VALUES (?, ?, ?, ?, ?, ?)",
            (40, "2026-11-11 11:00:00", "普通记录 spiXmodeX0 无下划线", "spiXmodeX0 日志", 1, "active"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status) VALUES (?, ?, ?, ?, ?, ?)",
            (41, "2026-11-11 11:05:00", "占空比拉满 100% 且使用 spi_mode_0 配置", "100% 占空比与 spi_mode_0", 1, "active"),
        )
        conn.commit()
    finally:
        conn.close()

    # Literal '_' / '%' must not act as SQL LIKE wildcard matching row #40
    esc_out = tool.execute({"query": "spi_mode_0"})
    assert "journal #41" in esc_out
    assert "journal #40" not in esc_out

    pct_out = tool.execute({"query": "100%"})
    assert "journal #41" in pct_out
    assert "journal #40" not in pct_out

    # Empty / unmatched results return purely objective notices
    no_hit = tool.execute({"query": "完全不存在的关键词_xyz"})
    assert no_hit == "[No memory records found matching the given criteria.]"

    missing_query = tool.execute({"query": "   "})
    assert missing_query.startswith("[Error]")


def test_progressive_date_fallback_and_start_end_range():
    from backend.services.agent_tools import TOOL_REGISTRY

    _seed_memory_data()
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (50, "2026-09-18 15:00:00", "九月十八 DMA 实验", "DMA 实验记录", 1, "active", "sess-1"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (51, "2026-10-05 09:30:00", "十月五日 ADC 校准", "ADC 校准总结", 1, "active", "sess-1"),
        )
        conn.commit()
    finally:
        conn.close()

    timeline_tool = TOOL_REGISTRY["get_memory_timeline"]
    search_tool = TOOL_REGISTRY["search_memory"]

    # 1. Closed range [start_date, end_date] filters inclusively on both timeline & search
    range_out = timeline_tool.execute({"start_date": "2026-10-05", "end_date": "2026-10-15"})
    assert "journal #51" in range_out
    assert "journal #10" in range_out
    assert "journal #50" not in range_out
    assert "conversation #103" not in range_out

    range_search = search_tool.execute({"query": "ADC", "start_date": "2026-10-01", "end_date": "2026-10-10"})
    assert "journal #51" in range_search

    bad_range = timeline_tool.execute({"start_date": "2026-10-20", "end_date": "2026-10-01"})
    assert bad_range.startswith("[Error]")

    # 2. Exact empty day inside active month -> lists active dates & counts in 2026-10
    empty_day_out = timeline_tool.execute({"date_range": "2026-10-10"})
    assert "2026-10-05" in empty_day_out
    assert "2026-10-15" in empty_day_out
    assert "Active dates in 2026-10" in empty_day_out
    # Archived #11 (2026-10-01) must NOT appear as an active date
    assert "2026-10-01" not in empty_day_out

    # 3. Empty day in an empty month (2026-08) -> falls back to active months in 2026
    empty_day_empty_month = timeline_tool.execute({"date_range": "2026-08-10"})
    assert "Active months in 2026" in empty_day_empty_month
    assert "2026-09" in empty_day_empty_month
    assert "2026-10" in empty_day_empty_month
    assert "2026-11" in empty_day_empty_month

    # 4. Empty month query (2026-07) -> lists active months in 2026
    empty_month_out = timeline_tool.execute({"date_range": "2026-07"})
    assert "Active months in 2026" in empty_month_out
    assert "2026-10" in empty_month_out

    # 5. Empty year query (2025-03) -> falls back to active years in DB (2026)
    empty_year_out = timeline_tool.execute({"date_range": "2025-03"})
    assert "Active years" in empty_year_out
    assert "2026" in empty_year_out


def test_memory_calendar_range_and_session_summary():
    from backend.services.agent_tools import TOOL_REGISTRY

    _seed_memory_data()
    conn = get_db_connection()
    try:
        # Second distinct conversation session on 2026-10-15 + another day 2026-10-05 journal
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-3", "电源纹波排查", "2026-10-15 22:00:00"),
        )
        conn.executemany(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            [
                (501, "sess-3", "user", "LDO 输出纹波有点大", "2026-10-15 21:50:00"),
                (502, "sess-3", "assistant", "加个 10uF 陶瓷电容试试。", "2026-10-15 21:51:00"),
            ],
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (55, "2026-10-05 18:00:00", "十月五日复习记录", "十月五日复习", 1, "active", "sess-1"),
        )
        conn.commit()
    finally:
        conn.close()

    cal_tool = TOOL_REGISTRY["get_memory_calendar"]
    cal_props = cal_tool.parameters_schema.get("properties", {})
    assert "mode" not in cal_props
    for key in ("start_date", "end_date", "date_range", "limit"):
        assert key in cal_props

    cal_out = cal_tool.execute({"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert "2026-10-05" in cal_out
    assert "2026-10-15" in cal_out
    assert "2 sessions" in cal_out
    assert "4 msgs" in cal_out
    assert "1 journal" in cal_out
    assert "I2C 调试记录" in cal_out
    assert "电源纹波排查" in cal_out
    # Archived 2026-10-01 and out-of-range 2026-11-12 must not appear as active day rows
    assert "- [2026-10-01]" not in cal_out
    assert "- [2026-11-12]" not in cal_out

    # Empty month in calendar falls back cleanly to active months in 2026
    empty_cal = cal_tool.execute({"date_range": "2026-08"})
    assert "Active months in 2026" in empty_cal
    assert "2026-10" in empty_cal


def test_stream_parser_and_tool_engine_compatibility():
    from backend.services.stream_parser import StreamParser
    from backend.services.tool_engine import ToolExecutionEngine

    engine = ToolExecutionEngine()
    assert engine._format_command_str("search_memory", {"query": "PWM"}) == "Remembering: 'PWM'"
    assert engine._format_command_str("get_memory_timeline", {"date_range": "2026-10"}) == "Remembering timeline: 2026-10"
    assert engine._format_command_str("get_memory_timeline", {"start_date": "2026-10-01", "end_date": "2026-10-15"}) == "Remembering timeline: 2026-10-01..2026-10-15"
    assert engine._format_command_str("get_memory_calendar", {"start_date": "2026-10-01", "end_date": "2026-10-31"}) == "Remembering calendar: 2026-10-01..2026-10-31"
    assert engine._format_command_str("get_memory_calendar", {"date_range": "2026-10"}) == "Remembering calendar: 2026-10"
    assert engine._format_command_str("expand_memory", {"source_type": "journal", "record_id": 12}) == "Remembering detail: journal#12"

    # Fallback direct XML sanitization in StreamParser for all 4 atomic memory tools
    for tool_name in ("search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory"):
        assert tool_name in StreamParser.KNOWN_TOOL_NAMES

    parser = StreamParser()
    parser.process_chunk({"type": "text", "text": 'Let me check.\n<get_memory_calendar>{"date_range": "2026-10"}</get_memory_calendar>'})
    assert parser.has_tool_calls() is True
    assert parser.get_clean_content() == "Let me check."
    parsed = parser.get_parsed_tool_calls()
    assert parsed[0]["name"] == "get_memory_calendar"
    assert parsed[0]["param"] == {"date_range": "2026-10"}


def test_agent_executor_two_hop_and_memory_search_budget_limit():
    import json
    from unittest.mock import patch
    from backend.services.agent_executor import AgentExecutor
    from backend.services.agent_tools import TOOL_REGISTRY

    _seed_memory_data()

    class MockLLM:
        def __init__(self, responses):
            self.responses = responses
            self.iteration_count = 0
            self.received_messages = []

        def stream_completion(self, messages, **kwargs):
            self.received_messages.append([dict(m) for m in messages])
            chunks = self.responses[self.iteration_count]
            self.iteration_count += 1
            for c in chunks:
                yield c

    # Scenario A: 2-hop search_memory -> expand_memory -> final reply
    two_hop_llm = MockLLM([
        [{"type": "tool_calls_chunk", "tool_calls": [
            {"index": 0, "id": "c1", "type": "function", "function": {"name": "search_memory", "arguments": '{"query": "4.7k"}'}}
        ]}],
        [{"type": "tool_calls_chunk", "tool_calls": [
            {"index": 0, "id": "c2", "type": "function", "function": {"name": "expand_memory", "arguments": '{"source_type": "journal", "record_id": 10}'}}
        ]}],
        [{"type": "text", "text": "查到了，当时约定标准模式用 4.7kΩ 上拉电阻。"}],
    ])
    executor = AgentExecutor(llm_client=two_hop_llm, max_iterations=5)
    events = list(executor.run([{"role": "user", "content": "以前 I2C 上拉电阻定多少来着？"}]))
    tool_starts = [e for e in events if e.get("type") == "tool_start"]
    assert len(tool_starts) == 2
    assert tool_starts[0]["tool_name"] == "search_memory"
    assert tool_starts[0]["command"] == "Remembering: '4.7k'"
    assert tool_starts[1]["tool_name"] == "expand_memory"
    assert tool_starts[1]["command"] == "Remembering detail: journal#10"
    assert "完整记录：开漏输出模式下" in two_hop_llm.received_messages[-1][-1]["content"]
    assert any(e.get("type") == "text" and "4.7kΩ" in e.get("text", "") for e in events)

    # Scenario B (ISSUE-66): 6 consecutive memory calls execute without 3/3 ceiling or max_iterations=5 truncation
    tool = TOOL_REGISTRY["search_memory"]
    call_counter = {"count": 0}
    orig_execute = tool.execute

    def counted_execute(params):
        call_counter["count"] += 1
        return orig_execute(params)

    def _tc_chunk(idx_id, payload):
        return [{"type": "tool_calls_chunk", "tool_calls": [
            {"index": 0, "id": idx_id, "type": "function", "function": {"name": "search_memory", "arguments": json.dumps(payload)}}
        ]}]

    unbounded_turns = [
        _tc_chunk(f"b{i}", {"query": f"k{i}"}) for i in range(1, 7)
    ] + [[{"type": "text", "text": "查了六轮，确实没有更多记录了。"}]]

    budget_llm = MockLLM(unbounded_turns)
    with patch.object(tool, "execute", side_effect=counted_execute):
        unbounded_executor = AgentExecutor(llm_client=budget_llm)
        budget_events = list(unbounded_executor.run([{"role": "user", "content": "仔细翻翻看有没有遗漏"}]))

    assert call_counter["count"] == 6
    tool_outputs = [e.get("text", "") for e in budget_events if e.get("type") == "tool_output"]
    assert len(tool_outputs) == 6
    assert not any("Memory search limit reached" in out for out in tool_outputs)
    assert any(e.get("type") == "text" and "查了六轮" in e.get("text", "") for e in budget_events)


def test_model_router_stream_chat_not_capped_at_five_iterations(mock_rag_client):
    import json
    from unittest.mock import patch
    from backend.services.model_router import stream_chat

    class MultiStepMockLLM:
        def __init__(self):
            self.turn = 0

        def stream_completion(self, messages, **kwargs):
            self.turn += 1
            if self.turn <= 6:
                yield {"type": "tool_calls_chunk", "tool_calls": [
                    {
                        "index": 0,
                        "id": f"mr_{self.turn}",
                        "type": "function",
                        "function": {"name": "search_memory", "arguments": json.dumps({"query": "4.7k"})},
                    }
                ]}
            else:
                yield {"type": "text", "text": "六轮探索后完成总结。"}

    _seed_memory_data()
    with patch("backend.services.model_router.OpenAILLMClient", return_value=MultiStepMockLLM()):
        events = list(stream_chat([{"role": "user", "content": "帮我深挖以前的记录"}], "你是导师"))

    tool_starts = [e for e in events if isinstance(e, dict) and e.get("type") == "tool_start"]
    assert len(tool_starts) == 6
    assert any(isinstance(e, dict) and e.get("type") == "text" and "六轮探索后完成总结" in e.get("text", "") for e in events)


def test_context_manager_protocol_includes_search_memory_without_polluting_static_prompt():
    from backend.services.context_manager import get_cross_reference_protocol
    from backend.services.prompts import get_static_system_prompt

    static_prompt = get_static_system_prompt()
    for leaked in ("search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory", "TOOL ROUTING"):
        assert leaked not in static_prompt

    protocol = get_cross_reference_protocol()
    assert "TOOL ROUTING" in protocol
    for cat in ("[Memory]", "[Workspace]", "[Web]", "[Collab]"):
        assert cat in protocol
    for mem_tool in ("search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory"):
        assert mem_tool in protocol
    assert "grep_search" in protocol
    assert "2-3" not in protocol
    assert "at most" not in protocol.lower()
    assert "chat_messages" not in protocol
    assert "memory_logs" not in protocol
    assert "First check `<openclaw_gateway_status>`" not in protocol

    env_block = protocol.split("<environment_constraints>")[1].split("</environment_constraints>")[0]
    assert len(env_block) < 1150

    # Strictly objective engineering protocol: zero persona stage directions
    for banned in ("撒娇", "娇嗔", "掩饰", "coquettish"):
        assert banned not in protocol


def test_subconscious_memory_notices_point_in_situ_to_memory_tools(mock_rag_client):
    from backend.services.context_manager import build_base_system_prompt

    _seed_memory_data()
    mock_rag_client.retrieve.return_value = []
    mock_rag_client.retrieve_memory.return_value = ["【对话记录 (2026-10-15)】之前约定采用 4.7kΩ。"]

    bundle, _, _ = build_base_system_prompt(last_user_msg="以前 I2C 电阻定多少？")
    tail = bundle.dynamic_tail

    archives_block = tail.split("<retrieved_past_memory_archives>")[1].split("</retrieved_past_memory_archives>")[0]
    journals_block = tail.split("<recent_journal_summaries>")[1].split("</recent_journal_summaries>")[0]

    for block in (archives_block, journals_block):
        assert "[Memory]" in block
        assert "search_memory" in block
        assert "not disk files" in block
    assert "search_memory" not in bundle.static_system_prompt


def test_all_12_tools_have_orthogonal_category_prefixes_and_no_db_leakage():
    import json
    from backend.services.agent_tools import TOOL_REGISTRY

    expected_categories = {
        "search_memory": "[Memory]",
        "get_memory_timeline": "[Memory]",
        "get_memory_calendar": "[Memory]",
        "expand_memory": "[Memory]",
        "read_file": "[Workspace]",
        "grep_search": "[Workspace]",
        "replace_file_content": "[Workspace]",
        "create_file": "[Workspace]",
        "execute_bash": "[Workspace]",
        "web_search": "[Web]",
        "read_url_content": "[Web]",
        "call_openclaw_agent": "[Collab]",
    }
    assert set(TOOL_REGISTRY.keys()) == set(expected_categories.keys())

    for name, prefix in expected_categories.items():
        tool = TOOL_REGISTRY[name]
        assert tool.description.startswith(prefix), f"{name} description must start with {prefix}"

    # No SQLite table names tempting small models toward bash/file probing
    for mem_name in ("search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory"):
        tool = TOOL_REGISTRY[mem_name]
        serialized = json.dumps({"desc": tool.description, "params": tool.parameters_schema}, ensure_ascii=False)
        assert "chat_messages" not in serialized
        assert "memory_logs" not in serialized

    # Workspace tools explicitly forbid chat/diary recall
    for ws_name in ("read_file", "grep_search", "execute_bash"):
        assert "NEVER for past chats/diaries" in TOOL_REGISTRY[ws_name].description






