import os
import json
import logging
from typing import Generator, List, Dict
from openai import OpenAI
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

def get_active_model() -> Dict:
    """从数据库获取当前激活的模型配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, protocol, base_url, api_key FROM model_config WHERE is_active = 1 LIMIT 1"
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
        "api_key": os.getenv("DEEPSEEK_API_KEY", "")
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
    system_prompt: str
) -> Generator[str, None, None]:
    """
    流式对话接口路由器。
    支持 openai 协议（DeepSeek, Qwen 本地, Gemma 本地等），后续可扩展 claude / gemini 协议。
    """
    model_info = get_active_model()
    protocol = model_info["protocol"]
    base_url = model_info["base_url"]
    api_key = model_info["api_key"]
    model_name = model_info["name"]
    
    # 映射模型名称到 API 要求的具体 model 字符串
    model_id_api = "deepseek-chat"
    if "qwen" in model_name.lower():
        model_id_api = "qwen3.6-35b"  # 本地 llama.cpp
    elif "gemma" in model_name.lower():
        model_id_api = "gemma-9b"      # 本地 Ollama
    elif "deepseek" in model_name.lower():
        model_id_api = "deepseek-chat"
        
    # 如果 API Key 为空且环境变量里有，则使用环境变量的值
    if not api_key:
        if "deepseek" in model_name.lower():
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if api_key:
                update_model_key_if_empty(model_info["id"], api_key)
        elif "claude" in model_name.lower():
            api_key = os.getenv("CLAUDE_API_KEY", "")
        elif "gemini" in model_name.lower():
            api_key = os.getenv("GEMINI_API_KEY", "")

    # 构造请求 messages，系统提示词放在首位
    formatted_messages = [{"role": "system", "content": system_prompt}] + messages

    logger.info(f"Routing chat to model: {model_name} (Protocol: {protocol}, URL: {base_url})")

    # 1. OpenAI 协议 (DeepSeek & 本地模型)
    if protocol == "openai":
        if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            yield f"[系统提示] 错误：检测到模型 {model_name} 需要 API Key，但当前数据库和环境变量中皆未配置。请检查您的 `.env` 或在设置中配置密钥。"
            return

        try:
            client = OpenAI(
                api_key=api_key or "no-key-required",
                base_url=base_url
            )
            
            response = client.chat.completions.create(
                model=model_id_api,
                messages=formatted_messages,
                stream=True,
                temperature=1.0,  # 稍微高一点让角色扮演更生动
                max_tokens=2000
            )
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta_content = chunk.choices[0].delta.content
                    if delta_content:
                        yield delta_content
                        
        except Exception as e:
            logger.error(f"Error during OpenAI stream chat: {e}", exc_info=True)
            yield f"[后端错误] 无法连接到 {model_name} API。错误详情: {str(e)}"

    # 2. Gemini 协议 (开发备用)
    elif protocol == "gemini":
        yield "[系统提示] Gemini 协议暂未完全集成，第一阶段 MVP 优先推荐使用 DeepSeek (在线)。"
        
    # 3. Claude 协议 (开发备用)
    elif protocol == "claude":
        yield "[系统提示] Claude 协议暂未完全集成，第一阶段 MVP 优先推荐使用 DeepSeek (在线)。"
        
    else:
        yield f"[系统提示] 未知协议: {protocol}"
