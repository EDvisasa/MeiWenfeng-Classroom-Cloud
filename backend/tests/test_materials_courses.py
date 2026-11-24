import os
import shutil
import pytest
from fastapi.testclient import TestClient
from backend.services.materials_manager import MaterialsManager
from backend.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_courses(tmp_path, monkeypatch):
    """Isolate MaterialsManager root to tmp_path so tests never write to production data/materials."""
    isolated_materials = str(tmp_path / "materials")
    os.makedirs(isolated_materials, exist_ok=True)
    monkeypatch.setattr(MaterialsManager, "_get_base_materials_dir", classmethod(lambda cls: isolated_materials))
    yield

def test_list_courses_contains_default():
    """Default global course must always be present."""
    courses = MaterialsManager.list_courses()
    assert any(c["id"] == "default" and c["is_default"] is True for c in courses)

def test_create_course_and_isolation():
    """Test creating an isolated course, verifying its directories and file isolation."""
    created = MaterialsManager.create_course("test_course_a", "线性代数专项课")
    assert created["id"] == "test_course_a"
    assert created["name"] == "线性代数专项课"

    # Verify course listing
    courses = MaterialsManager.list_courses()
    matching = [c for c in courses if c["id"] == "test_course_a"]
    assert len(matching) == 1
    assert matching[0]["name"] == "线性代数专项课"

    # Save a file in test_course_a
    rel_path = "Lessons/matrix_basics.md"
    content_a = "# 矩阵基础教程\n这是专项课程的内容"
    saved = MaterialsManager.save_material_content(rel_path, content_a, course_id="test_course_a")
    assert saved is True

    # Read back from test_course_a
    read_a = MaterialsManager.get_material_content(rel_path, course_id="test_course_a")
    assert read_a == content_a

    # Default course must NOT see this file (isolation)
    read_default = MaterialsManager.get_material_content(rel_path, course_id="default")
    assert "Document not found" in read_default

    # Verify knowledge tree for test_course_a
    tree_a = MaterialsManager.build_knowledge_tree(course_id="test_course_a")
    lessons_cat = next((cat for cat in tree_a if cat["category"] == "Lessons"), None)
    assert lessons_cat is not None
    assert any(f["path"] == rel_path for f in lessons_cat["files"])

def test_course_id_security_guardrails():
    """Invalid or traversal course_ids must be rejected with ValueError."""
    with pytest.raises(ValueError):
        MaterialsManager.create_course("../../../etc", "Hack Course")

    with pytest.raises(ValueError):
        MaterialsManager.create_course("course/with/slash", "Hack")

    with pytest.raises(ValueError):
        MaterialsManager.save_material_content("Lessons/test.md", "bad", course_id="../escape")

def test_api_course_management_endpoints(monkeypatch):
    """Test HTTP API endpoints for course list, create, tree, and isolated file operations."""
    # Mock RAG
    sync_called = []
    class MockRagClient:
        def sync_knowledge(self, files_content, dataset_name="Classroom_Knowledge"):
            sync_called.append((files_content, dataset_name))
            return {"status": "success"}

    import backend.routers.course as course_mod
    monkeypatch.setattr(course_mod, "get_rag_client", lambda: MockRagClient(), raising=False)

    # 1. GET courses
    res = client.get("/api/chat/materials/courses")
    assert res.status_code == 200
    data = res.json()
    assert "courses" in data
    assert any(c["id"] == "default" for c in data["courses"])

    # 2. POST create course
    res_create = client.post("/api/chat/materials/courses/create", json={
        "course_id": "tdd_course",
        "name": "TDD 专项研修课"
    })
    assert res_create.status_code == 200
    assert res_create.json()["course"]["id"] == "tdd_course"

    # 3. Save file into tdd_course via API
    res_save = client.post("/api/chat/materials/save", json={
        "path": "Lessons/tdd_intro.md",
        "content": "# TDD Intro\nRed Green Refactor",
        "course_id": "tdd_course"
    })
    assert res_save.status_code == 200
    assert len(sync_called) == 1
    assert "tdd_course/Lessons/tdd_intro.md" in sync_called[0][0]

    # 4. GET tree for tdd_course
    res_tree = client.get("/api/chat/materials/tree?course_id=tdd_course")
    assert res_tree.status_code == 200
    tree_data = res_tree.json()
    assert tree_data["course_id"] == "tdd_course"
    lessons_node = next((cat for cat in tree_data["knowledge_tree"] if cat["category"] == "Lessons"), None)
    assert lessons_node is not None
    assert any(f["name"] == "tdd_intro" for f in lessons_node["files"])

    # 5. GET content with course_id
    res_content = client.get("/api/chat/materials/content?path=Lessons/tdd_intro.md&course_id=tdd_course")
    assert res_content.status_code == 200
    assert "Red Green Refactor" in res_content.json()["content"]

