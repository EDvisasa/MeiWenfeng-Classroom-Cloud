import sqlite3

conn = sqlite3.connect('d:/MeiWenfeng-Classroom/backend/classroom.db')
rows = conn.execute("SELECT id, length(content), content FROM memory_logs WHERE level = 0 AND status = 'active' ORDER BY length(content) DESC LIMIT 10").fetchall()

for rid, length, content in rows:
    print(f"ID: {rid}, Length: {length}")
    print(repr(content[:200]))
    print("...")

conn.close()
