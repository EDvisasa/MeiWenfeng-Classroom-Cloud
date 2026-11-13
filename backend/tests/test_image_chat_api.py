import json
import pytest
from pydantic import ValidationError
from backend.routers.chat import ChatRequest, Message
from backend.services.context_manager import assemble_messages
from backend.routers.memory import save_session, get_sessions, SessionSavePayload, Message as MemoryMessage

def test_chat_request_with_images():
    data = {
        "messages": [
            {
                "role": "user",
                "content": "请分析这张图片中的代码",
                "images": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
                "timestamp": "2026-09-13T10:00:00"
            }
        ],
        "persona_type": "simplified"
    }
    req = ChatRequest.model_validate(data)
    assert len(req.messages) == 1
    assert req.messages[0].images is not None
    assert len(req.messages[0].images) == 1
    assert req.messages[0].images[0].startswith("data:image/png;base64,")

def test_assemble_messages_multimodal():
    multimodal_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "分析这张图"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}}
            ],
            "timestamp": "2026-09-13T10:00:00"
        }
    ]
    system_prompt = "You are Mei Wenfeng."
    assembled = assemble_messages(multimodal_messages, system_prompt)
    
    # Check that the system message and user message are present
    assert len(assembled) >= 2
    assert assembled[0]["role"] == "system"
    user_msg = assembled[-1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    
    # Verify image_url is preserved and strictly ordered BEFORE text (required by strata-poly / kvmem)
    types = [item.get("type") for item in user_msg["content"] if isinstance(item, dict)]
    assert "text" in types
    assert "image_url" in types
    assert types.index("image_url") < types.index("text")
    
    img_item = next(item for item in user_msg["content"] if item.get("type") == "image_url")
    assert img_item["image_url"]["url"] == "data:image/png;base64,xyz"
    
    # Verify text item received current_user_instruction injection
    text_item = next(item for item in user_msg["content"] if item.get("type") == "text")
    assert "<current_user_instruction>" in text_item["text"]
    assert "分析这张图" in text_item["text"]

def test_memory_session_save_and_retrieve_with_images():
    test_session_id = "test_image_session_unit_test"
    dummy_image = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    payload = SessionSavePayload(
        id=test_session_id,
        title="测试图片会话",
        messages=[
            MemoryMessage(
                role="user",
                content="请看这张图片",
                images=[dummy_image],
                timestamp="2026-09-13 10:00:00"
            ),
            MemoryMessage(
                role="assistant",
                content="收到，这是测试图片！",
                images=None,
                timestamp="2026-09-13 10:00:05"
            )
        ]
    )
    
    # Save session
    res = save_session(payload)
    assert res["status"] == "success"
    
    # Retrieve sessions
    all_sessions = get_sessions()
    saved = next((s for s in all_sessions if s["id"] == test_session_id), None)
    assert saved is not None
    assert len(saved["messages"]) == 2
    
    first_msg = saved["messages"][0]
    assert first_msg["role"] == "user"
    assert first_msg["content"] == "请看这张图片"
    assert isinstance(first_msg.get("images"), list)
    assert len(first_msg["images"]) == 1
    assert first_msg["images"][0] == dummy_image
    
    second_msg = saved["messages"][1]
    assert second_msg["role"] == "assistant"
    assert second_msg.get("images") == []
    
    # Cleanup
    from backend.routers.memory import delete_session
    delete_session(test_session_id)


def test_assemble_messages_image_only_places_text_after_image():
    """验证纯图片消息在尾部注入时，图片依然位于最前面，[图片输入] 文本必须排在图片后面"""
    multimodal_messages = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,onlyimg"}}],
        }
    ]
    assembled = assemble_messages(multimodal_messages, "You are Mei Wenfeng.")
    content = assembled[-1]["content"]
    types = [item.get("type") for item in content]
    assert types == ["image_url", "text"]
    assert "[图片输入]" in content[-1]["text"]


def test_send_message_multimodal_images_always_before_text(tmp_path, mock_rag_client):
    """验证 chat.py send_message 在 images 字段、@current_file 图片与 @path 图片三条路径下，均保证 image_url 排在 text 之前"""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    img_file = tmp_path / "sample.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    captured_messages = []

    def fake_stream_chat(messages, system_prompt, max_tokens=None, stream_controller=None):
        captured_messages.append(messages)
        yield {"type": "text", "text": "收到图片"}

    with patch("backend.routers.chat.stream_chat", side_effect=fake_stream_chat):
        # 1. Payload images 字段
        r1 = client.post("/api/chat/send", json={
            "session_id": "test-img-order-1",
            "messages": [{"role": "user", "content": "看这张上传的图", "images": ["data:image/png;base64,upload123"]}],
            "dry_run": True,
        })
        assert r1.status_code == 200

        # 2. @current_file 图片
        r2 = client.post("/api/chat/send", json={
            "session_id": "test-img-order-2",
            "messages": [{"role": "user", "content": "看 @current_file"}],
            "current_file_path": str(img_file),
            "dry_run": True,
        })
        assert r2.status_code == 200

        # 3. @path 图片
        r3 = client.post("/api/chat/send", json={
            "session_id": "test-img-order-3",
            "messages": [{"role": "user", "content": f"看 @{img_file}"}],
            "dry_run": True,
        })
        assert r3.status_code == 200

    assert len(captured_messages) == 3
    for msgs in captured_messages:
        last_content = msgs[-1]["content"]
        assert isinstance(last_content, list)
        types = [it.get("type") for it in last_content]
        assert "image_url" in types and "text" in types
        assert types.index("image_url") < types.index("text")
        assert types[-1] == "text"
