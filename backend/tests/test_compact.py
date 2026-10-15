import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db_connection, init_db
from backend.services.compact_service import (
    compact_conversation_messages,
    check_and_auto_compact,
    generate_compact_summary,
)
from backend.services.context_manager import ContextBundle, assemble_messages


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database schema is initialized and up to date."""
    init_db()
    yield


def test_database_schema_has_compact_columns():
    """Verify chat_sessions table contains compact_summary and compact_cutoff_id columns."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(chat_sessions)")
    columns = {row["name"]: row["type"] for row in cursor.fetchall()}
    conn.close()

    assert "compact_summary" in columns, "chat_sessions must have compact_summary column"
    assert "compact_cutoff_id" in columns, "chat_sessions must have compact_cutoff_id column"


def test_generate_compact_summary_mocked():
    """Verify generate_compact_summary calls model and returns structured XML tag."""
    mock_summary_text = (
        "【阿冯】：确认了三人小群设计方案\n"
        "【吻锋】：支持该方案并进行了调侃\n"
        "【小白】：完成了工单记录\n"
        "【三人共识与关键事件】：决定启动 ISSUE-24 开发"
    )
    
    with patch("backend.services.compact_service.call_llm_for_summary", return_value=mock_summary_text):
        messages = [
            {"role": "user", "content": "阿冯: 我们把三人聊天做成淡金置顶吧"},
            {"role": "assistant", "content": "吻锋: 夫君的主意真好~"},
            {"role": "assistant", "content": "小白: 没问题，已记录工单 🍵"},
        ]
        result = generate_compact_summary(messages)
        assert "<compact_summary>" in result
        assert "</compact_summary>" in result
        assert "【阿冯】" in result
        assert "【小白】" in result


def test_compact_conversation_messages_logic():
    """Verify conversation messages are split into summary + recent preserved turns."""
    mock_summary = "【前情提要】：讨论了项目架构与开发计划。"
    
    with patch("backend.services.compact_service.call_llm_for_summary", return_value=mock_summary):
        # Generate 20 test messages
        messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"} for i in range(20)]
        
        compacted, summary_text = compact_conversation_messages(messages, keep_recent_turns=6)
        
        # Must retain 6 recent turns + 1 summary turn at head
        assert len(compacted) == 7
        assert compacted[0]["role"] == "user"
        assert "<compact_summary>" in compacted[0]["content"]
        assert compacted[-1]["content"] == "Message 19"
        assert compacted[-6]["content"] == "Message 14"


def test_assemble_messages_with_compact_summary():
    """Verify assemble_messages properly preserves <compact_summary> at head without breaking system prompt."""
    static_prompt = "你是媚吻锋。"
    bundle = ContextBundle(static_system_prompt=static_prompt, dynamic_tail="")
    
    messages = [
        {"role": "user", "content": "<compact_summary>\n【前期纪要】三人在讨论系统架构。\n</compact_summary>"},
        {"role": "assistant", "content": "*微微一笑* 夫君说得在理。"},
        {"role": "user", "content": "那我们现在开始写代码吧！"}
    ]
    
    assembled = assemble_messages(messages, bundle)
    
    # First message should be system prompt
    assert assembled[0]["role"] == "system"
    assert assembled[0]["content"] == static_prompt
    
    # Second message should be the compact summary
    assert assembled[1]["role"] == "user"
    assert "<compact_summary>" in assembled[1]["content"]
    
    # Last message should be latest user input with dynamic tail
    assert assembled[-1]["role"] == "user"
    assert "那我们现在开始写代码吧！" in assembled[-1]["content"]


def test_check_and_auto_compact_triggers_when_exceeding_threshold():
    """Verify auto-compact triggers when estimated token count exceeds threshold."""
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": "A" * 500} for i in range(20)]
    
    # Total tokens ~ 2500, with threshold 2000 it should trigger
    with patch("backend.services.compact_service.call_llm_for_summary", return_value="【自动浓缩纪要】"):
        needed, compacted_msgs, hint = check_and_auto_compact(
            messages=messages,
            custom_max_tokens=2000,
            threshold_ratio=0.8,
            keep_recent_turns=4
        )
        assert needed is True
        assert hint is not None
        assert len(compacted_msgs) == 5  # 1 summary + 4 recent
        assert "<compact_summary>" in compacted_msgs[0]["content"]


def test_slash_compact_command_via_testclient():
    """Test sending /compact command returns streaming compaction confirmation."""
    client = TestClient(app)
    
    payload = {
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "夫君好~"},
            {"role": "user", "content": "/compact"}
        ],
        "persona_type": "simplified"
    }
    
    with patch("backend.services.compact_service.call_llm_for_summary", return_value="【浓缩前情提要】"):
        response = client.post("/api/chat/send", json=payload)
        assert response.status_code == 200
        content = response.text
        assert "compact" in content.lower() or "浓缩" in content or "记忆" in content
