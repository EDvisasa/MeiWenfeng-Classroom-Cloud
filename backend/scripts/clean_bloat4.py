import sqlite3
import re

conn = sqlite3.connect('d:/MeiWenfeng-Classroom/backend/classroom.db')
rows = conn.execute("SELECT id, content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()

updated = 0
for rid, content in rows:
    # Remove from 【当前激活文件内容: up to the end of the user message (before 媚吻锋：)
    new_content = re.sub(r'【当前激活文件内容:.*?(?=\n媚吻锋：)', '\n[附加文件已被系统截断]\n', content, flags=re.DOTALL)
    if new_content != content:
        conn.execute('UPDATE memory_logs SET content = ? WHERE id = ?', (new_content, rid))
        updated += 1

conn.commit()

# Print new total length
rows = conn.execute("SELECT content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()
total_len = sum(len(r[0]) for r in rows)
print(f"Cleaned up {updated} bloated memory logs. New total length: {total_len}")

conn.close()
