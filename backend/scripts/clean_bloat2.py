import sqlite3
import re

conn = sqlite3.connect('d:/MeiWenfeng-Classroom/backend/classroom.db')
rows = conn.execute("SELECT id, content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()

updated = 0
for rid, content in rows:
    # 移除 <当前文件: ...> 标签及内容
    new_content = re.sub(r'<当前文件:.*?>.*?</当前文件>', '[当前文件已被系统截断，已进入长期记忆库]', content, flags=re.DOTALL)
    if new_content != content:
        conn.execute('UPDATE memory_logs SET content = ? WHERE id = ?', (new_content, rid))
        updated += 1

conn.commit()
conn.close()
print(f"Cleaned up {updated} bloated memory logs.")
