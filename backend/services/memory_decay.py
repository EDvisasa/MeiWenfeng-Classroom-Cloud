import logging
import sqlite3
from typing import List, Dict, Any
from backend.database import get_db_connection
from backend.services.model_router import get_active_model
from backend.services.rag_factory import get_rag_client
from openai import OpenAI
import os

import threading

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent decay processes
_decay_lock = threading.Lock()

# 定义延时降级配置
DECAY_CONFIGS = [
    {"level": 1, "threshold": "-2 days", "next_level": 2, "prompt": "请将以下几天的纪要高度浓缩。客观记录这期间的核心突破与转折点。\n请严格遵循第三方客观视角，不得加入情绪化语言、主观推测或过度升华。\n务必严格按照以下4个字段格式输出：\n【时间跨度】：{time_span}\n【面向对象】：（列出参与这段时间事件的所有人物/实体）\n【详细纪要】：（客观记录这几天的核心事件经过与转折点，不超过200字）\n【学情洞察】：（提炼这段时间总体的认知成长方向和下一步学习目标。若无则填“无”）"},
    {"level": 2, "threshold": "-7 days", "next_level": 3, "prompt": "请将以下近期的阶段总结提炼为长期记忆。客观记录最核心的事件节点。\n请严格遵循第三方客观视角，不得加入情绪化语言、主观推测或过度升华。\n务必严格按照以下4个字段格式输出：\n【时间跨度】：{time_span}\n【面向对象】：（列出参与这段时间事件的所有人物/实体）\n【详细纪要】：（客观记录这期间最重大的事件和根本性的转变，不超过300字）\n【学情洞察】：（提炼重大的心境或认知突破。若无则填“无”）"},
    {"level": 3, "threshold": "-30 days", "next_level": 4, "prompt": "请将过去一个月的阶段总结提炼为长期学习档案。\n请严格遵循第三方客观视角，不得加入情绪化语言、主观推测或过度升华。\n务必严格按照以下4个字段格式输出：\n【时间跨度】：{time_span}\n【面向对象】：（列出参与这段时间事件的所有核心人物/实体）\n【详细纪要】：（客观记录这期间最核心的阶段性成果与学习轨迹，不超过400字）\n【学情洞察】：（提炼核心的认知跃迁与长远学习挑战。若无则填“无”）"},
    {"level": 4, "threshold": "-365 days", "next_level": 5, "prompt": "请将过去一整年的学习档案提炼为年度终极总结。\n请严格遵循第三方客观视角，不得加入情绪化语言、主观推测或过度升华。\n务必严格按照以下4个字段格式输出：\n【时间跨度】：{time_span}\n【面向对象】：（列出年度核心互动人物/实体）\n【详细纪要】：（客观记录这一整年的终极学习成果、核心转折点与能力沉淀，不超过500字）\n【学情洞察】：（提炼用户在这一年中的根本性认知升级与未来的终极学习方向。若无则填“无”）"}
]

def generate_summary(text: str, prompt: str) -> str:
    """调用大模型生成总结，包含防截断重试和完整性校验"""
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
        if env_key: api_key = env_key
        if env_url: base_url = env_url

    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        logger.warning("No API Key configured, cannot summarize memory.")
        return ""
        
    prompt += "\\n【重要指令】：请直接输出纯文本总结，绝对不要包含任何 Markdown 格式或多余的换行，并且整段文字必须严格以完整的中文句号“。”结尾。"

    safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
    client = OpenAI(api_key=api_key or "no-key-required", base_url=safe_base_url)
    
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_id_api,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                stream=False,
                temperature=0.5
            )
            content = response.choices[0].message.content.strip()
            
            # 完整性校验：是否以标点符号结尾
            if content and content[-1] in ('。', '！', '？', '.', '!', '?', '”', '"', '）', ')'):
                import time
                time.sleep(2) # 正常的防御性休眠
                return content
            else:
                logger.warning(f"Summary incomplete or truncated (Attempt {attempt+1}/3): {content}")
                
        except Exception as e:
            logger.error(f"Failed to generate summary (Attempt {attempt+1}/3): {e}")
            
        import time
        time.sleep(3) # 失败后休眠再重试

    logger.error("All retries failed or resulted in truncated text. Aborting summary generation.")
    return ""

from backend.services.action_registry import SideEffectHandler, action_registry

class MemoryDecayHandler(SideEffectHandler):
    """
    Side effect handler for triggering memory decay.
    """
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        phase_a_only = attrs.get("phase_a_only", False)
        phase_b_only = attrs.get("phase_b_only", False)
        process_memory_decay(phase_a_only=phase_a_only, phase_b_only=phase_b_only)

# Register the handler
action_registry.register("memory_decay", MemoryDecayHandler())

def check_decay_needed(phase_b_only=True) -> bool:
    """检查是否需要进行记忆衰减压缩"""
    import datetime
    import re
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not phase_b_only:
            cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
            if cursor.fetchone()[0] >= 10:
                return True

        for config in DECAY_CONFIGS:
            level = config["level"]
            threshold_str = config["threshold"]

            match = re.search(r'\d+', threshold_str)
            if not match: continue
            threshold_days = int(match.group())

            cursor.execute("SELECT timestamp FROM memory_logs WHERE level = ? AND status = 'active' ORDER BY timestamp ASC LIMIT 1", (level,))
            oldest = cursor.fetchone()
            if oldest:
                oldest_time = datetime.datetime.strptime(oldest["timestamp"], "%Y-%m-%d %H:%M:%S")
                window_end = oldest_time + datetime.timedelta(days=threshold_days)
                if window_end < datetime.datetime.now():
                    return True
        return False
    finally:
        conn.close()

def process_memory_decay(phase_a_only=False, phase_b_only=False) -> Dict[str, Any]:
    """
    检查 memory_logs 表，实现：
    1. 即时归档 (Level 0 -> Level 1): 合并今日所有的 Level 0 对话，生成或更新今日的 Level 1 日记。
    2. 被动延时降级 (Level 1->2, 2->3, 3->4, 4->5)
    """
    if not _decay_lock.acquire(blocking=False):
        logger.info("Memory decay process is already running. Skipping this trigger.")
        return {"processed": 0, "levels": {}, "skipped": True}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        stats = {"processed": 0, "levels": {}}

        # ==========================
        # Phase A: 即时归档 (Level 0 -> 1)
        # ==========================
        level0_rows = []
        if not phase_b_only:
            cursor.execute("SELECT id, content, timestamp FROM memory_logs WHERE level = 0 AND status = 'active' ORDER BY timestamp ASC")
            level0_rows = cursor.fetchall()

        if level0_rows:
            # 检查今天是否已经有 Level 1 的日记
            cursor.execute("SELECT id, summary FROM memory_logs WHERE level = 1 AND status = 'active' AND date(timestamp) = date('now')")
            today_level1 = cursor.fetchone()

            combined_text = ""
            if today_level1:
                combined_text += f"【今日旧日记】\\n{today_level1['summary']}\\n---\\n"

            combined_text += "【新聊天记录】\\n"
            combined_text += "\n---\n".join([r["content"] for r in level0_rows])

            start_time = level0_rows[0]["timestamp"][:16]
            end_time = level0_rows[-1]["timestamp"][:16]
            time_span = f"{start_time} ~ {end_time}"

            prompt = f"""请将以下【今日旧日记】（如果有）和【新聊天记录】合并浓缩为全新的纪要。
请严格遵循第三方客观视角，不得加入情绪化语言、主观推测或过度升华。
务必严格按照以下4个字段格式输出：
【时间跨度】：{time_span}
【面向对象】：（列出参与本次事件或探讨的所有人物/实体）
【详细纪要】：（客观记录事件经过与讨论的核心内容，不超过200字）
【学情洞察】：（仅提炼用户在本次探讨中暴露的知识盲区、易错点或下一步学习方向。若无则填“无”）"""
            new_summary = generate_summary(combined_text, prompt)

            if new_summary:
                # 标记 Level 0 为已压缩
                l0_ids = [r["id"] for r in level0_rows]
                cursor.execute(f"UPDATE memory_logs SET status = 'compressed' WHERE id IN ({','.join(['?']*len(l0_ids))})", l0_ids)

                if today_level1:
                    # 更新今日旧日记
                    cursor.execute("UPDATE memory_logs SET summary = ? WHERE id = ?", (new_summary, today_level1["id"]))
                    l1_id = today_level1["id"]
                else:
                    # 插入新日记
                    cursor.execute("INSERT INTO memory_logs (content, summary, level, status) VALUES ('', ?, 1, 'active')", (new_summary,))
                    l1_id = cursor.lastrowid

                conn.commit()

                # 同步到 RAGFlow 或 当前后端
                import datetime
                date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sync_text = f"【记录时间：{date_str}】\n{new_summary}"
                filename = f"Memory_Level_1_{l1_id}.md"
                rag_client = get_rag_client()
                rag_client.sync_knowledge({filename: sync_text}, dataset_name="Memory_Knowledge")

                stats["processed"] += len(level0_rows)
                stats["levels"][0] = len(level0_rows)

        # ==========================
        # Phase B: 被动延时降级 (Level N -> N+1)
        # 修复了时间窗口压缩 Bug，确保能够按时间块聚合日志
        # ==========================
        import datetime
        import re

        configs_to_run = DECAY_CONFIGS if not phase_a_only else []
        for config in configs_to_run:
            level = config["level"]
            threshold_str = config["threshold"]
            next_level = config["next_level"]
            prompt = config["prompt"]

            # 从 threshold 中提取天数（例如 "-2 days" -> 2）
            match = re.search(r'\d+', threshold_str)
            if not match:
                continue
            threshold_days = int(match.group())

            # 寻找该层级最老的一条活跃日志
            cursor.execute("SELECT timestamp FROM memory_logs WHERE level = ? AND status = 'active' ORDER BY timestamp ASC LIMIT 1", (level,))
            oldest = cursor.fetchone()

            if not oldest:
                continue

            oldest_time = datetime.datetime.strptime(oldest["timestamp"], "%Y-%m-%d %H:%M:%S")
            window_end = oldest_time + datetime.timedelta(days=threshold_days)
            current_time = datetime.datetime.now()

            # 只有当整个时间窗口（如 2 天、7 天）完全成为过去时，才进行打包压缩
            if window_end < current_time:
                cursor.execute("""
                    SELECT id, summary, timestamp FROM memory_logs
                    WHERE level = ? AND status = 'active' AND timestamp <= ?
                    ORDER BY timestamp ASC
                """, (level, window_end.strftime("%Y-%m-%d %H:%M:%S")))

                rows = cursor.fetchall()
                if not rows:
                    continue

                start_time = rows[0]["timestamp"][:16]
                end_time = rows[-1]["timestamp"][:16]
                time_span = f"{start_time} ~ {end_time}"

                dynamic_prompt = prompt.replace("{time_span}", time_span)

                combined_text = "\n---\n".join([r["summary"] for r in rows])
                new_summary = generate_summary(combined_text, dynamic_prompt)

                if new_summary:
                    old_ids = [r["id"] for r in rows]
                    cursor.execute(f"UPDATE memory_logs SET status = 'compressed' WHERE id IN ({','.join(['?']*len(old_ids))})", old_ids)

                    cursor.execute("""
                        INSERT INTO memory_logs (content, summary, level, status)
                        VALUES ('', ?, ?, 'active')
                    """, (new_summary, next_level))
                    new_id = cursor.lastrowid

                    conn.commit()

                    filename = f"Memory_Level_{next_level}_{new_id}.md"
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sync_text = f"【记录时间：{date_str}】\n{new_summary}"
                    rag_client = get_rag_client()
                    rag_client.sync_knowledge({filename: sync_text}, dataset_name="Memory_Knowledge")

                    stats["processed"] += len(rows)
                    stats["levels"][level] = len(rows)

        conn.close()
        return stats
    finally:
        _decay_lock.release()
