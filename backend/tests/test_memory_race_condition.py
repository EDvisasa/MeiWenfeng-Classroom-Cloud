import pytest
import threading
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

    # Coordinate threads deterministically without sleeping
    import backend.services.memory_decay as md
    original_generate_summary = md.generate_summary

    call_count = 0
    entered = threading.Event()
    release = threading.Event()

    def slow_mock_summary(text, prompt):
        nonlocal call_count
        call_count += 1
        entered.set()
        assert release.wait(timeout=2.0)
        return f"Mocked summary {call_count}"

    md.generate_summary = slow_mock_summary

    try:
        # Hold _decay_lock inside worker 1, then run concurrent contenders that must skip immediately
        results = []

        def run_decay():
            results.append(process_memory_decay())

        primary = threading.Thread(target=run_decay)
        primary.start()
        assert entered.wait(timeout=2.0)

        contenders = [threading.Thread(target=run_decay) for _ in range(2)]
        for t in contenders:
            t.start()
        for t in contenders:
            t.join()

        release.set()
        primary.join()

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
        assert call_count == 1
        assert sum(1 for r in results if r.get("skipped")) == 2
        assert level1_count == 1, f"Race condition: created {level1_count} level 1 summaries instead of 1"
        assert level0_count == 0, f"Race condition: {level0_count} level 0 logs remained active"

    finally:
        # Restore mock
        md.generate_summary = original_generate_summary
