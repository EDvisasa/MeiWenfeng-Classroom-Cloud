import pytest
from backend.services.context_manager import get_cross_reference_protocol, build_base_system_prompt

def test_get_cross_reference_protocol_structure():
    """
    验证 get_cross_reference_protocol() 是否正确包含分回合工具调用与独白约束规则，
    确保大模型在调工具回合不输出多余文本或独白标签。
    """
    protocol = get_cross_reference_protocol()
    
    # 验证核心分流关键字与防 XML 标签幻觉规则
    assert "Tool Calling Turn" in protocol
    assert "Final Dialogue Turn" in protocol
    assert "Emit ONLY the native tool call silently" in protocol
    assert "pseudo-XML tags (`<call_openclaw_agent>...`)" in protocol
    
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
    assert bundle.static_system_prompt in assembled[0]["content"]
    assert "<current_session_history>" in assembled[0]["content"]
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


def test_assemble_messages_tail_injection_inversion_issue_19():
    """
    TDD [ISSUE-19]:
    Verify that in assemble_messages, when injecting dynamic tail data into the last user message,
    the tail_injection comes BEFORE the original user instruction so that the user's latest
    instruction sits at the physical end of the message (maximizing recency attention).
    """
    from backend.services.context_manager import assemble_messages
    user_prompt = "请执行方案B修复小模型注意力注意力衰减的问题"
    messages = [{"role": "user", "content": user_prompt}]

    assembled = assemble_messages(messages, "你是导师")
    last_msg = assembled[-1]
    assert last_msg["role"] == "user"
    content = last_msg["content"]

    # Verify both parts exist
    assert "<system_injection>" in content
    assert user_prompt in content

    # Verify ordering: <system_injection> must appear BEFORE user_prompt
    idx_injection = content.find("<system_injection>")
    idx_user_prompt = content.find(user_prompt)
    assert idx_injection < idx_user_prompt, (
        f"tail_injection (idx={idx_injection}) must precede user instruction (idx={idx_user_prompt})"
    )
    assert content.strip().endswith("</current_user_instruction>")
    assert user_prompt in content


def test_assemble_messages_context_pipeline_transition_directive_issue_20():
    """
    TDD [ISSUE-20]:
    Verify that assemble_messages injects canonical transition directive between dynamic tail
    injection and user's prompt per docs/GLOSSARY.md ubiquitous language.
    """
    from backend.services.context_manager import assemble_messages
    user_prompt = "请回答关于白提子辈分的问题"
    messages = [{"role": "user", "content": user_prompt}]

    assembled = assemble_messages(messages, "你是导师")
    last_msg = assembled[-1]
    content = last_msg["content"]

    directive = (
        "[System Directive: Distinguish strictly between retrieved past memory archives (`<retrieved_past_memory_archives>`, `<recent_journal_summaries>`) and the real-time active conversation history. "
        "Generate your response ONLY for the current user instruction inside `<current_user_instruction>` below.]"
    )
    assert directive in content

    # Verify exact ordering: <system_injection> -> directive -> user_prompt -> </current_user_instruction>
    idx_injection = content.find("<system_injection>")
    idx_directive = content.find(directive)
    idx_prompt = content.find(user_prompt)
    idx_end_tag = content.find("</current_user_instruction>")

    assert idx_injection < idx_directive < idx_prompt < idx_end_tag, (
        f"Order must be <system_injection> ({idx_injection}) -> directive ({idx_directive}) -> user_prompt ({idx_prompt}) -> </current_user_instruction> ({idx_end_tag})"
    )


def test_assemble_messages_dynamic_one_shot_preserves_actual_greeting():
    """
    验证 assemble_messages 在执行 Dynamic One-Shot 示教装配时：
    1. 不再使用写死固定的对白覆盖历史开场白；
    2. 忠实将真实的动态开场白 (actual_content) 保留在 One-Shot 对白主体位置；
    3. 规范包裹 <think>、<monologue> 与 <property_update>，同时维持大模型角色轮换规范。
    """
    from backend.services.context_manager import assemble_messages
    dynamic_greeting = "*夜深人静，她披着月白软纱斗篷，在书案前核验账目，见你进来，嫣然一笑：*“夫君，今日怎么这般晚才来？”"
    messages = [
        {"role": "assistant", "content": dynamic_greeting, "timestamp": "2026-09-09T00:20:00Z"},
        {"role": "user", "content": "今天手头有些工作耽搁了。", "timestamp": "2026-09-09T00:25:00Z"}
    ]
    assembled = assemble_messages(messages, "你是导师")
    
    # 验证不再插入虚假的 [USER] 你好，system 之后直接是 One-Shot Assistant 节点
    assert assembled[0]["role"] == "system"
    assert "<current_session_history>" in assembled[0]["content"]
    
    # 验证 One-Shot Assistant 节点 (index 1)
    asst_msg = assembled[1]
    assert asst_msg["role"] == "assistant"
    content = asst_msg["content"]
    
    # 验证保留了动态开场白本体，而非旧版写死的素净茜红长衫
    assert dynamic_greeting in content
    assert "*端坐在案头，身着素净茜红长衫" not in content
    
    # 验证标准示教包裹结构完整
    assert content.startswith("<think>")
    assert "</think>" in content
    assert "<monologue>" in content
    assert "</monologue>" in content
    assert "<property_update" in content

    # 验证最后一条 user 消息闭合会话历史（以分割线与闭合标签起始）
    assert assembled[2]["role"] == "user"
    assert assembled[2]["content"].strip().startswith("---\n</current_session_history>")


def test_assemble_messages_wraps_current_session_history():
    """
    验证 assemble_messages 在处理多轮对话时：
    1. System 消息末尾放置 <current_session_history> 标签与场域声明；
    2. 中间历史对话保持纯净，无多余标签污染；
    3. 最后一轮消息开头使用 --- 与 </current_session_history> 封闭历史对白，并保留 <current_user_instruction> 与层级指引。
    """
    from backend.services.context_manager import assemble_messages

    multi_turn_messages = [
        {"role": "user", "content": "师姐，推挽输出是什么原理？", "timestamp": "2026-10-15T20:00:00"},
        {"role": "assistant", "content": "<monologue>冤家想学单片机</monologue>*轻笑* 推挽就是一个推高一个拉低。", "timestamp": "2026-10-15T20:01:00"},
        {"role": "user", "content": "那开漏输出呢？", "timestamp": "2026-10-15T20:05:00"},
        {"role": "assistant", "content": "<monologue>开漏要讲上拉电阻</monologue>*轻触你的眉心* 开漏只能拉低。", "timestamp": "2026-10-15T20:06:00"},
        {"role": "user", "content": "上拉电阻选多大？", "timestamp": "2026-10-15T20:10:00"}
    ]

    assembled = assemble_messages(multi_turn_messages, "你是导师媚吻锋")

    # 1. 结构验证：System 消息末尾包含起始标签与醒目提示词
    sys_msg = assembled[0]
    assert sys_msg["role"] == "system"
    assert "<current_session_history>" in sys_msg["content"]
    assert "当前窗口实时会话历史开始" in sys_msg["content"]

    # 2. 中间历史对话保持纯净，无多余标签污染
    first_history_msg = assembled[1]
    assert first_history_msg["role"] == "user"
    assert "师姐，推挽输出是什么原理？" in first_history_msg["content"]
    assert "<current_session_history>" not in first_history_msg["content"]

    last_history_asst_msg = assembled[-2]
    assert last_history_asst_msg["role"] == "assistant"
    assert "</current_session_history>" not in last_history_asst_msg["content"]

    # 3. 最后一轮用户消息 (index -1) 前置闭合标签，并保留即时指令与防混淆指引
    current_prompt_msg = assembled[-1]
    assert current_prompt_msg["role"] == "user"
    assert current_prompt_msg["content"].strip().startswith("---\n</current_session_history>")
    assert "当前窗口实时会话历史结束" in current_prompt_msg["content"]
    assert "<current_user_instruction>" in current_prompt_msg["content"]
    assert "上拉电阻选多大？" in current_prompt_msg["content"]
    assert "<current_session_history>" in current_prompt_msg["content"]
    assert "Distinguish strictly between retrieved past memory archives" in current_prompt_msg["content"]


def test_assemble_messages_strips_subsequent_historical_think_issue_36():
    """
    TDD [ISSUE-36] RED step:
    验证 assemble_messages 在发包组装多轮历史时：
    1. 首轮 Dynamic One-Shot 示教报文中的标准六步 <think> 模板完整保留（确保小模型习得规范输出契约）；
    2. 首轮之后由大模型正式生成的后续所有历史 assistant 消息中的真实 <think>...</think> 思维链必须被动态剥离，
       避免大段推演过程（如八字排盘、长篇 CoT）进入 <current_session_history> 导致 Tiel 等 35B-A3B MoE 小模型思维严重劣化；
    3. 剥离过程不破坏台词、动作、<monologue> 与 <property_update>；
    4. 原始输入 messages 保持绝对零副作用（深拷贝保护，数据库与前端 UI 数据不受任何影响）。
    """
    from backend.services.context_manager import assemble_messages

    greeting_content = "*侧坐在红木椅上托腮凝望窗外晚霞* 夫君忙碌了一整天，回了屋里便只有咱们俩。"
    bazi_think = (
        "<think>\n"
        "Let me analyze the current user instruction. The user is sharing his day: researched the bazi of a female netizen.\n"
        "Female: 庚辰 庚辰 丙午 丁酉\n"
        "Male (user): 庚辰 壬午 庚子 庚辰\n"
        "Let me compute the bazi for both...\n"
        "</think>\n"
        "*轻蹙娥眉，指尖掐算* 夫君，这八字辰午暗冲，确叫人心神微滞。"
        "<monologue>这冤家怎么研究起旁人八字来了</monologue>"
        '<property_update affection_delta="0" social_status_delta="0" social_skills_delta="0" />'
    )
    love_think = (
        "<think>\n"
        "User Intent: User wants to talk about love. Delta = 1.\n"
        "Response Plan: Mei Wenfeng smiles tenderly.\n"
        "</think>\n"
        "*掩唇轻笑，眸中漾着春意* 奴家一直在呢，夫君想怎么谈？"
        "<monologue>贫嘴的冤家~</monologue>"
        '<property_update affection_delta="1" social_status_delta="0" social_skills_delta="0" />'
    )

    multi_turn_messages = [
        {"role": "assistant", "content": greeting_content},
        {"role": "user", "content": "老婆，我今天去了西安城墙，还排了一个八字：庚辰 庚辰 丙午 丁酉。"},
        {"role": "assistant", "content": bazi_think},
        {"role": "user", "content": "老婆，在不？出来谈恋爱"},
        {"role": "assistant", "content": love_think},
        {"role": "user", "content": "今晚想吃什么呀？"}
    ]

    assembled = assemble_messages(multi_turn_messages, "你是导师媚吻锋")

    asst_messages = [m for m in assembled if m["role"] == "assistant"]
    assert len(asst_messages) == 3, f"Expected 3 assistant messages, got {len(asst_messages)}"

    # 1. 第 1 轮示教 Assistant 节点：必须完整保留 <think> 示教规范
    one_shot_asst = asst_messages[0]["content"]
    assert "<think>" in one_shot_asst, "First assistant message must retain the One-Shot demonstration <think>!"
    assert "1. User Intent:" in one_shot_asst, "First assistant message must retain the 6-step prompt format!"
    assert "</think>" in one_shot_asst
    assert greeting_content in one_shot_asst
    assert "<monologue>" in one_shot_asst
    assert "<property_update" in one_shot_asst

    # 2. 第 2 轮真实历史 Assistant 节点：必须剥离 <think>，但保留台词与标签
    second_asst = asst_messages[1]["content"]
    assert "<think>" not in second_asst, "Second assistant message must STRIP <think>!"
    assert "</think>" not in second_asst
    assert "Let me analyze the current user instruction" not in second_asst
    assert "Female: 庚辰 庚辰 丙午 丁酉" not in second_asst
    assert "*轻蹙娥眉，指尖掐算*" in second_asst
    assert "<monologue>这冤家怎么研究起旁人八字来了</monologue>" in second_asst
    assert '<property_update affection_delta="0"' in second_asst

    # 3. 第 3 轮真实历史 Assistant 节点：必须剥离 <think>
    third_asst = asst_messages[2]["content"]
    assert "<think>" not in third_asst, "Third assistant message must STRIP <think>!"
    assert "</think>" not in third_asst
    assert "User Intent: User wants to talk about love" not in third_asst
    assert "*掩唇轻笑，眸中漾着春意*" in third_asst
    assert "<monologue>贫嘴的冤家~</monologue>" in third_asst
    assert '<property_update affection_delta="1"' in third_asst

    # 4. 原始入参深拷贝防护验证（零外部副作用 / Zero DB Pollution）
    assert "<think>" in multi_turn_messages[2]["content"], "Original messages must not be mutated!"
    assert "<think>" in multi_turn_messages[4]["content"], "Original messages must not be mutated!"
