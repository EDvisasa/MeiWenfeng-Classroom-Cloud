import pytest
from pydantic import ValidationError
from backend.routers.chat import ChatRequest, Message

def test_chat_request_validation():
    # Test that valid complete data passes
    valid_data = {
        "messages": [{"role": "user", "content": "hello", "timestamp": "123"}],
        "persona_type": "simplified",
        "current_file_path": "/path/to/file.js",
        "cursor_line": 264,
        "custom_max_tokens": 8192
    }
    req = ChatRequest.model_validate(valid_data)
    assert req.cursor_line == 264

def test_chat_request_validation_with_nulls():
    # Test that Pydantic V2 correctly handles explicitly passed null values (None)
    # for optional fields without raising 422 Unprocessable Content.
    null_data = {
        "messages": [{"role": "user", "content": None, "timestamp": None}],
        "persona_type": None,
        "current_file_path": None,
        "cursor_line": None,
        "custom_max_tokens": None
    }
    
    req = ChatRequest.model_validate(null_data)
    
    # Assert that fields are properly defaulted or set to None
    assert req.persona_type is None
    assert req.current_file_path is None
    assert req.cursor_line is None
    assert req.custom_max_tokens is None
    assert req.messages[0].content is None
    assert req.messages[0].timestamp is None

def test_slash_handler_update_persona():
    from backend.services.slash_handler import handle_slash_command
    class DummyPayload:
        current_file_path = None
        persona_type = "simplified"

    res = handle_slash_command("/update_persona", DummyPayload(), "/update_persona", [])
    assert res is not None
    assert hasattr(res, "body_iterator")



def test_chat_request_atmosphere_mode():
    # 验证 ChatRequest 默认 atmosphere_mode 为 daily，且支持 study
    req_default = ChatRequest(messages=[Message(role="user", content="hello")])
    assert req_default.atmosphere_mode == "daily"

    req_study = ChatRequest(messages=[Message(role="user", content="hello")], atmosphere_mode="study")
    assert req_study.atmosphere_mode == "study"


def test_system_context_and_mission_draft_respect_atmosphere_mode(mock_db_path):
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock
    from backend.main import app
    from backend.database import get_db_connection

    client = TestClient(app)

    res_study = client.post(
        "/api/chat/system_context",
        json={
            "messages": [{"role": "user", "content": "查看当前模式"}],
            "persona_type": "simplified",
            "atmosphere_mode": "study",
        },
    )
    assert res_study.status_code == 200
    assert "<active_atmosphere_mode>STUDY" in res_study.json()["system_prompt"]

    res_daily = client.post(
        "/api/chat/system_context",
        json={
            "messages": [{"role": "user", "content": "查看当前模式"}],
            "persona_type": "simplified",
            "atmosphere_mode": "daily",
        },
    )
    assert res_daily.status_code == 200
    assert "<active_atmosphere_mode>DAILY" in res_daily.json()["system_prompt"]

    # Active mission_draft must still forward payload.atmosphere_mode into handle_mission_interrogation
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO mission_draft (id, goal, is_active) VALUES (1, '测试课题', 1) "
            "ON CONFLICT(id) DO UPDATE SET goal = '测试课题', is_active = 1"
        )
        conn.commit()
    finally:
        conn.close()

    with patch("backend.services.slash_handler.handle_mission_interrogation") as mock_interrogation:
        from fastapi.responses import StreamingResponse
        mock_interrogation.return_value = StreamingResponse(iter(["data: [DONE]\n\n"]), media_type="text/event-stream")
        res_send = client.post(
            "/api/chat/send",
            json={
                "messages": [{"role": "user", "content": "每天1小时"}],
                "persona_type": "simplified",
                "atmosphere_mode": "study",
            },
        )
        assert res_send.status_code == 200
        assert mock_interrogation.called
        assert mock_interrogation.call_args.kwargs.get("atmosphere_mode") == "study"


def test_course_select_status_and_lesson_lock_guard(mock_db_path, tmp_path):
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from backend.main import app
    from backend.services.materials_manager import MaterialsManager
    from backend.services.mission_manager import MissionManager
    from backend.services.course_manager import (
        enter_lesson_lock,
        exit_lesson_lock,
        set_selected_course_id,
    )

    test_materials = str(tmp_path / "materials")
    with patch.object(MaterialsManager, "_get_materials_dir", return_value=test_materials):
        MissionManager.finalize_draft(
            "研读《滴天髓》原典",
            "每日50分钟",
            "名家批注",
            "零基础",
            course_id="ditiansui_bazi",
            course_name="滴天髓",
        )
        exit_lesson_lock()
        set_selected_course_id("default")

        client = TestClient(app)

        # Selecting a course off-class updates selected_course_id without mutating active_course_id
        res_sel = client.post("/api/chat/course/select", json={"course_id": "ditiansui_bazi"})
        assert res_sel.status_code == 200
        sel_data = res_sel.json()
        assert sel_data["selected_course_id"] == "ditiansui_bazi"
        assert sel_data["active_course_id"] == "default"
        assert sel_data["is_in_lesson"] is False

        # Status endpoint returns selected course's mission preview while showing default archive isolation
        res_status = client.get("/api/chat/status")
        assert res_status.status_code == 200
        st = res_status.json()
        assert st["selected_course_id"] == "ditiansui_bazi"
        assert st["active_course_id"] == "default"
        assert st["is_in_lesson"] is False
        assert "研读《滴天髓》原典" in st["mission"]["parsed_goal"]
        assert any(c["id"] == "ditiansui_bazi" for c in st["courses"])

        # During lesson lock, switching course via /course/select is rejected (409)
        enter_lesson_lock("ditiansui_bazi")
        res_blocked = client.post("/api/chat/course/select", json={"course_id": "default"})
        assert res_blocked.status_code == 409

        exit_lesson_lock()

        # Creating a course via KnowledgeLibrary endpoint syncs into /api/chat/status course list (1-to-1)
        res_create = client.post(
            "/api/chat/materials/courses/create",
            json={"course_id": "calc_advanced", "name": "高等微积分"},
        )
        assert res_create.status_code == 200
        status_courses = client.get("/api/chat/status").json()["courses"]
        lib_courses = client.get("/api/chat/materials/courses").json()["courses"]
        assert [(c["id"], c["name"]) for c in status_courses] == [(c["id"], c["name"]) for c in lib_courses]
