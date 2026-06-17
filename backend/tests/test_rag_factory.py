import pytest
from unittest.mock import patch, MagicMock

from backend.services.rag_factory import get_rag_client
from backend.services.ragflow_client import RAGFlowClient
from backend.services.chroma_client import ChromaRAGClient
from backend.services.external_rag_client import ExternalRAGClient

# 测试 1: 验证工厂返回的客户端是否都实现了 RAGClient 接口方法
@patch("backend.services.rag_factory.get_rag_config")
def test_ragflow_client_interface(mock_get_config):
    mock_get_config.return_value = {"backend_type": "ragflow"}
    client = get_rag_client()

    assert isinstance(client, RAGFlowClient)
    assert hasattr(client, "retrieve")
    assert hasattr(client, "sync_knowledge")
    assert hasattr(client, "get_sync_status")

    # 验证新增加的代理方法
    assert hasattr(client, "save_memory")
    assert hasattr(client, "retrieve_memory")

    # 验证不支持内存高频写入的后端是否安全返回 False 和空列表
    assert client.save_memory("user", "assistant") is False
    assert client.retrieve_memory("query") == []

@patch("backend.services.rag_factory.get_rag_config")
def test_external_client_interface(mock_get_config):
    mock_get_config.return_value = {"backend_type": "external"}
    client = get_rag_client()

    assert isinstance(client, ExternalRAGClient)
    assert hasattr(client, "save_memory")
    assert hasattr(client, "retrieve_memory")

    assert client.save_memory("user", "assistant") is False
    assert client.retrieve_memory("query") == []

@patch("backend.services.rag_factory.get_rag_config")
def test_chroma_client_interface(mock_get_config):
    mock_get_config.return_value = {"backend_type": "chromadb"}
    client = get_rag_client()

    assert isinstance(client, ChromaRAGClient)
    assert hasattr(client, "save_memory")
    assert hasattr(client, "retrieve_memory")

    # 我们不需要在这里测试 Chroma 的实际写入，只测试它有这个方法即可

# 测试 2: 验证各个客户端的 retrieve 方法返回的都是 List[str] 格式
def test_ragflow_retrieve_returns_list():
    client = RAGFlowClient()
    # 模拟 httpx.Client().post 返回
    with patch("httpx.Client.post") as mock_post, patch("backend.services.ragflow_client.RAGFlowClient._get_or_create_dataset", return_value="ds-123"):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"chunks": [{"content": "chunk1"}, {"content": "chunk2"}]}}
        mock_post.return_value = mock_resp

        # 强制给个假 key 以通过检查
        with patch.dict("os.environ", {"RAGFLOW_API_KEY": "fake_key"}):
            results = client.retrieve("test query")
            assert isinstance(results, list)
            assert len(results) == 2
            assert results[0] == "chunk1"

def test_external_retrieve_returns_list():
    client = ExternalRAGClient(base_url="http://test", api_key="test")
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"chunks": ["chunk1", "chunk2"]}
        mock_post.return_value = mock_resp

        results = client.retrieve("test query")
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0] == "chunk1"
