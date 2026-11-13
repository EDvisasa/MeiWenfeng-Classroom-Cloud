import pytest
import sqlite3
import os
import json
from unittest.mock import patch, MagicMock

from backend.database import init_db, get_db_connection
from backend.services.course_manager import (
    get_active_course_id,
    set_active_course_id,
    reset_active_course_id,
    get_active_course,
    advance_course_progress,
    append_to_syllabus,
    get_formatted_syllabus,
)
from backend.services.mission_manager import MissionManager
from backend.services.materials_manager import MaterialsManager
from backend.services.action_registry import action_registry
from backend.services.slash_handler import handle_slash_command
import backend.services.side_effects


@pytest.fixture(autouse=True)
def clean_and_reset_env(tmp_path):
    """Create a temporary sqlite db and materials directory for isolation testing."""
    test_db = str(tmp_path / "test_classroom.db")
    test_materials = str(tmp_path / "materials")
    os.makedirs(test_materials, exist_ok=True)

    with patch("backend.database.DB_PATH", test_db), \
         patch("backend.services.course_manager.DB_PATH", test_db), \
         patch.object(MaterialsManager, "_get_materials_dir", return_value=test_materials):
        reset_active_course_id()
        init_db()
        yield test_db, test_materials
        reset_active_course_id()


class DummyPayload:
    def __init__(self, current_file_path=None, persona_type="simplified", session_id="test_sess_001"):
        self.current_file_path = current_file_path
        self.persona_type = persona_type
        self.session_id = session_id


def test_new_course_handler_mirrors_syllabus_md(clean_and_reset_env):
    """Verify <new_course> handler appends to DB and mirrors to courses/<course_id>/Lessons/syllabus.md."""
    test_db, test_materials = clean_and_reset_env

    course_id = "pde_sim"
    MaterialsManager.create_course(course_id, "偏微分方程仿真")
    set_active_course_id(course_id)

    handler = action_registry.get_handler("new_course")
    assert handler is not None

    handler.handle({"phase": "第一阶段：离散化基础", "topic": "有限差分网格剖分"}, "")
    handler.handle({"phase": "第一阶段：离散化基础", "topic": "一维波动方程显式积分"}, "")

    # 1. Verify in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT phase, topic, lesson_no, course_id FROM course_progress WHERE course_id = ?", (course_id,))
    rows = cursor.fetchall()
    assert len(rows) == 2
    assert rows[0]["topic"] == "有限差分网格剖分"
    assert rows[1]["topic"] == "一维波动方程显式积分"
    conn.close()

    # 2. Verify mirrored file exists on disk
    syllabus_md = os.path.join(test_materials, "courses", course_id, "Lessons", "syllabus.md")
    assert os.path.exists(syllabus_md)
    with open(syllabus_md, "r", encoding="utf-8") as f:
        content = f.read()
    assert "有限差分网格剖分" in content
    assert "一维波动方程显式积分" in content


def test_lesson_command_dual_track_and_isolation(clean_and_reset_env):
    """Verify /lesson [course_id] locks active course, updates session, and scopes sandbox."""
    test_db, test_materials = clean_and_reset_env

    course_id = "quantum_sim"
    MaterialsManager.create_course(course_id, "量子仿真")
    append_to_syllabus("第一阶段", "薛定谔方程初探", course_id=course_id, lesson_no=1)

    # Activate lesson 1
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE course_progress SET status = 'active' WHERE course_id = ? AND topic = '薛定谔方程初探'", (course_id,))
    conn.commit()
    conn.close()

    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        payload = DummyPayload(session_id="sess_q")
        handle_slash_command(f"/lesson {course_id}", payload, f"/lesson {course_id}", [])

        assert mock_stream.called
        call_args = mock_stream.call_args
        system_injection = call_args[0][3]
        prelude_hint = call_args[1]["prelude_hint"]

        # Verify active course locked
        assert get_active_course_id() == course_id
        # Verify system injection has course and sandbox path
        assert course_id in system_injection
        assert f"courses/{course_id}/Sandbox/" in system_injection
        assert "薛定谔方程初探" in system_injection
        # Verify prelude hint has study atmosphere
        assert prelude_hint["atmosphere"] == "study"


def test_end_lesson_resets_to_default_archive(clean_and_reset_env):
    """Verify /end_lesson dismisses class, unloads directives, and resets active archive to default."""
    test_db, test_materials = clean_and_reset_env

    set_active_course_id("quantum_sim")
    assert get_active_course_id() == "quantum_sim"

    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        payload = DummyPayload(session_id="sess_q")
        handle_slash_command("/end_lesson", payload, "/end_lesson", [])

        assert mock_stream.called
        call_args = mock_stream.call_args
        system_injection = call_args[0][3]
        prelude_hint = call_args[1]["prelude_hint"]

        # Verify active archive reset to default
        assert get_active_course_id() == "default"
        # Verify mode="recess" and daily atmosphere
        assert 'mode="recess"' in system_injection
        assert prelude_hint["atmosphere"] == "daily"


def test_plan_command_scoped_and_preserves_completed(clean_and_reset_env):
    """Verify /plan scopes to course and protects completed lessons."""
    test_db, test_materials = clean_and_reset_env

    course_id = "mech_robotics"
    MaterialsManager.create_course(course_id, "机器人动力学")
    append_to_syllabus("第一阶段", "刚体运动学", course_id=course_id, lesson_no=1)
    append_to_syllabus("第一阶段", "拉格朗日方程", course_id=course_id, lesson_no=2)

    # Mark lesson 1 completed
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE course_progress SET status = 'completed' WHERE course_id = ? AND topic = '刚体运动学'", (course_id,))
    cursor.execute("UPDATE course_progress SET status = 'active' WHERE course_id = ? AND topic = '拉格朗日方程'", (course_id,))
    conn.commit()
    conn.close()

    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        payload = DummyPayload(session_id="sess_mech")
        handle_slash_command(f"/plan {course_id}", payload, f"/plan {course_id}", [])

        assert mock_stream.called
        call_args = mock_stream.call_args
        system_injection = call_args[0][3]

        assert course_id in system_injection
        assert "[已完成]" in system_injection
        assert "刚体运动学" in system_injection
        assert "COMPLETED LESSONS PROTECTION" in system_injection
