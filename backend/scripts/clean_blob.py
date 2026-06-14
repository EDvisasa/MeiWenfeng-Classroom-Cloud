import sqlite3
import re

conn = sqlite3.connect('d:/MeiWenfeng-Classroom/backend/classroom.db')
rows = conn.execute("SELECT id, content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()

updated = 0
for rid, content in rows:
    new_content = content
    # Remove large chunks of binary data (PNGs, JPEGs, etc)
    if 'PNG\n\x1a' in new_content or len(new_content) > 10000:
        # Just truncate the file content block
        new_content = re.sub(r'【文件内容:.*?(?=\n媚吻锋：)', '\n[文件包含二进制数据，已截断]\n', new_content, flags=re.DOTALL)
        
        # If still too large, just truncate the whole thing
        if len(new_content) > 10000:
            new_content = new_content[:500] + '\n...[日志过大，已被强制截断]...\n' + new_content[-500:]

    if new_content != content:
        conn.execute('UPDATE memory_logs SET content = ? WHERE id = ?', (new_content, rid))
        updated += 1

conn.commit()

rows = conn.execute("SELECT content FROM memory_logs WHERE level = 0 AND status = 'active'").fetchall()
total_len = sum(len(r[0]) for r in rows)
print(f"Cleaned up {updated} bloated memory logs. New total length: {total_len}")

conn.close()
