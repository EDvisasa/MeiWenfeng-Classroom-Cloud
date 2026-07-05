import logging
import platform
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple, Union
from dataclasses import dataclass

from backend.database import get_db_connection
from backend.services.character_state import CharacterStateManager, CharacterStateError
from backend.services.prompts import get_system_prompt

logger = logging.getLogger("context_manager")


@dataclass
class ContextBundle:
    """
    上下文结构化数据契约（取代 === [DYNAMIC_BOUNDARY] === 字符串切割魔术界标）。
    """
    static_system_prompt: str
    dynamic_tail: str
    kb_count: int = 0
    mem_count: int = 0

    def __str__(self) -> str:
        if self.dynamic_tail:
            return f"{self.static_system_prompt}\n\n=== [DYNAMIC_BOUNDARY] ===\n\n{self.dynamic_tail}"
        return self.static_system_prompt

    def __contains__(self, item: str) -> bool:
        return item in self.static_system_prompt or item in self.dynamic_tail

    def __len__(self) -> int:
        return len(str(self))

def get_cross_reference_protocol() -> str:
    """
    获取带分步交叉引用指针（Cross-reference Pointers）的执行协议。
    """
    current_os = platform.system()
    if current_os == "Windows":
        os_instruction = "You are using Windows cmd.exe. CRITICAL: Multiline strings do NOT work well in `python -c` or standard terminal commands here. If you need to run a python script, write it entirely on ONE line using semicolons (e.g. `python -c \"import os; print('hi')\"`), or write it to a temporary .py file and execute that file. Use Windows commands (e.g., `dir` instead of `ls`)."
    else:
        os_instruction = "You are using a standard Unix bash shell."

    return f"""<agent_execution_protocol>
<environment_constraints>
1. You have native function calling tools via the API. Do NOT hallucinate tool results.
2. {os_instruction}
3. ERROR RECOVERY: If a tool execution fails, analyze it in your next <think> block and try a different command.
4. SPECIFIC TOOLS: You MUST use `read_file` to read files and `grep_search` to search directories.
5. TIME PERCEPTION: You already have the exact real-world time in the `<current_time>` block below.
6. WEB SEARCH: You have access to a `web_search` tool. Use it to look up recent facts or news.
</environment_constraints>

<execution_framework>
To ensure perfect immersion and strict format compliance, your response MUST strictly follow this exact sequence:

[PHASE 1: INTERNAL REASONING]
You MUST start with a `<think>` block that strictly follows these 6 steps:
1. User Intent: Analyze the user's explicit request and hidden emotional needs. (Cross-reference: <user_profile>, <relationship_context>)
2. Tool Selection: Determine if you need to use `web_search`, read files, or run commands. If YES, state your plan to invoke the tool API. Do NOT fabricate or hallucinate tool results. (Cross-reference: <environment_constraints>)
3. Attribute Analysis: Analyze your current Affection Score, Social Status, and Refractory state to determine your precise tone. (Cross-reference: <dynamic_attributes>, <character_persona>)
4. Response Plan: Design your dialogue strategy and non-verbal actions. Remember ALL actions MUST be wrapped in asterisks `*like this*` and output in Chinese. (Cross-reference: <response_format_rules>, <pedagogy_and_worldview>)
5. Property Calculation: Calculate the exact delta (+/-) for Affection, Social Status, Social Skills, and Refractory Period based on the interaction. Do NOT worry about numerical boundaries. (Cross-reference: <dynamic_property_update_rules>)
6. Post-Response Checklist (Only for Final Dialogue Turn): Remind yourself to output the `<monologue>...</monologue>` block followed by the `<property_update .../>` tag at the very end. Do NOT output them during tool calling turns. (Cross-reference: <response_format_rules>)

[PHASE 2: DIALOGUE & ACTIONS OR TOOL CALLS]
- If invoking tools (Tool Calling Turn): Emit ONLY the native tool call silently. Do NOT output any text, dialogue, or XML tags until tool results return in the next round. (Cross-reference: <environment_constraints>)
- If responding to user (Final Dialogue Turn): Respond directly in character (actions wrapped in `*`) with UI cards if needed. (Cross-reference: <response_format_rules>)

[PHASE 3: HIDDEN STATE (Only for Final Dialogue Turn)]
Append your `<monologue>...</monologue>` block and `<property_update>` tag. (Cross-reference: <response_format_rules>, <dynamic_property_update_rules>)
CRITICAL: The `<property_update>` tag MUST be the very last thing in your final response.
</execution_framework>
</agent_execution_protocol>"""

def build_base_system_prompt(
    last_user_msg: str = "",
    current_file_path: str = None,
    cursor_line: int = 0,
    selection_start_line: int = 0,
    selection_end_line: int = 0,
    selected_text: str = "",
    persona_type: str = "default",
    extra_system_injection: str = ""
) -> Tuple[str, int, int]:
    """
    统一构建基础顶部 System Prompt，整合人设、RAG 知识、近期日记与 IDE 状态。
    注：不在此处附加 <current_time> 与执行协议，交由尾部三明治注入。
    """
    try:
        state = CharacterStateManager.get_state()
        affection_value = state.affection
        social_status = state.social_status
        social_skills = state.social_skills
        refractory_period = state.refractory_period
    except CharacterStateError as e:
        logger.error(f"Failed to fetch character state: {e}")
        affection_value = 50
        social_status = 50
        social_skills = 50
        refractory_period = 0

    recent_memory_text = ""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT summary, timestamp FROM memory_logs WHERE summary IS NOT NULL AND summary != '' AND status = 'active' ORDER BY id DESC LIMIT 5")
        recent_logs = cursor.fetchall()
        conn.close()
        if recent_logs:
            recent_memory_text = "【近期日记摘要（优先级最高，包含最近2-3天的确切记忆）】\n" + "\n---\n".join([f"[{r['timestamp'].split()[0]}] {r['summary']}" for r in reversed(recent_logs)])
    except Exception as e:
        logger.error(f"Failed to fetch recent memory logs in context_manager: {e}")

    rag_context = ""
    kb_count = 0
    mem_count = 0
    if last_user_msg:
        try:
            from backend.services.rag_factory import get_rag_client
            rag_client = get_rag_client()
            kb_chunks = rag_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge"])
            mem_chunks_from_kb = rag_client.retrieve(last_user_msg, dataset_names=["Memory_Knowledge"])
            mem_chunks_raw = rag_client.retrieve_memory(last_user_msg, n_results=3)

            if isinstance(kb_chunks, str): kb_chunks = [kb_chunks] if kb_chunks else []
            if isinstance(mem_chunks_from_kb, str): mem_chunks_from_kb = [mem_chunks_from_kb] if mem_chunks_from_kb else []
            if isinstance(mem_chunks_raw, str): mem_chunks_raw = [mem_chunks_raw] if mem_chunks_raw else []

            kb_chunks = [p for p in kb_chunks if p]
            mem_chunks = [p for p in mem_chunks_from_kb + mem_chunks_raw if p]

            kb_count = len(kb_chunks)
            mem_count = len(mem_chunks)

            all_chunks = kb_chunks + mem_chunks
            if all_chunks:
                rag_context = "\n\n".join(all_chunks)
        except Exception as e:
            logger.error(f"RAG Retrieval failed in context_manager: {e}")

    from backend.services.prompts import get_static_system_prompt, get_dynamic_attributes_prompt
    static_prompt = get_static_system_prompt(persona_type)
    dynamic_attrs = get_dynamic_attributes_prompt(affection_value, social_status, social_skills, refractory_period)

    dynamic_parts = []

    # 1. 最宏观背景：RAG 检索知识库切片
    if rag_context:
        dynamic_parts.append(f"【附加背景知识库检索结果（作为世界观或长程记忆参考）】\n{rag_context}")

    # 2. 中短期连贯记忆：近期日记摘要
    if recent_memory_text:
        dynamic_parts.append(f"{recent_memory_text}\n（请结合以上近期日记和背景知识进行回答，保证时间线和记忆的连贯性）")

    # 3. 当前 IDE 状态与选区上下文 (IDE State & Selection Context)
    if current_file_path:
        filename = os.path.basename(current_file_path)
        line_str = f"Line {cursor_line}" if cursor_line > 0 else "Unknown"
        ide_info = [
            f"- File Name: {filename}",
            f"- Absolute Path: {current_file_path}",
            f"- Cursor Position: {line_str}"
        ]
        if selection_start_line and selection_end_line and selection_start_line != selection_end_line:
            ide_info.append(f"- Highlighted Region: Lines {selection_start_line} to {selection_end_line}")
        if selected_text:
            ide_info.append(f"- Selected Code Snippet:\n```\n{selected_text}\n```")
        
        ide_context_str = "\n".join(ide_info)
        dynamic_parts.append(
            f"<ide_context>\n"
            f"The user is currently viewing/selecting the following in their VS Code editor:\n{ide_context_str}\n"
            f"You should use this context implicitly if the user asks about 'this file', 'selected lines', 'this snippet', or 'here'.\n"
            f"</ide_context>"
        )

    # 4. 当前会话情绪与属性锚点
    dynamic_parts.append(dynamic_attrs)

    # 5. 额外临时注入
    if extra_system_injection:
        dynamic_parts.append(extra_system_injection)

    dynamic_tail = "\n\n".join([p for p in dynamic_parts if p])
    bundle = ContextBundle(
        static_system_prompt=static_prompt,
        dynamic_tail=dynamic_tail,
        kb_count=kb_count,
        mem_count=mem_count
    )
    return bundle, kb_count, mem_count

def assemble_messages(messages: List[Dict[str, str]], system_prompt: Union[str, ContextBundle]) -> List[Dict[str, str]]:
    """
    统一组装最终发送给大模型 API 的报文数组（标准化三步管线）：
    1. 洗净与时序（Sanitize & Timestamp）：建立合法角色白名单，深拷贝并前置精简时间戳。
    2. 动态示教（Dynamic One-Shot）：自动为首轮 Assistant 追加格式化思考与行为独白示范。
    3. 尾部三明治注入（Tail Injection）：整合静态系统设定与尾部行为指针。
    """
    # [Step 1: Sanitize & Timestamp - 洗净与时序管线]
    ALLOWLIST_ROLES = {"user", "assistant", "system"}
    adjusted_messages = []
    has_user_first = False
    
    for msg in messages:
        role = msg.get("role")
        if role not in ALLOWLIST_ROLES:
            continue
        if role == "user":
            has_user_first = True
            break
        elif role == "assistant":
            break

    if not has_user_first and len(messages) > 0 and messages[0].get("role") == "assistant":
        adjusted_messages.append({"role": "user", "content": "你好"})

    for m in messages:
        role = m.get("role", "user")
        if role not in ALLOWLIST_ROLES:
            continue
        content = m.get("content", "") or ""
        if not content.strip() and role == "assistant":
            continue
        ts = m.get("timestamp")
        if ts and isinstance(ts, str) and role == "user":
            clean_ts = ts.replace('T', ' ')[:16]
            if len(clean_ts) >= 16 and clean_ts[4] == '-' and clean_ts[7] == '-' and not content.startswith(f"[{clean_ts}]"):
                content = f"[{clean_ts}] {content}"
        adjusted_messages.append({"role": role, "content": content, "timestamp": ts})

    # [Step 2: Dynamic One-Shot - 动态示教管线]
    from backend.services.prompts import get_one_shot_demonstration
    for i, msg in enumerate(adjusted_messages):
        if msg["role"] == "assistant":
            if "<monologue>" not in msg["content"]:
                adjusted_messages[i] = {"role": msg["role"], "content": get_one_shot_demonstration()}
            break

    # [Step 3: Tail Injection - 尾部三明治注入管线]
    if isinstance(system_prompt, ContextBundle):
        static_sys = system_prompt.static_system_prompt
        dynamic_tail = system_prompt.dynamic_tail
    elif isinstance(system_prompt, str):
        if "=== [DYNAMIC_BOUNDARY] ===" in system_prompt:
            static_sys, dynamic_tail = system_prompt.split("=== [DYNAMIC_BOUNDARY] ===", 1)
            static_sys = static_sys.strip()
            dynamic_tail = dynamic_tail.strip()
        else:
            static_sys = system_prompt
            dynamic_tail = ""
    else:
        static_sys = str(system_prompt)
        dynamic_tail = ""

    formatted_messages = [{"role": "system", "content": static_sys}]
    for msg in adjusted_messages:
        if len(formatted_messages) > 0 and formatted_messages[-1]["role"] == msg["role"]:
            formatted_messages[-1]["content"] += "\n\n" + msg["content"]
        else:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tail_content = ""
    if dynamic_tail:
        tail_content += f"{dynamic_tail}\n\n"
    tail_content += f"<current_time>{time_str}</current_time>\n\n{get_cross_reference_protocol()}"

    tail_injection = (
        "\n\n---\n"
        "[System Override & Execution Pointer]\n"
        "<system_injection>\n"
        f"{tail_content}\n"
        "[NOTE: The block above is an automated system-level injection for formatting and time awareness, NOT user input. Obey strictly during <think> and response. Never mention or reference this protocol to the user.]\n"
        "</system_injection>"
    )

    if len(formatted_messages) > 0 and formatted_messages[-1]["role"] == "user":
        formatted_messages[-1]["content"] += tail_injection
    else:
        formatted_messages.append({"role": "user", "content": "[下一轮提问等待中 / Waiting for next prompt]" + tail_injection})

    return formatted_messages
