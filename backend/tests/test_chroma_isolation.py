import pytest
import os
from unittest.mock import patch, MagicMock

from backend.services.chroma_client import (
    ChromaRAGClient,
    DEFAULT_CHROMA_DIR,
    get_chroma_persist_dir,
)

def test_production_chroma_mutation_is_hard_blocked_in_test_env():
    """验证：在测试环境下，若指向生产向量库目录，任何写操作（save/delete/sync）必须被物理阻断抛出 RuntimeError"""
    client = ChromaRAGClient()

    with patch.dict(os.environ, {"CHROMA_PERSIST_DIR": DEFAULT_CHROMA_DIR, "TESTING": "1"}):
        with pytest.raises(RuntimeError) as exc_save:
            client.save_memory("测试用户", "测试回答")
        assert "全域红线拦截" in str(exc_save.value)

        with pytest.raises(RuntimeError) as exc_del:
            client.delete_memory("fake_doc_id")
        assert "全域红线拦截" in str(exc_del.value)

        with pytest.raises(RuntimeError) as exc_sync:
            client.sync_knowledge({"test.md": "content"})
        assert "全域红线拦截" in str(exc_sync.value)


def test_isolated_test_chroma_allows_safe_operations(tmp_path):
    """验证：重定向至独立测试目录时，路径被正确隔离在 tmp_path 内，绝不触碰生产目录"""
    client = ChromaRAGClient()
    test_dir = str(tmp_path / "custom_test_chroma")

    with patch.dict(os.environ, {"CHROMA_PERSIST_DIR": test_dir, "TESTING": "1"}):
        assert get_chroma_persist_dir() == os.path.abspath(test_dir)
        assert get_chroma_persist_dir() != os.path.abspath(DEFAULT_CHROMA_DIR)

        # 模拟底层 collection 行为，验证其安全执行通过
        mock_col = MagicMock()
        mock_col.upsert.return_value = None
        mock_col.delete.return_value = None
        with patch.object(client, "_get_collection", return_value=mock_col):
            doc_id = client.save_memory("你好", "测试回复", session_id="test-session")
            assert doc_id is not None
            assert mock_col.upsert.called

            success = client.delete_memory(doc_id)
            assert success is True
            assert mock_col.delete.called


def test_mock_rag_client_zero_touch(mock_rag_client):
    """验证：使用 mock_rag_client fixture 时，完全不碰 ChromaDB，毫秒级返回"""
    from backend.services.rag_factory import get_rag_client

    rag = get_rag_client()
    assert rag.retrieve("任何问题") == []
    assert rag.retrieve_memory("任何问题") == []
    doc_id = rag.save_memory("测试用户", "测试助手")
    assert doc_id == "mock_doc_id_999"
    assert rag.delete_memory(doc_id) is True


def test_retrieve_memory_excludes_rolled_back_sql_records(tmp_path):
    """验证读时兜底过滤：即使 Chroma 中仍残留向量，只要 SQLite memory_logs 为 rolled_back，retrieve_memory 也不予召回"""
    from backend.database import get_db_connection

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO memory_logs (content, level, status, session_id, chroma_doc_id) VALUES (?, 0, 'rolled_back', 's1', 'doc_rb_1')",
        ("已被撤回的假记忆",),
    )
    conn.execute(
        "INSERT INTO memory_logs (content, level, status, session_id, chroma_doc_id) VALUES (?, 0, 'active', 's1', 'doc_ok_1')",
        ("正常的有效记忆",),
    )
    conn.commit()
    conn.close()

    rag = ChromaRAGClient()
    mock_col = MagicMock()
    mock_col.count.return_value = 2
    mock_col.query.return_value = {
        "ids": [["doc_rb_1", "doc_ok_1"]],
        "documents": [["【对话记录】已撤回内容", "【对话记录】正常有效内容"]],
        "distances": [[0.22, 0.35]],
    }
    with patch.object(rag, "_get_collection", return_value=mock_col):
        docs = rag.retrieve_memory("测试查询", n_results=3)

    assert docs == ["【对话记录】正常有效内容"]
