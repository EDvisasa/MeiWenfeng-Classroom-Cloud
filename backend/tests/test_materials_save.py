import os
import pytest
from backend.services.materials_manager import MaterialsManager

def test_save_material_content_tracer_bullet():
    """
    Tracer Bullet Test: Verify that save_material_content successfully writes
    a markdown file under Sandbox/ and get_material_content reads it back.
    """
    rel_path = "Sandbox/test_tdd_tracer.md"
    test_content = "# TDD Tracer Bullet\nThis is a test file for TDD."

    try:
        # This should succeed when save_material_content is implemented
        result = MaterialsManager.save_material_content(rel_path, test_content)
        assert result is True

        # Verify reading it back via get_material_content
        read_content = MaterialsManager.get_material_content(rel_path)
        assert read_content == test_content
    finally:
        # Clean up the created test file
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(base_root, "data", "materials", rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)

def test_save_material_content_security_guardrails():
    """Verify that path traversal and non-md extensions are strictly blocked."""
    with pytest.raises(ValueError, match="Directory traversal attempt"):
        MaterialsManager.save_material_content("../../windows/system32/hack.md", "hack")
        
    with pytest.raises(ValueError, match="Only .md files can be modified"):
        MaterialsManager.save_material_content("Sandbox/hack.py", "print('hack')")

def test_api_materials_save_endpoint(monkeypatch):
    """
    Verify POST /api/chat/materials/save writes file, blocks illegal paths with 403,
    and initiates background RAG sync.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # Mock RAG client sync_knowledge so we can verify it was called without hitting external vector DB
    sync_called = []
    class MockRagClient:
        def sync_knowledge(self, files_content, dataset_name="Classroom_Knowledge"):
            sync_called.append((files_content, dataset_name))
            return {"status": "success"}

    import backend.routers.course as course_mod
    monkeypatch.setattr(course_mod, "get_rag_client", lambda: MockRagClient(), raising=False)

    rel_path = "Sandbox/test_api_save.md"
    test_content = "# API Save Test\nTesting POST endpoint."

    try:
        # Test valid save
        res = client.post("/api/chat/materials/save", json={"path": rel_path, "content": test_content})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["status"] == "success"
        
        # Verify file actually written
        assert MaterialsManager.get_material_content(rel_path) == test_content
        
        # Verify background RAG sync initiated
        assert len(sync_called) == 1
        assert sync_called[0][0] == {rel_path: test_content}
        assert sync_called[0][1] == "Classroom_Knowledge"

        # Test traversal rejection (403)
        res_traversal = client.post("/api/chat/materials/save", json={"path": "../hack.md", "content": "hack"})
        assert res_traversal.status_code == 403
        assert "Directory traversal attempt" in res_traversal.json()["detail"]

        # Test extension rejection (403)
        res_ext = client.post("/api/chat/materials/save", json={"path": "Sandbox/test.py", "content": "print('hack')"})
        assert res_ext.status_code == 403
        assert "Only .md files can be modified" in res_ext.json()["detail"]

    finally:
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(base_root, "data", "materials", rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)
