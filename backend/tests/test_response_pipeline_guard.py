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
    captured = []
    
    class DummyHandler(SideEffectHandler):
        def handle(self, attrs, content):
            captured.append({"attrs": attrs, "content": content})
            
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

