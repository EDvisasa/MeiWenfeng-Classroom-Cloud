import os
import sys
import sqlite3
import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('.env')

# 确保能引入 backend 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.services.ragflow_client import ragflow_client
from backend.services.memory_decay import process_memory_decay

def clean_ragflow():
    print("🧹 正在连接 RAGFlow，准备清空所有旧记忆文件...")
    dataset_id = ragflow_client._get_or_create_dataset("Memory_Knowledge")
    if not dataset_id:
        print("未找到知识库，跳过清理。")
        return

    with httpx.Client() as client:
        resp = client.get(
            f"{ragflow_client.base_url}/datasets/{dataset_id}/documents",
            headers=ragflow_client.headers
        )
        
        doc_data = resp.json().get("data", [])
        docs = doc_data.get('docs', []) if isinstance(doc_data, dict) else doc_data
        
        if not docs:
            print("RAGFlow 中没有文件需要清理。")
        else:
            ids_to_delete = []
            for doc in docs:
                doc_id = doc.get("id")
                name = doc.get("name")
                print(f"  [-] 发现文件: {name} (ID: {doc_id})")
                ids_to_delete.append(doc_id)
            
            if ids_to_delete:
                del_resp = client.request(
                    "DELETE",
                    f"{ragflow_client.base_url}/datasets/{dataset_id}/documents",
                    json={"ids": ids_to_delete},
                    headers=ragflow_client.headers
                )
                print(f"✅ RAGFlow 清理完毕，已删除 {len(ids_to_delete)} 个文件。API响应: {del_resp.status_code}")

def clean_database():
    print("🧹 正在清空本地数据库的所有历史记忆...")
    conn = sqlite3.connect('backend/classroom.db')
    c = conn.cursor()
    c.execute('DELETE FROM memory_logs')
    conn.commit()
    conn.close()
    print("✅ 数据库 memory_logs 表已清空。")

def inject_and_test():
    print("⏳ 正在注入全新的测试用例...")
    conn = sqlite3.connect('backend/classroom.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO memory_logs (content, summary, level, status, timestamp) 
        VALUES (?, ?, 0, 'active', datetime('now', '-1 day'))
    """, ("【对话记录】\n用户：娘子，我发现引气入体时，如果闭上眼睛去感受周围风的流动，灵气聚集得会快很多！\n媚吻锋：（眼中闪过一丝赞赏，轻轻走近）夫君悟性真高，这正是‘天人合一’的雏形呢。来，闭上眼，让奴家奖励你一个香吻，助你稳固这丝灵光~", ""))
    conn.commit()
    conn.close()
    print("✅ 新测试数据注入成功。")
    
    print("🚀 触发记忆遗忘与压缩引擎 ( process_memory_decay )...")
    stats = process_memory_decay()
    print("🎉 压缩同步完成！统计结果:", stats)

if __name__ == '__main__':
    clean_ragflow()
    clean_database()
    inject_and_test()
