import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.routers.course import router as course_router
from backend.database import init_db
import backend.database as db_module

# 构造极简的隔离 FastAPI 实例，避免拉起主项目时加载 ChromaDB
app = FastAPI()
app.include_router(course_router)
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    # 1. 隔离数据库：使用临时的测试数据库
    test_db_path = tmp_path / "test_classroom.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db_path))
    init_db()
    
    # 2. 隔离文件系统：欺骗 MaterialsManager 让它在 tmp_path 里面找文件
    original_abspath = os.path.abspath
    def mock_abspath(path):
        if "materials_manager.py" in path:
            return os.path.join(str(tmp_path), "backend", "services", "materials_manager.py")
        return original_abspath(path)
    monkeypatch.setattr(os.path, "abspath", mock_abspath)
    
    # 手动建立四组标准的假目录
    materials_dir = tmp_path / "data" / "materials"
    (materials_dir / "Lessons").mkdir(parents=True, exist_ok=True)
    (materials_dir / "LDRs").mkdir(parents=True, exist_ok=True)
    (materials_dir / "References").mkdir(parents=True, exist_ok=True)
    (materials_dir / "Settings").mkdir(parents=True, exist_ok=True)
    
    yield

def test_status_endpoint_returns_mission_and_tree():
    """测试行为 1：状态大动脉（聚合查询）验证"""
    response = client.get("/api/chat/status")
    assert response.status_code == 200
    data = response.json()
    
    # 验证模块存在
    assert "mission" in data
    assert "knowledge_tree" in data
    
    # 验证树结构分类（不一定有文件，但四大金刚目录必须存在）
    tree = data["knowledge_tree"]
    categories = [node["category"] for node in tree]
    assert "Lessons" in categories
    assert "LDRs" in categories
    assert "References" in categories
    assert "Settings" in categories

def test_materials_content_success(tmp_path):
    """测试行为 2：按需文本拉取验证"""
    # Arrange：在物理文件系统中植入一篇《TDD 测试讲义.md》
    test_file = tmp_path / "data" / "materials" / "Lessons" / "TDD_Tutorial.md"
    test_content = "# TDD is awesome\nWrite tests first!"
    test_file.write_text(test_content, encoding="utf-8")
    
    # Act
    response = client.get("/api/chat/materials/content?path=Lessons/TDD_Tutorial.md")
    
    # Assert
    assert response.status_code == 200
    assert response.json()["content"] == test_content

def test_materials_content_directory_traversal():
    """测试行为 3：恶意目录穿透防范"""
    # Act
    response = client.get("/api/chat/materials/content?path=../../../main.py")
    
    # Assert
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]
