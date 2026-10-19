import logging
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.database import get_db_connection
from backend.services.character_state import CharacterStateManager, CharacterStateError
from backend.services.model_router import stream_chat, get_active_model
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
    content: Optional[Any] = ""
    timestamp: Optional[str] = None
    images: Optional[List[str]] = None

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[Message]
    persona_type: Optional[str] = "simplified"
    current_file_path: Optional[str] = ""
    cursor_line: Optional[int] = 0
    selection_start_line: Optional[int] = 0
    selection_end_line: Optional[int] = 0
    selected_text: Optional[str] = ""
    custom_max_tokens: Optional[int] = 8192

def _build_full_system_prompt(payload: ChatRequest, original_last_user_msg: str):
    from backend.services.context_manager import build_base_system_prompt
    return build_base_system_prompt(
        last_user_msg=original_last_user_msg,
        current_file_path=payload.current_file_path,
        cursor_line=payload.cursor_line or 0,
        selection_start_line=payload.selection_start_line or 0,
        selection_end_line=payload.selection_end_line or 0,
        selected_text=payload.selected_text or "",
        persona_type=payload.persona_type or "default"
    )

@router.post("/system_context")
def get_system_context(payload: ChatRequest):
    """前端调用以获取当前状态下隐藏上下文（系统设定、RAG、好感度等）所占用的准确 Token 数"""
    raw_last = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    if isinstance(raw_last, list):
        last_user_msg = " ".join(item.get("text", "") for item in raw_last if isinstance(item, dict) and item.get("type") == "text")
    elif isinstance(raw_last, str):
        last_user_msg = raw_last
    else:
        last_user_msg = str(raw_last or "")

    system_prompt, _, _ = _build_full_system_prompt(payload, last_user_msg)
    from backend.services.context_manager import assemble_messages
    
    formatted_messages = [{"role": m.role, "content": m.content, "timestamp": m.timestamp, "images": m.images} for m in payload.messages]
    assembled = assemble_messages(formatted_messages, system_prompt)
    full_preview_prompt = "\n\n--- [Message Boundary] ---\n\n".join([
        f"[{m['role'].upper()}]\n{m['content'] if isinstance(m['content'], str) else json.dumps(m['content'], ensure_ascii=False)}"
        for m in assembled
    ])
    
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = len(encoding.encode(full_preview_prompt))
    except Exception as e:
        logger.error(f"tiktoken fallback: {e}")
        tokens = len(full_preview_prompt) // 4
        
    return {"status": "success", "baseSystemTokens": tokens, "system_prompt": full_preview_prompt}

@router.post("/send")
def send_message(payload: ChatRequest):
    """发送对话消息，返回流式 EventSource"""
    # 提取最后一条用户消息
    raw_last = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    if isinstance(raw_last, list):
        last_user_msg = " ".join(item.get("text", "") for item in raw_last if isinstance(item, dict) and item.get("type") == "text")
    elif isinstance(raw_last, str):
        last_user_msg = raw_last
    else:
        last_user_msg = str(raw_last or "")
    original_last_user_msg = last_user_msg

    # 1. 转换消息格式并注入用户上传的图片 (视觉多模态格式转换)
    formatted_messages = [{"role": msg.role, "role_original": msg.role, "content": msg.content, "timestamp": msg.timestamp, "images": msg.images} for msg in payload.messages]
    cleaned_messages = []
    for m in formatted_messages:
        item_content = m["content"]
        msg_images = m.get("images")
        if msg_images and isinstance(msg_images, list) and len(msg_images) > 0:
            text_str = ""
            existing_images = []
            if isinstance(item_content, str):
                text_str = item_content
            elif isinstance(item_content, list):
                for sub in item_content:
                    if isinstance(sub, dict):
                        if sub.get("type") == "text":
                            text_str += sub.get("text", "")
                        elif sub.get("type") == "image_url":
                            existing_images.append(sub)
            
            new_content = []
            if text_str:
                new_content.append({"type": "text", "text": text_str})
            else:
                new_content.append({"type": "text", "text": "请看这张图片"})
            
            new_content.extend(existing_images)
            for img_url in msg_images:
                new_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
            item_content = new_content

        cleaned_messages.append({"role": m["role"], "content": item_content, "timestamp": m.get("timestamp")})

    # 2. 检查是否处于 mission_draft 阻塞状态 (Hard Block)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM mission_draft WHERE is_active = 1 LIMIT 1")
        draft = cursor.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to check mission_draft: {e}")
        draft = None

    clean_msg = last_user_msg.strip()
    clean_msg_lower = clean_msg.lower()

    if draft and clean_msg_lower == "/cancel_mission":
        return handle_slash_command(clean_msg, payload, last_user_msg, cleaned_messages)

    if draft and not clean_msg_lower.startswith("/cancel_mission"):
        from backend.services.slash_handler import handle_mission_interrogation
        return handle_mission_interrogation(last_user_msg, cleaned_messages, payload.persona_type, dict(draft))

    # 3. 拦截斜杠指令或特殊的测验提交
    if clean_msg.startswith('/') or clean_msg in ("/update_persona", "update_persona", "更新人设", "/更新人设"):
        return handle_slash_command(clean_msg, payload, last_user_msg, cleaned_messages)
        
    if "<submit_quiz_result" in clean_msg:
        # 拦截测验提交，将其映射为一个隐式的 slash command，以确保系统提示词注入
        return handle_slash_command("/lesson_continue", payload, last_user_msg, cleaned_messages)

    # 处理 @current_file
    if "@current_file" in last_user_msg and payload.current_file_path:
        try:
            import os
            import base64
            if os.path.exists(payload.current_file_path) and os.path.isfile(payload.current_file_path):
                ext = payload.current_file_path.lower().split('.')[-1]
                if ext in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
                    with open(payload.current_file_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode('utf-8')
                    mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else f"image/{ext}"
                    replacement_text = f"<image_attached filename=\"{os.path.basename(payload.current_file_path)}\"/>"
                    last_user_msg = last_user_msg.replace("@current_file", f"@current_file {replacement_text}")
                    
                    for msg in reversed(cleaned_messages):
                        if msg["role"] == "user":
                            if isinstance(msg["content"], str):
                                msg["content"] = [
                                    {"type": "text", "text": msg["content"].replace("@current_file", f"@current_file {replacement_text}")}
                                ]
                            else:
                                for item in msg["content"]:
                                    if item.get("type") == "text":
                                        item["text"] = item["text"].replace("@current_file", f"@current_file {replacement_text}")
                            msg["content"].append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_data}"}
                            })
                            break
                else:
                    with open(payload.current_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read(20000)

                    file_info = f"\n\n<file_content filename=\"{os.path.basename(payload.current_file_path)}\">\n{file_content}\n</file_content>\n"
                    last_user_msg = last_user_msg.replace("@current_file", f"@current_file {file_info}")

                    for msg in reversed(cleaned_messages):
                        if msg["role"] == "user":
                            if isinstance(msg["content"], str):
                                msg["content"] = msg["content"].replace("@current_file", f"@current_file {file_info}")
                            else:
                                for item in msg["content"]:
                                    if item.get("type") == "text":
                                        item["text"] = item["text"].replace("@current_file", f"@current_file {file_info}")
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

    # 4. 前置上下文防爆检测与 Auto-Compact 触发
    from backend.services.compact_service import check_and_auto_compact
    
    # 动态获取当前激活模型的 max_context_tokens (上下文窗口上限)
    active_model = get_active_model()
    context_window_limit = active_model.get("max_context_tokens") or 8192
    
    auto_compacted, final_messages_for_llm, auto_compact_hint = check_and_auto_compact(
        messages=cleaned_messages,
        session_id=payload.session_id,
        custom_max_tokens=context_window_limit,
        threshold_ratio=0.8,
        keep_recent_turns=10
    )

    pipeline = ResponsePipeline(registry=action_registry)
    pipeline.original_user_msg = original_last_user_msg

    def event_generator():
        try:
            # 推送 Auto-Compact 防爆提示 (如果触发)
            if auto_compact_hint:
                yield f"data: {json.dumps(auto_compact_hint, ensure_ascii=False)}\n\n"

            if kb_count > 0 or mem_count > 0:
                parts = []
                if kb_count > 0: parts.append(f"{kb_count} 个讲义片段")
                if mem_count > 0: parts.append(f"{mem_count} 个长期记忆")
                hint_text = f"🔍 成功检索并加载：{' 和 '.join(parts)}"
                yield f"data: {json.dumps({'type': 'system_hint', 'text': hint_text}, ensure_ascii=False)}\n\n"

            content_stream = stream_chat(final_messages_for_llm, system_prompt, max_tokens=payload.custom_max_tokens)
            yield from pipeline.process_stream(content_stream)
        except Exception as e:
            import traceback
            with open("debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"CRASH CAUGHT: {type(e).__name__}: {str(e)}\n")
                traceback.print_exc(file=f)
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
class ToolApprovalRequest(BaseModel):
    approval_id: str
    action: str  # "approve" or "reject"

@router.post("/approve_tool")
async def approve_tool(request: ToolApprovalRequest):
    from backend.services.agent_tools import PENDING_APPROVALS
    if request.approval_id not in PENDING_APPROVALS:
        return {"status": "error", "message": "Approval ID not found or already processed."}
    
    if request.action not in ["approve", "reject"]:
        return {"status": "error", "message": "Invalid action."}
        
    PENDING_APPROVALS[request.approval_id] = request.action
    return {"status": "success", "message": f"Tool execution {request.action}d."}


@router.get("/greeting")
def get_greeting(
    affection: Optional[int] = None,
    force_reunion: Optional[str] = None
):
    """
    获取基于物理时段、好感阶段、久别重逢状态与 61KB 原版生活行为的笛卡尔积开场白 (ADR-010)。
    支持前端新建会话时秒级调用，完全告别单一写死纯文本。
    """
    from backend.services.greeting_service import GreetingService
    return GreetingService.generate_greeting(affection=affection, force_reunion=force_reunion)

