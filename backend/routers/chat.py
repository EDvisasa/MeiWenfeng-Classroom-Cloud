import logging
import asyncio
import json
import httpx
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
    persona_type: str = "simplified"

@router.post("/send")
def send_message(payload: ChatRequest):
    """发送对话消息，返回流式 EventSource"""
    # 提取最后一条用户消息
    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    
    # 拦截更新人设指令
    clean_msg = last_user_msg.strip()
    if clean_msg in ("更新人设", "/更新人设"):
        import os
        import re
        from backend.services.model_router import get_active_model
        from openai import OpenAI
        from backend.services.prompts import SUMMARIZATION_SYSTEM_PROMPT
        
        def update_event_generator():
            yield f"data: {json_escape('[系统更新] 正在检测本地角色卡源目录...')}\n\n"
            
            # 1. 索源与读取：找到性格调色盘目录下最大版本号的文本文件
            external_dir = "D:/Games/AI小说文档/01-SillyTarern文件/01-[roll点开局·遇仙记]/02-角色卡/00-[自创]遇仙记/02-媚吻锋/00-人设文档/性格调色盘"
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
                yield f"data: {json_escape('[系统更新] 错误：未找到原版人设卡片，更新终止。')}\n\n"
                return
                
            yield f"data: {json_escape(f'[系统更新] 发现最新原版人设：{os.path.basename(latest_file)}，正在读取并写入本地缓存...')}\n\n"
            
            # 2. 读取并覆写本地原版人设缓存
            try:
                with open(latest_file, "r", encoding="utf-8") as f:
                    full_persona = f.read()
                
                # 写入 backend/services/mei_wenfeng_persona.txt
                services_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services")
                local_original_path = os.path.join(services_dir, "mei_wenfeng_persona.txt")
                
                with open(local_original_path, "w", encoding="utf-8") as f:
                    f.write(full_persona)
                yield f"data: {json_escape('[系统更新] 原版人设本地缓存更新成功！')}\n\n"
            except Exception as e:
                yield f"data: {json_escape(f'[系统更新] 更新原版人设缓存失败: {e}')}\n\n"
                return
                
            # 3. 提炼精简人设
            yield f"data: {json_escape('[系统更新] 正在通过大语言模型提炼生成精简人设...')}\n\n"
            
            try:
                model_info = get_active_model()
                api_key = model_info["api_key"]
                base_url = model_info["base_url"]
                model_name = model_info["name"]
                
                model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
                if "qwen" in model_name.lower():
                    model_id_api = "qwen3.6-35b"
                elif "gemma" in model_name.lower():
                    model_id_api = "gemma-9b"
                elif "deepseek" in model_name.lower():
                    model_id_api = "deepseek-chat"
                    
                if ("deepseek" in model_name.lower() or model_info["protocol"] == "openai") and "本地" not in model_name:
                    env_key = os.getenv("AIRP_MODEL_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
                    env_url = os.getenv("AIRP_MODEL_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
                    if env_key: api_key = env_key
                    if env_url: base_url = env_url
                
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
                
                # 写入本地精简缓存
                local_simplified_path = os.path.join(services_dir, "mei_wenfeng_persona_simplified.txt")
                with open(local_simplified_path, "w", encoding="utf-8") as f:
                    f.write(simplified_persona)
                yield f"data: {json_escape('[系统更新] 精简人设本地缓存生成成功！')}\n\n"
                
                # 同步覆盖写入外部“当前精简人设.md”
                external_simplified_dir = "D:/Games/AI小说文档/01-SillyTarern文件/01-[roll点开局·遇仙记]/02-角色卡/00-[自创]遇仙记/02-媚吻锋/02-延伸功能-媚吻锋学习小课堂/01_动态人设系统"
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
            
        return StreamingResponse(update_event_generator(), media_type="text/event-stream")

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
    rag_context = ""
    if last_user_msg:
        try:
            rag_context = ragflow_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge", "Memory_Knowledge"])
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value, payload.persona_type)
    if rag_context:
        system_prompt += f"\n\n【附加背景知识库检索结果（作为世界观或讲义参考）】\n{rag_context}\n\n（请结合以上背景知识进行回答，若相关则自然地融入你的话语中，若无关则忽略）"

    # 3. 剥离消息以满足 model_router 要求的格式 (role, content)
    cleaned_messages = [{"role": m["role"], "content": m["content"]} for m in formatted_messages]

    def event_generator():
        accumulated_assistant_content = ""
        try:
            # 用 stream_chat 获取生成器
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
                except Exception as e:
                    logger.error(f"Failed to save memory: {e}")
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

from backend.services.memory_decay import process_memory_decay

@router.post("/summarize")
def summarize_memory():
    """触发记忆压缩和遗忘算法"""
    try:
        stats = process_memory_decay()
        return {"status": "success", "message": "记忆压缩整理完成。", "stats": stats}
    except Exception as e:
        logger.error(f"Memory decay failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def json_escape(text: str) -> str:
    """包装为 JSON 字符串，便于前端原样解析"""
    return json.dumps({"text": text}, ensure_ascii=False)

class SyncRequest(BaseModel):
    files: Dict[str, str]

@router.post("/sync_knowledge")
def sync_knowledge(payload: SyncRequest):
    """同步前端知识库文件到 RAGFlow"""
    result = ragflow_client.sync_knowledge(payload.files)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@router.get("/models")
def list_models():
    """获取所有模型配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, protocol, base_url, api_key, is_active, selected_model_id FROM model_config")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ModelUpdateRequest(BaseModel):
    id: int
    base_url: str
    api_key: str = ""
    protocol: str = "openai"
    selected_model_id: str = ""

@router.post("/models/update")
def update_model_config(payload: ModelUpdateRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE model_config 
               SET base_url = ?, api_key = ?, protocol = ?, selected_model_id = ? 
               WHERE id = ?""",
            (payload.base_url, payload.api_key, payload.protocol, payload.selected_model_id, payload.id)
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/available")
def get_available_models(base_url: str, api_key: str = None, protocol: str = "openai"):
    if protocol != "openai":
        return {"status": "success", "models": []}
    
    headers = {}
    if api_key and api_key != "none" and api_key.strip() != "":
        headers["Authorization"] = f"Bearer {api_key}"
        
    try:
        # Avoid IPv6 connection issues on Windows with httpx by mapping localhost to 127.0.0.1
        safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
        url = f"{safe_base_url.rstrip('/')}/models"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data", [])
                model_ids = [m.get("id") for m in models_list if m.get("id")]
                return {"status": "success", "models": model_ids}
            else:
                return {"status": "error", "message": f"API returned status {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
        cursor.execute("SELECT name, selected_model_id FROM model_config WHERE is_active = 1 LIMIT 1")
        model_row = cursor.fetchone()
        active_model = model_row["name"] if model_row else "未设置"
        active_sub_model = model_row["selected_model_id"] if model_row and model_row["selected_model_id"] else None
        
        # 获取课程大纲
        cursor.execute("SELECT id, phase, topic, status, score FROM course_progress")
        course_rows = cursor.fetchall()
        course_list = [dict(r) for r in course_rows]
        
        conn.close()
        return {
            "affection": affection,
            "active_model": active_model,
            "active_sub_model": active_sub_model,
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

def build_file_tree(dir_path: str):
    import os
    ignore_dirs = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', 'build', '.idea', '.vscode'}
    tree = []
    try:
        for entry in os.scandir(dir_path):
            if entry.name in ignore_dirs:
                continue
            if entry.is_dir():
                children = build_file_tree(entry.path)
                tree.append({
                    "name": entry.name,
                    "path": entry.path.replace("\\", "/"),
                    "is_dir": True,
                    "children": children
                })
            else:
                tree.append({
                    "name": entry.name,
                    "path": entry.path.replace("\\", "/"),
                    "is_dir": False
                })
    except Exception as e:
        print(f"Error reading directory {dir_path}: {e}")
    # 文件夹排前面，文件排后面，各按名字升序排序
    tree.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return tree

@router.get("/files/list")
def list_files(root_dir: str = None):
    import os
    if not root_dir:
        # 默认到项目根目录
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_dir = os.path.abspath(root_dir)
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        raise HTTPException(status_code=400, detail="Invalid directory path")
    return {
        "root_name": os.path.basename(root_dir) or root_dir,
        "root_path": root_dir.replace("\\", "/"),
        "tree": build_file_tree(root_dir)
    }

@router.get("/files/content")
def get_file_content(file_path: str):
    import os
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SyncFileRequest(BaseModel):
    file_path: str
    dataset_name: str = "Classroom_Knowledge"

@router.post("/files/sync")
def sync_file(payload: SyncFileRequest):
    import os
    file_path = os.path.abspath(payload.file_path)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        filename = os.path.basename(file_path)
        result = ragflow_client.sync_knowledge({filename: content}, dataset_name=payload.dataset_name)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/sync_status")
def get_sync_status_api(dataset_name: str = "Classroom_Knowledge"):
    result = ragflow_client.get_sync_status(dataset_name)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

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

