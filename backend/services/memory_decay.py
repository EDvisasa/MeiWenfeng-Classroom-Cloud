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
    {"level": 1, "threshold": "-2 days", "next_level": 2, "prompt": "请将以下这几天的修仙日记进一步压缩，提炼出这段时间的修炼主线和师生关系进展。\n请严格按照以下格式输出：\n【时间跨度】：（根据内容总结时间跨度）\n【涉及事物/功法】：（提炼核心道具、功法或话题）\n【阶段总结】：（一句话高度概括该阶段）\n【修行心得】：（提炼出易错点、非直觉洞察和下一步学习方向）\n【详细记忆】：（不超过150字的具体经过）"},
    {"level": 2, "threshold": "-7 days", "next_level": 3, "prompt": "请将以下近期的修炼总结高度浓缩为长期记忆标签。\n请严格按照以下格式输出：\n【时间跨度】：（如：近一周）\n【核心关键点】：（提炼最重要的突破或转折点）\n【阶段总结】：（一句话概括）\n【修行心得】：（提炼这段时间总体的认知成长和下一阶段方向）\n【详细记忆】：（不超过200字）"},
    {"level": 3, "threshold": "-30 days", "next_level": 4, "prompt": "请提炼出过去这一个月甚至更久的核心羁绊与命运轨迹，凝练成一段史诗般的传记记忆。\n请严格按照以下格式输出：\n【时间跨度】：（如：近一个月）\n【命运节点】：（最核心的羁绊或境界节点）\n【史诗总结】：（一句话概括）\n【修行心得】：（境界或心境的重大突破领悟）\n【详细记忆】：（不超过300字）"}
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

def process_memory_decay() -> Dict[str, Any]:
    """
    检查 memory_logs 表，实现：
    1. 即时归档 (Level 0 -> Level 1): 合并今日所有的 Level 0 对话，生成或更新今日的 Level 1 日记。
    2. 被动延时降级 (Level 1->2, 2->3, 3->4)
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
        cursor.execute("SELECT id, content FROM memory_logs WHERE level = 0 AND status = 'active' ORDER BY timestamp ASC")
        level0_rows = cursor.fetchall()

        if level0_rows:
            # 检查今天是否已经有 Level 1 的日记
            cursor.execute("SELECT id, summary FROM memory_logs WHERE level = 1 AND status = 'active' AND date(timestamp) = date('now')")
            today_level1 = cursor.fetchone()

            combined_text = ""
            if today_level1:
                combined_text += f"【今日旧日记】\\n{today_level1['summary']}\\n---\\n"

            combined_text += "【新聊天记录】\\n"
            combined_text += "\\n---\\n".join([r["content"] for r in level0_rows])

            prompt = """请将以下【今日旧日记】（如果有）和【新聊天记录】合并浓缩，生成一份全新的今日修仙日记。
请务必严格按照以下格式输出：
【时间】：（根据内容填写大致时间段）
【涉及事物/功法】：（提炼聊天中提及的重要道具、功法、知识点或话题）
【一句话总结】：（用一句话高度概括核心事件）
【修行心得】：（提炼出易错点、非直觉洞察和下一步的 Zone of Proximal Development 挑战区）
【详细记忆】：（总结今天的核心事件和情感进展，不超过150字）"""
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

        for config in DECAY_CONFIGS:
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

                start_date = rows[0]["timestamp"].split()[0]
                end_date = rows[-1]["timestamp"].split()[0]
                if start_date == end_date:
                    date_range_str = start_date
                else:
                    date_range_str = f"{start_date} 至 {end_date}"

                dynamic_prompt = prompt.replace("（根据内容总结时间跨度）", date_range_str)
                dynamic_prompt = dynamic_prompt.replace("（如：近一周）", date_range_str)
                dynamic_prompt = dynamic_prompt.replace("（如：近一个月）", date_range_str)

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
