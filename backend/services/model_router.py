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
    selected_model_id = model_info.get("selected_model_id")
    
    # 优先采用用户在配置界面选择的子模型 ID
    if selected_model_id:
        model_id_api = selected_model_id
    else:
        # 降级：映射模型名称到 API 要求的具体 model 字符串
        model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
        if "qwen" in model_name.lower():
            model_id_api = "qwen3.6-35b"  # 本地 llama.cpp
        elif "gemma" in model_name.lower():
            model_id_api = "gemma-9b"      # 本地 Ollama
        elif "deepseek" in model_name.lower():
            model_id_api = "deepseek-chat"

        
    # 如果是 DeepSeek 或默认的在线模型，优先从环境变量覆盖 base_url 和 api_key（防止在线代理随时变动）
    # 但如果是“本地”模型，绝不覆盖，保留其 localhost:xxxx 端口
    if ("deepseek" in model_name.lower() or protocol == "openai") and "本地" not in model_name:
        env_key = os.getenv("AIRP_MODEL_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        env_url = os.getenv("AIRP_MODEL_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        
        if env_key:
            api_key = env_key
        if env_url:
            base_url = env_url

    # 构造请求 messages，系统提示词放在首位
    formatted_messages = [{"role": "system", "content": system_prompt}] + messages

    logger.info(f"Routing chat to model: {model_name} (Protocol: {protocol}, URL: {base_url})")

    # 1. OpenAI 协议 (DeepSeek & 本地模型)
    if protocol == "openai":
        if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            yield {"type": "text", "text": f"[系统提示] 错误：检测到模型 {model_name} 需要 API Key，但当前数据库和环境变量中皆未配置。请检查您的 `.env` 或在设置中配置密钥。"}
            return

        try:
            # Avoid IPv6 connection issues on Windows with httpx by mapping localhost to 127.0.0.1
            safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
            client = OpenAI(
                api_key=api_key or "no-key-required",
                base_url=safe_base_url
            )
            
            system_injection = """
【重要系统指令：工具调用】
你现在拥有执行本地终端命令的能力。如果需要读取文件、列出目录、搜索内容等，请在回答的**末尾**输出以下格式：
<execute_bash>
你要执行的完整命令
</execute_bash>
系统会自动拦截并执行，然后将结果返回给你。每次只能执行一个命令，收到结果前请不要继续回答。如果不需要执行命令，则正常回答即可。
"""
            # Insert the system instruction into the first message
            if len(formatted_messages) > 0 and formatted_messages[0]["role"] == "system":
                formatted_messages[0]["content"] = str(formatted_messages[0]["content"]) + "\n\n" + system_injection
            else:
                formatted_messages.insert(0, {"role": "system", "content": system_injection})
            
            max_iterations = 5
            iteration = 0
            current_messages = formatted_messages.copy()
            
            while iteration < max_iterations:
                iteration += 1
                response = client.chat.completions.create(
                    model=model_id_api,
                    messages=current_messages,
                    stream=True,
                    temperature=1.0,
                    max_tokens=2000
                )
                
                full_content = ""
                
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        
                        # 1. 拦截 Reasoning Content
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            yield {"type": "thinking", "text": delta.reasoning_content}
                            
                        # 2. 普通文本内容 (Text)
                        if delta.content:
                            full_content += delta.content
                            yield {"type": "text", "text": delta.content}
                            
                # 检查是否包含工具调用
                import re
                match = re.search(r'<execute_bash>(.*?)</execute_bash>', full_content, re.DOTALL)
                
                if not match:
                    break # 结束对话
                    
                command = match.group(1).strip()
                
                current_messages.append({
                    "role": "assistant",
                    "content": full_content
                })
                
                yield {"type": "tool_start", "tool_name": "execute_bash", "command": command}
                
                import subprocess
                try:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                    output = result.stdout + result.stderr
                    if not output.strip():
                        output = "[Command executed successfully with no output]"
                except subprocess.TimeoutExpired:
                    output = "[Error] Command timed out after 10 seconds."
                except Exception as e:
                    output = f"[Error] {e}"
                
                yield {"type": "tool_output", "text": output}
                
                # 将工具执行结果喂给模型
                current_messages.append({
                    "role": "user",
                    "content": f"[系统返回的执行结果]:\n{output}\n\n请根据上述结果继续回答或执行下一步。"
                })
                
                yield {"type": "tool_end"}
                        
        except Exception as e:
            logger.error(f"Error during OpenAI stream chat: {e}", exc_info=True)
            yield {"type": "text", "text": f"[后端错误] 无法连接到 {model_name} API。错误详情: {str(e)}"}

    # 2. Gemini 协议 (开发备用)
    elif protocol == "gemini":
        yield "[系统提示] Gemini 协议暂未完全集成，第一阶段 MVP 优先推荐使用 DeepSeek (在线)。"
        
    # 3. Claude 协议 (开发备用)
    elif protocol == "claude":
        yield "[系统提示] Claude 协议暂未完全集成，第一阶段 MVP 优先推荐使用 DeepSeek (在线)。"
        
    else:
        yield f"[系统提示] 未知协议: {protocol}"
