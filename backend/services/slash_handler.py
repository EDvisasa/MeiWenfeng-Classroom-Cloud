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

    # === 5. /设定目标 ===
    if clean_cmd.startswith("/设定目标"):
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
    topic_name = "默认修仙"
    if current_file_path:
        topic_name = os.path.basename(current_file_path).replace(".md", "")

    if clean_cmd == "/上课":
        system_injection = f"[系统指令] 用户刚刚触发了 /上课 指令。用户的终极宏大目标(Mission)是：【{user_mission}】。请你立刻进入导师状态，结合当前课题《{topic_name}》的讲义内容，主动开启今天的授课。请注意，授课的举例和教导方向必须紧紧围绕用户的宏大目标！如果概念复杂，请在回复中暗藏 `<explainer title=\"文件名称.md\"># Markdown讲义内容...</explainer>` 来自动生成实体玉简。"
    elif clean_cmd == "/交作业":
        system_injection = f"""[系统指令-苏格拉底严师模式] 
用户触发了 /交作业 指令，代表准备接受考核。当前正在学习的课题是《{topic_name}》，用户的终极宏大目标是：【{user_mission}】。
请遵循以下最高准则：
1. **绝对不要直接给出答案**。
2. 提出刚好超出玩家当前认知一点点的问题 (Zone of Proximal Development)。
3. 根据上下文找出玩家逻辑中的模糊地带进行连环追问。
4. 结合玩家的宏大目标来施加压力或给予鼓励。
5. **通关判定**：一旦你通过多轮对答，确信用户已经完美且深入地掌握了《{topic_name}》的核心精髓，请在你那次回复的最末尾输出且仅输出此特殊标识符：`[SYSTEM_PASS]`。
6. **术语沉淀**：当你确信用户搞懂了某个复杂新名词（如“灵根”），请在回复中暗藏 `<glossary term="名词">简练的定义</glossary>`。"""
    elif clean_cmd == "/计划":
        system_injection = f"[系统指令] 用户触发了 /计划 指令。用户的终极宏大目标是：【{user_mission}】。请你以导师身份，结合他的目标点评近期学习态度，并告诉他接下来的修炼规划。"
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
                # --- Post-processing AI Response ---
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # 1. 拦截 [SYSTEM_PASS] 推进课程进度
                if "[SYSTEM_PASS]" in accumulated_assistant_content:
                    try:
                        cursor.execute("SELECT id FROM course_progress WHERE status = 'active' ORDER BY id ASC LIMIT 1")
                        active_row = cursor.fetchone()
                        if active_row:
                            active_id = active_row["id"]
                            cursor.execute("UPDATE course_progress SET status = 'completed' WHERE id = ?", (active_id,))
                            
                            # 激活下一节课
                            cursor.execute("SELECT id FROM course_progress WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
                            next_row = cursor.fetchone()
                            if next_row:
                                next_id = next_row["id"]
                                cursor.execute("UPDATE course_progress SET status = 'active' WHERE id = ?", (next_id,))
                        logger.info("课程进度已通过 [SYSTEM_PASS] 自动推进！")
                    except Exception as e:
                        logger.error(f"处理 [SYSTEM_PASS] 失败: {e}")

                # 2. 拦截 <glossary> 存入字典
                glossary_matches = re.finditer(r'<glossary\s+term="([^"]+)">([\s\S]*?)</glossary>', accumulated_assistant_content)
                for match in glossary_matches:
                    term = match.group(1).strip()
                    definition = match.group(2).strip()
                    try:
                        cursor.execute("INSERT OR IGNORE INTO glossary (term, definition) VALUES (?, ?)", (term, definition))
                        logger.info(f"术语已收录: {term}")
                    except Exception as e:
                        logger.error(f"处理 glossary 失败: {e}")

                # 3. 拦截 <explainer> 生成本地讲义
                explainer_matches = re.finditer(r'<explainer\s+title="([^"]+)">([\s\S]*?)</explainer>', accumulated_assistant_content)
                for match in explainer_matches:
                    title = match.group(1).strip()
                    content = match.group(2).strip()
                    try:
                        # 确保存放讲义的目录存在
                        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "讲义玉简")
                        os.makedirs(docs_dir, exist_ok=True)
                        filepath = os.path.join(docs_dir, title)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info(f"实体讲义玉简已生成: {filepath}")
                        # 发送给前端，前端会通过 postMessage 转发给 VS Code 插件
                        yield f"data: {json.dumps({'type': 'open_explainer', 'filePath': filepath}, ensure_ascii=False)}\\n\\n"
                    except Exception as e:
                        logger.error(f"处理 explainer 失败: {e}")

                # 4. 常规写入记忆
                try:
                    # 从记录中剔除特殊标签以免污染记忆
                    clean_memory_content = re.sub(r'\[SYSTEM_PASS\]', '', accumulated_assistant_content)
                    clean_memory_content = re.sub(r'<glossary[\s\S]*?</glossary>', '', clean_memory_content)
                    clean_memory_content = re.sub(r'<explainer[\s\S]*?</explainer>', '', clean_memory_content)
                    
                    memory_content = f"【对话记录】\n用户：{last_user_msg}\n媚吻锋：{clean_memory_content.strip()}"
                    cursor.execute(
                        "INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')",
                        (memory_content,)
                    )
                    conn.commit()
                    save_memory_to_rag(last_user_msg, clean_memory_content.strip(), level=0)
                except Exception as e:
                    logger.error(f"Failed to save memory: {e}")
                finally:
                    conn.close()
                    
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
            
        yield f"data: {json_escape(f'[知识库联动] 正在同步本地文件《{filename}》到当前知识库后端，请稍候...')}\n\n"
        
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

def _handle_set_mission(clean_cmd: str) -> StreamingResponse:
    """处理 /设定目标 [具体内容]"""
    mission_text = clean_cmd.replace("/设定目标", "").strip()
    def generator():
        if not mission_text:
            yield f"data: {json_escape('[系统提示] 目标内容不能为空，格式为：/设定目标 我的目标是打败魔尊')}\\n\\n"
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
            yield f"data: {json_escape(f'[系统提示] 宏大目标已铭记于心：【{mission_text}】。接下来的所有授课和考核都将以此为最高导向！')}\\n\\n"
        except Exception as e:
            yield f"data: {json_escape('[系统报错] 目标设定失败: ' + str(e))}\\n\\n"
    return StreamingResponse(generator(), media_type="text/event-stream")
