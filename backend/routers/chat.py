import logging
import asyncio
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.services.model_router import stream_chat, get_active_model
from backend.services.prompts import get_system_prompt
from backend.database import get_db_connection
from backend.services.ragflow_client import ragflow_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@router.post("/send")
async def send_message(payload: ChatRequest):
    """发送对话消息，返回流式 EventSource"""
    # 1. 转换消息格式
    formatted_messages = [{"role": msg.role, "role_original": msg.role, "content": msg.content} for msg in payload.messages]
    
    # 2. 从数据库加载好感度，用于拼接 System Prompt
    affection_value = 100
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        row = cursor.fetchone()
        if row:
            affection_value = row["value"]
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch affection: {e}")

    # 提取最后一条用户消息用于 RAG 检索
    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    rag_context = ""
    if last_user_msg:
        try:
            rag_context = await ragflow_client.retrieve(last_user_msg)
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value)
    if rag_context:
        system_prompt += f"\n\n【附加背景知识库检索结果（作为世界观或讲义参考）】\n{rag_context}\n\n（请结合以上背景知识进行回答，若相关则自然地融入你的话语中，若无关则忽略）"

    # 3. 剥离消息以满足 model_router 要求的格式 (role, content)
    cleaned_messages = [{"role": m["role"], "content": m["content"]} for m in formatted_messages]

    def event_generator():
        # 用 stream_chat 获取生成器
        content_stream = stream_chat(cleaned_messages, system_prompt)
        for chunk in content_stream:
            # 采用 event-stream 格式： "data: {chunk}\n\n"
            # 替换换行符，防破坏 EventSource 协议，但可以直接传原始文本，在前端按行拼接
            yield f"data: {json_escape(chunk)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

def json_escape(text: str) -> str:
    """包装为 JSON 字符串，便于前端原样解析"""
    return json.dumps({"text": text}, ensure_ascii=False)

class SyncRequest(BaseModel):
    files: Dict[str, str]

@router.post("/sync_knowledge")
async def sync_knowledge(payload: SyncRequest):
    """同步前端知识库文件到 RAGFlow"""
    result = await ragflow_client.sync_knowledge(payload.files)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@router.get("/models")
def list_models():
    """获取所有模型配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, protocol, base_url, is_active FROM model_config")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/switch_model")
def switch_model(payload: Dict[str, Any] = Body(...)):
    """切换当前激活的模型"""
    model_id = payload.get("id")
    if model_id is None:
        raise HTTPException(status_code=400, detail="Missing model 'id' in request body")
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 先将所有模型设为不激活
        cursor.execute("UPDATE model_config SET is_active = 0")
        # 将选中的模型设为激活
        cursor.execute("UPDATE model_config SET is_active = 1 WHERE id = ?", (model_id,))
        conn.commit()
        
        # 获取最新的激活模型
        cursor.execute("SELECT name FROM model_config WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Model not found")
            
        return {"status": "success", "active_model": row["name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
def get_status_summary():
    """获取右侧状态栏所需的课程进度和好感度数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取好感度
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        aff_row = cursor.fetchone()
        affection = aff_row["value"] if aff_row else 50
        
        # 获取当前激活的模型
        cursor.execute("SELECT name FROM model_config WHERE is_active = 1 LIMIT 1")
        model_row = cursor.fetchone()
        active_model = model_row["name"] if model_row else "未设置"
        
        # 获取课程大纲
        cursor.execute("SELECT id, phase, topic, status, score FROM course_progress")
        course_rows = cursor.fetchall()
        course_list = [dict(r) for r in course_rows]
        
        conn.close()
        return {
            "affection": affection,
            "active_model": active_model,
            "course_progress": course_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update_affection")
def update_affection(payload: Dict[str, Any] = Body(...)):
    """更新好感度值（主要是由斜杠命令 /奖励 或者课后触发）"""
    delta = payload.get("delta", 0)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO affection (id, value, last_updated) VALUES (1, 50, datetime('now'))")
            current = 50
        else:
            current = row["value"]
            
        new_val = max(0, min(100, current + delta))
        cursor.execute("UPDATE affection SET value = ?, last_updated = datetime('now') WHERE id = 1")
        conn.commit()
        conn.close()
        return {"status": "success", "affection": new_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/images")
def list_character_images():
    """获取本地目录下所有角色图片文件名"""
    import os
    IMAGE_DIR = "D:/Games/AI小说文档/01-SillyTarern文件/01-[roll点开局·遇仙记]/02-角色卡/00-[自创]遇仙记/02-媚吻锋/00-图片资源/正常"
    if not os.path.exists(IMAGE_DIR):
        return []
    try:
        files = os.listdir(IMAGE_DIR)
        valid_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        img_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_extensions]
        # 排序以保证列表顺序一致
        img_files.sort()
        return img_files
    except Exception as e:
        logger.error(f"Error listing images: {e}")
        return []
