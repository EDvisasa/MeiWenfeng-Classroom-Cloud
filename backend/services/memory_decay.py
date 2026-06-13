import logging
import sqlite3
from typing import List, Dict, Any
from backend.database import get_db_connection
from backend.services.model_router import get_active_model
from backend.services.rag_factory import get_rag_client
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

# 定义延时降级配置
DECAY_CONFIGS = [
    {"level": 1, "threshold": "-2 days", "next_level": 2, "prompt": "请将以下这几天的修仙日记进一步压缩，提炼出这段时间的修炼主线和师生关系进展，不超过150字。"},
    {"level": 2, "threshold": "-7 days", "next_level": 3, "prompt": "请将以下近期的修炼总结高度浓缩为长期记忆标签，包括主角的修为境界突破、重要感情转折点等，不超过200字。"},
    {"level": 3, "threshold": "-30 days", "next_level": 4, "prompt": "请提炼出过去这一个月甚至更久的核心羁绊与命运轨迹，凝练成一段史诗般的传记记忆。"}
]

def generate_summary(text: str, prompt: str) -> str:
    """调用大模型生成总结，包含防截断重试和完整性校验"""
    model_info = get_active_model()
    protocol = model_info["protocol"]
    base_url = model_info["base_url"]
    api_key = model_info["api_key"]
    model_name = model_info["name"]
    
    model_id_api = os.getenv("AIRP_MODEL_NAME", "gpt-4o-mini")
    if "qwen" in model_name.lower():
        model_id_api = "qwen3.6-35b"
    elif "gemma" in model_name.lower():
        model_id_api = "gemma-9b"
    elif "deepseek" in model_name.lower():
        model_id_api = "deepseek-chat"
        
    if "deepseek" in model_name.lower() or protocol == "openai":
        env_key = os.getenv("AIRP_MODEL_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        env_url = os.getenv("AIRP_MODEL_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        if env_key: api_key = env_key
        if env_url: base_url = env_url

    if not api_key:
        logger.warning("No API Key configured, cannot summarize memory.")
        return ""
        
    prompt += "\n【重要指令】：请直接输出纯文本总结，绝对不要包含任何 Markdown 格式或多余的换行，并且整段文字必须严格以完整的中文句号“。”结尾。"

    client = OpenAI(api_key=api_key or "no-key-required", base_url=base_url)
    
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
            combined_text += f"【今日旧日记】\n{today_level1['summary']}\n---\n"
        
        combined_text += "【新聊天记录】\n"
        combined_text += "\n---\n".join([r["content"] for r in level0_rows])

        prompt = "请将以下【今日旧日记】（如果有）和【新聊天记录】合并浓缩，生成一份不超过150字的全新今日修仙日记，总结今天的核心事件和情感进展。"
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
            filename = f"Memory_Level_1_{l1_id}.md"
            rag_client = get_rag_client()
            rag_client.sync_knowledge({filename: new_summary}, dataset_name="Memory_Knowledge")
            
            stats["processed"] += len(level0_rows)
            stats["levels"][0] = len(level0_rows)

    # ==========================
    # Phase B: 被动延时降级 (Level N -> N+1)
    # ==========================
    for config in DECAY_CONFIGS:
        level = config["level"]
        threshold = config["threshold"]
        next_level = config["next_level"]
        prompt = config["prompt"]
        
        cursor.execute(f"""
            SELECT id, summary FROM memory_logs 
            WHERE level = ? AND timestamp < datetime('now', ?) AND status = 'active'
            ORDER BY timestamp ASC
        """, (level, threshold))
        
        rows = cursor.fetchall()
        if not rows:
            continue
            
        combined_text = "\n---\n".join([r["summary"] for r in rows])
        new_summary = generate_summary(combined_text, prompt)
        
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
            rag_client = get_rag_client()
            rag_client.sync_knowledge({filename: new_summary}, dataset_name="Memory_Knowledge")
            
            stats["processed"] += len(rows)
            stats["levels"][level] = len(rows)
            
    conn.close()
    return stats
