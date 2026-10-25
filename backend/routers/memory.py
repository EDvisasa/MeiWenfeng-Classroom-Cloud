import json
import logging
import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from backend.database import get_db_connection
from backend.services.memory_decay import check_decay_needed
from backend.services.action_registry import action_registry
from backend.services.response_pipeline import json_escape
from backend.services.model_router import get_active_model
from backend.services.prompts import SUMMARIZATION_SYSTEM_PROMPT
from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["memory", "sessions"])

class Message(BaseModel):
    role: str
    content: Optional[str] = ""
    timestamp: Optional[str] = None
    images: Optional[List[str]] = None

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
        from backend.services.memory_decay import process_memory_decay
        stats = process_memory_decay()
        return {"status": "success", "message": "记忆压缩整理完成。", "stats": stats}
    except Exception as e:
        logger.error(f"Memory decay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/command/update_persona_stream")
def update_persona_stream():
    """同步提炼人设的 SSE 流接口"""
    def generator():
        yield f"data: {json_escape('[系统更新] 正在检测本地角色卡源目录...')}\n\n"
        # 优先从环境变量读取原版人设文件夹路径，默认指向 data/persona/original 避免泄露隐私路径
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        external_dir = os.getenv("PERSONA_SOURCE_DIR", os.path.join(base_root, "data", "persona", "original"))
        latest_file = None
        try:
            if os.path.exists(external_dir):
                files = os.listdir(external_dir)
                card_files = []
                pattern = re.compile(r"媚吻锋人物性格卡片V(\d+(?:\.\d+)?).*?\.txt")
                for f in files:
                    match = pattern.match(f)
                    if match:
                        try:
                            version = float(match.group(1))
                            card_files.append((version, f))
                        except ValueError:
                            pass
                if card_files:
                    card_files.sort(key=lambda x: x[0], reverse=True)
                    latest_file = os.path.join(external_dir, card_files[0][1])
        except Exception as e:
            yield f"data: {json_escape(f'[系统更新] 检测源目录失败: {e}')}\n\n"
        if not latest_file:
            yield f"data: {json_escape(f'[系统更新] 错误：在目录 {external_dir} 中未找到匹配的原版人设卡片，更新终止。')}\n\n"
            return
        yield f"data: {json_escape(f'[系统更新] 发现最新原版人设：{os.path.basename(latest_file)}，正在读取并写入本地缓存...')}\n\n"
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                full_persona = f.read()
            services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
            local_original_path = os.path.join(services_dir, "mei_wenfeng_persona.txt")
            with open(local_original_path, "w", encoding="utf-8") as f:
                f.write(full_persona)
            yield f"data: {json_escape('[系统更新] 原版人设本地缓存更新成功！')}\n\n"
        except Exception as e:
            yield f"data: {json_escape(f'[系统更新] 更新原版人设缓存失败: {e}')}\n\n"
            return
        yield f"data: {json_escape('[系统更新] 正在通过大语言模型提炼生成精简人设...')}\n\n"
        try:
            model_info = get_active_model()
            api_key = model_info["api_key"]
            base_url = model_info["base_url"]
            model_name = model_info["name"]
            selected_model_id = model_info.get("selected_model_id")
            if selected_model_id:
                model_id_api = selected_model_id
            else:
                model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
                if "qwen" in model_name.lower(): model_id_api = "qwen3.6-35b"
                elif "gemma" in model_name.lower(): model_id_api = "gemma-9b"
                elif "deepseek" in model_name.lower(): model_id_api = "deepseek-chat"
            if base_url:
                base_url = base_url.replace("://localhost:", "://127.0.0.1:")
            client = OpenAI(api_key=api_key or "no-key-required", base_url=base_url)
            response = client.chat.completions.create(
                model=model_id_api,
                messages=[
                    {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": "请提炼以下全量人设卡内容：\n\n" + full_persona}
                ],
                stream=False,
                temperature=0.3
            )
            simplified_persona = response.choices[0].message.content.strip()
            local_simplified_path = os.path.join(services_dir, "mei_wenfeng_persona_simplified.txt")
            with open(local_simplified_path, "w", encoding="utf-8") as f:
                f.write(simplified_persona)
            yield f"data: {json_escape('[系统更新] 精简人设本地缓存生成成功！')}\n\n"
            # 优先从环境变量读取精简人设同步输出目录，默认指向 data/persona/simplified
            base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            external_simplified_dir = os.getenv("PERSONA_SIMPLIFIED_OUTPUT_DIR", os.path.join(base_root, "data", "persona", "simplified"))
            if not os.path.exists(external_simplified_dir):
                try:
                    os.makedirs(external_simplified_dir, exist_ok=True)
                except Exception:
                    pass
            if os.path.exists(external_simplified_dir):
                external_simplified_path = os.path.join(external_simplified_dir, "当前精简人设.md")
                header_warning = "> ⚠️ **注意**：本文件为 AI 自动生成的精简缓存。请勿手动修改此文件。如需更新，请对 AI 发送【更新人设】指令，AI 将自动从数据源提取最新卡片并重写此文件。\n\n"
                with open(external_simplified_path, "w", encoding="utf-8") as f:
                    f.write(header_warning + simplified_persona)
                yield f"data: {json_escape('[系统更新] 精简人设已成功同步写入外部 当前精简人设.md。')}\n\n"
        except Exception as e:
            yield f"data: {json_escape(f'[系统更新] 生成精简人设失败: {e}')}\n\n"
            return
    return StreamingResponse(generator(), media_type="text/event-stream")

@router.get("/sessions")
def get_sessions():
    """获取所有历史会话及其消息（确保 openclaw_trio_chat 始终置顶并存在）"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 确保 openclaw_trio_chat 会话在数据库中常驻
        cursor.execute("SELECT id FROM chat_sessions WHERE id = 'openclaw_trio_chat'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO chat_sessions (id, title, updated_at) VALUES ('openclaw_trio_chat', '小白有话说...', datetime('now'))"
            )
            conn.commit()

        # 获取所有会话，按最后更新时间降序排列
        cursor.execute("SELECT id, title, updated_at FROM chat_sessions ORDER BY updated_at DESC")
        raw_sessions = [dict(row) for row in cursor.fetchall()]
        
        # 将 openclaw_trio_chat 强制固定在第一位
        trio_sess = None
        other_sessions = []
        for s in raw_sessions:
            if s["id"] == "openclaw_trio_chat":
                s["title"] = "小白有话说..."
                trio_sess = s
            else:
                other_sessions.append(s)
        
        sessions = ([trio_sess] if trio_sess else []) + other_sessions

        for sess in sessions:
            cursor.execute(
                "SELECT role, content, timestamp, images FROM chat_messages WHERE session_id = ? ORDER BY id ASC", 
                (sess["id"],)
            )
            sess_messages = []
            for row in cursor.fetchall():
                msg_dict = {
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"]
                }
                raw_images = row["images"]
                if raw_images:
                    try:
                        msg_dict["images"] = json.loads(raw_images)
                    except Exception:
                        msg_dict["images"] = []
                else:
                    msg_dict["images"] = []
                sess_messages.append(msg_dict)
            sess["messages"] = sess_messages
            
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
            images_json = json.dumps(msg.images, ensure_ascii=False) if msg.images else None
            if msg.timestamp:
                cursor.execute(
                    "INSERT INTO chat_messages (session_id, role, content, images, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (payload.id, msg.role, msg.content, images_json, msg.timestamp)
                )
            else:
                cursor.execute(
                    "INSERT INTO chat_messages (session_id, role, content, images) VALUES (?, ?, ?, ?)",
                    (payload.id, msg.role, msg.content, images_json)
                )
            
        conn.commit()
        conn.close()
        return {"status": "success", "session_id": payload.id}
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """删除指定的聊天会话及其消息（openclaw_trio_chat 永久保护不予删除）"""
    if session_id == "openclaw_trio_chat":
        raise HTTPException(status_code=403, detail="【小白有话说...】为永久专属三人会话，禁止删除。")

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
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RollbackStepPayload(BaseModel):
    expected_user_msg: Optional[str] = None
    expected_assistant_msg: Optional[str] = None

@router.post("/sessions/{session_id}/rollback_step")
def rollback_session_step(session_id: str, payload: Optional[RollbackStepPayload] = None):
    """
    单步回滚指定会话的最末一轮对话 (LIFO)。
    1. 时序自检：核对数据库中该会话最末轮消息与前端期望内容，若漂移则返回 409 Conflict，防止误删；
    2. 对话表回滚：删除最末一轮消息（用户消息与助手回复）；
    3. 记忆库软标记失效：将关联的 memory_logs 标记为 'rolled_back'（排除出后续召回与压缩）；
    4. 向量库硬删除：精准从 ChromaDB conversation_memory collection 中移除该切片，确保语义彻底抹除；
    5. 好感度与状态机保持纯粹隔离（按方案 A 约定，不回退好感度，保证多窗口互不污染）。
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, role, content FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 20",
            (session_id,)
        )
        recent_rows = cursor.fetchall()
        if not recent_rows:
            conn.close()
            raise HTTPException(status_code=400, detail="会话中已无可回滚的消息")

        # 逆序解析最末一轮（穿透跳过 system_info 等辅助消息）
        idx = 0
        while idx < len(recent_rows) and recent_rows[idx]["role"] in ("system_info", "system_action", "system_hint"):
            idx += 1

        if idx >= len(recent_rows):
            # 仅剩系统辅助消息，直接清理
            ids_to_delete = [r["id"] for r in recent_rows]
            actual_assistant = None
            actual_user = None
        elif recent_rows[idx]["role"] == "assistant":
            actual_assistant = recent_rows[idx]
            ids_to_delete = [r["id"] for r in recent_rows[:idx + 1]]

            # 寻找该助手回复对应的用户消息（穿透中间的 system_info，如搜索检索提示）
            u_idx = idx + 1
            while u_idx < len(recent_rows) and recent_rows[u_idx]["role"] in ("system_info", "system_action", "system_hint"):
                ids_to_delete.append(recent_rows[u_idx]["id"])
                u_idx += 1

            if u_idx < len(recent_rows) and recent_rows[u_idx]["role"] == "user":
                actual_user = recent_rows[u_idx]
                ids_to_delete.append(actual_user["id"])
            else:
                actual_user = None
        else:
            # 最末一条是用户消息
            actual_assistant = None
            actual_user = recent_rows[idx]
            ids_to_delete = [r["id"] for r in recent_rows[:idx + 1]]

        # 校验时序漂移断言
        if payload and payload.expected_assistant_msg is not None:
            if not actual_assistant or payload.expected_assistant_msg.strip() != actual_assistant["content"].strip():
                conn.close()
                raise HTTPException(
                    status_code=409,
                    detail="时序已漂移：期望助手回复与数据库最末条记录不符，中止回滚以防损坏历史记录。"
                )
        if payload and payload.expected_user_msg is not None:
            if not actual_user or payload.expected_user_msg.strip() != actual_user["content"].strip():
                conn.close()
                raise HTTPException(
                    status_code=409,
                    detail="时序已漂移：期望用户提问与数据库最末条记录不符，中止回滚以防损坏历史记录。"
                )

        # 精准软标记失效当前轮次的 memory_logs
        invalidated_mem_id = None
        deleted_chroma = False

        if actual_user:
            user_snippet = actual_user["content"][:40]
            # 1. 优先根据 session_id 且内容严格匹配该轮用户提问
            cursor.execute(
                "SELECT id, chroma_doc_id, content FROM memory_logs WHERE session_id = ? AND status = 'active' AND content LIKE ? ORDER BY id DESC LIMIT 1",
                (session_id, f"%用户：{user_snippet}%")
            )
            mem_row = cursor.fetchone()

            # 2. 备用安全匹配：若未按前缀匹配到，核验当前会话最新一条 active 记忆是否确属本轮
            if not mem_row:
                cursor.execute(
                    "SELECT id, chroma_doc_id, content FROM memory_logs WHERE session_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                    (session_id,)
                )
                candidate_row = cursor.fetchone()
                if candidate_row and (user_snippet in candidate_row["content"] or (actual_assistant and actual_assistant["content"][:30] in candidate_row["content"])):
                    mem_row = candidate_row

            if mem_row:
                invalidated_mem_id = mem_row["id"]
                cursor.execute("UPDATE memory_logs SET status = 'rolled_back' WHERE id = ?", (invalidated_mem_id,))

                chroma_doc_id = mem_row["chroma_doc_id"]
                if chroma_doc_id:
                    try:
                        from backend.services.rag_factory import get_rag_client
                        rag_client = get_rag_client()
                        deleted_chroma = bool(rag_client.delete_memory(chroma_doc_id))
                    except Exception as e:
                        logger.error(f"Failed to delete Chroma memory for doc_id {chroma_doc_id}: {e}")

        # 删除 chat_messages 中的最末轮条目
        placeholders = ",".join("?" for _ in ids_to_delete)
        cursor.execute(f"DELETE FROM chat_messages WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,))
        remaining_count = cursor.fetchone()[0]
        conn.close()

        return {
            "status": "success",
            "session_id": session_id,
            "rolled_back_ids": ids_to_delete,
            "invalidated_memory_id": invalidated_mem_id,
            "deleted_chroma": deleted_chroma,
            "remaining_messages": remaining_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rollback step failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

