import pytest
from backend.services.context_manager import get_cross_reference_protocol, build_base_system_prompt

def test_get_cross_reference_protocol_structure():
    """
    验证 get_cross_reference_protocol() 是否正确包含分回合工具调用与独白约束规则，
    确保大模型在调工具回合不输出多余文本或独白标签。
    """
    protocol = get_cross_reference_protocol()
    
    # 验证核心分流关键字
    assert "Tool Calling Turn" in protocol
    assert "Final Dialogue Turn" in protocol
    assert "Emit ONLY the native tool call silently" in protocol
    
    # 验证 GPS 导航锚点 (Cross-reference)
    assert "(Cross-reference: <environment_constraints>)" in protocol
    assert "(Cross-reference: <response_format_rules>)" in protocol
    assert "(Cross-reference: <response_format_rules>, <dynamic_property_update_rules>)" in protocol

def test_build_base_system_prompt(mock_db_path):
    """
    验证 build_base_system_prompt 能正常构建系统提示词且不会报错，
    同时确保应用了 mock_db_path 隔离生产数据库。
    """
    prompt, kb_count, mem_count = build_base_system_prompt(
        last_user_msg="测试消息",
        persona_type="default"
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert kb_count >= 0
    assert mem_count >= 0

def test_build_base_system_prompt_with_selection(mock_db_path):
    """
    验证 build_base_system_prompt 在传入 IDE 光标选区及选中代码片段时，
    能准确构建 <ide_context> 区域提示词。
    """
    prompt, _, _ = build_base_system_prompt(
        last_user_msg="请解释这段代码",
        current_file_path="/path/to/app.js",
        cursor_line=15,
        selection_start_line=10,
        selection_end_line=20,
        selected_text="function hello() { return 'world'; }"
    )
    assert "<ide_context>" in prompt
    assert "- Highlighted Region: Lines 10 to 20" in prompt
    assert "function hello() { return 'world'; }" in prompt
