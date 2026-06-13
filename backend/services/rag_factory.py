"""
RAG 工厂模块 —— 根据数据库中的 rag_config 动态返回当前激活的 RAG 客户端实例。

支持的后端类型：
  - "chromadb"  → ChromaRAGClient  (本地向量库，默认)
  - "ragflow"   → RAGFlowClient    (需要 RAGFlow Docker 服务在线)
  - "external"  → ExternalRAGClient (自定义外部 RAG API 接口)
"""
from __future__ import annotations
from typing import Dict, Any, Optional, List


def get_rag_config() -> Dict[str, Any]:
    """从 SQLite 读取当前 RAG 配置"""
    from backend.database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rag_config WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass
    # 默认回退
    return {
        "backend_type": "chromadb",
        "ragflow_url": "http://localhost/api/v1",
        "ragflow_key": "",
        "external_url": "",
        "external_key": ""
    }


def get_rag_client():
    """动态返回当前配置对应的 RAG 客户端实例"""
    config = get_rag_config()
    backend_type = config.get("backend_type", "chromadb")
    
    if backend_type == "ragflow":
        import os
        os.environ["RAGFLOW_BASE_URL"] = config.get("ragflow_url", "")
        os.environ["RAGFLOW_API_KEY"] = config.get("ragflow_key", "")
        from backend.services.ragflow_client import RAGFlowClient
        return RAGFlowClient()
    
    elif backend_type == "external":
        from backend.services.external_rag_client import ExternalRAGClient
        return ExternalRAGClient(
            base_url=config.get("external_url", ""),
            api_key=config.get("external_key", "")
        )
    
    else:  # "chromadb" (default)
        from backend.services.chroma_client import chroma_rag_client
        return chroma_rag_client


def save_memory_to_rag(user_msg: str, assistant_msg: str, level: int = 0) -> bool:
    """
    把对话存入当前 RAG 后端的记忆存储。
    - chromadb 后端：直接写入 conversation_memory collection
    - ragflow / external 后端：降级到仅写 SQLite（RAGFlow 本身不适合高频写入）
    """
    config = get_rag_config()
    backend_type = config.get("backend_type", "chromadb")
    
    if backend_type == "chromadb":
        from backend.services.chroma_client import chroma_rag_client
        return chroma_rag_client.save_memory(user_msg, assistant_msg, level)
    
    # 其他后端不支持高频写入，只存 SQLite（由调用方保证）
    return False


def retrieve_memory(query: str, n_results: int = 3) -> list:
    """从当前 RAG 后端检索对话记忆（只对 chromadb 有实际效果）"""
    config = get_rag_config()
    backend_type = config.get("backend_type", "chromadb")
    
    if backend_type == "chromadb":
        from backend.services.chroma_client import chroma_rag_client
        return chroma_rag_client.retrieve_memory(query, n_results)
    
    return []
