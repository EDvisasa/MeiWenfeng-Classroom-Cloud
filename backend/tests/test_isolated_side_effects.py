import pytest
import sqlite3
import os
import json
from unittest.mock import patch

from backend.database import init_db, get_db_connection
from backend.services.course_manager import (
    get_active_course_id,
    set_active_course_id,
    reset_active_course_id,
    create_course,
)
from backend.services.materials_manager import MaterialsManager
from backend.services.action_registry import action_registry
from backend.services.agent_tools import CreateFileTool, ReplaceFileContentTool, ReadFileTool
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


def test_glossary_and_explainer_isolation(clean_and_reset_env):
    """Verify glossary and explainer handlers isolate DB records and files per course."""
    test_db, test_materials = clean_and_reset_env

    # 1. Create Course A and Course B
    MaterialsManager.create_course("course_a", "课程A")
    MaterialsManager.create_course("course_b", "课程B")

    glossary_handler = action_registry.get_handler("glossary")
    explainer_handler = action_registry.get_handler("explainer")
    assert glossary_handler is not None
    assert explainer_handler is not None

    # 2. Record glossary and explainer for Course A
    set_active_course_id("course_a")
    glossary_handler.handle({"term": "偏微分方程"}, "包含未知函数的偏导数的方程")
    explainer_handler.handle({"title": "pde_intro.md"}, "这是偏微分方程的详细讲义")

    # 3. Record glossary and explainer for Course B
    set_active_course_id("course_b")
    glossary_handler.handle({"term": "波函数"}, "描述微观粒子量子状态的复值函数")
    explainer_handler.handle({"title": "wave_function.md"}, "这是量子波函数的详细讲义")

    # 4. Verify DB records for glossary
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT term, course_id FROM glossary WHERE course_id = 'course_a'")
    terms_a = [r["term"] for r in cursor.fetchall()]
    assert "偏微分方程" in terms_a
    assert "波函数" not in terms_a

    cursor.execute("SELECT term, course_id FROM glossary WHERE course_id = 'course_b'")
    terms_b = [r["term"] for r in cursor.fetchall()]
    assert "波函数" in terms_b
    assert "偏微分方程" not in terms_b
    conn.close()

    # 5. Verify filesystem glossary.json isolation
    glossary_json_a = os.path.join(test_materials, "courses", "course_a", "Settings", "glossary.json")
    glossary_json_b = os.path.join(test_materials, "courses", "course_b", "Settings", "glossary.json")
    assert os.path.exists(glossary_json_a)
    assert os.path.exists(glossary_json_b)

    with open(glossary_json_a, "r", encoding="utf-8") as f:
        data_a = json.load(f)
    assert "偏微分方程" in data_a
    assert "波函数" not in data_a

    with open(glossary_json_b, "r", encoding="utf-8") as f:
        data_b = json.load(f)
    assert "波函数" in data_b
    assert "偏微分方程" not in data_b

    # 6. Verify References directory isolation
    ref_a = os.path.join(test_materials, "courses", "course_a", "References")
    ref_b = os.path.join(test_materials, "courses", "course_b", "References")
    assert any("pde_intro" in f for f in os.listdir(ref_a))
    assert not any("wave_function" in f for f in os.listdir(ref_a))

    assert any("wave_function" in f for f in os.listdir(ref_b))
    assert not any("pde_intro" in f for f in os.listdir(ref_b))


def test_sandbox_tools_isolation_and_relative_path(clean_and_reset_env):
    """Verify sandbox tools auto-anchor relative paths to active course and prevent cross-course escapes."""
    test_db, test_materials = clean_and_reset_env

    MaterialsManager.create_course("course_a", "课程A")
    MaterialsManager.create_course("course_b", "课程B")

    create_tool = CreateFileTool()
    replace_tool = ReplaceFileContentTool()

    # 1. In Course A, create file using relative path
    set_active_course_id("course_a")
    res_a = create_tool.execute({"path": "solution.py", "content": "print('Hello Course A')"})
    assert "[Success]" in res_a

    course_a_file = os.path.join(test_materials, "courses", "course_a", "Sandbox", "solution.py")
    assert os.path.exists(course_a_file)
    with open(course_a_file, "r", encoding="utf-8") as f:
        assert "Hello Course A" in f.read()

    # 2. In Course B, create file with the same relative path
    set_active_course_id("course_b")
    res_b = create_tool.execute({"path": "solution.py", "content": "print('Hello Course B')"})
    assert "[Success]" in res_b

    course_b_file = os.path.join(test_materials, "courses", "course_b", "Sandbox", "solution.py")
    assert os.path.exists(course_b_file)
    with open(course_b_file, "r", encoding="utf-8") as f:
        assert "Hello Course B" in f.read()

    # Course A file should remain unaffected
    with open(course_a_file, "r", encoding="utf-8") as f:
        assert "Hello Course A" in f.read()

    # 3. Security Boundary: Course B cannot modify Course A's sandbox
    res_cross = replace_tool.execute({
        "path": course_a_file,
        "old_content": "Course A",
        "new_content": "Hacked"
    })
    assert "GUARDRAIL BLOCKED" in res_cross or "boundary violation" in res_cross

