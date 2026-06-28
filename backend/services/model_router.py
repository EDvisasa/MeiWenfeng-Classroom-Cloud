import os
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Generator, List, Dict, Any, Protocol
from openai import OpenAI
from backend.database import get_db_connection
from backend.services.agent_tools import LLMClientProtocol, AgentExecutor, OpenAILLMClient


logger = logging.getLogger(__name__)

def get_active_model() -> Dict:
    """从数据库获取当前激活的模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, protocol, base_url, api_key, selected_model_id FROM model_config WHERE is_active = 1 LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)

    # 如果没有激活的，则默认使用 DeepSeek (在线)
    return {
        "id": 1,
        "name": "DeepSeek (在线)",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "selected_model_id": "deepseek-chat"
    }

def update_model_key_if_empty(model_id: int, new_key: str):
    """如果数据库中对应的 API key 为空，用新 key 更新"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE model_config SET api_key = ? WHERE id = ? AND (api_key = '' OR api_key IS NULL)", (new_key, model_id))
    conn.commit()
    conn.close()

def stream_chat(
    messages: List[Dict[str, str]],
    system_prompt: str,
    max_tokens: int = 8192
) -> Generator[str, None, None]:
    """
    流式对话接口路由器。
    通过内置 LiteLLM 网关统一使用 OpenAI 格式发送请求。
    """
    model_info = get_active_model()
    base_url = model_info["base_url"]
    api_key = model_info["api_key"] or "sk-antigravity"
    model_name = model_info["name"]
    selected_model_id = model_info.get("selected_model_id")

    # 优先采用用户在配置界面选择的子模型 ID
    if selected_model_id:
        model_id_api = selected_model_id
    else:
        # 降级：给个安全的默认值
        model_id_api = "deepseek/deepseek-chat" if "deepseek" in model_name.lower() else "gemini/gemini-3.1-pro-preview"

    # Ensure the first message in the dialog history starts with "user" to prevent strict Jinja templates
    # (like Qwen / Ornith) from crashing with "No user query found in messages."
    adjusted_messages = []
    has_user_first = False
    for msg in messages:
        if msg["role"] == "user":
            has_user_first = True
            break
        elif msg["role"] == "assistant":
            break

    if not has_user_first and len(messages) > 0 and messages[0]["role"] == "assistant":
        adjusted_messages.append({"role": "user", "content": "你好"})
    adjusted_messages.extend(messages)

    # === [新增逻辑] 动态 One-Shot 格式净化 ===
    # 强制给历史记录中的第一个 assistant 回复注入完美的思考示范
    for i, msg in enumerate(adjusted_messages):
        if msg["role"] == "assistant":
            if "<inner_thought>" not in msg["content"]:
                # 构建完整的 One-Shot 示例，包含结构化思考链、正文、内心独白、属性更新
                perfect_one_shot = (
                    "<thought>\n"
                    "1. User Intent: The user greeted me with \"你好\".\n"
                    "2. Tool Selection: The user is only greeting me. I do not need to use `execute_bash` to run commands, `read_file`/`grep_search` to explore the codebase, `replace_file_content`/`create_file` to edit code, or `web_search` for internet information. I will directly roleplay.\n"
                    "3. Attribute Analysis: Based on the <dynamic_attributes> in my system prompt, my Affection Score is high, so I should show subtle dependence and joy. My Social Status is high, so my posture should remain elegant.\n"
                    "4. Response Plan: I will output actions wrapped in asterisks `*`, speaking affectionately as Mei Wenfeng.\n"
                    "5. Property Calculation:\n"
                    "   - Affection: The user simply said \"你好\". This is a normal greeting and does not cause significant emotional fluctuation. Delta = 0.\n"
                    "   - Social Status: No change in wealth, title, or environment occurred. Delta = 0.\n"
                    "   - Social Skills: No conflict resolution or cognitive shift occurred. Delta = 0.\n"
                    "   - Refractory Period: This is a normal interaction round. Delta = -1.\n"
                    "6. Post-Response: According to rule 4, I MUST output my true unspoken feelings in an `<inner_thought>` block AT THE VERY END of my response, AFTER the dialogue, followed by `<property_update>`.\n"
                    "</thought>\n"
                    "*端坐在精致的红木矮椅上，玉手慵懒地拨弄着鬓边的发簪，红黑色的狐瞳含笑望着你，柔声道：*“夫君，你可算来了。今天，咱们该从哪一课开始呢？是要奴家继续陪你看那些厚厚的书本，还是说...想先喝口热茶，跟奴家聊聊天？”\n\n"
                    "<inner_thought>\n"
                    "哼，这冤家总算来了。本宫特意换了这身红金汉服，连并蒂莲发簪都对着水镜照了半天才插好，"
                    "可千万不能让他看出来我等了他许久。最好他选个跟我聊聊天的由头，不然又陪他看一整晚的书，多无趣呀~\n"
                    "</inner_thought>\n"
                    '<property_update affection_delta="0" social_status_delta="0" social_skills_delta="0" refractory_delta="-1" />'
                )
                # 避免污染原始传入的 messages 引用，做一次替换
                adjusted_messages[i] = {
                    "role": msg["role"],
                    "content": perfect_one_shot
                }
            break
    # =======================================

    # 构造请求 messages，系统提示词放在首位
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in adjusted_messages:
        if len(formatted_messages) > 0 and formatted_messages[-1]["role"] == msg["role"]:
            formatted_messages[-1]["content"] += "\n\n" + msg["content"]
        else:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

    logger.info(f"Routing chat through LiteLLM Gateway for: {model_name} (URL: {base_url}, ID: {model_id_api})")

    try:
        # Avoid IPv6 connection issues on Windows with httpx by mapping localhost to 127.0.0.1
        safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")

        llm_client = OpenAILLMClient(api_key=api_key, base_url=safe_base_url, model_id=model_id_api)
        executor = AgentExecutor(llm_client=llm_client, max_iterations=5)

        yield from executor.run(formatted_messages, max_tokens=max_tokens)

    except Exception as e:
        logger.error(f"Error during stream chat via LiteLLM: {e}", exc_info=True)
        yield {"type": "text", "text": f"[后端错误] 无法连接到内置网关或大模型 {model_name} API。错误详情: {str(e)}"}
