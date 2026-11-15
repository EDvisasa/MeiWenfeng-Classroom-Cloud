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
        assert "get_memory_calendar" in block
        assert "get_memory_timeline" in block
        assert "search_memory" in block
        assert block.index("get_memory_calendar") < block.index("get_memory_timeline") < block.index("search_memory")
        assert "not disk files" in block
    assert "search_memory" not in bundle.static_system_prompt


def test_all_12_tools_have_orthogonal_category_prefixes_and_no_db_leakage():
    import json
    from backend.services.agent_tools import TOOL_REGISTRY

    expected_categories = {
        "get_memory_calendar": "[Memory]",
        "get_memory_timeline": "[Memory]",
        "search_memory": "[Memory]",
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

    # [Memory] tools must be exposed in funnel order: calendar -> timeline -> search -> expand
    mem_order = [k for k in TOOL_REGISTRY.keys() if expected_categories[k] == "[Memory]"]
    assert mem_order == ["get_memory_calendar", "get_memory_timeline", "search_memory", "expand_memory"]
    assert "ONLY tool category" in TOOL_REGISTRY["get_memory_calendar"].description
    assert "ONLY tool category" not in TOOL_REGISTRY["search_memory"].description

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


def test_memory_search_strips_tool_batch_and_tool_xml_shells():
    from backend.services.agent_tools import TOOL_REGISTRY

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-clean", "标签清理测试", "2026-11-15 22:27:00"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                20,
                "2026-11-15 22:26:51",
                (
                    "【对话记录 (2026-11-15 22:26:50)】\n"
                    "用户：老婆，改了一下了，你再试试工具调用？\n"
                    "媚吻锋：<tool_batch> </tool_batch> <tool_batch> </tool_batch> "
                    "<tool_batch><call_tool name=\"search_memory\">\n<query>abc</query>\n</call_tool></tool_batch> 已查清。"
                ),
                None,
                0,
                "active",
                "sess-clean",
            ),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                21,
                "2026-11-15 22:26:52",
                "<tool_batch> </tool_batch> <tool_batch> </tool_batch>",
                None,
                0,
                "active",
                "sess-clean",
            ),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                201,
                "sess-clean",
                "assistant",
                "*微笑* 查到了。\n<tool_batch>\n<function=get_memory_calendar>\n<parameter=date_range>\n2026-07\n</parameter>\n</function>",
                "2026-11-15 22:27:00",
            ),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                202,
                "sess-clean",
                "assistant",
                '<call_tool name="read_file" /> 真实正文内容',
                "2026-11-15 22:27:10",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    timeline_out = TOOL_REGISTRY["get_memory_timeline"].execute({"date_range": "2026-11-15", "limit": 10})
    assert "老婆，改了一下了" in timeline_out
    assert "已查清" in timeline_out
    assert "*微笑* 查到了。" in timeline_out
    assert "真实正文内容" in timeline_out
    assert "journal #21" not in timeline_out
    for dirty in ("<tool_batch", "</tool_batch", "<call_tool", "<function=", "<parameter="):
        assert dirty not in timeline_out

    expand_journal = TOOL_REGISTRY["expand_memory"].execute({"source_type": "journal", "record_id": 20})
    assert "已查清" in expand_journal
    assert "<tool_batch" not in expand_journal

    expand_conv = TOOL_REGISTRY["expand_memory"].execute({"source_type": "conversation", "record_id": 201})
    assert "*微笑* 查到了。" in expand_conv
    assert "真实正文内容" in expand_conv
    assert "<tool_batch" not in expand_conv
    assert "<function=" not in expand_conv


def test_context_manager_strips_tool_batch_shells_from_history_and_archives(mock_rag_client):
    from backend.services.context_manager import build_base_system_prompt, assemble_messages

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (30, "2026-11-14 10:00:00", "原文", "<tool_batch> </tool_batch> 昨天讨论了上拉电阻。", 1, "active", "sess-hist"),
        )
        conn.commit()
    finally:
        conn.close()

    mock_rag_client.retrieve.return_value = []
    mock_rag_client.retrieve_memory.return_value = [
        "【对话记录 (2026-11-14)】媚吻锋：<tool_batch> </tool_batch> 采用 4.7kΩ。"
    ]

    bundle, _, _ = build_base_system_prompt(last_user_msg="复习")
    archives_block = bundle.dynamic_tail.split("<retrieved_past_memory_archives>")[1].split("</retrieved_past_memory_archives>")[0]
    journals_block = bundle.dynamic_tail.split("<recent_journal_summaries>")[1].split("</recent_journal_summaries>")[0]

    assert "采用 4.7kΩ。" in archives_block
    assert "昨天讨论了上拉电阻。" in journals_block
    assert "<tool_batch" not in archives_block
    assert "<tool_batch" not in journals_block

    history = [
        {"role": "assistant", "content": "*迎上前* 开场白<tool_batch> </tool_batch>"},
        {"role": "user", "content": "查一下记录"},
        {
            "role": "assistant",
            "content": "<tool_batch> </tool_batch>\n<call_tool name=\"search_memory\">\n<query>k</query>\n</call_tool>\n好的，查到了。<monologue>记下</monologue><property_update affection_delta=\"1\" />",
        },
        {"role": "user", "content": "谢谢"},
    ]
    assembled = assemble_messages(history, bundle)
    for msg in assembled:
        if msg["role"] == "assistant":
            assert "<tool_batch" not in msg["content"]
            assert "</tool_batch" not in msg["content"]
            assert "<call_tool" not in msg["content"]

    assert "好的，查到了。" in assembled[3]["content"]
    assert "<monologue>记下</monologue>" in assembled[3]["content"]
    assert '<property_update affection_delta="1"' in assembled[3]["content"]
    assert "<tool_batch>" in history[2]["content"]


def test_rolled_back_memories_excluded_from_search_timeline_calendar_and_expand():
    from backend.services.agent_tools import TOOL_REGISTRY

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-rb", "回滚隔离测试", "2026-11-15 23:39:49"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                70,
                "2026-06-29 22:15:09",
                "【对话记录】醉仙楼历史存档正文（已压缩但仍合法的历史日记）。",
                "醉仙楼六月压缩总结",
                1,
                "compressed",
                "sess-rb",
            ),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                71,
                "2026-11-15 23:39:49",
                "【对话记录】用户：测试工具\n媚吻锋：醉仙楼幻觉测试废话（已撤回回滚，绝不应再被查出）。",
                None,
                0,
                "rolled_back",
                "sess-rb",
            ),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                72,
                "2026-11-16 01:31:12",
                "【对话记录】用户：再试试\n媚吻锋：醉仙楼现存有效日记记录。",
                None,
                0,
                "active",
                "sess-rb",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    search_out = TOOL_REGISTRY["search_memory"].execute({"query": "醉仙楼"})
    assert "journal #70" in search_out
    assert "journal #72" in search_out
    assert "journal #71" not in search_out
    assert "幻觉测试废话" not in search_out

    tl_out = TOOL_REGISTRY["get_memory_timeline"].execute({"date_range": "2026-11-15", "limit": 10})
    assert "journal #71" not in tl_out
    assert "2026-11-16" in tl_out

    cal_out = TOOL_REGISTRY["get_memory_calendar"].execute({"date_range": "2026-11"})
    assert "- [2026-11-15]" not in cal_out
    assert "- [2026-11-16]" in cal_out

    expand_rb = TOOL_REGISTRY["expand_memory"].execute({"source_type": "journal", "record_id": 71})
    assert "幻觉测试废话" not in expand_rb
    assert "No memory record found" in expand_rb

    expand_comp = TOOL_REGISTRY["expand_memory"].execute({"source_type": "journal", "record_id": 70})
    assert "醉仙楼历史存档正文" in expand_comp


def test_search_memory_multi_keyword_ranking_and_partial_fallback():
    from backend.services.agent_tools import TOOL_REGISTRY

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-kw", "多词检索测试", "2026-11-16 01:00:00"),
        )
        conn.executemany(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (80, "2026-06-29 10:00:00", "那天夜里路过醉仙楼喝茶。", None, 0, "compressed", "sess-kw"),
                (81, "2026-06-30 10:00:00", "醉仙楼楼上两人初次相遇试探。", None, 0, "compressed", "sess-kw"),
                (82, "2026-11-10 10:00:00", "后来又提起醉仙楼。", None, 0, "active", "sess-kw"),
                (83, "2026-11-11 10:00:00", "<think>醉仙楼</think><tool_batch><function=search_memory>试探</function></tool_batch>只有普通闲聊。", None, 0, "active", "sess-kw"),
                (84, "2026-11-12 10:00:00", "实测参数 spi_mode_0 与 100% 占空比通过。", "spi_mode_0 与 100% 总结", 1, "active", "sess-kw"),
                (85, "2026-11-12 10:05:00", "干扰项 spiXmodeX0 与 100X 参数。", "spiXmodeX0 与 100X 总结", 1, "active", "sess-kw"),
            ],
        )
        conn.executemany(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            [
                (801, "sess-kw", "assistant", "当年在醉仙楼初次见面时还互相试探呢。", "2026-10-01 12:00:00"),
                (802, "sess-kw", "assistant", "<think>初次见面 第一天 醉仙楼 相遇 试探 猎物</think>只是普通的晚安。", "2026-10-02 12:00:00"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    tool = TOOL_REGISTRY["search_memory"]

    # Space-separated keywords must NOT return empty when matching records exist,
    # and must rank higher-overlap matches (3 hits -> 2 hits -> 1 hit) ahead of newer 1-hit records.
    multi_out = tool.execute({"query": "初次见面 第一天 醉仙楼 相遇 试探 猎物", "limit": 5})
    assert "No memory records found" not in multi_out
    assert "conversation #801" in multi_out
    assert "journal #81" in multi_out
    assert "journal #82" in multi_out
    assert "conversation #802" not in multi_out
    assert "journal #83" not in multi_out

    pos_801 = multi_out.find("conversation #801")
    pos_81 = multi_out.find("journal #81")
    pos_82 = multi_out.find("journal #82")
    assert pos_801 < pos_81 < pos_82

    # Literal LIKE wildcards ('_', '%') still strictly respected across multiple terms
    esc_multi = tool.execute({"query": "spi_mode_0 100%"})
    assert "journal #84" in esc_multi
    assert "journal #85" not in esc_multi


def test_empty_notice_hints_peer_target_and_tool_engine_formats_non_default_target():
    from backend.services.agent_tools import TOOL_REGISTRY
    from backend.services.tool_engine import ToolExecutionEngine

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-split", "跨库时间线提示测试", "2026-08-18 12:00:00"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (90, "2026-06-28 15:00:00", "六月底初谈醉仙楼设定。", "六月底醉仙楼笔记", 0, "compressed", "sess-split"),
        )
        conn.execute(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (91, "2026-07-05 10:00:00", "七月初日常记录。", "七月初日常", 0, "compressed", "sess-split"),
        )
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (901, "sess-split", "user", "八月十八正式开启的会话。", "2026-08-18 12:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    tl_tool = TOOL_REGISTRY["get_memory_timeline"]
    search_tool = TOOL_REGISTRY["search_memory"]

    # 1. Timeline scoped to target='conversations' on 2026-06-01..2026-07-15 must still reveal peer journals
    conv_only_tl = tl_tool.execute({
        "start_date": "2026-06-01",
        "end_date": "2026-07-15",
        "target": "conversations",
    })
    assert "target='conversations'" in conv_only_tl
    assert "2026-08 (1)" in conv_only_tl
    assert "journals" in conv_only_tl
    assert "2 matching journals" in conv_only_tl
    assert "target='all'" in conv_only_tl

    # 2. Keyword search scoped to target='conversations' without dates hints when journals match
    conv_only_search = search_tool.execute({"query": "醉仙楼", "target": "conversations"})
    assert "target='conversations'" in conv_only_search
    assert "1 matching journals" in conv_only_search
    assert "target='all'" in conv_only_search

    # 3. Default target='all' unmatched query keeps exact canonical empty notice
    assert search_tool.execute({"query": "完全不存在_no_peer_match"}) == "[No memory records found matching the given criteria.]"

    # 4. ToolExecutionEngine shows non-default target in UI command string while preserving default output
    engine = ToolExecutionEngine()
    assert engine._format_command_str("get_memory_timeline", {"start_date": "2026-06-01", "end_date": "2026-07-15"}) == "Remembering timeline: 2026-06-01..2026-07-15"
    assert engine._format_command_str(
        "get_memory_timeline",
        {"start_date": "2026-06-01", "end_date": "2026-07-15", "target": "conversations"},
    ) == "Remembering timeline (conversations): 2026-06-01..2026-07-15"
    assert engine._format_command_str("search_memory", {"query": "醉仙楼", "target": "journals"}) == "Remembering (journals): '醉仙楼'"
    assert engine._format_command_str("search_memory", {"query": "醉仙楼", "target": "all"}) == "Remembering: '醉仙楼'"


def test_date_range_supports_year_and_all_plus_calendar_schema_docs():
    from backend.services.agent_tools import TOOL_REGISTRY

    cal_tool = TOOL_REGISTRY["get_memory_calendar"]
    tl_tool = TOOL_REGISTRY["get_memory_timeline"]
    search_tool = TOOL_REGISTRY["search_memory"]

    cal_props = cal_tool.parameters_schema.get("properties", {})
    tl_props = tl_tool.parameters_schema.get("properties", {})
    cal_desc_lower = cal_tool.description.lower()

    assert "'yyyy'" in cal_props["date_range"]["description"].lower()
    assert "'all'" in cal_props["date_range"]["description"].lower()
    assert "yyyy" in cal_desc_lower or "year" in cal_desc_lower
    assert "target" in cal_props
    assert cal_props["target"]["enum"] == ["all", "journals", "conversations"]
    assert "order" in cal_props
    assert cal_props["order"]["enum"] == ["newest", "oldest"]
    assert "order" in tl_props
    assert tl_props["order"]["enum"] == ["newest", "oldest"]

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-yr", "跨年历史测试", "2026-10-15 10:00:00"),
        )
        conn.executemany(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "2025-12-20 09:00:00", "2025年旧笔记关键词标记", "2025冬日旧账", 1, "active", "sess-yr"),
                (2, "2026-06-24 08:30:00", "2026年6月启动关键词标记", "2026夏至起点", 1, "active", "sess-yr"),
                (3, "2026-10-15 18:00:00", "2026年10月复盘关键词标记", "2026秋日复盘", 1, "active", "sess-yr"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    year_cal = cal_tool.execute({"date_range": "2026"})
    assert "2026-06-24" in year_cal
    assert "2026-10-15" in year_cal
    assert "2025-12-20" not in year_cal

    all_cal = cal_tool.execute({"date_range": "all"})
    omitted_cal = cal_tool.execute({})
    for out in (all_cal, omitted_cal):
        assert "2025-12-20" in out
        assert "2026-06-24" in out
        assert "2026-10-15" in out

    year_tl = tl_tool.execute({"date_range": "2025"})
    assert "journal #1" in year_tl
    assert "journal #2" not in year_tl

    year_search = search_tool.execute({"query": "关键词标记", "date_range": "2026"})
    assert "journal #2" in year_search
    assert "journal #3" in year_search
    assert "journal #1" not in year_search

    empty_year = cal_tool.execute({"date_range": "2024"})
    assert "Active years" in empty_year
    assert "2025" in empty_year
    assert "2026" in empty_year


def test_calendar_target_order_and_truncation_earliest_anchor():
    from backend.services.agent_tools import TOOL_REGISTRY

    cal_tool = TOOL_REGISTRY["get_memory_calendar"]
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-aug", "八月初回会话", "2026-08-18 20:00:00"),
        )
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-nov", "十一月测试会话", "2026-11-15 12:00:00"),
        )
        # 20 daily journals from 2026-06-24..2026-07-13 so total active days (22) exceed default limit (15)
        journal_rows = [
            (
                100 + day_offset,
                f"2026-06-{24 + day_offset:02d} 10:00:00" if day_offset < 7 else f"2026-07-{day_offset - 6:02d} 10:00:00",
                f"连续日记第 {day_offset} 天",
                f"日记摘要 #{day_offset}",
                0,
                "compressed",
                None,
            )
            for day_offset in range(20)
        ]
        conn.executemany(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            journal_rows,
        )
        conn.executemany(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            [
                (501, "sess-aug", "user", "八月十八第一句", "2026-08-18 20:00:00"),
                (502, "sess-aug", "assistant", "八月十八回复", "2026-08-18 20:01:00"),
                (503, "sess-nov", "user", "十一月提问", "2026-11-15 12:00:00"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    # Default calendar shows latest 15 days, clipping June, and surfaces earliest_active_day + total_active_days + oldest hint
    default_cal = cal_tool.execute({})
    assert "earliest_active_day: 2026-06-24" in default_cal
    assert "total_active_days: 22 (showing latest 15)" in default_cal
    assert "- [2026-06-24]" not in default_cal
    assert "- [2026-08-18]" in default_cal
    assert "- [2026-11-15]" in default_cal
    assert 'order="oldest"' in default_cal

    # Filtered range starting 2026-07-01 still reports DB earliest_active_day 2026-06-24 when truncated or narrowed
    filtered_cal = cal_tool.execute({"start_date": "2026-06-28", "end_date": "2026-11-16", "limit": 5})
    assert "earliest_active_day: 2026-06-24" in filtered_cal
    assert "showing latest 5" in filtered_cal

    # order='oldest' starts directly from 2026-06-24
    oldest_cal = cal_tool.execute({"order": "oldest", "limit": 5})
    assert "earliest_active_day: 2026-06-24" in oldest_cal
    assert "total_active_days: 22 (showing oldest 5)" in oldest_cal
    assert "- [2026-06-24]" in oldest_cal
    assert "- [2026-06-28]" in oldest_cal
    assert "- [2026-08-18]" not in oldest_cal
    assert "- [2026-11-15]" not in oldest_cal

    # target='conversations' isolates chat sessions so June/July journals do not crowd them out
    conv_cal = cal_tool.execute({"target": "conversations"})
    assert "- [2026-08-18]" in conv_cal
    assert "- [2026-11-15]" in conv_cal
    assert "2026-06-" not in conv_cal
    assert "active_days: 2" in conv_cal

    # Empty June query scoped to conversations gives peer hint about June journals
    june_conv = cal_tool.execute({"date_range": "2026-06", "target": "conversations"})
    assert "target='conversations'" in june_conv
    assert "matching journals" in june_conv
    assert "2026-08" in june_conv

    assert cal_tool.execute({"order": "random"}).startswith("[Error]")
    assert cal_tool.execute({"target": "invalid"}).startswith("[Error]")


def test_timeline_order_oldest_anchor_and_ui_formatting():
    from backend.services.agent_tools import TOOL_REGISTRY
    from backend.services.tool_engine import ToolExecutionEngine

    tl_tool = TOOL_REGISTRY["get_memory_timeline"]
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, updated_at) VALUES (?, ?, ?)",
            ("sess-first", "初始对话", "2026-08-18 20:00:00"),
        )
        conn.executemany(
            "INSERT INTO memory_logs (id, timestamp, content, summary, level, status, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (10, "2026-06-24 09:00:00", "最早日记内容", "六月廿四日记", 0, "active", None),
                (11, "2026-10-16 14:00:00", "十月日记内容", "十月十六日记", 0, "active", None),
            ],
        )
        conn.executemany(
            "INSERT INTO chat_messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            [
                (201, "sess-first", "user", "八月十八最早一句", "2026-08-18 20:00:00"),
                (202, "sess-first", "assistant", "八月十八第一句答复", "2026-08-18 20:01:00"),
                (203, "sess-first", "user", "十一月十五最新消息", "2026-11-15 22:00:00"),
                (204, "sess-first", "assistant", "十一月十五最新答复", "2026-11-15 22:01:00"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    newest_out = tl_tool.execute({"limit": 2})
    assert "conversation #204" in newest_out
    assert "conversation #203" in newest_out
    assert "journal #10" not in newest_out
    assert "earliest_active_day: 2026-06-24" in newest_out
    assert 'order="oldest"' in newest_out or "order='oldest'" in newest_out

    # Unified chronological oldest across BOTH journals and conversations
    oldest_all = tl_tool.execute({"order": "oldest", "limit": 2})
    lines_all = [ln for ln in oldest_all.splitlines() if ln.startswith("- [")]
    assert len(lines_all) == 2
    assert "journal #10" in lines_all[0]
    assert "conversation #201" in lines_all[1]

    oldest_conv = tl_tool.execute({"target": "conversations", "order": "oldest", "limit": 2})
    lines_conv = [ln for ln in oldest_conv.splitlines() if ln.startswith("- [")]
    assert "conversation #201" in lines_conv[0]
    assert "conversation #202" in lines_conv[1]

    assert tl_tool.execute({"order": "bogus"}).startswith("[Error]")

    engine = ToolExecutionEngine()
    assert engine._format_command_str("get_memory_calendar", {}) == "Remembering calendar: all"
    assert engine._format_command_str("get_memory_calendar", {"date_range": "2026"}) == "Remembering calendar: 2026"
    assert engine._format_command_str(
        "get_memory_calendar",
        {"target": "conversations", "order": "oldest"},
    ) == "Remembering calendar (conversations, oldest): all"
    assert engine._format_command_str(
        "get_memory_timeline",
        {"date_range": "2026-08", "order": "oldest"},
    ) == "Remembering timeline (oldest): 2026-08"
    assert engine._format_command_str("get_memory_calendar", {"date_range": "2026-10"}) == "Remembering calendar: 2026-10"





