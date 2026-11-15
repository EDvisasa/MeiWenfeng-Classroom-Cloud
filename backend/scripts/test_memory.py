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
    raise RuntimeError(
        "【安全拦截】严禁在测试中直连并清空生产数据库 backend/classroom.db！"
        "用户重要记忆必须受到绝对物理保护。"
    )

def inject_and_test():
    raise RuntimeError(
        "【安全拦截】严禁在测试中直连并污染生产数据库 backend/classroom.db！"
        "如需测试，请通过 pytest 与 conftest.py 提供的临时数据库执行。"
    )

if __name__ == '__main__':
    print("本测试脚本已受【数据库变异拦截规则】物理保护，严禁直连生产数据库执行。")

