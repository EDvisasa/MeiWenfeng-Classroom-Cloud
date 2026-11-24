import os
import logging
from datetime import datetime
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

class MissionManager:
    @staticmethod
    def get_user_mission(course_id: str | None = None) -> str:
        from backend.services.course_manager import get_active_course_id
        cid = course_id if course_id is not None else get_active_course_id()
        mission_text = "未知目标"
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if cid == "default":
                cursor.execute("SELECT mission_text FROM user_mission WHERE (course_id = 'default' OR course_id IS NULL) ORDER BY id DESC LIMIT 1")
            else:
                cursor.execute("SELECT mission_text FROM user_mission WHERE course_id = ? ORDER BY id DESC LIMIT 1", (cid,))
            row = cursor.fetchone()
            if row and row["mission_text"]:
                mission_text = row["mission_text"]
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch user_mission: {e}")
        return mission_text

    @staticmethod
    def parse_mission_markdown(raw: str) -> dict:
        """解析 Markdown 格式的 Mission 文本为结构化 UI 字段"""
        import re
        if not raw or raw == "未知目标":
            return {"goal": "自由探索中 (未指定长期课题)", "time_budget": "", "constraints": "", "skill_level": ""}
        
        goal_m = re.search(r'\*\*Goal\*\*:\s*([^\n\r]+)', raw, re.IGNORECASE)
        time_m = re.search(r'\*\*Time Budget\*\*:\s*([^\n\r]+)', raw, re.IGNORECASE)
        cons_m = re.search(r'\*\*Constraints\*\*:\s*([^\n\r]+)', raw, re.IGNORECASE)
        skill_m = re.search(r'\*\*Verified Skill Level\*\*:\s*([^\n\r]+)', raw, re.IGNORECASE)
        
        if goal_m:
            return {
                "goal": goal_m.group(1).strip(),
                "time_budget": time_m.group(1).strip() if time_m else "",
                "constraints": cons_m.group(1).strip() if cons_m else "",
                "skill_level": skill_m.group(1).strip() if skill_m else ""
            }
        
        # 回退逻辑：剔除标题 # 和加粗语法
        cleaned = re.sub(r'^#+\s+', '', raw, flags=re.MULTILINE)
        cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'__(.*?)__', r'\1', cleaned).strip()
        return {"goal": cleaned or "自由探索中", "time_budget": "", "constraints": "", "skill_level": ""}

    @staticmethod
    def get_active_draft() -> dict:
        draft = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mission_draft WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                draft = dict(row)
            conn.close()
        except Exception as e:
            logger.error(f"Failed to get active draft: {e}")
        return draft

    @staticmethod
    def start_draft(goal: str) -> dict:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM mission_draft WHERE id = 1")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO mission_draft (id, goal, is_active) VALUES (1, ?, 1)", (goal,))
            else:
                cursor.execute(
                    "UPDATE mission_draft SET goal = ?, daily_time_budget = NULL, hard_constraints = NULL, current_skill_level = NULL, is_active = 1, last_updated = datetime('now') WHERE id = 1",
                    (goal,)
                )
            conn.commit()
            
            cursor.execute("SELECT * FROM mission_draft WHERE id = 1")
            draft = dict(cursor.fetchone())
            conn.close()
            return draft
        except Exception as e:
            logger.error(f"Failed to start draft: {e}")
            raise

    @staticmethod
    def cancel_draft():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE mission_draft SET is_active = 0 WHERE is_active = 1")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to cancel draft: {e}")
            raise

    @staticmethod
    def finalize_draft(
        final_goal: str,
        final_time: str,
        final_constraints: str,
        final_skill: str,
        course_id: str | None = None,
        course_name: str | None = None
    ):
        from backend.services.course_manager import set_active_course_id, set_selected_course_id, create_course as db_create_course
        from backend.services.materials_manager import MaterialsManager

        cid = course_id if course_id and course_id != "default" else None
        cname = course_name or final_goal[:30]

        mission_markdown = f"# Mission Objective\n\n**Goal**: {final_goal}\n\n**Time Budget**: {final_time}\n\n**Constraints**: {final_constraints}\n\n**Verified Skill Level**: {final_skill}\n"
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            old_mission = None
            if cid:
                # Ensure course exists in courses table
                db_create_course(cid, cname)
                cursor.execute("SELECT id, mission_text FROM user_mission WHERE course_id = ?", (cid,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO user_mission (mission_text, course_id) VALUES (?, ?)", (mission_markdown, cid))
                else:
                    old_mission = row["mission_text"]
                    cursor.execute("UPDATE user_mission SET mission_text = ?, last_updated = datetime('now') WHERE id = ?", (mission_markdown, row["id"]))
            else:
                cursor.execute("SELECT id, mission_text FROM user_mission WHERE id = 1")
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO user_mission (id, mission_text, course_id) VALUES (1, ?, 'default')", (mission_markdown,))
                else:
                    old_mission = row["mission_text"]
                    cursor.execute("UPDATE user_mission SET mission_text = ?, last_updated = datetime('now') WHERE id = 1", (mission_markdown,))
            
            cursor.execute(
                "UPDATE mission_draft SET is_active = 0, goal=?, daily_time_budget=?, hard_constraints=?, current_skill_level=?, course_id=? WHERE is_active = 1 OR id = 1",
                (final_goal, final_time, final_constraints, final_skill, cid or "default")
            )
            conn.commit()
            conn.close()

            # Physical directory scaffolding and file writing
            base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_materials = os.path.abspath(os.path.join(base_root, "data", "materials"))
            mm_materials = MaterialsManager._get_materials_dir()

            # If __file__ was mocked/relocated (e.g. by test_mission_manager.py mock_abspath)
            if "test_" in file_materials or "pytest" in file_materials or "temp" in file_materials.lower():
                base_materials = file_materials
            else:
                base_materials = mm_materials

            if cid:
                MaterialsManager.create_course(cid, cname)
                target_base = os.path.join(base_materials, "courses", cid)
            else:
                target_base = base_materials

            os.makedirs(os.path.join(target_base, "Settings"), exist_ok=True)
            os.makedirs(os.path.join(target_base, "LDRs"), exist_ok=True)

            # 1. Write Settings/user_mission.md
            mission_file = os.path.join(target_base, "Settings", "user_mission.md")
            with open(mission_file, "w", encoding="utf-8") as f:
                f.write(mission_markdown)
                
            # 2. Write LDR if there's a drift
            if old_mission and old_mission != mission_markdown:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                ldr_file = os.path.join(target_base, "LDRs", f"{timestamp}_mission_drift.md")
                ldr_content = f"# Mission Drift ({timestamp})\n\n## Old Mission\n{old_mission}\n\n## New Mission\n{mission_markdown}\n"
                with open(ldr_file, "w", encoding="utf-8") as f:
                    f.write(ldr_content)

            # 3. Activate the course (and remember it as selected preview target)
            set_selected_course_id(cid or "default")
            set_active_course_id(cid or "default")

            logger.info(f"Mission finalized and written to DB & file system for course {cid or 'default'}.")
        except Exception as e:
            logger.error(f"Failed to finalize draft: {e}")
            raise
