import os
import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
import tiktoken

from backend.database import get_db_connection
from backend.services.model_router import get_active_model

logger = logging.getLogger(__name__)

COMPACT_PROMPT_TEMPLATE = """请将以下多轮历史对话高度提炼浓缩为一段客观、结构化的【前情提要】。
严格遵循以下提取维度（若某项在对话中未涉及则自适应忽略，切勿无中生有）：

- 【阿冯（User）】：
  * 学习与认知：掌握了哪些知识点、遇到了什么理解卡点或具体疑问；
  * 诉求与决策：提出了什么新任务、做出了什么技术/架构/生活拍板；
- 【吻锋（Mentor/Assistant）】：
  * 授课与引导：讲解了什么核心概念、指出了什么关键技术要害；
  * 情感与羁绊：重要互动、约定或情感状态；
- 【小白（OpenClaw/Assistant）】：
  * 技术与执行：提供了什么方案、执行了什么脚本/测试、汇报了什么系统状态；
- 【三人共识与关键事件】：
  * 三人共同敲定的核心结论、有趣的打闹梗或下一步行动目标。

【输出格式要求】：
请直接输出纯文本，以清晰的字段分行呈现，控制在 300~500 字以内，结尾必须为完整的中文句号。
"""


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """估算消息列表所占用的 Token 数量"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        total_tokens = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total_tokens += len(encoding.encode(content)) + 4
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total_tokens += len(encoding.encode(item.get("text", ""))) + 4
        return total_tokens
    except Exception as e:
        logger.warning(f"tiktoken estimation fallback: {e}")
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 3


def call_llm_for_summary(messages: List[Dict[str, Any]]) -> str:
    """调用大模型提炼会话历史纪要"""
    model_info = get_active_model()
    protocol = model_info["protocol"]
    base_url = model_info["base_url"]
    api_key = model_info["api_key"]
    model_name = model_info["name"]
    selected_model_id = model_info.get("selected_model_id")

    if selected_model_id:
        model_id_api = selected_model_id
    else:
        model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
        if "qwen" in model_name.lower():
            model_id_api = "qwen3.6-35b"
        elif "gemma" in model_name.lower():
            model_id_api = "gemma-9b"
        elif "deepseek" in model_name.lower():
            model_id_api = "deepseek-chat"

    if ("deepseek" in model_name.lower() or protocol == "openai") and "本地" not in model_name:
        env_key = os.getenv("AIRP_MODEL_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        env_url = os.getenv("AIRP_MODEL_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        if env_key:
            api_key = env_key
        if env_url:
            base_url = env_url

    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        logger.warning("No API Key configured, cannot perform LLM compaction.")
        return ""

    # 将对话序列格式化为文本串
    convo_lines = []
    for m in messages:
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join([item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"])
        # 剥离内部标签避免干扰
        cleaned = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
        cleaned = re.sub(r'<monologue>.*?</monologue>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<property_update.*?>', '', cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            convo_lines.append(f"[{role.upper()}]: {cleaned}")

    full_convo_text = "\n\n".join(convo_lines)
    if not full_convo_text:
        return ""

    safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
    client = OpenAI(api_key=api_key or "no-key-required", base_url=safe_base_url)

    try:
        response = client.chat.completions.create(
            model=model_id_api,
            messages=[
                {"role": "system", "content": COMPACT_PROMPT_TEMPLATE},
                {"role": "user", "content": full_convo_text}
            ],
            stream=False,
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"Failed to generate compaction summary via LLM: {e}")
        return ""


def generate_compact_summary(messages: List[Dict[str, Any]]) -> str:
    """生成带有标准 XML 包装的结构化压缩摘要"""
    raw_summary = call_llm_for_summary(messages)
    if not raw_summary:
        raw_summary = "（早期对话主要围绕系统交互与功能调试展开。）"
    return f"<compact_summary>\n[Earlier Conversation Summary / 早期对话纪要]\n{raw_summary}\n</compact_summary>"


def compact_conversation_messages(
    messages: List[Dict[str, Any]],
    keep_recent_turns: int = 10
) -> Tuple[List[Dict[str, Any]], str]:
    """
    将长对话拆分为：头部 <compact_summary> 锚点 + 最近 keep_recent_turns 轮原始对白。
    """
    if len(messages) <= keep_recent_turns:
        return messages, ""

    older_messages = messages[:-keep_recent_turns]
    recent_messages = messages[-keep_recent_turns:]

    summary_xml = generate_compact_summary(older_messages)
    
    # 构造头部压缩锚点
    summary_message = {
        "role": "user",
        "content": summary_xml
    }

    compacted = [summary_message] + list(recent_messages)
    return compacted, summary_xml


def check_and_auto_compact(
    messages: List[Dict[str, Any]],
    custom_max_tokens: int = 8192,
    threshold_ratio: float = 0.8,
    keep_recent_turns: int = 10
) -> Tuple[bool, List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    检测当前消息 Token 占用是否超过阈值；超限则触发 Auto-Compact 并返回提示。
    """
    total_tokens = estimate_messages_tokens(messages)
    threshold = int(custom_max_tokens * threshold_ratio)

    if total_tokens > threshold and len(messages) > keep_recent_turns:
        logger.info(f"Auto-Compact triggered: {total_tokens} tokens > {threshold} (threshold {threshold_ratio*100}%)")
        compacted_msgs, summary_xml = compact_conversation_messages(messages, keep_recent_turns=keep_recent_turns)
        hint = {
            "type": "system_hint",
            "icon": "compact",
            "text": f"🧹 检测到会话上下文接近上限（估算 {total_tokens} tokens / 阈值 {threshold}），已自动浓缩早期对话记忆，会话无缝继续~"
        }
        return True, compacted_msgs, hint

    return False, messages, None


def save_session_compact_state(session_id: str, summary: str, cutoff_id: int):
    """持久化会话压缩状态与分水岭到数据库"""
    if not session_id:
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chat_sessions SET compact_summary = ?, compact_cutoff_id = ? WHERE id = ?",
            (summary, cutoff_id, session_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save compact state for session {session_id}: {e}")
