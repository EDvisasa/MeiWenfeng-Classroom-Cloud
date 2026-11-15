import os
import pytest
from backend.services.mission_manager import MissionManager

@pytest.fixture(autouse=True)
def setup_test_environment(mock_db_path, monkeypatch, tmp_path):
    # 1. 隔离数据库：复用 conftest.py 的快照测试库 mock_db_path，防止污染真实用户的 classroom.db
    # 2. 隔离文件系统：重定向物理文件写入路径到临时文件夹
    # MissionManager uses base_root = os.path.dirname(...) and builds 'data/materials'
    # We will mock the os.path.abspath to return the tmp_path so it writes inside tmp_path
    original_abspath = os.path.abspath
    def mock_abspath(path):
        if "mission_manager.py" in path:
            return os.path.join(str(tmp_path), "backend", "services", "mission_manager.py")
        return original_abspath(path)
    monkeypatch.setattr(os.path, "abspath", mock_abspath)
    
    yield
    
def test_start_draft_makes_mission_active():
    """测试行为 1：起草阻断。调用 start_draft 后，必须能获取到该草稿。"""
    goal = "I want to learn advanced React"
    
    # Act
    MissionManager.start_draft(goal)
    
    # Assert
    active_draft = MissionManager.get_active_draft()
    assert active_draft is not None
    assert active_draft["goal"] == goal
    assert active_draft["is_active"] == 1

def test_cancel_draft_clears_active_state():
    """测试行为 2：安全逃生舱。取消后，阻断必须解除。"""
    # Arrange
    MissionManager.start_draft("Some goal")
    assert MissionManager.get_active_draft() is not None
    
    # Act
    MissionManager.cancel_draft()
    
    # Assert
    assert MissionManager.get_active_draft() is None

def test_finalize_draft_updates_user_mission_and_writes_files(tmp_path):
    """测试行为 3：全局学习目标与配置参数的终审落地（集成验证）。"""
    # Arrange
    MissionManager.start_draft("Initial Goal")
    final_goal = "Master React Hooks"
    final_time = "2 hours a day"
    final_constraints = "No video tutorials"
    final_skill = "Intermediate"
    
    # Act
    MissionManager.finalize_draft(final_goal, final_time, final_constraints, final_skill)
    
    # Assert
    # a. get_user_mission() 能够返回新的任务 Markdown
    user_mission = MissionManager.get_user_mission()
    assert final_goal in user_mission
    assert final_constraints in user_mission
    
    # b. get_active_draft() 必须返回空（拦截解除）
    assert MissionManager.get_active_draft() is None
    
    # c. 物理验证：文件是否成功写入
    expected_mission_file = tmp_path / "data" / "materials" / "Settings" / "user_mission.md"
    assert expected_mission_file.exists(), "Mission markdown file was not generated on disk!"
    
    with open(expected_mission_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert final_goal in content
        assert final_time in content

def test_parse_mission_markdown():
    """测试行为 4：Markdown 课题文本结构化解析"""
    raw = (
        "# Mission Objective\n\n"
        "**Goal**: 捋顺OpenAI关于Navier-Stokes方程有限时间爆破论文的核心逻辑\n\n"
        "**Time Budget**: 每日1小时\n\n"
        "**Constraints**: 零预算、不看视频教程、以放松探索为主\n\n"
        "**Verified Skill Level**: 大学高数/线代基础，微积分尚可，但散度与矩阵运动学概念已生锈\n"
    )
    parsed = MissionManager.parse_mission_markdown(raw)
    assert parsed["goal"] == "捋顺OpenAI关于Navier-Stokes方程有限时间爆破论文的核心逻辑"
    assert parsed["time_budget"] == "每日1小时"
    assert parsed["constraints"] == "零预算、不看视频教程、以放松探索为主"
    assert "大学高数" in parsed["skill_level"]

    # 回退纯净文本
    raw_plain = "### 学 Rust 并写一个 OS"
    parsed_plain = MissionManager.parse_mission_markdown(raw_plain)
    assert parsed_plain["goal"] == "学 Rust 并写一个 OS"
