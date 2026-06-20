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
from backend.services.rag_factory import get_rag_client
from backend.services.memory_decay import process_memory_decay
from backend.services.response_pipeline import ResponsePipeline, json_escape
from backend.services.character_state import CharacterStateManager, CharacterStateError
from backend.services.action_registry import action_registry
import backend.services.side_effects  # Ensure handlers are registered

logger = logging.getLogger(__name__)

def handle_slash_command(command: str, payload: Any, last_user_msg: str, cleaned_messages: List[Dict[str, str]]) -> StreamingResponse:
    """
    统一处理各种以斜杠开头的纯前端指令。
    """
    clean_cmd = command.strip().lower()

    current_file_path = getattr(payload, 'current_file_path', None)
    persona_type = getattr(payload, 'persona_type', 'simplified')

    # === 1. /update_persona ===
    if clean_cmd in ("/update_persona", "update_persona"):
        return _handle_update_persona()

    # === 2. /summarize ===
    if clean_cmd == "/summarize":
        return _handle_summarize()

    # === 3. /prepare ===
    if clean_cmd == "/prepare":
        return _handle_prepare_lesson(current_file_path)

    # === 4. /reward ===
    if clean_cmd == "/reward":
        return _handle_reward()

    # === 5. /set_mission ===
    if clean_cmd.startswith("/set_mission"):
        return _handle_set_mission(clean_cmd)

    # 从数据库获取用户的宏大目标 (Mission)
    user_mission = "未知目标"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT mission_text FROM user_mission WHERE id = 1")
        row = cursor.fetchone()
        if row and row["mission_text"]:
            user_mission = row["mission_text"]
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch mission: {e}")

    # 以下指令均需要由大模型接管输出，因此使用“系统提示词注入”并拉起常规对话流
    system_injection = ""
    from backend.services.course_manager import get_active_course, get_formatted_syllabus

    active_course = get_active_course()
    topic_name = active_course["topic"] if active_course else "自由探索（当前无待办课题，请用 /计划 生成）"

    file_context = ""
    if current_file_path:
        file_context = f"<active_document>The user is currently reviewing the document: {os.path.basename(current_file_path)}</active_document>"

    if clean_cmd == "/lesson":
        system_injection = f"""<system_directive>
Event: The user just triggered the `/lesson` command.
User's Ultimate Mission: {user_mission}
Current Topic: {topic_name}
{file_context}

Action Required: Immediately enter your mentor persona. Proactively start today's lesson focused on the Current Topic.
Output Format: If the concept is complex, you MUST secretly embed an explainer in your response using this exact XML format: `<explainer title="Filename.md"># Markdown Content...</explainer>`. This will automatically generate a physical jade slip (document) for the user.
</system_directive>"""
    elif clean_cmd == "/submit":
        system_injection = f"""<system_directive mode="socratic_strict_mentor">
Event: The user triggered the `/submit` command, indicating they are ready for assessment.
Current Assessment Topic: {topic_name}
User's Ultimate Mission: {user_mission}
{file_context}

<critical_rules>
1. NEVER GIVE DIRECT ANSWERS.
2. Ask questions that are just slightly beyond the user's current understanding (Zone of Proximal Development).
3. Identify ambiguous areas in the user's logic and pursue them with follow-up questions.
4. Apply pressure or give encouragement by tying the assessment to their Ultimate Mission.
5. PASS CONDITION: Once you are absolutely certain the user has perfectly mastered '{topic_name}', you MUST output the exact identifier `[SYSTEM_PASS]` at the very end of your response.
6. GLOSSARY EXTRACTION: When you are certain the user has understood a complex new term, embed it using: `<glossary term="TermName">Concise Definition</glossary>`.
</critical_rules>
</system_directive>"""
    elif clean_cmd == "/plan":
        syllabus_text = get_formatted_syllabus()
        system_injection = f"""<system_directive>
Event: The user triggered the `/plan` command.
User's Ultimate Mission: {user_mission}

<current_syllabus_progress>
{syllabus_text}
</current_syllabus_progress>

Action Required: As a mentor, review their recent progress and outline their upcoming cultivation plan.
Output Format: If you need to append new topics to the syllabus, embed the following tag in your response: `<new_course phase="Phase Name" topic="Topic Name" />`. The system will automatically add it to the pending progress.
</system_directive>"""

    return _stream_normal_chat_with_injection(last_user_msg, cleaned_messages, persona_type, system_injection)

def _stream_normal_chat_with_injection(last_user_msg: str, cleaned_messages: List[Dict[str, str]], persona_type: str, system_injection: str) -> StreamingResponse:
    """
    在原本的大模型对话流基础上，追加特定的 System Prompt 注入，让大模型根据指令自动执行动作。
    采用解耦的 ResponsePipeline。
    """
    try:
        state = CharacterStateManager.get_state()
        affection_value = state.affection
        social_status = state.social_status
        social_skills = state.social_skills
        refractory_period = state.refractory_period
    except CharacterStateError as e:
        logger.error(f"Failed to fetch character state in slash handler: {e}")
        affection_value = 50
        social_status = 50
        social_skills = 50
        refractory_period = 0

    rag_context = ""
    if last_user_msg:
        try:
            rag_client = get_rag_client()
            kb_context = rag_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge", "Memory_Knowledge"])
            mem_context = rag_client.retrieve_memory(last_user_msg, n_results=3)
            # 兼容返回字符串或列表
            parts = []
            if kb_context:
                parts.extend(kb_context if isinstance(kb_context, list) else [kb_context])
            if mem_context:
                 parts.extend(mem_context if isinstance(mem_context, list) else [mem_context])
            if parts:
                rag_context = "\n\n".join(parts)
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value, persona_type, social_status, social_skills, refractory_period)
    if rag_context:
        system_prompt += f"\n\n<retrieved_background_knowledge>\n{rag_context}\n</retrieved_background_knowledge>\n<instruction>Integrate this background knowledge naturally into your response if relevant. If irrelevant, ignore it.</instruction>"

    if system_injection:
        system_prompt += f"\n\n{system_injection}\n"


    def on_stream_end(clean_text: str):
        if not last_user_msg or not clean_text:
            return
        try:
            from datetime import datetime
            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            memory_content = f"【对话记录 ({time_str})】\n用户：{last_user_msg}\n媚吻锋：{clean_text}"
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')",
                (memory_content,)
            )
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
            active_level0_count = cursor.fetchone()[0]
            if active_level0_count >= 10:
                import threading
                from backend.services.memory_decay import process_memory_decay
                threading.Thread(target=process_memory_decay, daemon=True).start()
            conn.close()

            rag_client = get_rag_client()
            rag_client.save_memory(last_user_msg, clean_text, level=0)
        except Exception as e:
            logger.error(f"Failed to save memory in callback: {e}")

    # 初始化管道
    pipeline = ResponsePipeline(on_stream_end=on_stream_end, registry=action_registry)

    def event_generator():
        try:
            content_stream = stream_chat(cleaned_messages, system_prompt)
            yield from pipeline.process_stream(content_stream)
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 下面保留原有的其他命令处理函数（_handle_reward, _handle_summarize 等）...
def _handle_reward() -> StreamingResponse:
    def raw_generator():
        try:
            state = CharacterStateManager.modify_state(affection_delta=10)
            yield f"[系统提示] 媚吻锋感到十分欢喜，对你的好感度增加了！当前好感度：{state.affection}\n\n"
            yield "*眼波流转，娇媚地白了你一眼，但嘴角的笑意却怎么也藏不住：*“夫君这是开窍了？就知道拿这些来哄奴家开心~”"
        except CharacterStateError as e:
            yield f"[系统提示] 奖励发送失败: {e}"

    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")

def _handle_summarize() -> StreamingResponse:
    def raw_generator():
        yield "[系统记忆压缩] 正在调用艾宾浩斯遗忘曲线算法进行后台压缩，请稍候...\n\n"
        import threading
        import time
        result_container = {}
        def target():
            try:
                from backend.services.memory_decay import process_memory_decay
                stats = process_memory_decay()
                result_container["stats"] = stats
            except Exception as e:
                result_container["error"] = str(e)

        t = threading.Thread(target=target)
        t.start()

        # Yield keep-alive messages to prevent frontend timeout and Errno 22 on Windows
        while t.is_alive():
            time.sleep(2)
            yield "...\n\n"

        t.join()
        if "error" in result_container:
            yield f"[系统记忆压缩] 压缩失败: {result_container['error']}"
        else:
            stats = result_container.get("stats", {})
            yield f"[系统记忆压缩] 压缩完成！新记忆已归档入库。处理统计: {json.dumps(stats, ensure_ascii=False)}"

    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")

def _handle_prepare_lesson(file_path: str) -> StreamingResponse:
    def raw_generator():
        if not file_path:
            yield "[系统提示] 备课失败：未能在上下文中获取到选中的讲义文件路径。"
            return
        filename = os.path.basename(file_path)
        yield f"[知识库联动] 正在同步本地文件《{filename}》到当前知识库后端，请稍候...\n\n"
        try:
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                 yield "[知识库联动] 错误：无效的文件路径。"
                 return
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            rag_client = get_rag_client()
            result = rag_client.sync_knowledge({filename: content}, dataset_name="Classroom_Knowledge")
            if result["status"] == "error":
                error_msg = result.get("message")
                yield f"[知识库联动] 同步出错: {error_msg}"
            else:
                yield "[知识库联动] 同步成功！媚吻锋已熟读这份讲义资料。"
        except Exception as e:
            yield f"[知识库联动] 发生异常: {e}"
            
    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")

def _handle_update_persona() -> StreamingResponse:
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

def _handle_set_mission(clean_cmd: str) -> StreamingResponse:
    mission_text = clean_cmd.replace("/set_mission", "").strip()
    def raw_generator():
        if not mission_text:
            yield "[系统提示] 目标内容不能为空，格式为：/设定目标 我的目标是打败魔尊"
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user_mission WHERE id = 1")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO user_mission (id, mission_text) VALUES (1, ?)", (mission_text,))
            else:
                cursor.execute("UPDATE user_mission SET mission_text = ?, last_updated = datetime('now') WHERE id = 1", (mission_text,))
            conn.commit()
            conn.close()
            yield f"[系统提示] 宏大目标已铭记于心：【{mission_text}】。接下来的所有授课和考核都将以此为最高导向！"
        except Exception as e:
            yield f"[系统报错] 目标设定失败: {e}"
            
    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")
