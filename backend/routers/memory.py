import logging
import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
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
    content: str = ""
    timestamp: str = None

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
        character_acknowledgement = "*伸了个懒腰，柔柔地搂住你的胳膊，红黑色的狐瞳含笑看着你，眼波娇嗔流转：*“夫君，奴家已经把自己的小档案更新好啦，这次绝对是最新最全的人设。随你喜欢精简的还是原汁原味的，奴家都听夫君的~”\n\n【此刻内心】：（哼，天天就知道折腾奴家，不过既然是夫君想要，那就算啦，等会儿得让他好好补偿人家才行~）"
        yield f"data: {json_escape(character_acknowledgement)}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")

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
                "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY id ASC", 
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
            if msg.timestamp:
                cursor.execute(
                    "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (payload.id, msg.role, msg.content, msg.timestamp)
                )
            else:
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
