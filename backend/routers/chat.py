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
    cursor_line: int = 0

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
    if clean_msg.startswith('/') or clean_msg in ("/update_persona",):
        return handle_slash_command(clean_msg, payload, last_user_msg, cleaned_messages)

    # 处理 @current_file
    if "@current_file" in last_user_msg and payload.current_file_path:
        try:
            import os
            if os.path.exists(payload.current_file_path) and os.path.isfile(payload.current_file_path):
                with open(payload.current_file_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
                
                # Replace "@current_file" with the file content in the last user message
                file_info = f"\n\n<file_content filename=\"{os.path.basename(payload.current_file_path)}\">\n{file_content}\n</file_content>\n"
                last_user_msg = last_user_msg.replace("@current_file", f"@current_file {file_info}")
                
                # Update the cleaned_messages for the AI
                for msg in reversed(cleaned_messages):
                    if msg["role"] == "user":
                        msg["content"] = msg["content"].replace("@current_file", f"@current_file {file_info}")
                        break
        except Exception as e:
            logger.error(f"Failed to read current file: {e}")

    # 处理任意绝对路径，例如 @D:\...\file.txt 或 @/Users/.../file.txt
    import re
    import os
    import base64
    # 匹配以 @ 开头的绝对路径（支持 Windows 和 Unix 风格，遇到空格结束）
    path_matches = list(re.finditer(r'@([a-zA-Z]:\\[^\s<>"]+|/[^\s<>"]+)', last_user_msg))
    for match in path_matches:
        full_match = match.group(0)
        file_path = match.group(1)
        
        try:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                ext = file_path.lower().split('.')[-1]
                if ext in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
                    # Image processing: vision multimodal format
                    with open(file_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode('utf-8')
                    mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else f"image/{ext}"
                    
                    replacement_text = f"<image_attached filename=\"{os.path.basename(file_path)}\"/>"
                    last_user_msg = last_user_msg.replace(full_match, replacement_text)
                    
                    for msg in reversed(cleaned_messages):
                        if msg["role"] == "user":
                            if isinstance(msg["content"], str):
                                msg["content"] = [
                                    {"type": "text", "text": msg["content"].replace(full_match, replacement_text)}
                                ]
                            else:
                                for item in msg["content"]:
                                    if item.get("type") == "text":
                                        item["text"] = item["text"].replace(full_match, replacement_text)
                            
                            msg["content"].append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_data}"}
                            })
                            break
                else:
                    # Text processing
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                    
                    file_info = f"\n\n<file_content filename=\"{os.path.basename(file_path)}\">\n{file_content}\n</file_content>\n"
                    last_user_msg = last_user_msg.replace(full_match, f"{full_match} {file_info}")
                    
                    for msg in reversed(cleaned_messages):
                        if msg["role"] == "user":
                            if isinstance(msg["content"], str):
                                msg["content"] = msg["content"].replace(full_match, f"{full_match} {file_info}")
                            else:
                                for item in msg["content"]:
                                    if item.get("type") == "text":
                                        item["text"] = item["text"].replace(full_match, f"{full_match} {file_info}")
                            break
        except Exception as e:
            logger.error(f"Failed to read mentioned file {file_path}: {e}")

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
    kb_count = 0
    mem_count = 0
    if last_user_msg:
        try:
            rag_client = get_rag_client()
            kb_chunks = rag_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge"])
            mem_chunks_from_kb = rag_client.retrieve(last_user_msg, dataset_names=["Memory_Knowledge"])
            mem_chunks_raw = retrieve_memory(last_user_msg, n_results=3)
            
            # 兼容旧版返回字符串的情况
            if isinstance(kb_chunks, str): kb_chunks = [kb_chunks] if kb_chunks else []
            if isinstance(mem_chunks_from_kb, str): mem_chunks_from_kb = [mem_chunks_from_kb] if mem_chunks_from_kb else []
            if isinstance(mem_chunks_raw, str): mem_chunks_raw = [mem_chunks_raw] if mem_chunks_raw else []
            
            kb_chunks = [p for p in kb_chunks if p]
            mem_chunks = [p for p in mem_chunks_from_kb + mem_chunks_raw if p]
            
            kb_count = len(kb_chunks)
            mem_count = len(mem_chunks)
            
            all_chunks = kb_chunks + mem_chunks
            if all_chunks:
                rag_context = "\n\n".join(all_chunks)
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value, payload.persona_type)
    
    if payload.current_file_path:
        import os
        filename = os.path.basename(payload.current_file_path)
        line_str = f"Line {payload.cursor_line}" if payload.cursor_line > 0 else "Unknown"
        system_prompt += f"\n\n<ide_context>\nThe user is currently viewing the following file in their VS Code editor:\n- File Name: {filename}\n- Absolute Path: {payload.current_file_path}\n- Cursor Position: {line_str}\nYou should use this context implicitly if the user asks about 'this file' or 'here'.\n</ide_context>"

    if rag_context:
        system_prompt += f"\n\n【附加背景知识库检索结果（作为世界观或讲义参考）】\n{rag_context}\n\n（请结合以上背景知识进行回答，若相关则自然地融入你的话语中，若无关则忽略）"

    def event_generator():
        accumulated_assistant_content = ""
        try:
            if kb_count > 0 or mem_count > 0:
                parts = []
                if kb_count > 0: parts.append(f"{kb_count} 个讲义片段")
                if mem_count > 0: parts.append(f"{mem_count} 个长期记忆")
                hint_text = f"🔍 成功检索并加载：{' 和 '.join(parts)}"
                yield f"data: {json.dumps({'type': 'system_hint', 'text': hint_text}, ensure_ascii=False)}\n\n"
                
            content_stream = stream_chat(cleaned_messages, system_prompt)
            for chunk in content_stream:
                if isinstance(chunk, dict):
                    if chunk.get("type") == "text" or "text" in chunk and not chunk.get("type"):
                        accumulated_assistant_content += chunk.get("text", "")
                    elif chunk.get("type") == "tool_output":
                        # Also accumulate tool output so it gets saved? No, usually tool outputs are separate messages.
                        pass
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                else:
                    accumulated_assistant_content += chunk
                    yield f"data: {json_escape(chunk)}\n\n"
        except BaseException as e:
            import traceback
            with open("debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"CRASH CAUGHT: {type(e).__name__}: {str(e)}\n")
                traceback.print_exc(file=f)
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


