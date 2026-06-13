import sys
import os
import sqlite3
import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import get_db_connection
from backend.services.memory_decay import generate_summary
from backend.services.rag_factory import get_rag_client

def migrate_memory_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch all memories level >= 1
    cursor.execute("SELECT id, level, summary, timestamp FROM memory_logs WHERE level >= 1 AND status = 'active'")
    rows = cursor.fetchall()
    
    if not rows:
        print("No active memory logs found above level 0.")
        return
        
    rag_client = get_rag_client()
    
    for row in rows:
        log_id = row["id"]
        level = row["level"]
        summary = row["summary"]
        timestamp = row["timestamp"]
        
        print(f"Migrating log {log_id} (Level {level}) - Date: {timestamp}")
        
        date_str = timestamp.split()[0]
        
        # Determine the prompt based on level
        if level == 1:
            prompt = f"""请将用户发给你的修仙日记进行重新排版，提取关键信息并严格按照以下格式输出。不要改变原本的核心意思，只是重新整理格式：
【时间】：{date_str}
【涉及事物/功法】：（提炼日记中提及的重要道具、功法、知识点或话题）
【一句话总结】：（用一句话高度概括核心事件）
【详细记忆】：（日记的具体情感与事件进展，不超过150字）"""
        elif level == 2:
            prompt = f"""请将用户发给你的阶段性总结重新排版，提取关键信息并严格按照以下格式输出。不要改变原本的核心意思，只是重新整理格式：
【时间跨度】：包含 {date_str} 的近期时间
【核心关键点】：（提炼最重要的突破或转折点）
【阶段总结】：（一句话概括）
【详细记忆】：（不超过200字）"""
        elif level == 3:
            prompt = f"""请将用户发给你的传记记忆重新排版，提取关键信息并严格按照以下格式输出。不要改变原本的核心意思，只是重新整理格式：
【时间跨度】：包含 {date_str} 的较长时间
【命运节点】：（最核心的羁绊或境界节点）
【史诗总结】：（一句话概括）
【详细记忆】：（不超过300字）"""
        else:
            continue
            
        try:
            # Send to LLM to reformat
            new_summary = generate_summary(summary, prompt)
            
            if new_summary:
                print(f"New Summary generated for {log_id}:\n{new_summary}\n")
                
                # Update database
                cursor.execute("UPDATE memory_logs SET summary = ? WHERE id = ?", (new_summary, log_id))
                
                # Sync to RAG
                filename = f"Memory_Level_{level}_{log_id}.md"
                rag_sync_text = f"【记录时间：{timestamp}】\n{new_summary}"
                rag_client.sync_knowledge({filename: rag_sync_text}, dataset_name="Memory_Knowledge")
                print(f"Synced {filename} to RAG.")
            else:
                print(f"Failed to generate new summary for log {log_id}.")
        except Exception as e:
            print(f"Error processing log {log_id}: {e}")
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    migrate_memory_logs()
