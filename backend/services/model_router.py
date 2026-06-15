import os
import json
import logging
from typing import Generator, List, Dict
from openai import OpenAI
from backend.database import get_db_connection
from backend.services.agent_tools import TOOL_REGISTRY

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
            
            import platform
            current_os = platform.system()
            os_instruction = f"Operating System: {current_os}."
            if current_os == "Windows":
                os_instruction += " You are using Windows cmd.exe. CRITICAL: Multiline strings do NOT work well in `python -c` or standard terminal commands here. If you need to run a python script, write it entirely on ONE line using semicolons (e.g. `python -c \"import os; print('hi')\"`), or write it to a temporary .py file and execute that file. Use Windows commands (e.g., `dir` instead of `ls`)."
            else:
                os_instruction += " You are using a standard Unix bash shell."

            system_injection = f"""
<tool_use_guidelines>
You have access to a local command-line terminal and file system tools. 
{os_instruction}

CRITICAL RULES:
1. THINK BEFORE YOU ACT: You MUST ALWAYS start your response with a <thought> block to explain your plan and reasoning.
2. ONE TOOL AT A TIME: You may only execute one tool call per turn. 
3. STOP AND WAIT: After closing the </call_tool> tag, you MUST STOP generating immediately. The system will automatically reply with "[System Tool Result]".
4. ERROR RECOVERY: If the system execution result contains an error, analyze it in your next <thought> block and try a different command. Do NOT bother the user with technical errors.
5. USE SPECIFIC TOOLS: You MUST use `read_file` to read file contents. NEVER use `cat` or `type` via `execute_bash`. If you don't know the exact file name, use `execute_bash` with `dir` or `ls` first to find the exact filename, then use `read_file`.
6. MAINTAIN PERSONA: When you have gathered all necessary information and are ready to reply to the user, you MUST completely drop the XML tags and resume your roleplay persona (狐妖导师) to give the final answer. NEVER expose XML tags or tool outputs to the user in your final reply.

TOOL EXECUTION FORMAT:
<thought>
I need to check the current directory contents.
</thought>
<call_tool name="execute_bash">
<command>{"dir" if current_os == "Windows" else "ls -la"}</command>
</call_tool>

OR to read a file (optionally specifying lines to read):
<thought>
I need to read lines 10 to 50 of config.json.
</thought>
<call_tool name="read_file">
<path>config.json</path>
<start_line>10</start_line>
<end_line>50</end_line>
</call_tool>

Remember: ALWAYS start with <thought>. NEVER mix conversational text with tool calls. Be strictly silent (except for <thought>) until the work is done.
</tool_use_guidelines>
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
                
                kwargs = {
                    "model": model_id_api,
                    "messages": current_messages,
                    "stream": True,
                    "temperature": 1.0,
                    "stop": ["</call_tool>", "</execute_bash>"]
                }
                if max_tokens > 0:
                    kwargs["max_tokens"] = max_tokens
                    
                response = client.chat.completions.create(**kwargs)
                
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
                import xml.etree.ElementTree as ET
                
                tool_name = None
                tool_param = {}
                command_str = ""
                
                # 新版 XML 解析
                match_new = re.search(r'<call_tool[^>]*>.*?(?:</call_tool>|$)', full_content, re.DOTALL)
                if match_new:
                    tool_xml = match_new.group(0)
                    if not tool_xml.endswith("</call_tool>"):
                        tool_xml += "</call_tool>"
                    try:
                        root = ET.fromstring(tool_xml)
                        tool_name = root.attrib.get("name")
                        for child in root:
                            tool_param[child.tag] = child.text if child.text else ""
                            
                        # 给前端展示用的友好字符串
                        if tool_name == "read_file":
                            path = tool_param.get("path", "")
                            start_line = tool_param.get("start_line", "")
                            end_line = tool_param.get("end_line", "")
                            if start_line and end_line:
                                command_str = f"{path} (Lines {start_line}-{end_line})"
                            elif start_line:
                                command_str = f"{path} (From line {start_line})"
                            else:
                                command_str = path
                        else:
                            command_str = tool_param.get("command", str(tool_param))
                    except Exception as e:
                        pass
                
                # 兼容旧版 <execute_bash> 标签 (以防模型没按新规矩来)
                if not tool_name:
                    match_old = re.search(r'<execute_bash>(.*?)(?:</execute_bash>|$)', full_content, re.DOTALL)
                    if match_old:
                        tool_name = "execute_bash"
                        command_str = match_old.group(1).strip()
                        tool_param = {"command": command_str}
                
                if not tool_name:
                    break # 结束对话
                
                current_messages.append({
                    "role": "assistant",
                    "content": full_content + ("</call_tool>" if match_new and "</call_tool>" not in full_content else "")
                })
                
                yield {"type": "tool_start", "tool_name": tool_name, "command": command_str}
                
                if tool_name in TOOL_REGISTRY:
                    output = TOOL_REGISTRY[tool_name].execute(tool_param)
                else:
                    output = f"[Error] Unknown tool: {tool_name}"
                
                yield {"type": "tool_output", "text": output}
                
                # 将工具执行结果喂给模型
                current_messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n{output}\n\n请根据上述结果继续分析，或者如果信息足够，请立刻使用狐妖人格进行最终回复（最终回复绝不能包含任何XML标签）。"
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
