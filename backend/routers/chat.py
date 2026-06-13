import logging
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

from backend.database import get_db_connection
from backend.services.model_router import stream_chat
from backend.services.prompts import get_system_prompt
from backend.services.rag_factory import get_rag_client, save_memory_to_rag, retrieve_memory
from backend.services.slash_handler import handle_slash_command

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona_type: str = "simplified"
    current_file_path: str = ""

def json_escape(text: str) -> str:
    """包装为 JSON 字符串，便于前端原样解析"""
    return json.dumps({"text": text}, ensure_ascii=False)

@router.post("/send")
def send_message(payload: ChatRequest):
    """发送对话消息，返回流式 EventSource"""
    # 提取最后一条用户消息
    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    
    # 1. 转换消息格式
    formatted_messages = [{"role": msg.role, "role_original": msg.role, "content": msg.content} for msg in payload.messages]
    cleaned_messages = [{"role": m["role"], "content": m["content"]} for m in formatted_messages]
    
    # 拦截斜杠指令
    clean_msg = last_user_msg.strip()
    if clean_msg.startswith('/') or clean_msg in ("更新人设",):
        return handle_slash_command(clean_msg, payload, last_user_msg, cleaned_messages)

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
    rag_context = ""
    if last_user_msg:
        try:
            rag_client = get_rag_client()
            kb_context = rag_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge", "Memory_Knowledge"])
            mem_context = retrieve_memory(last_user_msg, n_results=3)
            parts = [p for p in [kb_context, mem_context] if p]
            rag_context = "\n\n".join(parts)
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value, payload.persona_type)
    if rag_context:
        system_prompt += f"\n\n【附加背景知识库检索结果（作为世界观或讲义参考）】\n{rag_context}\n\n（请结合以上背景知识进行回答，若相关则自然地融入你的话语中，若无关则忽略）"

    def event_generator():
        accumulated_assistant_content = ""
        try:
            content_stream = stream_chat(cleaned_messages, system_prompt)
            for chunk in content_stream:
                accumulated_assistant_content += chunk
                yield f"data: {json_escape(chunk)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"
        finally:
            # 流式结束时，将用户最后一条消息和助手的回复写入短期记忆 (Level 0)
            if last_user_msg and accumulated_assistant_content:
                try:
                    memory_content = f"【对话记录】\n用户：{last_user_msg}\n媚吻锋：{accumulated_assistant_content}"
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')",
                        (memory_content,)
                    )
                    conn.commit()
                    conn.close()
                    save_memory_to_rag(last_user_msg, accumulated_assistant_content, level=0)
                except Exception as e:
                    logger.error(f"Failed to save memory: {e}")
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


