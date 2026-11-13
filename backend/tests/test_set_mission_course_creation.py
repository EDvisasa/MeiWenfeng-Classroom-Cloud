import pytest
import sqlite3
import os
import shutil
import tempfile
from unittest.mock import patch

from backend.database import init_db, get_db_connection
from backend.services.course_manager import (
    get_active_course_id,
    reset_active_course_id,
    get_course,
)
from backend.services.mission_manager import MissionManager
from backend.services.materials_manager import MaterialsManager
from backend.services.action_registry import action_registry
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
        action_registry.register("finalize_mission", backend.services.side_effects.FinalizeMissionHandler())
        yield test_db, test_materials
        reset_active_course_id()


def test_finalize_draft_creates_course_and_scaffolds_folders(clean_and_reset_env):
    """Verify finalize_draft with course_id scaffolds folders and writes Settings/user_mission.md."""
    test_db, test_materials = clean_and_reset_env

    course_id = "pde_navier_stokes"
    goal = "精通 Navier-Stokes 偏微分方程数值解法"
    time_budget = "每天 1.5 小时"
    constraints = "必须纯 Python + NumPy 手写离散格式"
    skill = "具备高等数学与初等流体力学背景"

    MissionManager.finalize_draft(
        final_goal=goal,
        final_time=time_budget,
        final_constraints=constraints,
        final_skill=skill,
        course_id=course_id,
        course_name="偏微分方程数值解"
    )

    # 1. Verify physical folders exist
    course_dir = os.path.join(test_materials, "courses", course_id)
    assert os.path.exists(course_dir), "Course directory was not created"
    for folder in ["Lessons", "Sandbox", "References", "LDRs", "Settings"]:
        sub = os.path.join(course_dir, folder)
        assert os.path.exists(sub), f"Subdirectory {folder} was not created"

    # 2. Verify Settings/user_mission.md exists in course dir, not in global root
    course_mission_file = os.path.join(course_dir, "Settings", "user_mission.md")
    assert os.path.exists(course_mission_file)
    with open(course_mission_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert goal in content
    assert constraints in content

    # 3. Verify SQLite courses table has course registered and active
    course_info = get_course(course_id)
    assert course_info is not None
    assert course_info["id"] == course_id
    assert course_info["name"] == "偏微分方程数值解"
    assert course_info["status"] == "active"

    # 4. Verify user_mission has record for course_id
    saved_mission = MissionManager.get_user_mission(course_id)
    assert goal in saved_mission

    # 5. Verify active course id is set to this course
    assert get_active_course_id() == course_id


def test_finalize_mission_handler_action(clean_and_reset_env):
    """Verify FinalizeMissionHandler action handles course_id attribute and slug fallback."""
    test_db, test_materials = clean_and_reset_env

    handler = action_registry.get_handler("finalize_mission")
    assert handler is not None

    attrs = {
        "goal": "掌握机器学习基础",
        "time": "每天1小时",
        "constraints": "无",
        "skill": "零基础",
        "course_id": "ml_basics"
    }
    handler.handle(attrs, "")

    # Verify course ml_basics was created
    course_dir = os.path.join(test_materials, "courses", "ml_basics")
    assert os.path.exists(course_dir)
    assert get_active_course_id() == "ml_basics"
