import pytest
import sqlite3
import os
import json
from unittest.mock import patch, MagicMock

from backend.database import get_db_connection
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
def clean_and_reset_env(mock_db_path, tmp_path):
    """Reuse snapshot sqlite db from mock_db_path and isolate materials dir."""
    test_materials = str(tmp_path / "materials")
    os.makedirs(test_materials, exist_ok=True)

    with patch("backend.services.course_manager.DB_PATH", mock_db_path), \
         patch.object(MaterialsManager, "_get_materials_dir", return_value=test_materials):
        reset_active_course_id()
        yield mock_db_path, test_materials
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


def test_slash_commands_and_interrogation_forward_atmosphere_mode(clean_and_reset_env):
    """Verify Bug #54: /lesson and mission interrogation preserve study mode, while /end_lesson forces daily."""
    from backend.services.slash_handler import _stream_normal_chat_with_injection, handle_mission_interrogation

    class StudyPayload(DummyPayload):
        def __init__(self, atmosphere_mode="study"):
            super().__init__(session_id="sess_atm")
            self.atmosphere_mode = atmosphere_mode

    course_id = "atm_test_course"
    MaterialsManager.create_course(course_id, "氛围测试")
    append_to_syllabus("第一阶段", "测试课时", course_id=course_id, lesson_no=1)

    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        handle_slash_command(f"/lesson {course_id}", StudyPayload("study"), f"/lesson {course_id}", [])
        assert mock_stream.call_args.kwargs.get("atmosphere_mode") == "study"

        mock_stream.reset_mock()
        handle_slash_command("/end_lesson", StudyPayload("study"), "/end_lesson", [])
        assert mock_stream.call_args.kwargs.get("atmosphere_mode") == "daily"

        mock_stream.reset_mock()
        handle_mission_interrogation(
            "帮我定个计划",
            [],
            "simplified",
            {"goal": "测试", "daily_time_budget": "", "hard_constraints": "", "current_skill_level": ""},
            session_id="sess_atm",
            atmosphere_mode="study",
        )
        assert mock_stream.call_args.kwargs.get("atmosphere_mode") == "study"

    with patch("backend.services.context_manager.build_base_system_prompt") as mock_build:
        mock_build.return_value = (MagicMock(), 0, 0)
        _stream_normal_chat_with_injection(
            "/lesson",
            [],
            "simplified",
            "<system_directive />",
            session_id="sess_atm",
            atmosphere_mode="study",
        )
        assert mock_build.call_args.kwargs.get("atmosphere_mode") == "study"


def test_lesson_locks_selected_course_and_end_lesson_releases_to_default(clean_and_reset_env):
    """Verify Bug #55: selecting a course keeps archive at default until /lesson locks it, and /end_lesson unlocks back to default."""
    from backend.services.course_manager import (
        set_selected_course_id,
        get_selected_course_id,
        is_in_lesson,
    )

    test_db, test_materials = clean_and_reset_env
    course_id = "ditiansui_bazi"
    MaterialsManager.create_course(course_id, "滴天髓研读")
    MissionManager.finalize_draft("研读原典", "每日50分钟", "批注对照", "零基础", course_id=course_id, course_name="滴天髓研读")
    # Simulate clean off-class state right after mission setup completes
    reset_active_course_id()
    set_selected_course_id(course_id)
    assert get_active_course_id() == "default"
    assert is_in_lesson() is False

    # Off-class <explainer> must save to default, not pollute ditiansui_bazi
    explainer_handler = action_registry.get_handler("explainer")
    explainer_handler.handle({"title": "casual_note"}, "课外闲聊笔记")
    default_ref_dir = os.path.join(test_materials, "References")
    course_ref_dir = os.path.join(test_materials, "courses", course_id, "References")
    assert any("casual_note" in f for f in os.listdir(default_ref_dir))
    assert not os.path.exists(course_ref_dir) or not any("casual_note" in f for f in os.listdir(course_ref_dir))

    # Running /lesson without explicit course arg automatically locks onto selected_course_id
    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        handle_slash_command("/lesson", DummyPayload(session_id="sess_dt"), "/lesson", [])
        assert is_in_lesson() is True
        assert get_active_course_id() == course_id
        assert get_selected_course_id() == course_id
        assert mock_stream.call_args.kwargs["prelude_hint"].get("in_lesson") is True

        # During lesson, <explainer> saves strictly into ditiansui_bazi
        explainer_handler.handle({"title": "lesson1_note"}, "通神论第一课")
        assert any("lesson1_note" in f for f in os.listdir(course_ref_dir))

        # /end_lesson releases lock & resets active archive to default, while keeping selected_course_id for next class
        handle_slash_command("/end_lesson", DummyPayload(session_id="sess_dt"), "/end_lesson", [])
        assert is_in_lesson() is False
        assert get_active_course_id() == "default"
        assert get_selected_course_id() == course_id
        assert mock_stream.call_args.kwargs["prelude_hint"].get("in_lesson") is False

