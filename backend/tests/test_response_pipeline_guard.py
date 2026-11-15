import pytest
from backend.services.response_pipeline import TagStreamInterceptor, ResponsePipeline
from backend.services.action_registry import ActionRegistry, SideEffectHandler

def test_interceptor_draft_property_update_does_not_deadlock():
    """
    ISSUE-42 / Bug 16:
    When the model drafts `6. Post-Response: <monologue> + <property_update> at end.` without `/>`,
    TagStreamInterceptor MUST NOT enter `in_tag = True` waiting for `</property_update>`.
    It must stream all subsequent story tokens in real-time.
    """
    interceptor = TagStreamInterceptor(target_tags=["property_update"])
    
    chunks = [
        "6. Post-Response: <monologue> + ",
        "<property_update>",
        " at end.\n",
        "*夜风从半掩的窗缝里溜进来* 夫君好呀",
        "<property_update affection_delta=\"1\" />"
    ]
    
    yielded_chunks = []
    for c in chunks:
        out = list(interceptor.process_chunk(c))
        yielded_chunks.append("".join(item.get("text", "") if isinstance(item, dict) else item for item in out))
        
    # The middle story chunk MUST be yielded in real-time, not buffered until finish()
    assert "*夜风从半掩的窗缝里溜进来* 夫君好呀" in yielded_chunks[3], "Story chunk was swallowed/buffered into deadlock!"
    assert interceptor.in_tag is False, "interceptor.in_tag should be False, not waiting for </property_update>!"
    
    # Real self-closing tag at the end should still be captured
    assert "property_update" in interceptor.intercepted_data
    assert interceptor.intercepted_data["property_update"][0]["attrs"] == {"affection_delta": "1"}


def test_interceptor_think_sandbox_tag_bypass():
    """
    ISSUE-42 / Bug 16:
    Inside <think>...</think>, any tag mentioned (such as <property_update>, <monologue>, <call_tool>)
    is pure model reasoning scratchpad and MUST NOT trigger tag interception or deadlock.
    """
    interceptor = TagStreamInterceptor(target_tags=["property_update"])
    
    text = (
        "<think>\n"
        "1. Plan: mention <property_update> and <monologue> here.\n"
        "</think>\n"
        "*微笑着看着你* 夫君请看：\n"
        "<property_update affection_delta=\"2\" />"
    )
    
    output = ""
    for ch in text:
        for processed in interceptor.process_chunk(ch):
            output += processed.get("text", "") if isinstance(processed, dict) else processed
            
    for processed in interceptor.finish():
        output += processed.get("text", "") if isinstance(processed, dict) else processed
        
    assert output == text
    assert interceptor.in_think is False
    # Only the one outside <think> should be in intercepted_data
    assert len(interceptor.intercepted_data["property_update"]) == 1
    assert interceptor.intercepted_data["property_update"][0]["attrs"] == {"affection_delta": "2"}


def test_interceptor_unclosed_slash_tolerant_property_update():
    """
    ISSUE-42:
    If model writes `<property_update affection_delta="+3">` (forgetting the `/` before `>`),
    it should extract the attributes without deadlocking.
    """
    interceptor = TagStreamInterceptor(target_tags=["property_update"])
    
    chunks = [
        "Ending dialogue. ",
        "<property_update affection_delta=\"+3\">",
        " More dialogue after."
    ]
    
    yielded = []
    for c in chunks:
        out = list(interceptor.process_chunk(c))
        yielded.append("".join(item.get("text", "") if isinstance(item, dict) else item for item in out))
        
    assert interceptor.in_tag is False
    assert "property_update" in interceptor.intercepted_data
    assert interceptor.intercepted_data["property_update"][0]["attrs"] == {"affection_delta": "+3"}
    assert " More dialogue after." in yielded[2]


def test_unclosed_explainer_does_not_swallow_monologue_or_property_update():
    """
    ISSUE-43 / Bug 37:
    When an <explainer> is unclosed, its side-effect handler must NOT receive
    trailing dialogue, <monologue>, or <property_update>.
    """
    registry = ActionRegistry()
    saved_handlers = dict(registry.handlers)
    captured = []
    
    class DummyHandler(SideEffectHandler):
        def handle(self, attrs, content):
            captured.append({"attrs": attrs, "content": content})
            
    try:
        registry.register("explainer", DummyHandler())
        
        pipeline = ResponsePipeline(registry=registry)
        clean_text = (
            '<explainer title="FFT Tutorial">\n'
            'Lecture content here.\n'
            '<monologue>Secret inner thought</monologue>\n'
            '<property_update affection_delta="1" />'
        )
        
        pipeline._execute_side_effects(clean_text)
        
        assert len(captured) == 1
        assert captured[0]["attrs"] == {"title": "FFT Tutorial"}
        assert "Secret inner thought" not in captured[0]["content"]
        assert "<monologue>" not in captured[0]["content"]
        assert "<property_update" not in captured[0]["content"]
        assert captured[0]["content"] == "Lecture content here."
    finally:
        registry.handlers = saved_handlers


def test_response_pipeline_production_db_guard_blocks_test_session_pollution(monkeypatch):
    """
    [Bug #46] 生产库长程记忆防污染守卫验证：
    当环境指向生产库且 session_id 属于测试前缀（如 test-session）或开启 dry_run 时，
    ResponsePipeline 必须绝对跳过向 memory_logs 和 ChromaDB 写入记忆。
    """
    from unittest.mock import patch, MagicMock
    import backend.database as db_mod

    # 模拟指向生产 classroom.db 路径
    monkeypatch.setattr(db_mod, "DB_PATH", "D:\\MeiWenfeng-Classroom\\backend\\classroom.db")

    with patch("backend.services.response_pipeline.get_rag_client") as mock_get_rag, \
         patch("backend.services.response_pipeline.get_db_connection") as mock_get_db:

        mock_rag = MagicMock()
        mock_get_rag.return_value = mock_rag
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn

        # 1. 模拟未做隔离的 test-session 测试调用
        pipeline_test = ResponsePipeline(session_id="test-session")
        pipeline_test.original_user_msg = "测试提问"
        pipeline_test._execute_side_effects("测试回答")

        # 必须拦截：绝不调用 RAG save_memory，绝不执行 INSERT INTO memory_logs
        assert not mock_rag.save_memory.called
        assert not mock_conn.cursor.called

        # 2. 模拟显式 dry_run=True 调用
        pipeline_dry = ResponsePipeline(session_id="real_user_session", dry_run=True)
        pipeline_dry.original_user_msg = "预演提问"
        pipeline_dry._execute_side_effects("预演回答")

        assert not mock_rag.save_memory.called
        assert not mock_conn.cursor.called


def test_clean_memory_text_strips_tool_batch_shells_completely():
    from backend.services.response_pipeline import clean_memory_text

    dirty_batch = (
        "你好呀！\n"
        "<tool_batch>\n<call_tool name=\"search_memory\">\n<query>x</query>\n</call_tool>\n</tool_batch>\n"
        "*微笑* 找到了。"
    )
    cleaned = clean_memory_text(dirty_batch)
    assert cleaned == "你好呀！\n\n*微笑* 找到了。" or cleaned == "你好呀！\n*微笑* 找到了。"
    assert "<tool_batch" not in cleaned
    assert "</tool_batch" not in cleaned
    assert "<call_tool" not in cleaned

    shells_only = clean_memory_text("<tool_batch> </tool_batch> <tool_batch> </tool_batch> <tool_call>{}</tool_call>")
    assert shells_only == ""

    unclosed_func = clean_memory_text(
        "夫君别急~\n<tool_batch>\n<function=get_memory_calendar>\n<parameter=date_range>2026-07</parameter>\n</function>"
    )
    assert unclosed_func == "夫君别急~"
    assert "<tool_batch" not in unclosed_func
    assert "<function=" not in unclosed_func


