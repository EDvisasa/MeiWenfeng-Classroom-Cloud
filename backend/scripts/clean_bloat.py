import sqlite3
import re

conn = sqlite3.connect('d:/MeiWenfeng-Classroom/backend/classroom.db')
rows = conn.execute("SELECT id, content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()

updated = 0
for rid, content in rows:
    # 移除 <file_content> 标签及内容
    new_content = re.sub(r'<file_content.*?</file_content>', '[附加文件已被系统截断，已进入长期记忆库]', content, flags=re.DOTALL)
    # 移除 <ide_context> 标签及内容
    new_content = re.sub(r'<ide_context.*?</ide_context>', '[代码上下文已截断]', new_content, flags=re.DOTALL)
    if new_content != content:
        conn.execute('UPDATE memory_logs SET content = ? WHERE id = ?', (new_content, rid))
        updated += 1

conn.commit()
conn.close()
print(f"Cleaned up {updated} bloated memory logs.")
