from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from typing import Dict, Any, Optional
from backend.database import get_db_connection
from backend.services.mission_manager import MissionManager
from backend.services.materials_manager import MaterialsManager
from backend.services.rag_factory import get_rag_client

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
        
        from backend.services.course_manager import (
            get_course_state,
            list_courses as db_list_courses,
            get_active_course,
        )
        course_state = get_course_state()
        selected_course_id = course_state["selected_course_id"]
        active_course_id = course_state["active_course_id"]
        is_in_lesson = course_state["is_in_lesson"]
        display_course_id = active_course_id if is_in_lesson else selected_course_id

        courses = db_list_courses()
        active_lesson = get_active_course(display_course_id)

        # 获取 Mission 相关状态（平时预览所选课题，上课时展示并锁定活跃课题）
        active_draft = MissionManager.get_active_draft()
        user_mission = MissionManager.get_user_mission(display_course_id)
        parsed_mission = MissionManager.parse_mission_markdown(user_mission)
        
        # 获取知识树（聚焦在当前展示课题）
        knowledge_tree = MaterialsManager.build_knowledge_tree(course_id=display_course_id)

        return {
            "affection": affection,
            "social_status": social_status,
            "social_skills": social_skills,
            "refractory_period": refractory_period,
            "active_model": active_model,
            "active_sub_model": active_sub_model,
            "selected_course_id": selected_course_id,
            "active_course_id": active_course_id,
            "is_in_lesson": is_in_lesson,
            "courses": courses,
            "active_lesson": active_lesson,
            "mission": {
                "current_mission": user_mission,
                "parsed_goal": parsed_mission.get("goal") or user_mission,
                "time_budget": parsed_mission.get("time_budget", ""),
                "constraints": parsed_mission.get("constraints", ""),
                "skill_level": parsed_mission.get("skill_level", ""),
                "is_drafting": active_draft is not None,
                "draft_details": active_draft
            },
            "knowledge_tree": knowledge_tree
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/course/select")
def select_course_preview(payload: Dict[str, Any] = Body(...)):
    """在未上课状态下切换右边栏选定/预览课题（不改变资料归档指针 active_course_id）。"""
    from backend.services.course_manager import get_course_state, is_in_lesson, set_selected_course_id

    if is_in_lesson():
        raise HTTPException(
            status_code=409,
            detail="当前正在上课锁定中，请先输入 /end_lesson 下课解锁后再切换课题",
        )
    course_id = payload.get("course_id", "default")
    set_selected_course_id(course_id)
    state = get_course_state()
    return {"status": "success", **state}


@router.post("/course/active")
def switch_active_course(payload: Dict[str, Any] = Body(...)):
    """切换当前全局活跃课程"""
    course_id = payload.get("course_id", "default")
    from backend.services.course_manager import set_active_course_id
    set_active_course_id(course_id)
    return {"status": "success", "active_course_id": course_id}

@router.get("/materials/courses")
def list_courses():
    """获取所有可用课程项目列表（包含全局基础课程与独立课程项目）"""
    try:
        courses = MaterialsManager.list_courses()
        return {"courses": courses}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/materials/courses/create")
def create_course(payload: Dict[str, Any] = Body(...)):
    """创建新的分课程项目隔离目录及标准子文件夹"""
    from backend.services.course_manager import create_course as db_create_course

    course_id = payload.get("course_id")
    name = payload.get("name")
    if not course_id:
        raise HTTPException(status_code=400, detail="Missing course_id")
    try:
        course = MaterialsManager.create_course(course_id, name)
        db_create_course(course["id"], course["name"])
        return {"status": "success", "course": course}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/materials/tree")
def get_materials_tree(course_id: Optional[str] = None):
    """获取指定课程的知识与微课目录大纲树"""
    try:
        tree = MaterialsManager.build_knowledge_tree(course_id=course_id)
        return {"knowledge_tree": tree, "course_id": course_id or "default"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/materials/content")
def get_material(path: str, course_id: Optional[str] = None):
    """获取指定课程下的 Markdown 文件内容"""
    try:
        content = MaterialsManager.get_material_content(path, course_id=course_id)
        return {"content": content, "path": path, "course_id": course_id or "default"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/materials/save")
def save_material(payload: Dict[str, Any] = Body(...), background_tasks: BackgroundTasks = None):
    """保存指定课程下的 Markdown 文件内容并异步同步到 RAG 向量知识库"""
    path = payload.get("path")
    content = payload.get("content")
    course_id = payload.get("course_id")
    if not path or content is None:
        raise HTTPException(status_code=400, detail="Missing path or content")
    try:
        MaterialsManager.save_material_content(path, content, course_id=course_id)
        if background_tasks:
            try:
                rag_client = get_rag_client()
                rag_key = f"{course_id}/{path}" if course_id and course_id != "default" else path
                import inspect
                sig = inspect.signature(rag_client.sync_knowledge)
                if "course_id" in sig.parameters:
                    background_tasks.add_task(rag_client.sync_knowledge, {rag_key: content}, "Classroom_Knowledge", course_id=course_id or "default")
                else:
                    background_tasks.add_task(rag_client.sync_knowledge, {rag_key: content}, "Classroom_Knowledge")
            except Exception:
                pass
        return {"status": "success", "message": "Material saved and RAG sync initiated", "course_id": course_id or "default"}
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
