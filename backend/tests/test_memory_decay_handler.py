import pytest
import sqlite3
from typing import Dict, Any
from backend.database import get_db_connection
from backend.services.action_registry import ActionRegistry
from backend.services.memory_decay import MemoryDecayHandler

from unittest.mock import patch

@pytest.fixture
def test_db(mock_db_path):
    conn = get_db_connection()
    yield conn
    conn.close()

def test_memory_decay_handler_registers_successfully():
    """Test that MemoryDecayHandler can be registered with ActionRegistry"""
    registry = ActionRegistry()
    handler = MemoryDecayHandler()
    registry.register("memory_decay", handler)

    retrieved_handler = registry.get_handler("memory_decay")
    assert retrieved_handler is handler
    assert isinstance(retrieved_handler, MemoryDecayHandler)

def test_memory_decay_handler_handles_phase_a(test_db):
    """Test that MemoryDecayHandler processes phase A when triggered"""
    # Setup initial data
    cursor = test_db.cursor()
    for i in range(10):
        cursor.execute(
            "INSERT INTO memory_logs (content, level, status, timestamp) VALUES (?, 0, 'active', datetime('now', '-1 minute'))",
            (f"Test message {i}",)
        )
    test_db.commit()

    # Execute handler with mocked LLM summary generation and RAG sync
    fake_summary = "【时间跨度】：12:00 ~ 12:01\n【面向对象】：测试\n【详细纪要】：这是一个自动化测试的模拟纪要。\n【学情洞察】：无。"
    with patch("backend.services.memory_decay.generate_summary", return_value=fake_summary), \
         patch("backend.services.memory_decay.get_rag_client"):
        handler = MemoryDecayHandler()
        handler.handle({"phase_a_only": True}, "")

    # Verify results
    cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'compressed'")
    compressed_count = cursor.fetchone()[0]

    # The exact logic of process_memory_decay will run, so we just check if it did something
    assert compressed_count > 0

def test_force_decay_api_failure_does_not_return_success(test_db):
    """Test that when generate_summary fails (API failure), force_decay endpoint does not silently return success"""
    from backend.routers.memory import force_decay
    from fastapi import HTTPException
    
    # Setup initial data needing decay (level 1 log older than threshold)
    cursor = test_db.cursor()
    cursor.execute(
        "INSERT INTO memory_logs (content, summary, level, status, timestamp) VALUES ('', 'Old summary', 1, 'active', datetime('now', '-3 days'))"
    )
    test_db.commit()

    # When generate_summary fails (returns empty string "" after retries due to API failure)
    with patch("backend.services.memory_decay.generate_summary", return_value=""):
        # force_decay should raise an HTTPException or indicate error, NOT silently return status: "success"
        with pytest.raises(HTTPException) as exc_info:
            force_decay()
        assert exc_info.value.status_code >= 500

def test_get_memory_status_endpoint(test_db):
    """Test get_memory_status returns correct uncompacted_count, threshold, and recent diaries"""
    from backend.routers.memory import get_memory_status
    cursor = test_db.cursor()
    # Insert 2 level 0 active records
    cursor.execute("INSERT INTO memory_logs (content, level, status, timestamp) VALUES ('msg1', 0, 'active', datetime('now', '-2 minute'))")
    cursor.execute("INSERT INTO memory_logs (content, level, status, timestamp) VALUES ('msg2', 0, 'active', datetime('now', '-1 minute'))")
    # Insert 2 level 1 records
    cursor.execute("INSERT INTO memory_logs (content, summary, level, status, timestamp) VALUES ('', '日记一', 1, 'active', datetime('now', '-2 days'))")
    cursor.execute("INSERT INTO memory_logs (content, summary, level, status, timestamp) VALUES ('', '日记二', 1, 'active', datetime('now', '-1 day'))")
    test_db.commit()

    res = get_memory_status()
    assert res["status"] == "success"
    assert res["uncompacted_count"] == 2
    assert res["threshold"] == 10
    assert res["total_diaries"] == 2
    assert len(res["recent_diaries"]) == 2
    # Verify descending sort order: '日记二' before '日记一'
    assert res["recent_diaries"][0]["summary"] == "日记二"
    assert res["recent_diaries"][1]["summary"] == "日记一"

def test_response_pipeline_auto_summarize_control(test_db):
    """Test that ResponsePipeline respects auto_summarize flag when uncompacted count reaches threshold"""
    from backend.services.response_pipeline import ResponsePipeline
    from backend.services.action_registry import ActionRegistry
    from unittest.mock import MagicMock

    cursor = test_db.cursor()
    # Pre-populate 9 active level 0 items (threshold is 10)
    for i in range(9):
        cursor.execute("INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')", (f"pre{i}",))
    test_db.commit()

    # Case A: auto_summarize = False
    mock_decay_handler = MagicMock()
    registry = ActionRegistry()
    registry.register("memory_decay", mock_decay_handler)

    pipeline_manual = ResponsePipeline(registry=registry, session_id="test_sess", auto_summarize=False)
    pipeline_manual.original_user_msg = "User says hello"

    with patch("backend.services.response_pipeline.get_rag_client"):
        # Consume the stream so finally executes
        list(pipeline_manual.process_stream(iter(["Assistant says hi"])))

    # Since auto_summarize was False, decay handler must NOT be called even though count is now 10
    mock_decay_handler.handle.assert_not_called()
    cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
    assert cursor.fetchone()[0] == 10

    # Case B: auto_summarize = True (with 10 already in DB + 1 new = 11 >= 10)
    mock_decay_handler_auto = MagicMock()
    registry_auto = ActionRegistry()
    registry_auto.register("memory_decay", mock_decay_handler_auto)

    pipeline_auto = ResponsePipeline(registry=registry_auto, session_id="test_sess", auto_summarize=True)
    pipeline_auto.original_user_msg = "Another question"

    with patch("backend.services.response_pipeline.get_rag_client"):
        list(pipeline_auto.process_stream(iter(["Another answer"])))

    # With auto_summarize=True, decay handler MUST be triggered
    mock_decay_handler_auto.handle.assert_called_once_with({"phase_a_only": True}, "")

