import pytest
import sqlite3
import os
import tempfile
from backend.services.course_manager import get_active_course

# Fixture to provide an isolated test database
@pytest.fixture
def test_db():
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Create the test DB schema
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE course_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase TEXT,
        topic TEXT,
        status TEXT,
        score INTEGER DEFAULT 0
    );
    """)
    # Insert initial syllabus data
    cursor.executemany(
        "INSERT INTO course_progress (phase, topic, status, score) VALUES (?, ?, ?, ?)",
        [
            ("第一阶段：环境与基础", "编程环境配置与基础语法入门", "active", 0),
            ("第一阶段：环境与基础", "变量数据类型与控制流逻辑", "pending", 0),
        ]
    )
    conn.commit()
    conn.close()
    
    yield temp_db_path
    
    # Cleanup after test
    os.remove(temp_db_path)

def test_get_active_course(test_db, monkeypatch):
    # Mock the DB_PATH in course_manager to use our test DB
    import backend.services.course_manager as cm
    monkeypatch.setattr(cm, "DB_PATH", test_db)
    
    active_course = get_active_course()
    
    assert active_course is not None
    assert active_course["phase"] == "第一阶段：环境与基础"
    assert active_course["topic"] == "编程环境配置与基础语法入门"
    assert active_course["status"] == "active"

def test_advance_course_progress(test_db, monkeypatch):
    import backend.services.course_manager as cm
    monkeypatch.setattr(cm, "DB_PATH", test_db)
    
    # Pre-condition check
    active = cm.get_active_course()
    assert active["topic"] == "编程环境配置与基础语法入门"
    
    # Advance progress
    new_active = cm.advance_course_progress()
    
    assert new_active is not None
    assert new_active["topic"] == "变量数据类型与控制流逻辑"
    assert new_active["status"] == "active"
    
    # Check old course is completed
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM course_progress WHERE topic = '编程环境配置与基础语法入门'")
    row = cursor.fetchone()
    conn.close()
    
    assert row["status"] == "completed"

def test_complete_all_courses(test_db, monkeypatch):
    import backend.services.course_manager as cm
    monkeypatch.setattr(cm, "DB_PATH", test_db)
    
    # We have 2 courses initially.
    cm.advance_course_progress() # finishes 1st, activates 2nd
    new_active = cm.advance_course_progress() # finishes 2nd, no more pending
    
    assert new_active is None
    
    # Verify all are completed
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM course_progress WHERE status != 'completed'")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 0

def test_get_formatted_syllabus(test_db, monkeypatch):
    import backend.services.course_manager as cm
    monkeypatch.setattr(cm, "DB_PATH", test_db)
    
    formatted = cm.get_formatted_syllabus()
    
    assert "第一阶段：环境与基础" in formatted
    assert "[当前]" in formatted
    assert "[未修]" in formatted
    assert "编程环境配置与基础语法入门" in formatted
    assert "变量数据类型与控制流逻辑" in formatted

def test_append_to_syllabus(test_db, monkeypatch):
    import backend.services.course_manager as cm
    monkeypatch.setattr(cm, "DB_PATH", test_db)
    
    cm.append_to_syllabus("第四阶段：元婴出窍", "神游太虚")
    
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT phase, topic, status FROM course_progress ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    assert row[0] == "第四阶段：元婴出窍"
    assert row[1] == "神游太虚"
    assert row[2] == "pending"
