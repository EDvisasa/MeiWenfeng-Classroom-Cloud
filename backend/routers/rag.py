import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from backend.database import get_db_connection
from backend.services.rag_factory import get_rag_client

router = APIRouter(prefix="/api/chat", tags=["rag", "knowledge"])

class SyncRequest(BaseModel):
    files: Dict[str, str]

@router.post("/sync_knowledge")
def sync_knowledge(payload: SyncRequest):
    """同步前端知识库文件到当前 RAG 后端"""
    rag_client = get_rag_client()
    result = rag_client.sync_knowledge(payload.files)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

class SyncFileRequest(BaseModel):
    file_path: str
    dataset_name: str = "Classroom_Knowledge"

@router.post("/files/sync")
def sync_file(payload: SyncFileRequest):
    file_path = os.path.abspath(payload.file_path)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        filename = os.path.basename(file_path)
        rag_client = get_rag_client()
        result = rag_client.sync_knowledge({filename: content}, dataset_name=payload.dataset_name)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/sync_status")
def get_sync_status_api(dataset_name: str = "Classroom_Knowledge"):
    rag_client = get_rag_client()
    result = rag_client.get_sync_status(dataset_name)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

# ── RAG 配置端点 ────────────────────────────────────────────────────

class RagConfigUpdate(BaseModel):
    backend_type: str  # "chromadb" | "ragflow" | "external"
    ragflow_url: str = ""
    ragflow_key: str = ""
    external_url: str = ""
    external_key: str = ""

@router.get("/rag/config")
def get_rag_config_api():
    """获取当前 RAG 后端配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rag_config WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return {"backend_type": "chromadb", "ragflow_url": "", "ragflow_key": "", "external_url": "", "external_key": ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rag/update")
def update_rag_config(payload: RagConfigUpdate):
    """保存 RAG 后端配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 如果行不存在则插入，否则更新
        cursor.execute("SELECT COUNT(*) FROM rag_config")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO rag_config (id, backend_type, ragflow_url, ragflow_key, external_url, external_key) VALUES (1, ?, ?, ?, ?, ?)",
                (payload.backend_type, payload.ragflow_url, payload.ragflow_key, payload.external_url, payload.external_key)
            )
        else:
            cursor.execute(
                """UPDATE rag_config SET backend_type=?, ragflow_url=?, ragflow_key=?, external_url=?, external_key=? WHERE id=1""",
                (payload.backend_type, payload.ragflow_url, payload.ragflow_key, payload.external_url, payload.external_key)
            )
        conn.commit()
        conn.close()
        return {"status": "success", "backend_type": payload.backend_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
