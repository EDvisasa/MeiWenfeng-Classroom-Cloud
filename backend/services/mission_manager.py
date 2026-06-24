import os
import logging
from datetime import datetime
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

class MissionManager:
    @staticmethod
    def get_user_mission() -> str:
        mission_text = "未知目标"
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT mission_text FROM user_mission WHERE id = 1")
            row = cursor.fetchone()
            if row and row["mission_text"]:
                mission_text = row["mission_text"]
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch user_mission: {e}")
        return mission_text

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
    def finalize_draft(final_goal: str, final_time: str, final_constraints: str, final_skill: str):
        mission_markdown = f"# Mission Objective\n\n**Goal**: {final_goal}\n\n**Time Budget**: {final_time}\n\n**Constraints**: {final_constraints}\n\n**Verified Skill Level**: {final_skill}\n"
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM user_mission WHERE id = 1")
            old_mission = None
            if not cursor.fetchone():
                cursor.execute("INSERT INTO user_mission (id, mission_text) VALUES (1, ?)", (mission_markdown,))
            else:
                cursor.execute("SELECT mission_text FROM user_mission WHERE id = 1")
                old_mission = cursor.fetchone()[0]
                cursor.execute("UPDATE user_mission SET mission_text = ?, last_updated = datetime('now') WHERE id = 1", (mission_markdown,))
            
            cursor.execute(
                "UPDATE mission_draft SET is_active = 0, goal=?, daily_time_budget=?, hard_constraints=?, current_skill_level=? WHERE id = 1",
                (final_goal, final_time, final_constraints, final_skill)
            )
            conn.commit()
            conn.close()

            # Write physical files to data/materials/
            base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            materials_dir = os.path.join(base_root, "data", "materials")
            
            # Ensure directories exist (in case they were deleted manually)
            os.makedirs(os.path.join(materials_dir, "Settings"), exist_ok=True)
            os.makedirs(os.path.join(materials_dir, "LDRs"), exist_ok=True)

            # 1. Write Settings/Mission.md
            mission_file = os.path.join(materials_dir, "Settings", "Mission边界与设定.md")
            with open(mission_file, "w", encoding="utf-8") as f:
                f.write(mission_markdown)
                
            # 2. Write LDR if there's a drift
            if old_mission and old_mission != mission_markdown:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                ldr_file = os.path.join(materials_dir, "LDRs", f"{timestamp}-Mission-Drift.md")
                ldr_content = f"# Mission Drift ({timestamp})\n\n## Old Mission\n{old_mission}\n\n## New Mission\n{mission_markdown}\n"
                with open(ldr_file, "w", encoding="utf-8") as f:
                    f.write(ldr_content)

            logger.info("Mission finalized and written to DB & file system.")
        except Exception as e:
            logger.error(f"Failed to finalize draft: {e}")
            raise
