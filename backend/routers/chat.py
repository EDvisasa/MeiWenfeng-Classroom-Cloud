import logging
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

from backend.database import get_db_connection
from backend.services.character_state import CharacterStateManager, CharacterStateError
from backend.services.model_router import stream_chat
from backend.services.memory_decay import check_decay_needed, process_memory_decay
from backend.services.prompts import get_system_prompt
from backend.services.rag_factory import get_rag_client
from backend.services.slash_handler import handle_slash_command
from backend.services.response_pipeline import ResponsePipeline, json_escape
from backend.services.action_registry import action_registry
import tiktoken

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
    custom_max_tokens: int = 8192

def _build_full_system_prompt(payload: ChatRequest, original_last_user_msg: str):
    # 2. 从数据库加载好感度和动态属性，用于拼接 System Prompt
    try:
        state = CharacterStateManager.get_state()
        affection_value = state.affection
        social_status = state.social_status
        social_skills = state.social_skills
        refractory_period = state.refractory_period
    except CharacterStateError as e:
        logger.error(f"Failed to fetch character state in chat router: {e}")
        affection_value = 50
        social_status = 50
        social_skills = 50
        refractory_period = 0

    # 提取最后一条用户消息用于 RAG 检索
    rag_context = ""
    recent_memory_text = ""
    kb_count = 0
    mem_count = 0

    # 提取最近几天的明确摘要（弥补向量数据库按时间检索的劣势）
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, summary FROM memory_logs WHERE level IN (1, 2) ORDER BY timestamp DESC LIMIT 3")
        recent_logs = cursor.fetchall()
        conn.close()
        if recent_logs:
            recent_memory_text = "【近期日记摘要（优先级最高，包含最近2-3天的确切记忆）】\n" + "\n---\n".join([f"[{r['timestamp'].split()[0]}] {r['summary']}" for r in reversed(recent_logs)])
    except Exception as e:
        logger.error(f"Failed to fetch recent memory logs: {e}")

    if original_last_user_msg:
        try:
            rag_client = get_rag_client()
            kb_chunks = rag_client.retrieve(original_last_user_msg, dataset_names=["Classroom_Knowledge"])
            mem_chunks_from_kb = rag_client.retrieve(original_last_user_msg, dataset_names=["Memory_Knowledge"])
            mem_chunks_raw = rag_client.retrieve_memory(original_last_user_msg, n_results=3)

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

    system_prompt = get_system_prompt(affection_value, payload.persona_type, social_status, social_skills, refractory_period)

    if payload.current_file_path:
        import os
        filename = os.path.basename(payload.current_file_path)
        line_str = f"Line {payload.cursor_line}" if payload.cursor_line > 0 else "Unknown"
        system_prompt += f"\n\n<ide_context>\nThe user is currently viewing the following file in their VS Code editor:\n- File Name: {filename}\n- Absolute Path: {payload.current_file_path}\n- Cursor Position: {line_str}\nYou should use this context implicitly if the user asks about 'this file' or 'here'.\n</ide_context>"

    if recent_memory_text or rag_context:
        system_prompt += "\n\n"
        if recent_memory_text:
            system_prompt += f"{recent_memory_text}\n\n"
        if rag_context:
            system_prompt += f"【附加背景知识库检索结果（作为世界观或长程记忆参考）】\n{rag_context}\n\n"
        system_prompt += "（请结合以上近期日记和背景知识进行回答，保证时间线和记忆的连贯性）"

    return system_prompt, kb_count, mem_count

@router.post("/system_context")
def get_system_context(payload: ChatRequest):
    """前端调用以获取当前状态下隐藏上下文（系统设定、RAG、好感度等）所占用的准确 Token 数"""
    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    system_prompt, _, _ = _build_full_system_prompt(payload, last_user_msg)
    
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = len(encoding.encode(system_prompt))
    except Exception as e:
        logger.error(f"tiktoken fallback: {e}")
        tokens = len(system_prompt) // 4
        
    return {"status": "success", "baseSystemTokens": tokens}

@router.post("/send")
def send_message(payload: ChatRequest):
    """发送对话消息，返回流式 EventSource"""
    # 提取最后一条用户消息
    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    original_last_user_msg = last_user_msg

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
    # 匹配以 @ 开头的任何路径（绝对或相对，遇到空格结束）
    path_matches = list(re.finditer(r'@([^\s<>"]+)', last_user_msg))
    for match in path_matches:
        full_match = match.group(0)
        file_path = match.group(1)

        resolved_path = None
        if os.path.exists(file_path) and os.path.isfile(file_path):
            resolved_path = file_path
        elif payload.current_file_path and not os.path.isabs(file_path):
            # Try to resolve relative path by searching upwards from current_file_path
            curr_dir = os.path.dirname(payload.current_file_path)
            while curr_dir and curr_dir != os.path.dirname(curr_dir):
                candidate = os.path.join(curr_dir, file_path)
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    resolved_path = candidate
                    break
                curr_dir = os.path.dirname(curr_dir)

        if resolved_path:
            file_path = resolved_path
            try:
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
                        file_content = f.read(20000)
                        if f.read(1):
                            file_content += "\n\n...[文件内容过大，已自动截断。如果您需要分析全部文本，请主动调用 `grep_search` 或 `read_file` 工具继续探索。]"

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

    system_prompt, kb_count, mem_count = _build_full_system_prompt(payload, original_last_user_msg)

    pipeline = ResponsePipeline(registry=action_registry)
    pipeline.original_user_msg = original_last_user_msg

    def event_generator():
        try:
            if kb_count > 0 or mem_count > 0:
                parts = []
                if kb_count > 0: parts.append(f"{kb_count} 个讲义片段")
                if mem_count > 0: parts.append(f"{mem_count} 个长期记忆")
                hint_text = f"🔍 成功检索并加载：{' 和 '.join(parts)}"
                yield f"data: {json.dumps({'type': 'system_hint', 'text': hint_text}, ensure_ascii=False)}\n\n"

            content_stream = stream_chat(cleaned_messages, system_prompt, max_tokens=payload.custom_max_tokens)
            yield from pipeline.process_stream(content_stream)
        except Exception as e:
            import traceback
            with open("debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"CRASH CAUGHT: {type(e).__name__}: {str(e)}\n")
                traceback.print_exc(file=f)
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
