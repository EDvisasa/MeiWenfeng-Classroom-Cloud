import os
import sqlite3
import chromadb

# 1. Reset classroom.db chat history
db_path = r'D:\MeiWenfeng-Classroom-Cloud\backend\classroom.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('DELETE FROM chat_messages')
    c.execute('DELETE FROM chat_sessions')
    c.execute('DELETE FROM memory_logs')
    conn.commit()
    conn.close()
    print('classroom.db chat history cleared.')

# 2. Reset chroma DB
chroma_dir = r'D:\MeiWenfeng-Classroom-Cloud\backend\rag_index\chroma'
if os.path.exists(chroma_dir):
    try:
        client = chromadb.PersistentClient(path=chroma_dir)
        for collection_name in ['classroom_knowledge', 'conversation_memory']:
            try:
                client.delete_collection(name=collection_name)
                print(f'Collection {collection_name} deleted.')
            except ValueError:
                pass
    except Exception as e:
        print(f'Chroma error: {e}')

print('Memory reset complete.')
