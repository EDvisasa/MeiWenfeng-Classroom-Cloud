import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection

client = TestClient(app)

def test_rollback_step_temporal_drift_protection():
    """
    测试时序漂移保护机制：
    若传入的 expected 消息与数据库尾部不一致，必须返回 409 且不得删除任何数据。
    """
    session_id = "test_drift_session"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO chat_sessions (id, title) VALUES (?, ?)", (session_id, "漂移测试"))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '第一条提问')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '第一条回答')", (session_id,))
    conn.commit()
    conn.close()

    # 尝试用错误的期望内容回滚
    payload = {
        "expected_user_msg": "完全不相干的提问",
        "expected_assistant_msg": "第一条回答"
    }
    resp = client.post(f"/api/chat/sessions/{session_id}/rollback_step", json=payload)
    assert resp.status_code == 409
    assert "时序已漂移" in resp.json()["detail"]

    # 验证数据库数据毫发无损
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 2

def test_rollback_step_success_soft_invalidates_memory_and_deletes_chroma():
    """
    测试单步回滚成功流：
    1. chat_messages 尾部一轮对话被精准删除；
    2. memory_logs 对应记录被软标记为 'rolled_back'；
    3. ChromaDB 向量切片被物理调用删除。
    """
    session_id = "test_rollback_success"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO chat_sessions (id, title) VALUES (?, ?)", (session_id, "回滚测试"))
    # Turn 1
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '历史问题 1')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '历史回答 1')", (session_id,))
    # Turn 2 (尾部，即将被回滚)
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '需要撤回的问题 2')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '需要撤回的回答 2')", (session_id,))
    
    # 模拟 Turn 2 的 memory_logs
    doc_id = "chroma_doc_to_delete_999"
    cursor.execute(
        "INSERT INTO memory_logs (content, level, status, session_id, chroma_doc_id) VALUES (?, 0, 'active', ?, ?)",
        ("【对话记录】用户：需要撤回的问题 2\n媚吻锋：需要撤回的回答 2", session_id, doc_id)
    )
    mem_log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    with patch("backend.services.rag_factory.get_rag_client") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.delete_memory.return_value = True
        mock_get_rag.return_value = mock_rag

        payload = {
            "expected_user_msg": "需要撤回的问题 2",
            "expected_assistant_msg": "需要撤回的回答 2"
        }
        resp = client.post(f"/api/chat/sessions/{session_id}/rollback_step", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["invalidated_memory_id"] == mem_log_id
        assert data["deleted_chroma"] is True
        assert data["remaining_messages"] == 2
        mock_rag.delete_memory.assert_called_once_with(doc_id)

    # 验证 SQLite 中数据状态
    conn = get_db_connection()
    cursor = conn.cursor()
    # 1. chat_messages 仅剩下 Turn 1
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    msgs = cursor.fetchall()
    assert len(msgs) == 2
    assert msgs[0]["content"] == "历史问题 1"
    assert msgs[1]["content"] == "历史回答 1"

    # 2. memory_logs 软标记为 rolled_back
    cursor.execute("SELECT status FROM memory_logs WHERE id = ?", (mem_log_id,))
    status = cursor.fetchone()[0]
    assert status == "rolled_back"

    # 3. 验证 active 状态的记忆中不再包含该记录（防止被召回或压缩）
    cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE id = ? AND status = 'active'", (mem_log_id,))
    assert cursor.fetchone()[0] == 0
    conn.close()

def test_rollback_empty_session():
    """
    当会话中无可回滚消息时，返回 400 友好报错。
    """
    session_id = "empty_session"
    resp = client.post(f"/api/chat/sessions/{session_id}/rollback_step", json={})
    assert resp.status_code == 400
    assert "无" in resp.json()["detail"]

def test_pipeline_e2e_memory_logging_and_rollback():
    """
    测试 ResponsePipeline 生成副作用、写入 session_id/chroma_doc_id，
    并随后被 rollback_step 成功级联回滚的端到端闭环。
    """
    from backend.services.response_pipeline import ResponsePipeline
    session_id = "sess_pipeline_e2e"

    with patch("backend.services.response_pipeline.get_rag_client") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.save_memory.return_value = "chroma_doc_e2e_777"
        mock_rag.delete_memory.return_value = True
        mock_get_rag.return_value = mock_rag

        pipeline = ResponsePipeline(session_id=session_id)
        pipeline.original_user_msg = "端到端提问测试"

        def dummy_stream():
            yield "端到端"
            yield "回答内容"

        # 消费流以触发副作用保存
        list(pipeline.process_stream(dummy_stream()))

        # 验证 memory_logs 确实记录了 session_id 和 chroma_doc_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, session_id, chroma_doc_id, status FROM memory_logs WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        assert row is not None
        mem_id = row["id"]
        assert row["session_id"] == session_id
        assert row["chroma_doc_id"] == "chroma_doc_e2e_777"
        assert row["status"] == "active"

        # 模拟该条消息在 chat_messages 中的存在
        cursor.execute("INSERT OR REPLACE INTO chat_sessions (id, title) VALUES (?, ?)", (session_id, "E2E测试"))
        cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '端到端提问测试')", (session_id,))
        cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '端到端回答内容')", (session_id,))
        conn.commit()
        conn.close()

        # 调用回滚接口
        with patch("backend.services.rag_factory.get_rag_client", return_value=mock_rag):
            resp = client.post(f"/api/chat/sessions/{session_id}/rollback_step", json={
                "expected_user_msg": "端到端提问测试",
                "expected_assistant_msg": "端到端回答内容"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["invalidated_memory_id"] == mem_id
            assert data["deleted_chroma"] is True
            mock_rag.delete_memory.assert_called_once_with("chroma_doc_e2e_777")

        # 再次核对 memory_logs 状态
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM memory_logs WHERE id = ?", (mem_id,))
        assert cursor.fetchone()[0] == "rolled_back"
        conn.close()

def test_rollback_step_with_interspersed_system_info_and_multiple_turns():
    """
    测试当消息队列中夹杂 system_info（如检索提示）时，
    单次回滚能穿透删除整轮（User+System+Asst），
    且精准只软标记失效当前轮次的 memory_logs，绝不波及上一轮记忆！
    """
    session_id = "sess_sys_info_isolation"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO chat_sessions (id, title) VALUES (?, ?)", (session_id, "隔离测试"))

    # Turn 1
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '第一轮用户提问')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'system_info', '🔍 成功检索并加载：4 个讲义片段')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '第一轮助手回答')", (session_id,))
    cursor.execute(
        "INSERT INTO memory_logs (content, level, status, session_id, chroma_doc_id) VALUES (?, 0, 'active', ?, ?)",
        ("【对话记录】\n用户：第一轮用户提问\n媚吻锋：第一轮助手回答", session_id, "doc_turn_1")
    )
    turn1_mem_id = cursor.lastrowid

    # Turn 2 (尾部，即将被回滚)
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'user', '第二轮待回滚用户提问')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'system_info', '🔍 成功检索并加载：7 个长期记忆')", (session_id,))
    cursor.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (?, 'assistant', '第二轮待回滚助手回答')", (session_id,))
    cursor.execute(
        "INSERT INTO memory_logs (content, level, status, session_id, chroma_doc_id) VALUES (?, 0, 'active', ?, ?)",
        ("【对话记录】\n用户：第二轮待回滚用户提问\n媚吻锋：第二轮待回滚助手回答", session_id, "doc_turn_2")
    )
    turn2_mem_id = cursor.lastrowid
    conn.commit()
    conn.close()

    with patch("backend.services.rag_factory.get_rag_client") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.delete_memory.return_value = True
        mock_get_rag.return_value = mock_rag

        resp = client.post(f"/api/chat/sessions/{session_id}/rollback_step", json={
            "expected_user_msg": "第二轮待回滚用户提问",
            "expected_assistant_msg": "第二轮待回滚助手回答"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["invalidated_memory_id"] == turn2_mem_id
        assert data["remaining_messages"] == 3
        mock_rag.delete_memory.assert_called_once_with("doc_turn_2")

    conn = get_db_connection()
    cursor = conn.cursor()
    # 验证 Turn 1 记忆依然完好且 active
    cursor.execute("SELECT status FROM memory_logs WHERE id = ?", (turn1_mem_id,))
    assert cursor.fetchone()[0] == "active"

    # 验证 Turn 2 记忆被软失效为 rolled_back
    cursor.execute("SELECT status FROM memory_logs WHERE id = ?", (turn2_mem_id,))
    assert cursor.fetchone()[0] == "rolled_back"

    # 验证剩余消息仅剩 Turn 1 的 3 条消息
    cursor.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    remaining = cursor.fetchall()
    assert len(remaining) == 3
    assert remaining[0]["role"] == "user"
    assert remaining[0]["content"] == "第一轮用户提问"
    assert remaining[1]["role"] == "system_info"
    assert remaining[2]["role"] == "assistant"
    assert remaining[2]["content"] == "第一轮助手回答"
    conn.close()


