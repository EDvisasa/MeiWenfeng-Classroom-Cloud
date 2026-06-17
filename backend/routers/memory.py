import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from backend.database import get_db_connection
from backend.services.memory_decay import process_memory_decay

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["memory", "sessions"])

class Message(BaseModel):
    role: str
    content: str

class SessionSavePayload(BaseModel):
    id: str
    title: str
    messages: List[Message]

@router.post("/summarize")
def summarize_memory():
    """触发记忆压缩和遗忘算法"""
    try:
        stats = process_memory_decay()
        return {"status": "success", "message": "记忆压缩整理完成。", "stats": stats}
    except Exception as e:
        logger.error(f"Memory decay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
def get_sessions():
    """获取所有历史会话及其消息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取所有会话，按最后更新时间降序排列
        cursor.execute("SELECT id, title, updated_at FROM chat_sessions ORDER BY updated_at DESC")
        sessions = [dict(row) for row in cursor.fetchall()]
        
        for sess in sessions:
            cursor.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC", 
                (sess["id"],)
            )
            sess["messages"] = [dict(row) for row in cursor.fetchall()]
            
        conn.close()
        return sessions
    except Exception as e:
        logger.error(f"Failed to fetch sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/save")
def save_session(payload: SessionSavePayload):
    """保存或更新会话及其所有关联消息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. 插入或覆盖更新会话
        cursor.execute(
            "INSERT OR REPLACE INTO chat_sessions (id, title, updated_at) VALUES (?, ?, datetime('now'))",
            (payload.id, payload.title)
        )
        
        # 2. 删除原有的消息
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (payload.id,))
        
        # 3. 批量插入新消息
        for msg in payload.messages:
            cursor.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                (payload.id, msg.role, msg.content)
            )
            
        conn.commit()
        conn.close()
        return {"status": "success", "session_id": payload.id}
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """删除指定的聊天会话及其消息"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 删除会话和消息
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        
        conn.commit()
        conn.close()
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
