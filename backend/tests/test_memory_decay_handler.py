import pytest
import sqlite3
from typing import Dict, Any
from backend.database import get_db_connection
from backend.services.action_registry import ActionRegistry
from backend.services.memory_decay import MemoryDecayHandler

from unittest.mock import patch

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test.db"
    with patch("backend.database.DB_PATH", str(db_file)):
        from backend.database import init_db
        init_db()
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
