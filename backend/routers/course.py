from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from backend.database import get_db_connection
from backend.services.mission_manager import MissionManager
from backend.services.materials_manager import MaterialsManager

router = APIRouter(prefix="/api/chat", tags=["course", "status", "materials"])

@router.get("/status")
def get_status_summary():
    """获取右侧状态栏所需的课程进度、Mission状态和好感度数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取好感度与动态属性
        cursor.execute("SELECT value, social_status, social_skills, refractory_period FROM affection WHERE id = 1")
        aff_row = cursor.fetchone()
        affection = aff_row["value"] if aff_row else 50
        social_status = aff_row["social_status"] if aff_row else 50
        social_skills = aff_row["social_skills"] if aff_row else 50
        refractory_period = aff_row["refractory_period"] if aff_row else 0

        # 获取当前激活的模型
        cursor.execute("SELECT name, selected_model_id FROM model_config WHERE is_active = 1 LIMIT 1")
        model_row = cursor.fetchone()
        active_model = model_row["name"] if model_row else "未设置"
        active_sub_model = model_row["selected_model_id"] if model_row and model_row["selected_model_id"] else None

        conn.close()
        
        # 获取 Mission 相关状态
        active_draft = MissionManager.get_active_draft()
        user_mission = MissionManager.get_user_mission()
        
        # 获取知识树
        knowledge_tree = MaterialsManager.build_knowledge_tree()

        return {
            "affection": affection,
            "social_status": social_status,
            "social_skills": social_skills,
            "refractory_period": refractory_period,
            "active_model": active_model,
            "active_sub_model": active_sub_model,
            "mission": {
                "current_mission": user_mission,
                "is_drafting": active_draft is not None,
                "draft_details": active_draft
            },
            "knowledge_tree": knowledge_tree
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/materials/content")
def get_material(path: str):
    """获取具体的 Markdown 文件内容"""
    try:
        content = MaterialsManager.get_material_content(path)
        return {"content": content}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update_affection")
def update_affection(payload: Dict[str, Any] = Body(...)):
    """更新好感度值及动态属性值"""
    delta = payload.get("delta", 0)
    social_status_delta = payload.get("social_status_delta", 0)
    social_skills_delta = payload.get("social_skills_delta", 0)
    refractory_delta = payload.get("refractory_delta", 0)
    set_refractory = payload.get("set_refractory", None)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value, social_status, social_skills, refractory_period FROM affection WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated) VALUES (1, 50, 50, 50, 0, datetime('now'))")
            current = 50
            cur_social_status = 50
            cur_social_skills = 50
            cur_refractory = 0
        else:
            current = row["value"]
            cur_social_status = row["social_status"]
            cur_social_skills = row["social_skills"]
            cur_refractory = row["refractory_period"]

        new_val = max(0, min(100, current + delta))
        new_social_status = max(0, min(100, cur_social_status + social_status_delta))
        new_social_skills = max(0, min(100, cur_social_skills + social_skills_delta))

        if set_refractory is not None:
            new_refractory = set_refractory
        else:
            new_refractory = max(0, cur_refractory + refractory_delta)

        cursor.execute("UPDATE affection SET value = ?, social_status = ?, social_skills = ?, refractory_period = ?, last_updated = datetime('now') WHERE id = 1", (new_val, new_social_status, new_social_skills, new_refractory))
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "affection": new_val,
            "social_status": new_social_status,
            "social_skills": new_social_skills,
            "refractory_period": new_refractory
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
