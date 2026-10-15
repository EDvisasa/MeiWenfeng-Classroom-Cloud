"""
ISSUE-03: ZPD (最近发展区) 动态难度追踪自适应算法
依据 docs/GLOSSARY.md，ZPD 指标列驻留于 course_progress 表。
"""
import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

from backend.services import course_manager as cm
from backend.services.slash_handler import handle_slash_command

ZPD_ACTIVE_TOPIC = "编程环境配置与基础语法入门"


@pytest.fixture
def course_db(mock_db_path, monkeypatch):
    """将 course_manager 的独立 DB_PATH 也劫持到 mock 临时库。"""
    monkeypatch.setattr(cm, "DB_PATH", mock_db_path)
    return mock_db_path


def _read_zpd_row(db_path, topic):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic, zpd_coefficient, consecutive_correct, consecutive_wrong "
        "FROM course_progress WHERE topic = ? ORDER BY id DESC LIMIT 1",
        (topic,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def test_course_progress_has_zpd_columns(mock_db_path):
    """Schema 迁移后 course_progress 必须包含三个 ZPD 指标列。"""
    conn = sqlite3.connect(mock_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(course_progress)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert {"zpd_coefficient", "consecutive_correct", "consecutive_wrong"} <= columns


def test_get_zpd_metrics_defaults(course_db):
    """未发生任何作答时，默认难度系数为 1.0，连对/连错计数为 0。"""
    metrics = cm.get_zpd_metrics()
    assert metrics["topic"] == ZPD_ACTIVE_TOPIC
    assert metrics["coefficient"] == 1.0
    assert metrics["consecutive_correct"] == 0
    assert metrics["consecutive_wrong"] == 0


def test_two_consecutive_correct_raise_coefficient(course_db):
    """连对两题后难度系数上升 0.1，连对计数清零。"""
    cm.record_quiz_result(True)
    cm.record_quiz_result(True)
    metrics = cm.get_zpd_metrics()
    assert metrics["coefficient"] == 1.1
    assert metrics["consecutive_correct"] == 0
    assert metrics["consecutive_wrong"] == 0


def test_two_consecutive_wrong_lower_coefficient(course_db):
    """升至 1.2 后连错两题，自动回退降级至 1.1。"""
    cm.record_quiz_result(True)
    cm.record_quiz_result(True)   # 1.1
    cm.record_quiz_result(True)
    cm.record_quiz_result(True)   # 1.2
    cm.record_quiz_result(False)
    cm.record_quiz_result(False)  # 1.1
    metrics = cm.get_zpd_metrics()
    assert metrics["coefficient"] == 1.1
    assert metrics["consecutive_wrong"] == 0


def test_interleaved_results_reset_streaks(course_db):
    """对/错交错时不应误触发连对连错晋级降级。"""
    cm.record_quiz_result(True)
    cm.record_quiz_result(False)
    cm.record_quiz_result(True)
    cm.record_quiz_result(True)
    metrics = cm.get_zpd_metrics()
    assert metrics["coefficient"] == 1.1
    assert metrics["consecutive_correct"] == 0


def test_coefficient_clamped_at_max(course_db):
    """难度系数封顶 3.0，防止无限上调。"""
    for _ in range(44):
        cm.record_quiz_result(True)
    metrics = cm.get_zpd_metrics()
    assert metrics["coefficient"] == 3.0


def _mock_llm_stream(monkeypatch, captured):
    import backend.services.slash_handler as sh

    def fake_build_base_system_prompt(**kwargs):
        captured["injection"] = kwargs.get("extra_system_injection", "")
        return "SYSTEM_PROMPT", 0, 0

    def fake_stream_chat(messages, system_prompt):
        yield "授课内容开始"
        yield " 第一节课内容。"

    monkeypatch.setattr("backend.services.context_manager.build_base_system_prompt", fake_build_base_system_prompt)
    monkeypatch.setattr(sh, "stream_chat", fake_stream_chat)
    rag_client = SimpleNamespace(save_memory=lambda *a, **k: None)
    monkeypatch.setattr(sh, "get_rag_client", lambda: rag_client)


def test_lesson_response_contains_zpd_coefficient(course_db, monkeypatch):
    """/lesson 响应体（SSE 流）必须包含当前 ZPD 难度系数，且注入指令携带该系数。"""
    captured = {}
    _mock_llm_stream(monkeypatch, captured)

    payload = SimpleNamespace(current_file_path=None, persona_type="simplified")
    response = handle_slash_command(
        "/lesson", payload, "/lesson",
        [{"role": "user", "content": "/lesson"}],
    )
    async def _collect_body():
        return "".join([chunk async for chunk in response.body_iterator])

    body = asyncio.run(_collect_body())

    assert "当前 ZPD 难度系数" in body
    assert "1.0" in body
    assert "ZPD Difficulty Coefficient" in captured["injection"]
    assert "1.0" in captured["injection"]


def test_lesson_continue_records_quiz_result(course_db, monkeypatch):
    """提交 <submit_quiz_result> 后，course_progress 的连对计数必须 +1。"""
    captured = {}
    _mock_llm_stream(monkeypatch, captured)

    payload = SimpleNamespace(current_file_path=None, persona_type="simplified")
    quiz_msg = '我选了：选项B\n<submit_quiz_result is_correct="true" selected="选项B" />'
    handle_slash_command(
        "/lesson_continue", payload, quiz_msg,
        [{"role": "user", "content": quiz_msg}],
    )

    row = _read_zpd_row(course_db, ZPD_ACTIVE_TOPIC)
    assert row is not None
    assert row["consecutive_correct"] == 1
    assert row["consecutive_wrong"] == 0


def test_lesson_continue_records_wrong_answer(course_db, monkeypatch):
    """提交错误答案后，连错计数 +1 且连对计数清零。"""
    captured = {}
    _mock_llm_stream(monkeypatch, captured)

    payload = SimpleNamespace(current_file_path=None, persona_type="simplified")
    quiz_msg = '我选了：选项A\n<submit_quiz_result is_correct="false" selected="选项A" />'
    handle_slash_command(
        "/lesson_continue", payload, quiz_msg,
        [{"role": "user", "content": quiz_msg}],
    )

    row = _read_zpd_row(course_db, ZPD_ACTIVE_TOPIC)
    assert row["consecutive_wrong"] == 1
    assert row["consecutive_correct"] == 0


def test_quiz_wrong_under_three_times_does_not_penalize_affection(course_db, monkeypatch):
    """答错 1~2 次时仅记录连错，不应扣除好感度。"""
    from backend.services.character_state import CharacterStateManager
    captured = {}
    _mock_llm_stream(monkeypatch, captured)

    payload = SimpleNamespace(current_file_path=None, persona_type="simplified")
    quiz_msg = '我选了：选项A\n<submit_quiz_result is_correct="false" selected="选项A" />'

    initial_aff = CharacterStateManager.get_state().affection
    handle_slash_command("/lesson_continue", payload, quiz_msg, [{"role": "user", "content": quiz_msg}])
    handle_slash_command("/lesson_continue", payload, quiz_msg, [{"role": "user", "content": quiz_msg}])

    current_aff = CharacterStateManager.get_state().affection
    assert current_aff == initial_aff
    assert "<slacking_warning>" not in captured.get("injection", "")


def test_quiz_wrong_three_times_triggers_affection_penalty_and_warning(course_db, monkeypatch):
    """连续答错达到 3 次时，好感度原子扣减 2 点，且注入 <slacking_warning> 警告。"""
    from backend.services.character_state import CharacterStateManager
    captured = {}
    _mock_llm_stream(monkeypatch, captured)

    payload = SimpleNamespace(current_file_path=None, persona_type="simplified")
    quiz_msg = '我选了：选项A\n<submit_quiz_result is_correct="false" selected="选项A" />'

    initial_aff = CharacterStateManager.get_state().affection
    # 连续答错 3 次
    handle_slash_command("/lesson_continue", payload, quiz_msg, [{"role": "user", "content": quiz_msg}])
    handle_slash_command("/lesson_continue", payload, quiz_msg, [{"role": "user", "content": quiz_msg}])
    handle_slash_command("/lesson_continue", payload, quiz_msg, [{"role": "user", "content": quiz_msg}])

    current_aff = CharacterStateManager.get_state().affection
    assert current_aff == initial_aff - 2
    assert "<slacking_warning>" in captured.get("injection", "")
    assert "有人故意瞎捣乱" in captured.get("injection", "")

