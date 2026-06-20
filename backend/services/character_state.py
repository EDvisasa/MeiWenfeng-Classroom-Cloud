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
            
            # Ensure row exists
            cursor.execute("SELECT 1 FROM affection WHERE id = 1")
            if not cursor.fetchone():
                cursor.execute("INSERT OR IGNORE INTO affection (id, value, social_status, social_skills, refractory_period, last_updated) VALUES (1, 50, 50, 50, 0, datetime('now'))")

            # Atomic update
            if set_refractory is not None:
                cursor.execute("""
                    UPDATE affection 
                    SET value = MIN(100, MAX(0, value + ?)),
                        social_status = MIN(100, MAX(0, social_status + ?)),
                        social_skills = MIN(100, MAX(0, social_skills + ?)),
                        refractory_period = MAX(0, ?),
                        last_updated = datetime('now')
                    WHERE id = 1
                """, (affection_delta, social_status_delta, social_skills_delta, set_refractory))
            else:
                cursor.execute("""
                    UPDATE affection 
                    SET value = MIN(100, MAX(0, value + ?)),
                        social_status = MIN(100, MAX(0, social_status + ?)),
                        social_skills = MIN(100, MAX(0, social_skills + ?)),
                        refractory_period = MAX(0, refractory_period + ?),
                        last_updated = datetime('now')
                    WHERE id = 1
                """, (affection_delta, social_status_delta, social_skills_delta, refractory_delta))

            # Retrieve the newly updated values within the same transaction lock
            cursor.execute("SELECT value, social_status, social_skills, refractory_period FROM affection WHERE id = 1")
            row = cursor.fetchone()
            
            conn.commit()
            conn.close()

            return CharacterState(
                affection=row["value"],
                social_status=row["social_status"],
                social_skills=row["social_skills"],
                refractory_period=row["refractory_period"]
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
