import pytest
from backend.services.response_pipeline import TagStreamInterceptor

def test_interceptor_basic_extraction():
    interceptor = TagStreamInterceptor(target_tags=["glossary"])
    text = "This is a test. <glossary>Quantum Computing</glossary> more text <glossary term=\"Qubit\">A qubit</glossary> end."
    output = ""
    for char in text:
        for chunk in interceptor.process_chunk(char):
            output += chunk.get("text", "") if isinstance(chunk, dict) else chunk
    for chunk in interceptor.finish():
        output += chunk.get("text", "") if isinstance(chunk, dict) else chunk
    
    assert output == "This is a test.  more text  end."
    assert "glossary" in interceptor.intercepted_data
    assert len(interceptor.intercepted_data["glossary"]) == 2
    assert interceptor.intercepted_data["glossary"][0]["content"] == "Quantum Computing"
    assert interceptor.intercepted_data["glossary"][1]["attrs"] == {"term": "Qubit"}
    assert interceptor.intercepted_data["glossary"][1]["content"] == "A qubit"

def test_interceptor_with_agent_executor_chunks():
    tags = ['system_pass', 'glossary', 'new_course', 'explainer', 'property_update']
    interceptor = TagStreamInterceptor(target_tags=tags)
    
    # Simulate AgentExecutor behavior (buffering tags till length 20 before emitting)
    text = '咱们继续往下读，好不好嘛？♡"<property_update affection_delta="+1" />'
    chunks = []
    
    prefix = '咱们继续往下读，好不好嘛？♡"'
    for c in prefix:
        chunks.append({"type": "text", "text": c})
        
    tag_part = '<property_update affection_delta="+1" />'
    part1 = tag_part[:21] # '<property_update affe'
    chunks.append({"type": "text", "text": part1})
    
    for c in tag_part[21:]:
        chunks.append({"type": "text", "text": c})
        
    output = ""
    for chunk in chunks:
        for processed in interceptor.process_chunk(chunk):
            output += processed.get("text", "") if isinstance(processed, dict) else processed
            
    for processed in interceptor.finish():
        output += processed.get("text", "") if isinstance(processed, dict) else processed
        
    assert output == '咱们继续往下读，好不好嘛？♡"'
    assert "property_update" in interceptor.intercepted_data
    assert interceptor.intercepted_data["property_update"][0]["attrs"] == {"affection_delta": "+1"}

def test_interceptor_bugfix_non_target_closing_tag_poisoning():
    tags = ['system_pass', 'glossary', 'new_course', 'explainer', 'property_update']
    interceptor = TagStreamInterceptor(target_tags=tags)
    
    # Simulate the bug where </thought> poisons the buffer and bypasses subsequent tag interception
    text = '</thought>\n听到你刚睡醒带着几分慵懒鼻音的“贴贴”...咱们继续往下读，好不好嘛？♡"<property_update affection_delta="+1" />'
    
    chunks = []
    for c in text[:text.find('<property_update')]:
        chunks.append({"type": "text", "text": c})
        
    tag_part = text[text.find('<property_update'):]
    part1 = tag_part[:21] # '<property_update affe'
    chunks.append({"type": "text", "text": part1})
    
    for c in tag_part[21:]:
        chunks.append({"type": "text", "text": c})
        
    output = ""
    for chunk in chunks:
        for processed in interceptor.process_chunk(chunk):
            output += processed.get("text", "") if isinstance(processed, dict) else processed
            
    for processed in interceptor.finish():
        output += processed.get("text", "") if isinstance(processed, dict) else processed
        
    assert "property_update" not in output
    assert '</thought>\n听到你刚睡醒' in output
    assert "property_update" in interceptor.intercepted_data
    assert interceptor.intercepted_data["property_update"][0]["attrs"] == {"affection_delta": "+1"}
