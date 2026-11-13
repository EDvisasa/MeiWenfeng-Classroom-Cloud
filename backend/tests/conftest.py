import pytest
from unittest.mock import patch

@pytest.fixture
def mock_get_active_course():
    with patch('backend.mcp_server.get_active_course') as mock_get:
        yield mock_get

@pytest.fixture
def mock_append_to_syllabus():
    with patch('backend.mcp_server.append_to_syllabus') as mock_append:
        yield mock_append

@pytest.fixture(autouse=True)
def mock_db_path(tmp_path):
    db_file = tmp_path / "test.db"
    with patch("backend.database.DB_PATH", str(db_file)):
        from backend.database import init_db
        init_db()
        yield str(db_file)

@pytest.fixture(autouse=True)
def isolate_chroma_db(tmp_path, monkeypatch):
    """
    【全域隔离】默认将 ChromaDB 向量库重定向到独立临时测试目录 (tmp_path/test_chroma)。
    物理切断任何单测连接生产向量库 (rag_index/chroma) 的可能。
    """
    test_chroma_dir = str(tmp_path / "test_chroma")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", test_chroma_dir)
    monkeypatch.setenv("TESTING", "1")
    from backend.services.chroma_client import chroma_rag_client
    with chroma_rag_client._lock:
        chroma_rag_client._client = None
        chroma_rag_client._active_dir = None
    yield test_chroma_dir
    with chroma_rag_client._lock:
        chroma_rag_client._client = None
        chroma_rag_client._active_dir = None

@pytest.fixture
def mock_rag_client(monkeypatch):
    """
    【零触碰 Mock】完全不启动 ChromaDB 进程、不加载模型权重的轻量 Mock。
    适用于绝大多数只需模拟 RAG 返回结果的快速单测。
    """
    from unittest.mock import MagicMock
    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = []
    mock_rag.retrieve_memory.return_value = []
    mock_rag.save_memory.return_value = "mock_doc_id_999"
    mock_rag.delete_memory.return_value = True
    mock_rag.sync_knowledge.return_value = {"status": "success", "chunks": 0}
    mock_rag.get_sync_status.return_value = {"status": "synced"}
    monkeypatch.setattr("backend.services.rag_factory.get_rag_client", lambda: mock_rag)
    monkeypatch.setattr("backend.services.chroma_client.chroma_rag_client", mock_rag)
    return mock_rag
