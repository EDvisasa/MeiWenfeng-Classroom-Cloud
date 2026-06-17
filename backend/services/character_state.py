import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

class CharacterStateError(Exception):
    """Exception raised for errors in the CharacterStateManager."""
    pass

@dataclass
class CharacterState:
    affection: int
    social_status: int
    social_skills: int
    refractory_period: int

class CharacterStateManager:
    """
    状态机接缝：管理角色的动态属性，封装所有的数值边界和业务流转逻辑。
    """
    
    @staticmethod
    def get_state() -> CharacterState:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value, social_status, social_skills, refractory_period FROM affection WHERE id = 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                return CharacterState(
                    affection=row["value"],
                    social_status=row["social_status"],
                    social_skills=row["social_skills"],
                    refractory_period=row["refractory_period"]
                )
            return CharacterState(affection=50, social_status=50, social_skills=50, refractory_period=0)
        except Exception as e:
            logger.error(f"Failed to get character state: {e}")
            raise CharacterStateError(f"Database error: {e}")

    @staticmethod
    def modify_state(
        affection_delta: int = 0,
        social_status_delta: int = 0,
        social_skills_delta: int = 0,
        refractory_delta: int = 0,
        set_refractory: Optional[int] = None
    ) -> CharacterState:
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

            new_val = max(0, min(100, current + affection_delta))
            new_social_status = max(0, min(100, cur_social_status + social_status_delta))
            new_social_skills = max(0, min(100, cur_social_skills + social_skills_delta))

            if set_refractory is not None:
                new_refractory = max(0, set_refractory)
            else:
                new_refractory = max(0, cur_refractory + refractory_delta)

            cursor.execute(
                "UPDATE affection SET value = ?, social_status = ?, social_skills = ?, refractory_period = ?, last_updated = datetime('now') WHERE id = 1",
                (new_val, new_social_status, new_social_skills, new_refractory)
            )
            conn.commit()
            conn.close()

            return CharacterState(
                affection=new_val,
                social_status=new_social_status,
                social_skills=new_social_skills,
                refractory_period=new_refractory
            )
        except Exception as e:
            logger.error(f"Failed to update character state: {e}")
            raise CharacterStateError(f"Database error: {e}")

    @staticmethod
    def trigger_climax(intensity: int = 10):
        """触发高潮，重置不应期"""
        return CharacterStateManager.modify_state(set_refractory=intensity)

    @staticmethod
    def advance_round(rounds: int = 1):
        """推进回合，自动衰减不应期"""
        return CharacterStateManager.modify_state(refractory_delta=-rounds)
