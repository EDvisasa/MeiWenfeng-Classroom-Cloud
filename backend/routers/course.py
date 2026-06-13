from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from backend.database import get_db_connection

router = APIRouter(prefix="/api/chat", tags=["course", "status"])

@router.get("/status")
def get_status_summary():
    """获取右侧状态栏所需的课程进度和好感度数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取好感度
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        aff_row = cursor.fetchone()
        affection = aff_row["value"] if aff_row else 50
        
        # 获取当前激活的模型
        cursor.execute("SELECT name, selected_model_id FROM model_config WHERE is_active = 1 LIMIT 1")
        model_row = cursor.fetchone()
        active_model = model_row["name"] if model_row else "未设置"
        active_sub_model = model_row["selected_model_id"] if model_row and model_row["selected_model_id"] else None
        
        # 获取课程大纲
        cursor.execute("SELECT id, phase, topic, status, score FROM course_progress")
        course_rows = cursor.fetchall()
        course_list = [dict(r) for r in course_rows]
        
        conn.close()
        return {
            "affection": affection,
            "active_model": active_model,
            "active_sub_model": active_sub_model,
            "course_progress": course_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update_affection")
def update_affection(payload: Dict[str, Any] = Body(...)):
    """更新好感度值（主要是由斜杠命令 /奖励 或者课后触发）"""
    delta = payload.get("delta", 0)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM affection WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO affection (id, value, last_updated) VALUES (1, 50, datetime('now'))")
            current = 50
        else:
            current = row["value"]
            
        new_val = max(0, min(100, current + delta))
        cursor.execute("UPDATE affection SET value = ?, last_updated = datetime('now') WHERE id = 1")
        conn.commit()
        conn.close()
        return {"status": "success", "affection": new_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
