import pytest
import sqlite3
import threading
import time
from backend.database import get_db_connection
from backend.services.memory_decay import process_memory_decay

def test_memory_decay_race_condition():
    """
    Test that process_memory_decay handles concurrent executions safely.
    It should not duplicate level 1 summaries when called concurrently.
    """
    # Setup test data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memory_logs")

    # Insert 10 level 0 logs to trigger decay
    for i in range(10):
        cursor.execute("INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')", (f"Test log {i}",))
    conn.commit()
    conn.close()

    # We will mock generate_summary to simulate network delay
    import backend.services.memory_decay as md
    original_generate_summary = md.generate_summary

    call_count = 0

    def slow_mock_summary(text, prompt):
        nonlocal call_count
        call_count += 1
        time.sleep(0.5) # Simulate API delay
        return f"Mocked summary {call_count}"

    md.generate_summary = slow_mock_summary

    try:
        # Run process_memory_decay concurrently
        threads = []
        for _ in range(3):
            t = threading.Thread(target=process_memory_decay)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check results
        conn = get_db_connection()
        cursor = conn.cursor()

        # How many level 1 logs were created?
        cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 1 AND status = 'active'")
        level1_count = cursor.fetchone()[0]

        # How many level 0 logs are still active?
        cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
        level0_count = cursor.fetchone()[0]

        conn.close()

        # It should only create ONE level 1 summary for today, even with concurrent calls
        assert level1_count == 1, f"Race condition: created {level1_count} level 1 summaries instead of 1"
        assert level0_count == 0, f"Race condition: {level0_count} level 0 logs remained active"

    finally:
        # Restore mock
        md.generate_summary = original_generate_summary
