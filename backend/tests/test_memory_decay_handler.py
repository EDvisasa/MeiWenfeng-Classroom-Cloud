import pytest
import sqlite3
from typing import Dict, Any
from backend.database import get_db_connection
from backend.services.action_registry import ActionRegistry
from backend.services.memory_decay import MemoryDecayHandler

@pytest.fixture
def test_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Clean up memory_logs table for testing
    cursor.execute("DELETE FROM memory_logs")
    conn.commit()
    yield conn
    cursor.execute("DELETE FROM memory_logs")
    conn.commit()
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

    # Execute handler
    handler = MemoryDecayHandler()
    handler.handle({"phase_a_only": True}, "")

    # Verify results
    cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'compressed'")
    compressed_count = cursor.fetchone()[0]

    # The exact logic of process_memory_decay will run, so we just check if it did something
    assert compressed_count > 0
