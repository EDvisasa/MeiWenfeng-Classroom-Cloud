import asyncio
import json
import pytest
import sqlite3
import uuid
from unittest.mock import patch

from backend.services.character_state import CharacterStateManager, CharacterState
from backend.services.slash_handler import handle_slash_command


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
    cursor.execute("""
        INSERT INTO affection (id, value, social_status, social_skills, refractory_period, last_updated)
        VALUES (1, 100, 80, 80, 0, datetime('now'))
    """)
    conn.commit()

    def mock_get_db():
        c = sqlite3.connect(db_uri, uri=True, timeout=10.0)
        c.row_factory = sqlite3.Row
        return c

    with patch("backend.services.character_state.get_db_connection", side_effect=mock_get_db):
        yield {"conn": conn, "db_uri": db_uri}

    conn.close()


def test_trigger_cooldown_resets_affection_to_80_and_refractory_to_25(mem_db):
    """验证 trigger_cooldown 原子化将好感度重置至 80，并将不应期拉至 25（绝对贤者）"""
    initial_state = CharacterStateManager.get_state()
    assert initial_state.affection == 100
    assert initial_state.refractory_period == 0

    new_state = CharacterStateManager.trigger_cooldown(target_affection=80, refractory_period=25)
    assert new_state.affection == 80
    assert new_state.refractory_period == 25

    # 验证持久化查询
    persisted = CharacterStateManager.get_state()
    assert persisted.affection == 80
    assert persisted.refractory_period == 25


def test_advance_round_natural_decay(mem_db):
    """验证 advance_round 自然衰减生理不应期，底线为 0"""
    CharacterStateManager.trigger_cooldown(target_affection=80, refractory_period=25)
    
    # 第一轮推进 -2
    s1 = CharacterStateManager.advance_round(rounds=2)
    assert s1.refractory_period == 23

    # 第二轮推进 -2
    s2 = CharacterStateManager.advance_round(rounds=2)
    assert s2.refractory_period == 21

    # 大跨度推进，确保底线为 0 不穿透
    s3 = CharacterStateManager.advance_round(rounds=30)
    assert s3.refractory_period == 0


def test_slash_handler_cooldown_command(mem_db):
    """验证 /cooldown 斜杠指令执行后重置数值并返回生动的清醒转场台词"""
    async def _run():
        class DummyPayload:
            current_file_path = None
            persona_type = "simplified"

        res = handle_slash_command("/cooldown", DummyPayload(), "/cooldown", [])
        
        # 消费异步生成器提取完整 SSE 纯文本
        body_text = ""
        async for chunk in res.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            for line in str(chunk).split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        if isinstance(payload, dict) and "text" in payload:
                            body_text += payload["text"]
                        elif isinstance(payload, str):
                            body_text += payload
                    except Exception:
                        pass
        return body_text

    body_text = asyncio.run(_run())
    assert "静心专注" in body_text or "余韵温存" in body_text or "清醒" in body_text
    assert "92" in body_text

    # 验证状态机已同步更新
    state = CharacterStateManager.get_state()
    assert state.affection == 92
    assert state.refractory_period == 25


def test_post_intimacy_cooldown_intent_detection():
    """验证包含事后清醒意图的提问能被意图识别检测器识别"""
    from backend.services.context_manager import is_cooldown_intent_detected

    assert is_cooldown_intent_detected("干完了，收拾一下吧") is True
    assert is_cooldown_intent_detected("好啦，余韵温存，咱们看看代码") is True
    assert is_cooldown_intent_detected("静心专注看题吧") is True
    assert is_cooldown_intent_detected("好啦，脑袋清醒了，聊点正事") is True
    assert is_cooldown_intent_detected("休息吧，进入贤者模式") is True
    assert is_cooldown_intent_detected("刚才做完了，咱们继续看代码") is True
    assert is_cooldown_intent_detected("今天把这个算法写完") is False
    assert is_cooldown_intent_detected("你好呀小狐狸") is False


def test_pipeline_refractory_auto_decay(mem_db):
    """验证每轮常规对话后，ResponsePipeline 自动将生理不应期衰减 2 点"""
    from backend.services.response_pipeline import ResponsePipeline
    from backend.services.side_effects import action_registry
    from unittest.mock import MagicMock

    CharacterStateManager.trigger_cooldown(target_affection=80, refractory_period=25)
    
    pipeline = ResponsePipeline(registry=action_registry)
    pipeline.original_user_msg = "夫君，咱们继续看代码吧"

    def dummy_stream():
        yield "好的夫君，咱们来看这段逻辑。"

    with patch("backend.services.response_pipeline.get_rag_client", return_value=MagicMock()):
        list(pipeline.process_stream(dummy_stream()))

    state = CharacterStateManager.get_state()
    assert state.refractory_period == 23


def test_get_cooldown_target_scheme_b():
    """验证方案 B 比例阻尼衰减制：A_new = max(A_current - 8, stage_floor)"""
    # 阶段四 (75~100，地板锁 75)
    assert CharacterStateManager.get_cooldown_target(100) == 92
    assert CharacterStateManager.get_cooldown_target(95) == 87
    assert CharacterStateManager.get_cooldown_target(85) == 77
    assert CharacterStateManager.get_cooldown_target(78) == 75  # max(70, 75) = 75
    assert CharacterStateManager.get_cooldown_target(76) == 75  # max(68, 75) = 75 (不反弹，不破阶)
    assert CharacterStateManager.get_cooldown_target(75) == 75

    # 阶段三 (50~74，地板锁 50)
    assert CharacterStateManager.get_cooldown_target(74) == 66  # 74 - 8 = 66
    assert CharacterStateManager.get_cooldown_target(65) == 57  # 65 - 8 = 57
    assert CharacterStateManager.get_cooldown_target(55) == 50  # max(47, 50) = 50
    assert CharacterStateManager.get_cooldown_target(52) == 50  # max(44, 50) = 50

    # 阶段二 (25~49，地板锁 25)
    assert CharacterStateManager.get_cooldown_target(40) == 32
    assert CharacterStateManager.get_cooldown_target(28) == 25

    # 阶段一 (0~24，地板锁 0)
    assert CharacterStateManager.get_cooldown_target(10) == 2
    assert CharacterStateManager.get_cooldown_target(5) == 0


def test_trigger_cooldown_scheme_b_default(mem_db):
    """验证 trigger_cooldown() 在方案 B 下根据当前好感阻尼回退 8 点且不破阶"""
    # 当前好感 100（阶段四）
    s1 = CharacterStateManager.trigger_cooldown()
    assert s1.affection == 92
    assert s1.refractory_period == 25

    # 修改到 76（阶段四下沿），再触发 cooldown，受地板锁 75 保护
    CharacterStateManager.modify_state(set_affection=76)
    s2 = CharacterStateManager.trigger_cooldown()
    assert s2.affection == 75
    assert s2.refractory_period == 25


def test_multi_climax_refractory_accumulation(mem_db):
    """验证高潮累加机制：首次高潮为 10，二次连战跃迁至 18 (精力透支)，三次连战跃迁至 24 (余韵温存)"""
    # 首次高潮
    s1 = CharacterStateManager.trigger_climax(intensity=10)
    assert s1.refractory_period == 10

    # 二次高潮（当前已有 10 分温存）
    s2 = CharacterStateManager.trigger_climax(intensity=10)
    assert s2.refractory_period == 18

    # 三次高潮（当前已有 18 分精力透支，跨入余韵温存）
    s3 = CharacterStateManager.trigger_climax(intensity=10)
    assert s3.refractory_period == 24

    # 四次高潮（保持在 24 上限保护不回退）
    s4 = CharacterStateManager.trigger_climax(intensity=10)
    assert s4.refractory_period == 24


def test_modify_state_is_cooldown_preserves_refractory(mem_db):
    """验证自然事后降温 modify_state(is_cooldown=True) 仅回退好感，保留当前温存值 10 不暴力置为 25"""
    # 先触发单次高潮，不应期设为 10
    CharacterStateManager.trigger_climax(intensity=10)
    cur = CharacterStateManager.get_state()
    assert cur.refractory_period == 10
    assert cur.affection == 100

    # 房事完毕自然降温：只传入 is_cooldown=True，不传 set_refractory
    state = CharacterStateManager.modify_state(is_cooldown=True)
    assert state.affection == 92  # 方案 B 回退 8 点
    assert state.refractory_period == 10  # 忠实保持 10 点温存，绝不暴力打到 25！


def test_slash_handler_dual_state_dialogue(mem_db):
    """验证 /cooldown 斜杠指令的双态自适应台词：真事后(refractory>0)娇软依偎，日常专注(refractory==0)端庄名师"""
    from backend.services.slash_handler import SlashHandler
    handler = SlashHandler()

    async def get_text(gen):
        text = ""
        async for chunk in gen:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            for line in str(chunk).split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        if isinstance(payload, dict) and "text" in payload:
                            text += payload["text"]
                        elif isinstance(payload, str):
                            text += payload
                    except Exception:
                        pass
        return text

    async def _run():
        # 态一：刚经历房事高潮 (refractory=10)
        CharacterStateManager.trigger_climax(intensity=10)
        output1 = await get_text(handler.handle("/cooldown", "session_1"))
        assert "伏在你怀里" in output1 or "刚折腾完" in output1 or "腿都还是软的" in output1

        # 态二：日常清白状态 (refractory=0)
        CharacterStateManager.modify_state(set_refractory=0)
        output2 = await get_text(handler.handle("/cooldown", "session_1"))
        assert "专心修习" in output2 or "收敛" in output2 or "倾囊相授" in output2
        assert "刚折腾完" not in output2  # 严禁出现腿软穿模

    asyncio.run(_run())


def test_property_update_handler_climax_accumulation(mem_db):
    """验证 PropertyUpdateHandler 收到大模型 set_refractory='10' 时不暴力覆盖，而是自适应累加 10 -> 18 -> 24"""
    from backend.services.side_effects import PropertyUpdateHandler
    handler = PropertyUpdateHandler()

    # 模拟第 1 轮高潮
    handler.handle({"set_refractory": "10"}, "")
    assert CharacterStateManager.get_state().refractory_period == 10

    # 模拟第 2 轮连战高潮
    handler.handle({"set_refractory": "10"}, "")
    assert CharacterStateManager.get_state().refractory_period == 18

    # 模拟第 3 轮连战高潮
    handler.handle({"set_refractory": "10"}, "")
    assert CharacterStateManager.get_state().refractory_period == 24


def test_property_update_handler_climax_event_tag(mem_db):
    """验证 PropertyUpdateHandler 识别纯语义事件标签 climax='true' 并自适应累加 10 -> 18 -> 24"""
    from backend.services.side_effects import PropertyUpdateHandler
    handler = PropertyUpdateHandler()

    handler.handle({"climax": "true"}, "")
    assert CharacterStateManager.get_state().refractory_period == 10

    handler.handle({"climax": "true"}, "")
    assert CharacterStateManager.get_state().refractory_period == 18

    handler.handle({"climax": "true"}, "")
    assert CharacterStateManager.get_state().refractory_period == 24


def test_property_update_handler_is_cooldown_scheme_b(mem_db):
    """验证 SideEffect 拦截器识别 is_cooldown='true' 并按方案 B 阻尼回落"""
    from backend.services.side_effects import PropertyUpdateHandler
    handler = PropertyUpdateHandler()
    handler.handle({"is_cooldown": "true"}, "")

    persisted = CharacterStateManager.get_state()
    assert persisted.affection == 92


def test_daily_gain_cap_is_4(mem_db):
    """验证单日好感获取上限已提升至 4 点"""
    from backend.services.character_state import DAILY_GAIN_CAP
    assert DAILY_GAIN_CAP == 4

    # 连续加分，验证第 4 分生效，第 5 分被封顶
    CharacterStateManager.modify_state(affection_delta=-60)  # 先降至 40 分（阶段二，避免阶段四单次加1阻尼）
    s1 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True)
    assert s1.affection == 42
    s2 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True)
    assert s2.affection == 44  # 此时当日增量已达 4 点

    # 尝试再加 2 点，受 DAILY_GAIN_CAP=4 限制，增量应为 0
    s3 = CharacterStateManager.modify_state(affection_delta=2, enforce_daily_cap=True)
    assert s3.affection == 44
    assert s3.daily_gain_amount == 4


def test_prompts_stage_4_and_cooldown_rules():
    """验证提示词阶段四包含生理状态制约说明，且移除日常手动扣减 refractory_delta"""
    from backend.services.prompts import get_dynamic_attributes_prompt, get_one_shot_demonstration

    prompt = get_dynamic_attributes_prompt(100, 50, 50, 25)
    # 矛盾一：阶段四需包含受生理状态/贤者模式影响说明
    assert "physiological state" in prompt or "Refractory Period" in prompt
    assert "is_cooldown" in prompt

    # 矛盾三：One-shot 中不应要求模型日常输出 refractory_delta="-1"
    demo = get_one_shot_demonstration()
    assert 'refractory_delta="-1"' not in demo


