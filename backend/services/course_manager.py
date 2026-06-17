import sqlite3
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "classroom.db")

def get_active_course() -> dict | None:
    """Retrieves the currently active course phase and topic."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT phase, topic, status FROM course_progress WHERE status = 'active' ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return dict(row)
    return None

def advance_course_progress() -> dict | None:
    """Marks current active course as completed and activates the next pending course."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get current active
    cursor.execute("SELECT id FROM course_progress WHERE status = 'active' ORDER BY id ASC LIMIT 1")
    active_row = cursor.fetchone()
    
    if active_row:
        cursor.execute("UPDATE course_progress SET status = 'completed' WHERE id = ?", (active_row["id"],))
        
    # Activate next pending
    cursor.execute("SELECT id FROM course_progress WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
    next_row = cursor.fetchone()
    
    if next_row:
        cursor.execute("UPDATE course_progress SET status = 'active' WHERE id = ?", (next_row["id"],))
        
    conn.commit()
    conn.close()
    
    return get_active_course()

def get_formatted_syllabus() -> str:
    """Retrieves the entire syllabus history formatted for the AI to read."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT phase, topic, status FROM course_progress ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "当前没有任何课程进度。"
        
    lines = []
    current_phase = None
    
    for row in rows:
        phase = row["phase"]
        topic = row["topic"]
        status = row["status"]
        
        if phase != current_phase:
            lines.append(f"\\n【{phase}】")
            current_phase = phase
            
        status_marker = "[未修]"
        if status == "completed":
            status_marker = "[已完成]"
        elif status == "active":
            status_marker = "[当前]"
            
        lines.append(f"- {status_marker} {topic}")
        
    return "\\n".join(lines).strip()

def append_to_syllabus(phase: str, topic: str) -> None:
    """Adds a new topic to the syllabus as pending."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO course_progress (phase, topic, status, score) VALUES (?, ?, 'pending', 0)",
        (phase, topic)
    )
    
    conn.commit()
    conn.close()
