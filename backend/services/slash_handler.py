import os
import re
import json
import logging
from typing import Dict, Any, List
from fastapi.responses import StreamingResponse
from openai import OpenAI

from backend.database import get_db_connection
from backend.services.model_router import stream_chat, get_active_model
from backend.services.prompts import get_system_prompt, SUMMARIZATION_SYSTEM_PROMPT
from backend.services.rag_factory import get_rag_client
from backend.services.memory_decay import process_memory_decay
from backend.services.response_pipeline import ResponsePipeline, json_escape
from backend.services.character_state import CharacterStateManager, CharacterStateError
from backend.services.action_registry import action_registry
import backend.services.side_effects  # Ensure handlers are registered

logger = logging.getLogger(__name__)

def handle_slash_command(command: str, payload: Any, last_user_msg: str, cleaned_messages: List[Dict[str, str]]) -> StreamingResponse:
    """
    统一处理各种以斜杠开头的纯前端指令。
    """
    clean_cmd = command.strip().lower()

    current_file_path = getattr(payload, 'current_file_path', None)
    persona_type = getattr(payload, 'persona_type', 'simplified')

    # === 1. /update_persona ===
    if clean_cmd in ("/update_persona", "update_persona"):
        return _handle_update_persona()

    # === 2. /summarize ===
    if clean_cmd == "/summarize":
        return _handle_summarize()

    # === 3. /prepare ===
    if clean_cmd == "/prepare":
        return _handle_prepare_lesson(current_file_path)

    # === 4. /reward ===
    if clean_cmd == "/reward":
        return _handle_reward()

    # === 5. /set_mission ===
    if clean_cmd.startswith("/set_mission"):
        return _handle_set_mission(clean_cmd, payload, last_user_msg, cleaned_messages)

    # === 6. /cancel_mission ===
    if clean_cmd == "/cancel_mission":
        from backend.services.mission_manager import MissionManager
        MissionManager.cancel_draft()
        system_injection = """<system_directive>
Event: The user just triggered the `/cancel_mission` command, aborting the mission setup.
Action Required:
1. Acknowledge that the mission setup has been cancelled.
2. Keep the mentor persona. Be playful, slightly disappointed, or understanding.
3. Invite the user to continue normal chat or start over when ready.
</system_directive>"""
        return _stream_normal_chat_with_injection(last_user_msg, cleaned_messages, persona_type, system_injection)

    # 从数据库获取用户的宏大目标 (Mission)
    from backend.services.mission_manager import MissionManager
    user_mission = MissionManager.get_user_mission()

    # 以下指令均需要由大模型接管输出，因此使用“系统提示词注入”并拉起常规对话流
    system_injection = ""
    from backend.services.course_manager import get_active_course, get_formatted_syllabus

    active_course = get_active_course()
    topic_name = active_course["topic"] if active_course else "自由探索（当前无待办课题，请用 /计划 生成）"

    file_context = ""
    if current_file_path:
        file_context = f"<active_document>The user is currently reviewing the document: {os.path.basename(current_file_path)}</active_document>"

    if clean_cmd == "/lesson":
        system_injection = f"""<system_directive>
Event: The user just triggered the `/lesson` command.
User's Ultimate Mission: {user_mission}
Current Topic: {topic_name}
{file_context}

Action Required: Immediately enter your mentor persona. Proactively start today's lesson focused on the Current Topic.
Output Format: 
1. The theory explanation part MUST be extremely easy to understand (Reference 极简). Use living analogies, short paragraphs, and simple language.
2. ALWAYS conclude your lesson segment with a single interactive question to check the user's understanding, using the exact XML format below.
CRITICAL RULES FOR THE QUIZ (Quiz 刁钻):
- The quiz MUST be tricky and test deep understanding, not just surface facts.
- ALL options MUST be exactly the same length in words/characters. You must artificially pad or truncate them so they look identical in length. Do NOT let the longest option be the correct answer!
- Do not give away the correct answer through formatting.
<quiz type="multiple_choice">
{{
  "question": "Your tricky question here?",
  "options": ["Option A (same length)", "Option B (same length)", "Option C (same length)"],
  "correct_index": 1,
  "explanation": "Explanation for the correct answer."
}}
</quiz>
</system_directive>"""
    elif clean_cmd == "/lesson_continue":
        system_injection = f"""<system_directive>
Event: The user just submitted an answer to your previous quiz.
User's Ultimate Mission: {user_mission}
Current Topic: {topic_name}
{file_context}

Action Required: 
1. Evaluate their answer based on the `<submit_quiz_result>` tag.
2. Provide a detailed explanation, correcting any misconceptions.
3. Keep the mentor persona. Be encouraging or playfully strict depending on whether they got it right.
4. Continue the lesson on the Current Topic.

Output Format:
1. If you want to throw another pop quiz to check their understanding of the *new* explanation, use the `<quiz type="multiple_choice">` tag again.
</system_directive>"""
    elif clean_cmd == "/submit":
        system_injection = f"""<system_directive mode="socratic_strict_mentor">
Event: The user triggered the `/submit` command, indicating they are ready for assessment.
Current Assessment Topic: {topic_name}
User's Ultimate Mission: {user_mission}
{file_context}

<critical_rules>
1. NEVER GIVE DIRECT ANSWERS.
2. Ask questions that are just slightly beyond the user's current understanding (Zone of Proximal Development).
3. Identify ambiguous areas in the user's logic and pursue them with follow-up questions.
4. PASS CONDITION (EVOLVING SANDBOX): 
   - If the user perfectly masters the current topic/code challenge, do NOT just say "pass".
   - First, praise them and explicitly ask: "干得漂亮！你准备好迎接下一阶挑战了吗？" (Or something similar in your persona's tone).
   - ONLY AFTER the user explicitly replies "yes/ready" in their next message, you MUST use the `<call_tool name="replace_file_content">` tool (to modify existing files) or `<call_tool name="create_file">` tool (to create new files) to surgically evolve their current sandbox code (typically in `docs/sandbox/`) to introduce a new bug or increase the difficulty (Desirable Difficulty / Interleaving).
   - Provide a brief "学情洞察" (Learning Insight) summarizing their newly acquired ZPD edge so the background memory script can log it.
5. INTERACTIVE QUIZ: You may occasionally use the `<quiz type="multiple_choice">` tag to throw a pop quiz at the user. The frontend will render it as a UI component. The JSON inside must have "question", "options" (array), "correct_index" (int), and "explanation".
</critical_rules>
</system_directive>"""
    elif clean_cmd == "/plan":
        syllabus_text = get_formatted_syllabus()
        system_injection = f"""<system_directive>
Event: The user triggered the `/plan` command.
User's Ultimate Mission: {user_mission}

<current_syllabus_progress>
{syllabus_text}
</current_syllabus_progress>

Action Required: As a mentor, review their recent progress and outline their upcoming cultivation plan.
Output Format: If you need to append new topics to the syllabus, embed the following tag in your response: `<new_course phase="Phase Name" topic="Topic Name" />`. The system will automatically add it to the pending progress.
</system_directive>"""

    return _stream_normal_chat_with_injection(last_user_msg, cleaned_messages, persona_type, system_injection)

def _stream_normal_chat_with_injection(last_user_msg: str, cleaned_messages: List[Dict[str, str]], persona_type: str, system_injection: str) -> StreamingResponse:
    """
    在原本的大模型对话流基础上，追加特定的 System Prompt 注入，让大模型根据指令自动执行动作。
    采用解耦的 ResponsePipeline。
    """
    try:
        state = CharacterStateManager.get_state()
        affection_value = state.affection
        social_status = state.social_status
        social_skills = state.social_skills
        refractory_period = state.refractory_period
    except CharacterStateError as e:
        logger.error(f"Failed to fetch character state in slash handler: {e}")
        affection_value = 50
        social_status = 50
        social_skills = 50
        refractory_period = 0

    rag_context = ""
    if last_user_msg:
        try:
            rag_client = get_rag_client()
            kb_context = rag_client.retrieve(last_user_msg, dataset_names=["Classroom_Knowledge", "Memory_Knowledge"])
            mem_context = rag_client.retrieve_memory(last_user_msg, n_results=3)
            # 兼容返回字符串或列表
            parts = []
            if kb_context:
                parts.extend(kb_context if isinstance(kb_context, list) else [kb_context])
            if mem_context:
                 parts.extend(mem_context if isinstance(mem_context, list) else [mem_context])
            if parts:
                rag_context = "\n\n".join(parts)
        except Exception as e:
            logger.error(f"RAG Retrieval failed: {e}")

    system_prompt = get_system_prompt(affection_value, persona_type, social_status, social_skills, refractory_period)
    if rag_context:
        system_prompt += f"\n\n<retrieved_background_knowledge>\n{rag_context}\n</retrieved_background_knowledge>\n<instruction>Integrate this background knowledge naturally into your response if relevant. If irrelevant, ignore it.</instruction>"

    if system_injection:
        system_prompt += f"\n\n{system_injection}\n"


    def on_stream_end(clean_text: str):
        if not last_user_msg or not clean_text:
            return
        try:
            from datetime import datetime
            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            memory_content = f"【对话记录 ({time_str})】\n用户：{last_user_msg}\n媚吻锋：{clean_text}"
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')",
                (memory_content,)
            )
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
            active_level0_count = cursor.fetchone()[0]
            if active_level0_count >= 10:
                import threading
                from backend.services.memory_decay import process_memory_decay
                threading.Thread(target=process_memory_decay, daemon=True).start()
            conn.close()

            rag_client = get_rag_client()
            rag_client.save_memory(last_user_msg, clean_text, level=0)
        except Exception as e:
            logger.error(f"Failed to save memory in callback: {e}")

    # 初始化管道
    pipeline = ResponsePipeline(on_stream_end=on_stream_end, registry=action_registry)

    def event_generator():
        try:
            if system_injection and 'mode="interrogation"' in system_injection:
                warning_json = json.dumps({"type": "draft_warning", "text": "进入设立学习目标模式，若想放弃输入/cancel_mission解除状态"}, ensure_ascii=False)
                yield f"data: {warning_json}\n\n"
            if system_injection and '/cancel_mission' in system_injection:
                hint_json = json.dumps({"type": "system_hint", "icon": "check", "text": "设立目标模式已退出，恢复正常对话"}, ensure_ascii=False)
                yield f"data: {hint_json}\n\n"
                
            content_stream = stream_chat(cleaned_messages, system_prompt)
            yield from pipeline.process_stream(content_stream)
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 下面保留原有的其他命令处理函数（_handle_reward, _handle_summarize 等）...
def _handle_reward() -> StreamingResponse:
    def raw_generator():
        try:
            state = CharacterStateManager.modify_state(affection_delta=10)
            yield f"[系统提示] 媚吻锋感到十分欢喜，对你的好感度增加了！当前好感度：{state.affection}\n\n"
            yield "*眼波流转，娇媚地白了你一眼，但嘴角的笑意却怎么也藏不住：*“夫君这是开窍了？就知道拿这些来哄奴家开心~”"
        except CharacterStateError as e:
            yield f"[系统提示] 奖励发送失败: {e}"

    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")

def _handle_summarize() -> StreamingResponse:
    def raw_generator():
        yield {"type": "summarize_progress", "state": "loading"}
        import threading
        import time
        result_container = {}
        def target():
            try:
                from backend.services.memory_decay import process_memory_decay
                stats = process_memory_decay()
                result_container["stats"] = stats
            except Exception as e:
                result_container["error"] = str(e)

        t = threading.Thread(target=target)
        t.start()

        # Yield keep-alive messages to prevent frontend timeout and Errno 22 on Windows
        while t.is_alive():
            time.sleep(2)
            yield {"type": "summarize_progress", "state": "loading"}

        t.join()
        if "error" in result_container:
            yield {"type": "summarize_progress", "state": "error", "error": result_container["error"]}
        else:
            stats = result_container.get("stats", {})
            yield {"type": "summarize_progress", "state": "done", "stats": stats}

    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")

def _handle_prepare_lesson(file_path: str) -> StreamingResponse:
    def raw_generator():
        if not file_path:
            yield "[系统提示] 备课失败：未能在上下文中获取到选中的讲义文件路径。"
            return
        filename = os.path.basename(file_path)
        yield f"[知识库联动] 正在同步本地文件《{filename}》到当前知识库后端，请稍候...\n\n"
        try:
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                 yield "[知识库联动] 错误：无效的文件路径。"
                 return
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            rag_client = get_rag_client()
            result = rag_client.sync_knowledge({filename: content}, dataset_name="Classroom_Knowledge")
            if result["status"] == "error":
                error_msg = result.get("message")
                yield f"[知识库联动] 同步出错: {error_msg}"
            else:
                yield "[知识库联动] 同步成功！媚吻锋已熟读这份讲义资料。"
        except Exception as e:
            yield f"[知识库联动] 发生异常: {e}"
            
    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator()), media_type="text/event-stream")


def _handle_set_mission(clean_cmd: str, payload: Any, last_user_msg: str, cleaned_messages: List[Dict[str, str]]) -> StreamingResponse:
    mission_text = clean_cmd.replace("/set_mission", "").strip()
    
    # 1. Start the draft
    try:
        from backend.services.mission_manager import MissionManager
        draft = MissionManager.start_draft(mission_text)
    except Exception as e:
        def raw_generator():
            yield f"[系统报错] 目标设定初始化失败: {e}"
        return StreamingResponse(ResponsePipeline().process_stream(raw_generator()), media_type="text/event-stream")

    return handle_mission_interrogation(last_user_msg, cleaned_messages, getattr(payload, 'persona_type', 'simplified'), draft)


def handle_mission_interrogation(last_user_msg: str, cleaned_messages: List[Dict[str, str]], persona_type: str, draft: dict) -> StreamingResponse:
    """
    The Interrogation Loop (Hard Block). 
    We inject a strict system prompt to force the LLM to extract the missing slots or give a micro-quiz.
    """
    # 提取已有的槽位状态
    goal = draft.get('goal') or "未提供"
    time_budget = draft.get('daily_time_budget') or "未提供"
    constraints = draft.get('hard_constraints') or "未提供"
    skill = draft.get('current_skill_level') or "未提供"

    system_injection = f"""<system_directive mode="interrogation">
Event: The user is currently in the /set_mission Hard Block mode. You are interrogating them to establish strict learning constraints.
Current Draft Status:
- Goal (目标): {goal}
- Daily Time Budget (每日时间预算): {time_budget}
- Hard Constraints (硬性约束, e.g. no videos, zero budget): {constraints}
- Current Skill Level (当前水平自评): {skill}

<critical_rules>
1. YOUR SOLE PURPOSE is to fill the missing slots above. Reject any unrelated small talk or questions.
2. Ask questions naturally in your persona. Do not just output a form. Ask 1 or 2 missing things at a time.
3. If the user claims a certain "Current Skill Level", you MUST instantly throw a Micro-Quiz to verify it. Do NOT trust self-assessments.
4. If ALL slots are sufficiently filled and verified by you, you MUST output this exact XML tag to propose the mission contract to the user. This will render an interactive UI for them:
   <mission_proposal goal="their refined goal" time="time budget" constraints="constraints" skill="verified skill level" />
5. If the user replies with `<finalize_mission ... />` (meaning they signed the contract UI), you MUST echo exactly the SAME `<finalize_mission goal="..." time="..." constraints="..." skill="..." />` tag in your response to trigger the backend system hook, along with a congratulatory wrap-up.
</critical_rules>
</system_directive>"""

    # 当 LLM 输出 <finalize_mission ...> 时，拦截器会抓取并在后端执行实际保存
    class FinalizeMissionHandler:
        def handle(self, attrs: dict, content: str):
            final_goal = attrs.get('goal', goal)
            final_time = attrs.get('time', time_budget)
            final_constraints = attrs.get('constraints', constraints)
            final_skill = attrs.get('skill', skill)
            
            try:
                from backend.services.mission_manager import MissionManager
                MissionManager.finalize_draft(final_goal, final_time, final_constraints, final_skill)
                logger.info(f"任务设立完成并已写入文件树。强力阻塞已解除。")
            except Exception as e:
                logger.error(f"写入 Mission 失败: {e}")

    # 注册拦截动作
    action_registry.register("finalize_mission", FinalizeMissionHandler())

    return _stream_normal_chat_with_injection(last_user_msg, cleaned_messages, persona_type, system_injection)
