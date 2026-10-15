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
    
    # Verify image_url is preserved
    types = [item.get("type") for item in user_msg["content"] if isinstance(item, dict)]
    assert "text" in types
    assert "image_url" in types
    
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
