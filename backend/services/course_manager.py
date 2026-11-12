import sqlite3
import os
from datetime import datetime

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "classroom.db")

_active_course_id: str = "default"

def _has_column(conn, table: str, column: str) -> bool:
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cursor.fetchall()]
        return column in cols
    except Exception:
        return False

def get_active_course_id() -> str:
    """Returns the currently active course ID (falls back to 'default')."""
    return _active_course_id

def set_active_course_id(course_id: str) -> str:
    """Sets the currently active course ID and updates last_accessed_at in the database."""
    global _active_course_id
    _active_course_id = course_id or "default"
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE courses SET last_accessed_at = datetime('now') WHERE id = ?",
            (_active_course_id,)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
    return _active_course_id

def reset_active_course_id() -> str:
    """Resets the currently active course ID back to 'default'."""
    return set_active_course_id("default")

def create_course(course_id: str, name: str) -> dict:
    """Creates a new course entry in the courses table if it does not already exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO courses (id, name, status, created_at, last_accessed_at) VALUES (?, ?, 'active', datetime('now'), datetime('now'))",
            (course_id, name)
        )
        conn.commit()
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"id": course_id, "name": name, "status": "active"}
    finally:
        conn.close()

def list_courses() -> list[dict]:
    """Lists all available courses ordered by last_accessed_at descending."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, status, created_at, last_accessed_at FROM courses ORDER BY last_accessed_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

def get_course(course_id: str) -> dict | None:
    """Retrieves course details by id."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, status, created_at, last_accessed_at FROM courses WHERE id = ?", (course_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()

def get_active_course(course_id: str | None = None) -> dict | None:
    """Retrieves the currently active course phase and topic for a specific course."""
    cid = course_id if course_id is not None else get_active_course_id()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        has_lno = _has_column(conn, "course_progress", "lesson_no")
        order_by = "lesson_no ASC, id ASC" if has_lno else "id ASC"

        if not has_cid or cid == "default":
            where_clause = "(course_id = 'default' OR course_id IS NULL) AND status = 'active'" if has_cid else "status = 'active'"
            cursor.execute(f"SELECT * FROM course_progress WHERE {where_clause} ORDER BY {order_by} LIMIT 1")
        else:
            cursor.execute(f"SELECT * FROM course_progress WHERE course_id = ? AND status = 'active' ORDER BY {order_by} LIMIT 1", (cid,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def advance_course_progress(course_id: str | None = None) -> dict | None:
    """Marks current active course as completed and activates the next pending course for this course_id."""
    cid = course_id if course_id is not None else get_active_course_id()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        has_lno = _has_column(conn, "course_progress", "lesson_no")
        order_by = "lesson_no ASC, id ASC" if has_lno else "id ASC"

        # Get current active
        if not has_cid or cid == "default":
            where_active = "(course_id = 'default' OR course_id IS NULL) AND status = 'active'" if has_cid else "status = 'active'"
            where_pending = "(course_id = 'default' OR course_id IS NULL) AND status = 'pending'" if has_cid else "status = 'pending'"
            cursor.execute(f"SELECT id FROM course_progress WHERE {where_active} ORDER BY {order_by} LIMIT 1")
            active_row = cursor.fetchone()
            if active_row:
                cursor.execute("UPDATE course_progress SET status = 'completed' WHERE id = ?", (active_row["id"],))
            cursor.execute(f"SELECT id FROM course_progress WHERE {where_pending} ORDER BY {order_by} LIMIT 1")
            next_row = cursor.fetchone()
            if next_row:
                cursor.execute("UPDATE course_progress SET status = 'active' WHERE id = ?", (next_row["id"],))
        else:
            cursor.execute(f"SELECT id FROM course_progress WHERE course_id = ? AND status = 'active' ORDER BY {order_by} LIMIT 1", (cid,))
            active_row = cursor.fetchone()
            if active_row:
                cursor.execute("UPDATE course_progress SET status = 'completed' WHERE id = ?", (active_row["id"],))
            cursor.execute(f"SELECT id FROM course_progress WHERE course_id = ? AND status = 'pending' ORDER BY {order_by} LIMIT 1", (cid,))
            next_row = cursor.fetchone()
            if next_row:
                cursor.execute("UPDATE course_progress SET status = 'active' WHERE id = ?", (next_row["id"],))
        conn.commit()
    finally:
        conn.close()

    return get_active_course(cid)

def get_formatted_syllabus(course_id: str | None = None) -> str:
    """Retrieves the entire syllabus history formatted for the AI to read, isolated by course_id."""
    cid = course_id if course_id is not None else get_active_course_id()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        has_lno = _has_column(conn, "course_progress", "lesson_no")
        order_by = "lesson_no ASC, id ASC" if has_lno else "id ASC"

        if not has_cid or cid == "default":
            where_clause = "WHERE (course_id = 'default' OR course_id IS NULL)" if has_cid else ""
            cursor.execute(f"SELECT * FROM course_progress {where_clause} ORDER BY {order_by}")
        else:
            cursor.execute(f"SELECT * FROM course_progress WHERE course_id = ? ORDER BY {order_by}", (cid,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return "当前没有任何课程进度。"

    lines = []
    current_phase = None

    for row in rows:
        phase = row["phase"]
        topic = row["topic"]
        status = row["status"]
        lesson_no = row["lesson_no"] if has_lno and "lesson_no" in row.keys() else None

        if phase != current_phase:
            lines.append(f"\n【{phase}】")
            current_phase = phase

        status_marker = "[未修]"
        if status == "completed":
            status_marker = "[已完成]"
        elif status == "active":
            status_marker = "[当前]"

        prefix = f"课时{lesson_no}: " if lesson_no else ""
        lines.append(f"- {status_marker} {prefix}{topic}")

    return "\n".join(lines).strip()

def append_to_syllabus(phase: str, topic: str, course_id: str | None = None, lesson_no: int | None = None) -> None:
    """Adds a new topic to the syllabus as pending."""
    cid = course_id if course_id is not None else get_active_course_id()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        has_lno = _has_column(conn, "course_progress", "lesson_no")

        if has_cid and has_lno:
            if lesson_no is None:
                cursor.execute("SELECT MAX(lesson_no) FROM course_progress WHERE course_id = ?", (cid,))
                max_val = cursor.fetchone()[0]
                lesson_no = (max_val or 0) + 1
            cursor.execute(
                "INSERT INTO course_progress (phase, topic, status, score, course_id, lesson_no) VALUES (?, ?, 'pending', 0, ?, ?)",
                (phase, topic, cid, lesson_no)
            )
        elif has_cid:
            cursor.execute(
                "INSERT INTO course_progress (phase, topic, status, score, course_id) VALUES (?, ?, 'pending', 0, ?)",
                (phase, topic, cid)
            )
        else:
            cursor.execute(
                "INSERT INTO course_progress (phase, topic, status, score) VALUES (?, ?, 'pending', 0)",
                (phase, topic)
            )
        conn.commit()
    finally:
        conn.close()

# ============ ZPD (最近发展区) 动态难度追踪 ============
# SSOT: docs/GLOSSARY.md —— ZPD 指标列驻留于 course_progress 表
ZPD_COEFFICIENT_MIN = 0.5
ZPD_COEFFICIENT_MAX = 3.0
ZPD_COEFFICIENT_STEP = 0.1
ZPD_STREAK_THRESHOLD = 2

def _resolve_zpd_topic(topic: str | None, course_id: str | None = None) -> str:
    """Resolves the topic to track; falls back to the active course topic."""
    if topic:
        return topic
    active = get_active_course(course_id)
    return active["topic"] if active else ""

def get_zpd_metrics(topic: str | None = None, course_id: str | None = None) -> dict:
    """Retrieves the current ZPD difficulty metrics (coefficient + streaks) for a topic."""
    cid = course_id if course_id is not None else get_active_course_id()
    resolved = _resolve_zpd_topic(topic, cid)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        if not has_cid or cid == "default":
            where_clause = "topic = ? AND (course_id = 'default' OR course_id IS NULL)" if has_cid else "topic = ?"
            cursor.execute(f"SELECT * FROM course_progress WHERE {where_clause} ORDER BY id DESC LIMIT 1", (resolved,))
        else:
            cursor.execute(
                "SELECT * FROM course_progress WHERE topic = ? AND course_id = ? ORDER BY id DESC LIMIT 1",
                (resolved, cid),
            )
        row = cursor.fetchone()
        if row:
            row_dict = dict(row)
            return {
                "topic": row_dict["topic"],
                "coefficient": float(row_dict.get("zpd_coefficient", 1.0)),
                "consecutive_correct": int(row_dict.get("consecutive_correct", 0)),
                "consecutive_wrong": int(row_dict.get("consecutive_wrong", 0)),
                "total_consecutive_wrong": int(row_dict.get("total_consecutive_wrong", 0)),
            }
        return {"topic": resolved, "coefficient": 1.0, "consecutive_correct": 0, "consecutive_wrong": 0, "total_consecutive_wrong": 0}
    finally:
        conn.close()

def record_quiz_result(is_correct: bool, topic: str | None = None, course_id: str | None = None) -> dict:
    """Updates ZPD metrics after a quiz answer."""
    cid = course_id if course_id is not None else get_active_course_id()
    resolved = _resolve_zpd_topic(topic, cid)
    metrics = get_zpd_metrics(resolved, cid)
    coefficient = metrics["coefficient"]
    consecutive_correct = metrics["consecutive_correct"]
    consecutive_wrong = metrics["consecutive_wrong"]
    total_consecutive_wrong = metrics.get("total_consecutive_wrong", 0)

    if is_correct:
        consecutive_correct += 1
        consecutive_wrong = 0
        total_consecutive_wrong = 0
        if consecutive_correct >= ZPD_STREAK_THRESHOLD:
            coefficient = round(min(coefficient + ZPD_COEFFICIENT_STEP, ZPD_COEFFICIENT_MAX), 2)
            consecutive_correct = 0
    else:
        consecutive_wrong += 1
        consecutive_correct = 0
        total_consecutive_wrong += 1
        if consecutive_wrong >= ZPD_STREAK_THRESHOLD:
            coefficient = round(max(coefficient - ZPD_COEFFICIENT_STEP, ZPD_COEFFICIENT_MIN), 2)
            consecutive_wrong = 0

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        has_cid = _has_column(conn, "course_progress", "course_id")
        if not has_cid or cid == "default":
            where_clause = "topic = ? AND (course_id = 'default' OR course_id IS NULL)" if has_cid else "topic = ?"
            cursor.execute(
                f"UPDATE course_progress SET zpd_coefficient = ?, consecutive_correct = ?, consecutive_wrong = ?, total_consecutive_wrong = ? WHERE {where_clause}",
                (coefficient, consecutive_correct, consecutive_wrong, total_consecutive_wrong, resolved),
            )
        else:
            cursor.execute(
                "UPDATE course_progress SET zpd_coefficient = ?, consecutive_correct = ?, consecutive_wrong = ?, total_consecutive_wrong = ? WHERE topic = ? AND course_id = ?",
                (coefficient, consecutive_correct, consecutive_wrong, total_consecutive_wrong, resolved, cid),
            )
        conn.commit()
    finally:
        conn.close()
    return get_zpd_metrics(resolved, cid)
