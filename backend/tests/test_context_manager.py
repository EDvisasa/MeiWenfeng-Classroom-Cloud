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
    验证 build_base_system_prompt 能正常构建系统提示词并隔离生产库，
    并在传入 IDE 光标选区及选中代码片段时准确构建 <ide_context> 区域提示词。
    """
    from backend.services.context_manager import ContextBundle

    prompt, kb_count, mem_count = build_base_system_prompt(
        last_user_msg="请解释这段代码",
        persona_type="default",
        current_file_path="/path/to/app.js",
        cursor_line=15,
        selection_start_line=10,
        selection_end_line=20,
        selected_text="function hello() { return 'world'; }",
    )
    assert isinstance(prompt, (str, ContextBundle))
    assert len(prompt) > 0
    assert kb_count >= 0
    assert mem_count >= 0
    assert "<ide_context>" in prompt
    assert "- Highlighted Region: Lines 10 to 20" in prompt
    assert "function hello() { return 'world'; }" in prompt


def test_assemble_messages_injects_timestamp():
    """
    TDD [Bug #5 / Bug #9] 回归用例:
    验证 assemble_messages 仅针对 role == 'user' 前置精简时序标尺 [YYYY-MM-DD HH:MM]，
    绝不对 assistant 对白前置时间戳，保持 <think> 开头。
    """
    from backend.services.context_manager import assemble_messages
    messages = [
        {"role": "user", "content": "早上讨论的那个问题", "timestamp": "2026-07-05 08:30:00"},
        {"role": "assistant", "content": "<think>\n1. User Intent...\n</think>\n*轻笑* 好呀，什么问题？<monologue>哼~</monologue>", "timestamp": "2026-07-05 08:30:05"},
        {"role": "user", "content": "就是关于GPIO的", "timestamp": "2026-07-05 10:00:00"},
    ]
    assembled = assemble_messages(messages, "你是导师媚吻锋")

    user_msgs = [m["content"] for m in assembled if m["role"] == "user"]
    assistant_msgs = [m["content"] for m in assembled if m["role"] == "assistant"]

    assert "[2026-07-05 08:30] 早上讨论的那个问题" in user_msgs[0]
    assert "[2026-07-05 10:00] 就是关于GPIO的" in user_msgs[1]
    for amsg in assistant_msgs:
        assert not amsg.startswith("[2026-07-05"), f"Assistant message should not start with timestamp: {amsg}"
        assert amsg.startswith("<think>"), f"Assistant message must cleanly start with <think>: {amsg}"

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


def test_assemble_messages_o1_tail_injection_no_reverse_scanning_bug_12():
    """
    TDD [Bug #12 / ISSUE-11]:
    验证尾部夹层在末尾非 user（无论是 assistant 还是 system）时绝不倒序污染历史 user 提问，
    而是独立挂载到末尾 [下一轮提问等待中] 容器。
    """
    from backend.services.context_manager import assemble_messages

    assembled_asst_end = assemble_messages([
        {"role": "user", "content": "问题1"},
        {"role": "assistant", "content": "回答1"},
    ], "你是导师")
    user_1 = [m for m in assembled_asst_end if "问题1" in m["content"]][0]
    assert "<system_injection>" not in user_1["content"], "Historical user message should not contain system_injection when turn ended with assistant!"

    assembled_sys_end = assemble_messages([
        {"role": "user", "content": "前期历史提问"},
        {"role": "assistant", "content": "前期历史回答"},
        {"role": "system", "content": "动态环境参数变更与通知"},
    ], "你是导师")
    user_msg = [m for m in assembled_sys_end if "前期历史提问" in m["content"]][0]
    assert "<system_injection>" not in user_msg["content"], "Historical user message must NEVER be polluted by reverse scanning!"

    last_msg = assembled_sys_end[-1]
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


def test_assemble_messages_context_pipeline_transition_directive_issue_20():
    """
    TDD [ISSUE-19 / ISSUE-20]:
    Verify assemble_messages places tail_injection + transition directive BEFORE user instruction
    ending cleanly with </current_user_instruction>.
    """
    from backend.services.context_manager import assemble_messages
    user_prompt = "请回答关于白提子辈分的问题"
    messages = [{"role": "user", "content": user_prompt}]

    assembled = assemble_messages(messages, "你是导师")
    last_msg = assembled[-1]
    assert last_msg["role"] == "user"
    content = last_msg["content"]

    directive = (
        "[System Directive: Distinguish strictly between retrieved past memory archives (`<retrieved_past_memory_archives>`, `<recent_journal_summaries>`) and the real-time active conversation history. "
        "Generate your response ONLY for the current user instruction inside `<current_user_instruction>` below.]"
    )
    assert directive in content

    idx_injection = content.find("<system_injection>")
    idx_directive = content.find(directive)
    idx_prompt = content.find(user_prompt)
    idx_end_tag = content.find("</current_user_instruction>")

    assert -1 not in (idx_injection, idx_directive, idx_prompt, idx_end_tag)
    assert idx_injection < idx_directive < idx_prompt < idx_end_tag, (
        f"Order must be <system_injection> ({idx_injection}) -> directive ({idx_directive}) -> user_prompt ({idx_prompt}) -> </current_user_instruction> ({idx_end_tag})"
    )
    assert content.strip().endswith("</current_user_instruction>")

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


def test_atmosphere_mode_injection_issue_48():
    """
    TDD [ISSUE-48]:
    验证 assemble_messages 与 build_base_system_prompt 对生活与研学双氛围模式的动静解耦注入。
    """
    from backend.services.context_manager import build_base_system_prompt, assemble_messages, ContextBundle

    # 1. 验证 build_base_system_prompt 传参与 ContextBundle 属性赋值
    bundle_daily, _, _ = build_base_system_prompt(atmosphere_mode="daily")
    assert bundle_daily.atmosphere_mode == "daily"
    assert "[MODE: DAILY / 生活模式]" in bundle_daily.static_system_prompt
    assert "[MODE: STUDY / 研学模式]" in bundle_daily.static_system_prompt

    bundle_study, _, _ = build_base_system_prompt(atmosphere_mode="study")
    assert bundle_study.atmosphere_mode == "study"

    # 2. 验证 assemble_messages 尾部注入的生活模式标签
    messages = [{"role": "user", "content": "今天吃什么"}]
    assembled_daily = assemble_messages(messages, bundle_daily)
    last_content_daily = assembled_daily[-1]["content"]
    assert "<active_atmosphere_mode>DAILY (生活模式" in last_content_daily

    # 3. 验证 assemble_messages 尾部注入的研学模式标签
    assembled_study = assemble_messages(messages, bundle_study)
    last_content_study = assembled_study[-1]["content"]
    assert "<active_atmosphere_mode>STUDY (研学模式" in last_content_study


def test_kv_cache_minute_time_and_static_first_ordering():
    """
    验证 KV-Cache Prefix 防击穿机制：
    1. <current_time> 精确到分钟 (YYYY-MM-DD HH:MM)，避免重试时秒级变化破坏缓存；
    2. 静态协议 <agent_execution_protocol> 位于动态块 <openclaw_gateway_status> 与 <current_time> 之前；
    3. <current_time> 位于 <system_injection> 最末尾（紧邻免责保护框）。
    """
    import re
    from backend.services.context_manager import assemble_messages, ContextBundle

    bundle = ContextBundle(static_system_prompt="You are a mentor.", dynamic_tail="<dynamic_attributes>score=10</dynamic_attributes>")
    assembled = assemble_messages([{"role": "user", "content": "再讲一遍"}], bundle)
    last_content = assembled[-1]["content"]

    time_match = re.search(r"<current_time>(.*?)</current_time>", last_content)
    assert time_match is not None
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", time_match.group(1)), f"Expected YYYY-MM-DD HH:MM, got {time_match.group(1)}"

    idx_proto_start = last_content.find("<agent_execution_protocol>")
    idx_proto_end = last_content.find("</agent_execution_protocol>")
    idx_dyn = last_content.find("<dynamic_attributes>score=10", idx_proto_end)
    idx_gw = last_content.find("<openclaw_gateway_status>", idx_proto_end)
    idx_time = last_content.find(f"<current_time>{time_match.group(1)}</current_time>")
    idx_note = last_content.find("[NOTE:", idx_proto_end)
    assert -1 not in (idx_proto_start, idx_proto_end, idx_dyn, idx_gw, idx_time, idx_note)
    assert idx_proto_start < idx_proto_end < idx_dyn < idx_gw < idx_time < idx_note


def test_file_content_extracted_before_session_history_end():
    """
    验证 @file 展开的大文件内容 <file_content> 会被前置归档在 </current_session_history> 之前，
    只把轻量的 tail_injection 与纯提问留在末尾，防止突破 --kvmem-query-max-tokens (8192)。
    """
    from backend.services.context_manager import assemble_messages

    large_body = "x = 1\n" * 3000
    user_msg = f"请帮我检查代码逻辑 @big.py \n\n<file_content filename=\"big.py\">\n{large_body}\n</file_content>\n"
    assembled = assemble_messages([{"role": "user", "content": user_msg}], "你是导师")
    content = assembled[-1]["content"]

    idx_file = content.find('<file_content filename="big.py">')
    idx_history_end = content.find("</current_session_history>")
    idx_sys_inj = content.find("<system_injection>")
    idx_instr_start = content.find("<current_user_instruction>")

    assert -1 not in (idx_file, idx_history_end, idx_sys_inj, idx_instr_start)
    assert idx_file < idx_history_end < idx_sys_inj < idx_instr_start

    tail_after_instr = content[idx_instr_start:]
    assert "请帮我检查代码逻辑 @big.py" in tail_after_instr
    assert "<file_content" not in tail_after_instr
    assert large_body not in tail_after_instr
