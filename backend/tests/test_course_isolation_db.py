import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch

from backend.database import init_db, get_db_connection
from backend.services.course_manager import (
    get_active_course_id,
    set_active_course_id,
    reset_active_course_id,
    create_course,
    list_courses,
    get_course,
    get_active_course,
    advance_course_progress,
    get_formatted_syllabus,
    append_to_syllabus,
    get_zpd_metrics,
    record_quiz_result,
)
from backend.services.mission_manager import MissionManager


@pytest.fixture(autouse=True)
def clean_and_reset_db(tmp_path):
    """Create a temporary sqlite db for isolation testing."""
    test_db = str(tmp_path / "test_classroom.db")
    with patch("backend.database.DB_PATH", test_db), \
         patch("backend.services.course_manager.DB_PATH", test_db):
        reset_active_course_id()
        init_db()
        yield test_db
        reset_active_course_id()


def test_init_db_creates_courses_table_and_default_seed():
    """Verify courses table is created with default course."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, status FROM courses WHERE id = 'default'")
    row = cursor.fetchone()
    assert row is not None
    assert row["id"] == "default"
    assert "全局基础课程" in row["name"]
    assert row["status"] == "active"
    conn.close()


def test_migrations_add_course_id_and_lesson_no():
    """Verify course_id column is added to user_mission, course_progress, glossary, mission_draft, chat_sessions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for table in ["user_mission", "course_progress", "glossary", "mission_draft", "chat_sessions"]:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [c[1] for c in cursor.fetchall()]
        assert "course_id" in columns, f"course_id column missing in {table}"

    cursor.execute("PRAGMA table_info(course_progress)")
    cp_columns = [c[1] for c in cursor.fetchall()]
    assert "lesson_no" in cp_columns, "lesson_no column missing in course_progress"
    conn.close()


def test_active_course_tracking():
    """Test get_active_course_id, set_active_course_id, and reset_active_course_id."""
    assert get_active_course_id() == "default"

    create_course("quantum_physics", "量子物理学基础")
    set_active_course_id("quantum_physics")
    assert get_active_course_id() == "quantum_physics"

    courses = list_courses()
    course_ids = [c["id"] for c in courses]
    assert "default" in course_ids
    assert "quantum_physics" in course_ids

    course_info = get_course("quantum_physics")
    assert course_info is not None
    assert course_info["name"] == "量子物理学基础"

    reset_active_course_id()
    assert get_active_course_id() == "default"


def test_course_progress_isolation():
    """Verify course_progress is isolated between different courses."""
    create_course("course_a", "课程A")
    create_course("course_b", "课程B")

    # Add topics for course A
    append_to_syllabus("第一阶段", "课程A第一课", course_id="course_a", lesson_no=1)
    append_to_syllabus("第一阶段", "课程A第二课", course_id="course_a", lesson_no=2)

    # Add topics for course B
    append_to_syllabus("第一阶段", "课程B第一课", course_id="course_b", lesson_no=1)

    # By default, append_to_syllabus adds with status='pending'. Activate the first lesson in each course
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE course_progress SET status = 'active' WHERE course_id = 'course_a' AND topic = '课程A第一课'")
    cursor.execute("UPDATE course_progress SET status = 'active' WHERE course_id = 'course_b' AND topic = '课程B第一课'")
    conn.commit()
    conn.close()

    # Active course check for Course A
    active_a = get_active_course("course_a")
    assert active_a is not None
    assert active_a["topic"] == "课程A第一课"

    # Active course check for Course B
    active_b = get_active_course("course_b")
    assert active_b is not None
    assert active_b["topic"] == "课程B第一课"

    # Advance course A
    next_a = advance_course_progress("course_a")
    assert next_a is not None
    assert next_a["topic"] == "课程A第二课"

    # Verify Course B remained unaffected
    active_b_after = get_active_course("course_b")
    assert active_b_after["topic"] == "课程B第一课"
    assert active_b_after["status"] == "active"

    # Formatted syllabus check
    syllabus_a = get_formatted_syllabus("course_a")
    assert "课程A第一课" in syllabus_a
    assert "课程A第二课" in syllabus_a
    assert "课程B第一课" not in syllabus_a

    syllabus_b = get_formatted_syllabus("course_b")
    assert "课程B第一课" in syllabus_b
    assert "课程A第一课" not in syllabus_b


def test_user_mission_isolation():
    """Verify MissionManager isolates mission_text per course_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_mission (course_id, mission_text) VALUES ('course_a', '# Mission A')")
    cursor.execute("INSERT INTO user_mission (course_id, mission_text) VALUES ('course_b', '# Mission B')")
    conn.commit()
    conn.close()

    mission_a = MissionManager.get_user_mission("course_a")
    assert mission_a == "# Mission A"

    mission_b = MissionManager.get_user_mission("course_b")
    assert mission_b == "# Mission B"


def test_backward_compatibility_defaults():
    """Verify calls without explicit course_id use 'default' course and preserve legacy behavior."""
    reset_active_course_id()
    assert get_active_course_id() == "default"

    active_default = get_active_course()
    assert active_default is not None
    assert active_default["status"] == "active"

    syllabus = get_formatted_syllabus()
    assert "编程环境配置与基础语法入门" in syllabus


def test_session_course_linkage():
    """Verify chat_sessions records course_id and supports session-course tracking."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_sessions (id, title, course_id) VALUES ('sess_pde', '偏微分方程研读', 'pde_navier_stokes')"
    )
    cursor.execute(
        "INSERT INTO chat_sessions (id, title) VALUES ('sess_daily', '日常闲聊')"
    )
    conn.commit()

    cursor.execute("SELECT id, course_id FROM chat_sessions WHERE id = 'sess_pde'")
    row_pde = cursor.fetchone()
    assert row_pde["course_id"] == "pde_navier_stokes"

    cursor.execute("SELECT id, course_id FROM chat_sessions WHERE id = 'sess_daily'")
    row_daily = cursor.fetchone()
    assert row_daily["course_id"] == "default"
    conn.close()
