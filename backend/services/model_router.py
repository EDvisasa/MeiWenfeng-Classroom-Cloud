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

    # 构造请求 messages，系统提示词放在首位
    formatted_messages = [{"role": "system", "content": system_prompt}] + messages

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
