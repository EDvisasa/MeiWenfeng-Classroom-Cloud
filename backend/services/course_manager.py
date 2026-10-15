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

# ============ ZPD (最近发展区) 动态难度追踪 ============
# SSOT: docs/GLOSSARY.md —— ZPD 指标列驻留于 course_progress 表
ZPD_COEFFICIENT_MIN = 0.5
ZPD_COEFFICIENT_MAX = 3.0
ZPD_COEFFICIENT_STEP = 0.1
ZPD_STREAK_THRESHOLD = 2

def _resolve_zpd_topic(topic: str | None) -> str:
    """Resolves the topic to track; falls back to the active course topic."""
    if topic:
        return topic
    active = get_active_course()
    return active["topic"] if active else ""


def get_zpd_metrics(topic: str | None = None) -> dict:
    """Retrieves the current ZPD difficulty metrics (coefficient + streaks) for a topic."""
    resolved = _resolve_zpd_topic(topic)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic, zpd_coefficient, consecutive_correct, consecutive_wrong "
        "FROM course_progress WHERE topic = ? ORDER BY id DESC LIMIT 1",
        (resolved,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "topic": row["topic"],
            "coefficient": float(row["zpd_coefficient"]),
            "consecutive_correct": int(row["consecutive_correct"]),
            "consecutive_wrong": int(row["consecutive_wrong"]),
        }
    return {"topic": resolved, "coefficient": 1.0, "consecutive_correct": 0, "consecutive_wrong": 0}


def record_quiz_result(is_correct: bool, topic: str | None = None) -> dict:
    """Updates ZPD metrics after a quiz answer.

    Two consecutive correct answers raise the difficulty coefficient; consecutive
    mistakes automatically lower it back down (ISSUE-03).
    """
    resolved = _resolve_zpd_topic(topic)
    metrics = get_zpd_metrics(resolved)
    coefficient = metrics["coefficient"]
    consecutive_correct = metrics["consecutive_correct"]
    consecutive_wrong = metrics["consecutive_wrong"]

    if is_correct:
        consecutive_correct += 1
        consecutive_wrong = 0
        if consecutive_correct >= ZPD_STREAK_THRESHOLD:
            coefficient = round(min(coefficient + ZPD_COEFFICIENT_STEP, ZPD_COEFFICIENT_MAX), 2)
            consecutive_correct = 0
    else:
        consecutive_wrong += 1
        consecutive_correct = 0
        if consecutive_wrong >= ZPD_STREAK_THRESHOLD:
            coefficient = round(max(coefficient - ZPD_COEFFICIENT_STEP, ZPD_COEFFICIENT_MIN), 2)
            consecutive_wrong = 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE course_progress SET zpd_coefficient = ?, consecutive_correct = ?, consecutive_wrong = ? WHERE topic = ?",
        (coefficient, consecutive_correct, consecutive_wrong, resolved),
    )
    conn.commit()
    conn.close()
    return get_zpd_metrics(resolved)
