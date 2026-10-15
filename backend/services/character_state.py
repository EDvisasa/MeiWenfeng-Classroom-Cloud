import logging
import threading
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

_state_lock = threading.RLock()

DAILY_GAIN_CAP = 4  # 日常单日好感正常获取上限

STAGE_THRESHOLDS = {
    4: {"min": 75, "max": 100, "name": "不分彼此期", "grace_days": 7, "floor": 65, "cooldown_target": 80},
    3: {"min": 50, "max": 74, "name": "交付沉溺期", "grace_days": 5, "floor": 40, "cooldown_target": 60},
    2: {"min": 25, "max": 49, "name": "心动排他期", "grace_days": 3, "floor": 20, "cooldown_target": 30},
    1: {"min": 0, "max": 24, "name": "审视防备期", "grace_days": 2, "floor": 10, "cooldown_target": 5},
}


class CharacterStateError(Exception):
    """Exception raised for errors in the CharacterStateManager."""
    pass


@dataclass
class CharacterState:
    affection: int
    social_status: int
    social_skills: int
    refractory_period: int
    daily_gain_date: Optional[str] = None
    daily_gain_amount: int = 0
    reunion_warmup_turns: int = 0


class CharacterStateManager:
    """
    状态机接缝：管理角色的动态属性，封装所有的数值边界、时间衰减与业务流转逻辑。
    """

    @staticmethod
    def get_stage(affection: int) -> int:
        """获取好感度所处的心境阶段 (1~4 阶)"""
        if affection >= 75:
            return 4
        elif affection >= 50:
            return 3
        elif affection >= 25:
            return 2
        return 1

    @staticmethod
    def get_cooldown_target(affection: int) -> int:
        """
        方案 B：比例阻尼衰减制
        A_new = max(A_current - 8, stage_floor)
        根据当前好感度平滑回退 8 点激情溢价，但受当前心境阶段的最低门槛锁保护，
        确保单调不增、不破心境阶梯、不发生低位反弹。
        例如：
        阶段四 (75~100): 100 -> 92, 95 -> 87, 85 -> 77, 78 -> 75, 76 -> 75
        阶段三 (50~74): 74 -> 66, 65 -> 57, 55 -> 50, 52 -> 50
        阶段二 (25~49): 40 -> 32, 28 -> 25
        阶段一 (0~24): 10 -> 2, 5 -> 0
        """
        stage = CharacterStateManager.get_stage(affection)
        stage_min = STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS[1])["min"]
        return max(affection - 8, stage_min)

    @staticmethod
    def get_stage_floor(stage: int) -> int:
        """获取该阶段的离线衰减保底线（绝对阻断点）"""
        return STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS[1])["floor"]

    @staticmethod
    def get_grace_period(stage: int) -> int:
        """获取该阶段的免扣信任缓冲天数"""
        return STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS[1])["grace_days"]

    @staticmethod
    def _ensure_columns(conn):
        """确保 affection 表包含新增列（自愈热补丁，兼容测试内存库与旧版本）"""
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(affection)")
            columns = {row[1] for row in cursor.fetchall()}
            if "daily_gain_date" not in columns:
                cursor.execute("ALTER TABLE affection ADD COLUMN daily_gain_date TEXT DEFAULT NULL")
            if "daily_gain_amount" not in columns:
                cursor.execute("ALTER TABLE affection ADD COLUMN daily_gain_amount INTEGER DEFAULT 0")
            if "reunion_warmup_turns" not in columns:
                cursor.execute("ALTER TABLE affection ADD COLUMN reunion_warmup_turns INTEGER DEFAULT 0")
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not verify or add columns to affection table: {e}")

    @staticmethod
    def evaluate_temporal_decay(now: Optional[datetime] = None) -> Tuple[CharacterState, Optional[Dict[str, Any]]]:
        """
        惰性结算好感度时间衰减。在每轮对话上下文构建前调用。
        根据离线天数与心境阶段缓冲期执行自然沉淀，严格受阶梯底线保底阻断。
        若产生衰减，返回更新后的状态以及久别重逢指令上下文 (reunion_info)。
        """
        if now is None:
            now = datetime.now()

        with _state_lock:
            try:
                conn = get_db_connection()
                CharacterStateManager._ensure_columns(conn)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns, last_updated 
                    FROM affection WHERE id = 1
                """)
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    return CharacterStateManager.get_state(), None

                last_updated_str = row["last_updated"]
                if not last_updated_str:
                    cursor.execute("UPDATE affection SET last_updated = ? WHERE id = 1", (now.strftime("%Y-%m-%d %H:%M:%S"),))
                    conn.commit()
                    conn.close()
                    return CharacterStateManager.get_state(), None

                try:
                    clean_ts = last_updated_str.split(".")[0].replace("T", " ")
                    last_updated_dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    conn.close()
                    return CharacterStateManager.get_state(), None

                delta_seconds = (now - last_updated_dt).total_seconds()
                if delta_seconds < 0:
                    delta_seconds = 0
                delta_days = int(delta_seconds // 86400)

                current_affection = int(row["value"])
                current_stage = CharacterStateManager.get_stage(current_affection)
                grace_days = CharacterStateManager.get_grace_period(current_stage)
                stage_floor = CharacterStateManager.get_stage_floor(current_stage)

                reunion_info = None
                if delta_days > grace_days:
                    excess_days = delta_days - grace_days
                    max_decay = max(0, current_affection - stage_floor)
                    decay_amount = min(excess_days, max_decay)

                    if decay_amount > 0:
                        new_affection = current_affection - decay_amount
                        warmup_turns = 2  # 触发 2 轮破冰保护期

                        cursor.execute("""
                            UPDATE affection 
                            SET value = ?,
                                reunion_warmup_turns = ?,
                                last_updated = ?
                            WHERE id = 1
                        """, (new_affection, warmup_turns, now.strftime("%Y-%m-%d %H:%M:%S")))
                        conn.commit()

                        reunion_info = {
                            "absent_days": delta_days,
                            "decay_amount": decay_amount,
                            "stage": current_stage,
                            "new_affection": new_affection,
                            "stage_floor": stage_floor,
                        }

                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns 
                    FROM affection WHERE id = 1
                """)
                updated_row = cursor.fetchone()
                conn.close()

                state = CharacterState(
                    affection=updated_row["value"],
                    social_status=updated_row["social_status"],
                    social_skills=updated_row["social_skills"],
                    refractory_period=updated_row["refractory_period"],
                    daily_gain_date=updated_row["daily_gain_date"],
                    daily_gain_amount=updated_row["daily_gain_amount"] or 0,
                    reunion_warmup_turns=updated_row["reunion_warmup_turns"] or 0,
                )
                return state, reunion_info

            except Exception as e:
                logger.error(f"Failed to evaluate temporal decay: {e}")
                raise CharacterStateError(f"Database error during decay eval: {e}")

    @staticmethod
    def get_state() -> CharacterState:
        with _state_lock:
            try:
                conn = get_db_connection()
                CharacterStateManager._ensure_columns(conn)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns 
                    FROM affection WHERE id = 1
                """)
                row = cursor.fetchone()
                conn.close()
                if row:
                    return CharacterState(
                        affection=row["value"],
                        social_status=row["social_status"],
                        social_skills=row["social_skills"],
                        refractory_period=row["refractory_period"],
                        daily_gain_date=row["daily_gain_date"],
                        daily_gain_amount=row["daily_gain_amount"] or 0,
                        reunion_warmup_turns=row["reunion_warmup_turns"] or 0
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
        set_refractory: Optional[int] = None,
        set_affection: Optional[int] = None,
        is_cooldown: bool = False,
        enforce_daily_cap: bool = False,
        now: Optional[datetime] = None
    ) -> CharacterState:
        if now is None:
            now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        with _state_lock:
            try:
                conn = get_db_connection()
                CharacterStateManager._ensure_columns(conn)
                cursor = conn.cursor()

                # Ensure row exists
                cursor.execute("SELECT 1 FROM affection WHERE id = 1")
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT OR IGNORE INTO affection 
                        (id, value, social_status, social_skills, refractory_period, daily_gain_date, daily_gain_amount, reunion_warmup_turns, last_updated) 
                        VALUES (1, 50, 50, 50, 0, NULL, 0, 0, datetime('now'))
                    """)

                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns 
                    FROM affection WHERE id = 1
                """)
                current_row = cursor.fetchone()
                cur_aff = current_row["value"]
                cur_gain_date = current_row["daily_gain_date"]
                cur_gain_amount = current_row["daily_gain_amount"] or 0
                cur_warmup_turns = current_row["reunion_warmup_turns"] or 0

                # 跨天重置当日收益计数
                if cur_gain_date != today_str:
                    cur_gain_date = today_str
                    cur_gain_amount = 0

                if is_cooldown:
                    set_affection = CharacterStateManager.get_cooldown_target(cur_aff)

                actual_affection_delta = affection_delta
                new_warmup_turns = cur_warmup_turns

                if set_affection is not None:
                    # 显式重置好感度（如事后清醒降温落位于阶段下限+5），原子化写入，不受单日日常增量上限限制
                    target_val = min(100, max(0, set_affection))
                    if set_refractory is not None:
                        cursor.execute("""
                            UPDATE affection 
                            SET value = ?,
                                social_status = MIN(100, MAX(0, social_status + ?)),
                                social_skills = MIN(100, MAX(0, social_skills + ?)),
                                refractory_period = MAX(0, ?),
                                daily_gain_date = ?,
                                daily_gain_amount = ?,
                                reunion_warmup_turns = ?,
                                last_updated = ?
                            WHERE id = 1
                        """, (target_val, social_status_delta, social_skills_delta, set_refractory,
                              cur_gain_date, cur_gain_amount, new_warmup_turns, now.strftime("%Y-%m-%d %H:%M:%S")))
                    else:
                        cursor.execute("""
                            UPDATE affection 
                            SET value = ?,
                                social_status = MIN(100, MAX(0, social_status + ?)),
                                social_skills = MIN(100, MAX(0, social_skills + ?)),
                                refractory_period = MAX(0, refractory_period + ?),
                                daily_gain_date = ?,
                                daily_gain_amount = ?,
                                reunion_warmup_turns = ?,
                                last_updated = ?
                            WHERE id = 1
                        """, (target_val, social_status_delta, social_skills_delta, refractory_delta,
                              cur_gain_date, cur_gain_amount, new_warmup_turns, now.strftime("%Y-%m-%d %H:%M:%S")))
                else:
                    if affection_delta > 0:
                        if cur_warmup_turns > 0:
                            # 破冰特权：翻倍 + 3 点补偿，且不占常规单日限额
                            actual_affection_delta = affection_delta * 2 + 3
                            new_warmup_turns = max(0, cur_warmup_turns - 1)
                        elif enforce_daily_cap:
                            # 常规日常防通胀控水（每日封顶 DAILY_GAIN_CAP）
                            remaining_cap = max(0, DAILY_GAIN_CAP - cur_gain_amount)
                            actual_affection_delta = min(affection_delta, remaining_cap)

                            # Stage 4 阻尼：>= 75 分时单次最多加 1
                            if cur_aff >= 75 and actual_affection_delta > 1:
                                actual_affection_delta = 1

                            cur_gain_amount += actual_affection_delta
                        else:
                            # 非受限调用（测试或特殊管理）：直接加，并记入当日增量
                            cur_gain_amount += affection_delta

                    elif affection_delta < 0:
                        # 惩罚性扣分不受单日上限限制，全额执行
                        pass

                    # Atomic update
                    if set_refractory is not None:
                        cursor.execute("""
                            UPDATE affection 
                            SET value = MIN(100, MAX(0, value + ?)),
                                social_status = MIN(100, MAX(0, social_status + ?)),
                                social_skills = MIN(100, MAX(0, social_skills + ?)),
                                refractory_period = MAX(0, ?),
                                daily_gain_date = ?,
                                daily_gain_amount = ?,
                                reunion_warmup_turns = ?,
                                last_updated = ?
                            WHERE id = 1
                        """, (actual_affection_delta, social_status_delta, social_skills_delta, set_refractory,
                              cur_gain_date, cur_gain_amount, new_warmup_turns, now.strftime("%Y-%m-%d %H:%M:%S")))
                    else:
                        cursor.execute("""
                            UPDATE affection 
                            SET value = MIN(100, MAX(0, value + ?)),
                                social_status = MIN(100, MAX(0, social_status + ?)),
                                social_skills = MIN(100, MAX(0, social_skills + ?)),
                                refractory_period = MAX(0, refractory_period + ?),
                                daily_gain_date = ?,
                                daily_gain_amount = ?,
                                reunion_warmup_turns = ?,
                                last_updated = ?
                            WHERE id = 1
                        """, (actual_affection_delta, social_status_delta, social_skills_delta, refractory_delta,
                              cur_gain_date, cur_gain_amount, new_warmup_turns, now.strftime("%Y-%m-%d %H:%M:%S")))

                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns 
                    FROM affection WHERE id = 1
                """)
                row = cursor.fetchone()
                
                conn.commit()
                conn.close()

                return CharacterState(
                    affection=row["value"],
                    social_status=row["social_status"],
                    social_skills=row["social_skills"],
                    refractory_period=row["refractory_period"],
                    daily_gain_date=row["daily_gain_date"],
                    daily_gain_amount=row["daily_gain_amount"] or 0,
                    reunion_warmup_turns=row["reunion_warmup_turns"] or 0
                )
            except Exception as e:
                logger.error(f"Failed to update character state: {e}")
                raise CharacterStateError(f"Database error: {e}")

    @staticmethod
    def trigger_climax(intensity: int = 10):
        """
        触发高潮生理反应（女性拟人生理演进梯级）：
        - 若当前不应期 == 0（【生机勃勃】常态初次高潮）：置为 intensity（默认 10，进入【余韵温存】，约 5 轮自然平复）；
        - 若当前不应期在 (0, 12] 之间（余韵温存未平复连战）：累加跃迁至 18（跨入【娇慵倦怠】，约 9 轮自然平复）；
        - 若当前不应期 > 12（娇慵倦怠状态下再战高潮）：累加跃迁至 24（跨入【骨软筋酥】，约 12 轮长效休止，主动温柔转移伴侣注意力至清白正事）；
        - 若当前值已 >= 24（如被 /cooldown 紧急制动置为 25 或达到上限）：保持极值，不再递减。
        """
        with _state_lock:
            cur = CharacterStateManager.get_state()
            if cur.refractory_period > 12:
                new_refractory = max(24, cur.refractory_period)
            elif cur.refractory_period > 0:
                new_refractory = max(18, intensity)
            else:
                new_refractory = intensity
            return CharacterStateManager.modify_state(set_refractory=new_refractory)

    @staticmethod
    def trigger_cooldown(target_affection: Optional[int] = None, refractory_period: int = 25) -> CharacterState:
        """
        触发事后清醒转场与好感潮汐回退：
        若未指定 target_affection，则按方案 B 阻尼回退 8 点（受当前心境阶段地板保护）；
        原子化将好感度重置至目标常态，并将生理不应期拉满至 25（激活 [绝对贤者] 状态）。
        """
        with _state_lock:
            try:
                conn = get_db_connection()
                CharacterStateManager._ensure_columns(conn)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM affection WHERE id = 1")
                row = cursor.fetchone()
                cur_aff = row["value"] if row else 100

                actual_target = target_affection if target_affection is not None else CharacterStateManager.get_cooldown_target(cur_aff)

                cursor.execute("""
                    UPDATE affection 
                    SET value = ?,
                        refractory_period = ?,
                        last_updated = datetime('now')
                    WHERE id = 1
                """, (actual_target, refractory_period))
                cursor.execute("""
                    SELECT value, social_status, social_skills, refractory_period,
                           daily_gain_date, daily_gain_amount, reunion_warmup_turns 
                    FROM affection WHERE id = 1
                """)
                row = cursor.fetchone()
                conn.commit()
                conn.close()
                if row:
                    return CharacterState(
                        affection=row["value"],
                        social_status=row["social_status"],
                        social_skills=row["social_skills"],
                        refractory_period=row["refractory_period"],
                        daily_gain_date=row["daily_gain_date"],
                        daily_gain_amount=row["daily_gain_amount"] or 0,
                        reunion_warmup_turns=row["reunion_warmup_turns"] or 0
                    )
                return CharacterState(affection=actual_target, social_status=50, social_skills=50, refractory_period=refractory_period)
            except Exception as e:
                logger.error(f"Failed to trigger cooldown: {e}")
                raise CharacterStateError(f"Database error: {e}")

    @staticmethod
    def advance_round(rounds: int = 1):
        """推进回合，自动衰减不应期"""
        return CharacterStateManager.modify_state(refractory_delta=-rounds)


