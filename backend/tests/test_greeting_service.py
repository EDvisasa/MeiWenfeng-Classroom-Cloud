import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.services.greeting_service import (
    GreetingService,
    get_time_slot,
    ORIGINAL_VIGNETTES,
    TRANSITION_ACTIONS,
    ROUTINE_DIALOGUES,
    REUNION_OVERRIDE_DIALOGUES
)
from backend.main import app


def test_time_slot_mapping():
    """验证现实物理时段的 6 档精准映射"""
    assert get_time_slot(datetime(2026, 9, 9, 7, 30)) == "dawn"       # 晨曦
    assert get_time_slot(datetime(2026, 9, 9, 10, 0)) == "morning"    # 上午
    assert get_time_slot(datetime(2026, 9, 9, 14, 15)) == "afternoon"  # 午后
    assert get_time_slot(datetime(2026, 9, 9, 18, 45)) == "dusk"       # 傍晚
    assert get_time_slot(datetime(2026, 9, 9, 21, 0)) == "evening"    # 夜阑
    assert get_time_slot(datetime(2026, 9, 9, 2, 30)) == "midnight"   # 子夜


def test_greeting_service_structure():
    """验证开场白合成结构包含四元槽位与合规格式"""
    res = GreetingService.generate_greeting(affection=80, now=datetime(2026, 9, 9, 15, 0))

    assert res["role"] == "assistant"
    assert "content" in res
    assert "timestamp" in res
    assert "meta" in res
    assert res["meta"]["stage"] == 4
    assert res["meta"]["time_slot"] == "afternoon"

    # 验证槽位拼装语法 *（...）*“...”
    content = res["content"]
    assert content.startswith("*（")
    assert "）*“" in content
    assert content.endswith("”")


def test_original_vignettes_contain_original_persona_elements():
    """验证行为动作池中忠实收纳原版 61KB 人设的核心元素"""
    all_ambient_text = " ".join(
        v["ambient"] for vignettes in ORIGINAL_VIGNETTES.values() for v in vignettes
    )

    # 原版人设特色符号校验
    assert "桃花扇" in all_ambient_text or "分身" in all_ambient_text
    assert "白桃乌龙" in all_ambient_text
    assert "螺子黛" in all_ambient_text or "眉笔" in all_ambient_text
    assert "并蒂莲" in all_ambient_text
    assert "软榻" in all_ambient_text or "练功" in all_ambient_text


def test_stage_matching_and_tone():
    """验证好感 4 阶在同一时段下展现截然不同的亲疏面相"""
    now = datetime(2026, 9, 9, 8, 0)  # 晨曦

    # Stage 1: 审视防备
    g1 = GreetingService.generate_greeting(affection=15, now=now)
    assert g1["meta"]["stage"] == 1
    assert any(w in g1["content"] for w in ["道友", "客套", "礼貌", "红尘明星", "经卷"])

    # Stage 4: 不分彼此
    g4 = GreetingService.generate_greeting(affection=95, now=now)
    assert g4["meta"]["stage"] == 4
    assert any(w in g4["content"] for w in ["夫君", "润润嗓子", "白桃乌龙", "新画", "欢喜", "扑入"])


def test_reunion_override_priority():
    """验证久别重逢状态拥有最高优先级覆盖常规开场对白"""
    now = datetime(2026, 9, 9, 14, 0)

    # 强制轻度重逢 (4~7天)
    g_reunion = GreetingService.generate_greeting(affection=85, now=now, force_reunion="light")
    assert g_reunion["meta"]["reunion_type"] == "light"
    assert "凉了又换" in g_reunion["content"] or "还知道回来" in g_reunion["content"]

    # 强制中度退阶重逢 (8~20天)
    g_medium = GreetingService.generate_greeting(affection=65, now=now, force_reunion="medium")
    assert g_medium["meta"]["reunion_type"] == "medium"
    assert "生分" in g_medium["content"] or "半月有余" in g_medium["content"] or "过客" in g_medium["content"]


def test_chat_greeting_api_endpoint():
    """验证 GET /api/chat/greeting 端点正常响应且契约合规"""
    client = TestClient(app)
    response = client.get("/api/chat/greeting?affection=85&force_reunion=light")

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "content" in data
    assert data["meta"]["stage"] == 4
    assert data["meta"]["reunion_type"] == "light"
