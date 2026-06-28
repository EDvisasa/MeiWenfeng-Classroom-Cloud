import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection

client = TestClient(app)

def test_save_session_preserves_tags():
    # 准备含有 <thought> 等标签的测试数据
    test_session_id = "test_session_123"
    test_title = "测试会话"
    test_messages = [
        {
            "role": "user",
            "content": "你好呀",
            "timestamp": "2026-06-28T12:00:00.000Z"
        },
        {
            "role": "assistant",
            "content": "<thought>\n这是一个测试思考过程。\n</thought>\n<inner_thought>\n内心独白测试\n</inner_thought>\n嗨，你好！<property_update affection_delta=\"1\" />",
            "timestamp": "2026-06-28T12:00:05.000Z"
        }
    ]

    payload = {
        "id": test_session_id,
        "title": test_title,
        "messages": test_messages
    }

    # 发送保存会话请求
    response = client.post("/api/chat/sessions/save", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "session_id": test_session_id}

    # 验证数据库中的确保存了含有标签的原始内容
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (test_session_id,))
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "你好呀"

    assert rows[1]["role"] == "assistant"
    # 验证标签是否被原样保留，并且没有任何删减
    expected_content = "<thought>\n这是一个测试思考过程。\n</thought>\n<inner_thought>\n内心独白测试\n</inner_thought>\n嗨，你好！<property_update affection_delta=\"1\" />"
    assert rows[1]["content"] == expected_content

    # 测试完成后，清理测试数据
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (test_session_id,))
    cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (test_session_id,))
    conn.commit()
    conn.close()
