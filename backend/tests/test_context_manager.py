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
    from backend.services.context_manager import ContextBundle
    assert isinstance(prompt, (str, ContextBundle))
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

def test_assemble_messages_injects_timestamp():
    """
    TDD [Bug #5] RED step:
    验证 assemble_messages 能够接收消息中的 timestamp 属性，
    并在每一轮对白的 content 前面自动注入精简的时序标尺 [YYYY-MM-DD HH:MM]。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "早上讨论的那个问题", "timestamp": "2026-07-05 08:30:00"},
        {"role": "assistant", "content": "好呀，什么问题？", "timestamp": "2026-07-05 08:30:05"},
        {"role": "user", "content": "就是关于GPIO的", "timestamp": "2026-07-05 10:00:00"}
    ]
    system_prompt = "你是导师媚吻锋"
    
    assembled = assemble_messages(messages, system_prompt)
    
    # 寻找所有的 user 和 assistant 消息
    user_msgs = [m["content"] for m in assembled if m["role"] == "user"]
    
    # 验证历史 user 消息中是否成功前置了精简时间戳 [2026-07-05 08:30]
    assert "[2026-07-05 08:30] 早上讨论的那个问题" in user_msgs[0]
    # 验证最后一条 user 消息也前置了精简时间戳 [2026-07-05 10:00]
    assert "[2026-07-05 10:00] 就是关于GPIO的" in user_msgs[1]


def test_assemble_messages_filters_system_info_bug_6():
    """
    TDD [Bug #6] RED step:
    验证 assemble_messages 在洗净边界（Sanitization Seam）建立合法 LLM 角色白名单 {"user", "assistant", "system"}，
    彻底拦截并过滤掉 role == 'system_info' 等 UI 提示卡片报文，防止对话记忆污染。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "system_info", "content": "🔍 成功检索并加载 3 条相关资料..."},
        {"role": "assistant", "content": "夫君，你来啦~"},
        {"role": "system_info", "content": "⚠️ 当前沙盒代码未保存"}
    ]
    system_prompt = "你是导师媚吻锋"
    assembled = assemble_messages(messages, system_prompt)
    
    roles = [m["role"] for m in assembled]
    assert "system_info" not in roles
    assert len([m for m in assembled if m["role"] == "system"]) == 1 # Index 0 static system
    assert len([m for m in assembled if m["role"] == "user" and "[下一轮提问等待中" not in m["content"]]) == 1
    assert len([m for m in assembled if m["role"] == "assistant"]) == 1


def test_context_bundle_contract_and_three_step_pipeline(mock_db_path):
    """
    TDD [ISSUE-10] RED step:
    验证 build_base_system_prompt 返回结构化的 ContextBundle 对象，
    并且 assemble_messages 能够接收 ContextBundle 完成标准化三步组装管线（不再使用魔法字符串切割）。
    """
    from backend.services.context_manager import build_base_system_prompt, assemble_messages, ContextBundle
    
    bundle, kb_count, mem_count = build_base_system_prompt(last_user_msg="测试消息", persona_type="default")
    assert isinstance(bundle, ContextBundle)
    assert hasattr(bundle, "static_system_prompt")
    assert hasattr(bundle, "dynamic_tail")
    
    messages = [{"role": "user", "content": "测试问候"}]
    assembled = assemble_messages(messages, bundle)
    assert len(assembled) >= 2
    assert assembled[0]["role"] == "system"
    assert assembled[0]["content"] == bundle.static_system_prompt
    assert "<system_injection>" in assembled[-1]["content"]


def test_assemble_messages_ignores_empty_assistant_placeholder_bug_7():
    """
    TDD [Bug #7] 回归用例:
    验证 assemble_messages 能够自动忽略并过滤内容为空或纯空白的 assistant 消息（如前端等待流式返回时的占位符），
    防止对空内容错误拼接时间戳前缀（变成 [2026-07-05 04:18] ），造成末尾残留无效空消息报文。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "臭宝！来找你啦", "timestamp": "2026-07-05T04:18:00Z"},
        {"role": "assistant", "content": "", "timestamp": "2026-07-05T04:18:02Z"},
        {"role": "assistant", "content": "   ", "timestamp": "2026-07-05T04:18:03Z"}
    ]
    assembled = assemble_messages(messages, "你是导师")
    assistant_msgs = [m for m in assembled if m["role"] == "assistant"]
    assert len(assistant_msgs) == 0, f"Expected 0 assistant messages, got {len(assistant_msgs)}: {assistant_msgs}"


def test_assemble_messages_only_injects_timestamp_to_user_messages_bug_9():
    """
    TDD [Bug #9] RED step:
    验证 assemble_messages 只针对 role == 'user' 的消息前置精简时间戳 [YYYY-MM-DD HH:MM]，
    对于 role == 'assistant' 的对白绝不能前置时间戳，保证其内容能够干净地以 <think> 开头，
    避免 AI 在上下文学习中误认为 assistant 回复也需要输出时间戳，并修复不同回合 assistant 消息格式不一致问题。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "早上讨论的那个问题", "timestamp": "2026-07-05 08:30:00"},
        {"role": "assistant", "content": "<think>\n1. User Intent...\n</think>\n*轻笑* 好呀，什么问题？<monologue>哼~</monologue>", "timestamp": "2026-07-05 08:30:05"},
        {"role": "user", "content": "就是关于GPIO的", "timestamp": "2026-07-05 10:00:00"}
    ]
    assembled = assemble_messages(messages, "你是导师")
    
    user_msgs = [m["content"] for m in assembled if m["role"] == "user"]
    assistant_msgs = [m["content"] for m in assembled if m["role"] == "assistant"]
    
    # 验证 user 消息带时间戳
    assert "[2026-07-05 08:30] 早上讨论的那个问题" in user_msgs[0]
    assert "[2026-07-05 10:00] 就是关于GPIO的" in user_msgs[1]
    
    # 验证 assistant 消息决不能带时间戳前缀，必须纯净地以 <think> 开头
    for amsg in assistant_msgs:
        assert not amsg.startswith("[2026-07-05"), f"Assistant message should not start with timestamp: {amsg}"
        assert amsg.startswith("<think>"), f"Assistant message must cleanly start with <think>: {amsg}"


def test_assemble_messages_prevents_visual_tearing_on_assistant_end_bug_12():
    """
    TDD [Bug #12] RED step:
    当传入的消息列表以 role == 'assistant' 结尾时（即回合完结后的预览状态），
    assemble_messages 绝不能盲目倒序将尾部夹层强塞入上一轮历史 user 消息中，
    必须保持历史 user 与 assistant 对白紧密相连无割裂，
    而将尾部夹层独立放置在末尾的待机容器或仅挂载于最新一轮有效提问上。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "问题1"},
        {"role": "assistant", "content": "回答1"}
    ]
    assembled = assemble_messages(messages, "你是导师")
    
    # 历史 user 消息不应当被插入 <system_injection> 夹层
    user_1 = [m for m in assembled if "问题1" in m["content"]][0]
    assert "<system_injection>" not in user_1["content"], "Historical user message should not contain system_injection when turn ended with assistant!"


def test_assemble_messages_o1_tail_injection_no_reverse_scanning_bug_12():
    """
    TDD [Bug #12 / ISSUE-11] RED step:
    验证 O(1) 尾部夹层重构要求：彻底废除对历史 user 消息的倒序扫描。
    如果物理消息列表最后一项不是 user（例如末尾为合法的 system 通知或待机状态），
    绝不能向后反向扫描去污染前期的 user 提问。
    只有当末尾最后一项恰好是 user 时追加于最末尾；否则必须独立生成干净的 [下一轮提问等待中] user 容器。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "前期历史提问"},
        {"role": "assistant", "content": "前期历史回答"},
        {"role": "system", "content": "动态环境参数变更与通知"}
    ]
    assembled = assemble_messages(messages, "你是导师")
    
    # 验证前期历史 user 提问绝对没有被倒序扫描污染
    user_msg = [m for m in assembled if "前期历史提问" in m["content"]][0]
    assert "<system_injection>" not in user_msg["content"], "Historical user message must NEVER be polluted by reverse scanning!"
    
    # 验证因为最末项 role != user，系统必须在最末尾 append 一个新的待机容器承载 <system_injection>
    last_msg = assembled[-1]
    assert last_msg["role"] == "user", "When last physical message is not user, should append a user container for injection"
    assert "[下一轮提问等待中 / Waiting for next prompt]" in last_msg["content"], "Should contain waiting prompt container"
    assert "<system_injection>" in last_msg["content"], "New container should carry system_injection"


def test_assemble_messages_injects_openclaw_gateway_status():
    """
    TDD [ISSUE-17]:
    Verify assemble_messages injects canonical <openclaw_gateway_status> tag
    into dynamic tail injection per docs/GLOSSARY.md ubiquitous language.
    """
    from unittest.mock import patch
    from backend.services.context_manager import assemble_messages
    messages = [{"role": "user", "content": "帮我叫白提子"}]

    with patch("backend.services.openclaw_client.check_openclaw_status", return_value={"online": True, "status_str": "ONLINE (WSL OpenClaw Gateway ready)"}):
        assembled = assemble_messages(messages, "系统提示")
        last_content = assembled[-1]["content"]
        assert "<openclaw_gateway_status>" in last_content
        assert "</openclaw_gateway_status>" in last_content
        assert "ONLINE (WSL OpenClaw Gateway ready)" in last_content
