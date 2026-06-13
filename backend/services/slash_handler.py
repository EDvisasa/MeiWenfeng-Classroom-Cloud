import os
import re
import json
import logging
from typing import Dict, Any, List
from fastapi.responses import StreamingResponse
from openai import OpenAI

from backend.database import get_db_connection
from backend.services.model_router import stream_chat, get_active_model
from backend.services.prompts import get_system_prompt, SUMMARIZATION_SYSTEM_PROMPT
from backend.services.rag_factory import get_rag_client, save_memory_to_rag, retrieve_memory
from backend.services.memory_decay import process_memory_decay

logger = logging.getLogger(__name__)

def json_escape(text: str) -> str:
    return json.dumps({"text": text}, ensure_ascii=False)

def handle_slash_command(command: str, payload: Any, last_user_msg: str, cleaned_messages: List[Dict[str, str]]) -> StreamingResponse:
    """
    统一处理各种以斜杠开头的纯前端指令。
    返回一个可迭代的生成器包装成的 StreamingResponse。
    """
    clean_cmd = command.strip().lower()
    
    # 获取上下文数据，前端在 ChatRequest 中可传入 current_file_path 等
    # payload 是 ChatRequest pydantic object
    current_file_path = getattr(payload, 'current_file_path', None)
    persona_type = getattr(payload, 'persona_type', 'simplified')
    
    # === 1. /更新人设 ===
    if clean_cmd in ("/更新人设", "更新人设"):
        return _handle_update_persona()
        
    # === 2. /总结 ===
    if clean_cmd == "/总结":
        return _handle_summarize()
        
    # === 3. /备课 ===
    if clean_cmd == "/备课":
        return _handle_prepare_lesson(current_file_path)
        
    # === 4. /奖励 ===
    if clean_cmd == "/奖励":
        return _handle_reward()

    # 以下指令均需要由大模型接管输出，因此使用“系统提示词注入”并拉起常规对话流
    system_injection = ""
    topic_name = "默认修仙"
    if current_file_path:
        topic_name = os.path.basename(current_file_path).replace(".md", "")

    if clean_cmd == "/上课":
        system_injection = f"[系统指令] 用户刚刚触发了 /上课 指令，代表新一轮课程开始。请你立刻进入导师状态，结合当前课题《{topic_name}》的讲义内容（若有），主动开启今天的授课，语气要积极投入。"
    elif clean_cmd == "/交作业":
        system_injection = f"[系统指令] 用户刚刚触发了 /交作业 指令，代表用户完成了学习准备接受考核。请你以导师身份，针对《{topic_name}》的知识点向用户提一个考验问题。"
    elif clean_cmd == "/计划":
        system_injection = f"[系统指令] 用户刚刚触发了 /计划 指令。请你以导师身份，简要点评用户近期的学习态度，并告诉他接下来的修炼规划。"
    else:
        # 未知指令，正常传递
        pass

    return _stream_normal_chat_with_injection(last_user_msg, cleaned_messages, persona_type, system_injection)

def _stream_normal_chat_with_injection(last_user_msg: str, cleaned_messages: List[Dict[str, str]], persona_type: str, system_injection: str) -> StreamingResponse:
    """
    在原本的大模型对话流基础上，追加特定的 System Prompt 注入，让大模型根据指令自动执行动作。
    """
    affection_value = 100
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        row = cursor.fetchone()
        if row: affection_value = row["value"]
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch affection: {e}")

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

    system_prompt = get_system_prompt(affection_value, persona_type)
    if rag_context:
        system_prompt += f"\n\n【附加背景知识库检索结果（作为世界观或讲义参考）】\n{rag_context}\n\n（请结合以上背景知识进行回答，若相关则自然地融入你的话语中，若无关则忽略）"
        
    if system_injection:
        system_prompt += f"\n\n{system_injection}\n"

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

def _handle_reward() -> StreamingResponse:
    """处理 /奖励：提升好感度并返回确认信息"""
    def generator():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM affection WHERE id = 1")
            row = cursor.fetchone()
            current = row["value"] if row else 50
            new_val = max(0, min(100, current + 10))
            if not row:
                cursor.execute("INSERT INTO affection (id, value, last_updated) VALUES (1, ?, datetime('now'))", (new_val,))
            else:
                cursor.execute("UPDATE affection SET value = ?, last_updated = datetime('now') WHERE id = 1", (new_val,))
            conn.commit()
            conn.close()
            yield f"data: {json_escape('[系统提示] 媚吻锋感到十分欢喜，对你的好感度增加了！当前好感度：' + str(new_val))}\n\n"
            yield f"data: {json_escape('*眼波流转，娇媚地白了你一眼，但嘴角的笑意却怎么也藏不住：*“夫君这是开窍了？就知道拿这些来哄奴家开心~”')}\n\n"
        except Exception as e:
            yield f"data: {json_escape('[系统提示] 奖励发送失败: ' + str(e))}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")

def _handle_summarize() -> StreamingResponse:
    """处理 /总结：触发记忆整理"""
    def generator():
        yield f"data: {json_escape('[系统记忆压缩] 正在调用艾宾浩斯遗忘曲线算法进行后台压缩，请稍候...')}\n\n"
        try:
            stats = process_memory_decay()
            yield f"data: {json_escape(f'[系统记忆压缩] 压缩完成！新记忆已归档入库。处理统计: {json.dumps(stats, ensure_ascii=False)}')}\n\n"
        except Exception as e:
            yield f"data: {json_escape('[系统记忆压缩] 压缩失败: ' + str(e))}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")

def _handle_prepare_lesson(file_path: str) -> StreamingResponse:
    """处理 /备课：同步选中的讲义到知识库"""
    def generator():
        if not file_path:
            yield f"data: {json_escape('[系统提示] 备课失败：未能在上下文中获取到选中的讲义文件路径。')}\n\n"
            return
            
        filename = os.path.basename(file_path)
        yield f"data: {json_escape(f'[知识库联动] 正在同步本地文件《{filename}》到当前 RAG 后端，请稍候...')}\n\n"
        
        try:
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                 yield f"data: {json_escape('[知识库联动] 错误：无效的文件路径。')}\n\n"
                 return
                 
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            rag_client = get_rag_client()
            result = rag_client.sync_knowledge({filename: content}, dataset_name="Classroom_Knowledge")
            if result["status"] == "error":
                error_msg = result.get("message")
                yield f"data: {json_escape(f'[知识库联动] 同步出错: {error_msg}')}\n\n"
            else:
                yield f"data: {json_escape('[知识库联动] 同步成功！媚吻锋已熟读这份讲义资料。')}\n\n"
        except Exception as e:
            yield f"data: {json_escape('[知识库联动] 发生异常: ' + str(e))}\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream")

def _handle_update_persona() -> StreamingResponse:
    """原封不动保留原有的 /更新人设 逻辑"""
    def generator():
        yield f"data: {json_escape('[系统更新] 正在检测本地角色卡源目录...')}\n\n"
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
        
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                full_persona = f.read()
            services_dir = os.path.dirname(os.path.abspath(__file__))
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
            model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
            if "qwen" in model_name.lower(): model_id_api = "qwen3.6-35b"
            elif "gemma" in model_name.lower(): model_id_api = "gemma-9b"
            elif "deepseek" in model_name.lower(): model_id_api = "deepseek-chat"
                
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
            
            local_simplified_path = os.path.join(services_dir, "mei_wenfeng_persona_simplified.txt")
            with open(local_simplified_path, "w", encoding="utf-8") as f:
                f.write(simplified_persona)
            yield f"data: {json_escape('[系统更新] 精简人设本地缓存生成成功！')}\n\n"
            
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
    
    return StreamingResponse(generator(), media_type="text/event-stream")
