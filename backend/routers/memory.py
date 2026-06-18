import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from backend.database import get_db_connection
from backend.services.memory_decay import check_decay_needed
from backend.services.action_registry import action_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["memory", "sessions"])

class Message(BaseModel):
    role: str
    content: str

class SessionSavePayload(BaseModel):
    id: str
    title: str
    messages: List[Message]


from backend.services.memory_decay import check_decay_needed

@router.get("/check_decay")
def check_decay():
    """检查是否需要进行跨级记忆压缩 (Level 1及以上)"""
    try:
        needed = check_decay_needed(phase_b_only=True)
        return {"needed": needed}
    except Exception as e:
        logger.error(f"Check decay failed: {e}")
        return {"needed": False}

@router.post("/force_decay")
def force_decay():
    """强制执行跨级记忆压缩 (Level 1及以上)"""
    try:
        handler = action_registry.get_handler("memory_decay")
        if handler:
            handler.handle({"phase_a_only": False, "phase_b_only": True}, "")
        return {"status": "success", "message": "记忆压缩已触发"}
    except Exception as e:
        logger.error(f"Force decay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/summarize")
def summarize_memory():
    """触发记忆压缩和遗忘算法"""
    try:
        handler = action_registry.get_handler("memory_decay")
        if handler:
            handler.handle({}, "")
        return {"status": "success", "message": "记忆压缩整理完成。"}
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
