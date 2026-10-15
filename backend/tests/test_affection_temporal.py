import pytest
import sqlite3
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from backend.services.character_state import CharacterStateManager, CharacterState


@pytest.fixture
def mem_db():
    """创建一个包含完整 affection 表的独立内存 SQLite 数据库供测试使用"""
    db_uri = f"file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared"
    conn = sqlite3.connect(db_uri, uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE affection (
        id INTEGER PRIMARY KEY,
        value INTEGER DEFAULT 50,
        social_status INTEGER DEFAULT 50,
        social_skills INTEGER DEFAULT 50,
        refractory_period INTEGER DEFAULT 0,
        daily_gain_date TEXT DEFAULT NULL,
        daily_gain_amount INTEGER DEFAULT 0,
        reunion_warmup_turns INTEGER DEFAULT 0,
        last_updated DATETIME
    );
    """)
    conn.commit()

    def mock_get_db():
        c = sqlite3.connect(db_uri, uri=True, timeout=10.0)
        c.row_factory = sqlite3.Row
        return c

    with patch("backend.services.character_state.get_db_connection", side_effect=mock_get_db):
        yield {"conn": conn, "db_uri": db_uri}

    conn.close()


def test_stage_thresholds_and_floors():
    """验证阶段划分、保底线与缓冲期的数学映射契约"""
    # 阶段判定
    assert CharacterStateManager.get_stage(100) == 4
    assert CharacterStateManager.get_stage(75) == 4
    assert CharacterStateManager.get_stage(74) == 3
    assert CharacterStateManager.get_stage(50) == 3
    assert CharacterStateManager.get_stage(49) == 2
    assert CharacterStateManager.get_stage(25) == 2
    assert CharacterStateManager.get_stage(24) == 1
    assert CharacterStateManager.get_stage(0) == 1

    # 各阶段保底线
    assert CharacterStateManager.get_stage_floor(4) == 65
    assert CharacterStateManager.get_stage_floor(3) == 40
    assert CharacterStateManager.get_stage_floor(2) == 20
    assert CharacterStateManager.get_stage_floor(1) == 10

    # 信任缓冲期
    assert CharacterStateManager.get_grace_period(4) == 7
    assert CharacterStateManager.get_grace_period(3) == 5
    assert CharacterStateManager.get_grace_period(2) == 3
    assert CharacterStateManager.get_grace_period(1) == 2


def test_temporal_decay_within_grace_period_no_decay(mem_db):
    """验证在信任缓冲期内的离线不发生任何好感衰减"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)
    past = now - timedelta(days=5)  # Stage 4 缓冲期为 7 天，5 天 <= 7 天

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated)
        VALUES (1, 90, 50, 50, 0, ?)
    """, (past.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    state, reunion_info = CharacterStateManager.evaluate_temporal_decay(now=now)

    assert state.affection == 90
    assert reunion_info is None
    assert state.reunion_warmup_turns == 0


def test_temporal_decay_beyond_grace_period_smooth_decay(mem_db):
    """验证超出缓冲期后按天自然平滑递减，并触发破冰回温轮次"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)
    past = now - timedelta(days=10)  # 超出 7 天缓冲期 3 天

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated)
        VALUES (1, 90, 50, 50, 0, ?)
    """, (past.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    state, reunion_info = CharacterStateManager.evaluate_temporal_decay(now=now)

    # 90 - 3 = 87
    assert state.affection == 87
    assert reunion_info is not None
    assert reunion_info["absent_days"] == 10
    assert reunion_info["decay_amount"] == 3
    assert reunion_info["new_affection"] == 87
    assert reunion_info["stage_floor"] == 65
    assert state.reunion_warmup_turns == 2


def test_temporal_decay_stops_strictly_at_stage_floor(mem_db):
    """验证极端长时间离线时，衰减严格阻断在阶段保底线，绝不无限跌穿"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)
    past = now - timedelta(days=60)  # 离线整整 60 天

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated)
        VALUES (1, 90, 50, 50, 0, ?)
    """, (past.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    state, reunion_info = CharacterStateManager.evaluate_temporal_decay(now=now)

    # Stage 4 保底线是 65，即使过了 60 天也只能停留在 65
    assert state.affection == 65
    assert reunion_info is not None
    assert reunion_info["decay_amount"] == 25  # 90 - 65
    assert state.reunion_warmup_turns == 2


def test_stage_three_floor_stops_at_forty(mem_db):
    """验证 Stage 3（50~74）离线衰减精确阻断于 40 点"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)
    past = now - timedelta(days=30)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated)
        VALUES (1, 60, 50, 50, 0, ?)
    """, (past.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    state, reunion_info = CharacterStateManager.evaluate_temporal_decay(now=now)

    assert state.affection == 40
    assert reunion_info["decay_amount"] == 20
    assert state.reunion_warmup_turns == 2


def test_warmup_bonus_and_turn_decrement(mem_db):
    """验证破冰保护期内的真诚互动享受翻倍与 +3 补偿，且按轮次递减"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, reunion_warmup_turns, last_updated)
        VALUES (1, 65, 50, 50, 0, 2, ?)
    """, (now.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    # 第 1 轮破冰：大模型输出 +1 -> 破冰翻倍与补偿：1 * 2 + 3 = 5 点
    s1 = CharacterStateManager.modify_state(affection_delta=1, enforce_daily_cap=True, now=now)
    assert s1.affection == 70
    assert s1.reunion_warmup_turns == 1

    # 第 2 轮破冰：大模型输出 +1 -> 再次加 5 点
    s2 = CharacterStateManager.modify_state(affection_delta=1, enforce_daily_cap=True, now=now)
    assert s2.affection == 75
    assert s2.reunion_warmup_turns == 0

    # 第 3 轮：破冰保护已结束，恢复常规防通胀控水
    s3 = CharacterStateManager.modify_state(affection_delta=1, enforce_daily_cap=True, now=now)
    assert s3.affection == 76
    assert s3.reunion_warmup_turns == 0


def test_anti_inflation_daily_gain_cap(mem_db):
    """验证常规交互下单日好感净增封顶为 3 点，且跨日自动重置"""
    conn = mem_db["conn"]
    day1 = datetime(2026, 9, 8, 10, 0, 0)
    day2 = datetime(2026, 9, 9, 10, 0, 0)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, daily_gain_date, daily_gain_amount, reunion_warmup_turns, last_updated)
        VALUES (1, 50, 50, 50, 0, NULL, 0, 0, ?)
    """, (day1.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    # Day 1: 第一次加 2 点 -> 成功加 2 (累计 2)
    s1 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True, now=day1)
    assert s1.affection == 52
    assert s1.daily_gain_amount == 2

    # Day 1: 第二次加 2 点 -> 只能加 1 点 (达到每日上限 3 点)
    s2 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True, now=day1)
    assert s2.affection == 53
    assert s2.daily_gain_amount == 3

    # Day 1: 第三次加 1 点 -> 无法增加 (加 0 点)
    s3 = CharacterStateManager.modify_state(affection_delta=1, enforce_daily_cap=True, now=day1)
    assert s3.affection == 53
    assert s3.daily_gain_amount == 3

    # Day 2: 跨天后自动重置配额，又可以正常增长
    s4 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True, now=day2)
    assert s4.affection == 55
    assert s4.daily_gain_amount == 2


def test_mistake_penalty_not_blocked_by_cap(mem_db):
    """验证连续答错等惩罚性扣分不受每日上限阻拦，全额即时扣除"""
    conn = mem_db["conn"]
    now = datetime(2026, 9, 8, 12, 0, 0)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, daily_gain_amount, last_updated)
        VALUES (1, 80, 50, 50, 0, 3, ?)
    """, (now.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()

    # 当日虽然已满 3 点上限，但扣分不受限
    s = CharacterStateManager.modify_state(affection_delta=-2, enforce_daily_cap=True, now=now)
    assert s.affection == 78
