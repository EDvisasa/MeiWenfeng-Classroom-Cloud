import json
import logging
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi.responses import StreamingResponse

from backend.database import get_db_connection
from backend.services.action_registry import action_registry
from backend.services.character_state import CharacterStateError, CharacterStateManager
from backend.services.memory_decay import process_memory_decay
from backend.services.model_router import get_active_model, stream_chat
from backend.services.prompts import SUMMARIZATION_SYSTEM_PROMPT, get_system_prompt
from backend.services.rag_factory import get_rag_client
from backend.services.response_pipeline import ResponsePipeline, json_escape
import backend.services.side_effects  # Ensure side-effect handlers are registered

logger = logging.getLogger(__name__)

_QUIZ_RESULT_TAG_RE = re.compile(r'<submit_quiz_result\b[^>]*?is_correct\s*=\s*"(true|false)"', re.IGNORECASE)


def _parse_quiz_result_correct(message: str) -> Optional[bool]:
    """Extracts the is_correct flag from a <submit_quiz_result> tag; returns None when absent."""
    match = _QUIZ_RESULT_TAG_RE.search(message or "")
    if not match:
        return None
    return match.group(1).lower() == "true"


def _sse_response(raw_generator_fn: Callable[[], Iterable[Any]]) -> StreamingResponse:
    """Wrap a raw SSE item generator through ResponsePipeline into a StreamingResponse."""
    pipeline = ResponsePipeline()
    return StreamingResponse(pipeline.process_stream(raw_generator_fn()), media_type="text/event-stream")


def _sync_session_course_id(session_id: Optional[str], course_id: str) -> None:
    """Best-effort sync of active course_id onto the persisted chat session."""
    if not session_id:
        return
    try:
        conn = get_db_connection()
        conn.execute("UPDATE chat_sessions SET course_id = ? WHERE id = ?", (course_id, session_id))
        conn.commit()
        conn.close()
    except Exception:
        pass


@dataclass
class SlashCommandContext:
    """Normalized request context passed into every CommandStrategy."""

    raw_command: str
    clean_cmd: str
    payload: Any
    last_user_msg: str
    cleaned_messages: List[Dict[str, str]]
    current_file_path: Optional[str]
    persona_type: str
    session_id: Optional[str]
    atmosphere_mode: str = "daily"

    @classmethod
    def from_request(
        cls,
        command: str,
        payload: Any,
        last_user_msg: str,
        cleaned_messages: List[Dict[str, str]],
    ) -> "SlashCommandContext":
        return cls(
            raw_command=command,
            clean_cmd=(command or "").strip().lower(),
            payload=payload,
            last_user_msg=last_user_msg,
            cleaned_messages=cleaned_messages,
            current_file_path=getattr(payload, "current_file_path", None),
            persona_type=getattr(payload, "persona_type", "simplified"),
            session_id=getattr(payload, "session_id", None),
            atmosphere_mode=getattr(payload, "atmosphere_mode", None) or "daily",
        )


def _resolve_course_context(
    ctx: SlashCommandContext,
    allow_course_arg: bool = False,
    fallback_to_selected: bool = False,
    lock_on_lesson: bool = False,
) -> Dict[str, Any]:
    """Resolve active/selected course, mission, topic, ZPD helpers scope, and optional file tag."""
    from backend.services.course_manager import (
        enter_lesson_lock,
        get_active_course,
        get_active_course_id,
        get_selected_course_id,
        set_selected_course_id,
    )
    from backend.services.mission_manager import MissionManager

    tokens = ctx.clean_cmd.split()
    if allow_course_arg and len(tokens) > 1:
        target_course_id = tokens[1].strip()
        if lock_on_lesson:
            enter_lesson_lock(target_course_id)
        else:
            set_selected_course_id(target_course_id)
        _sync_session_course_id(ctx.session_id, target_course_id)
    else:
        active_cid = get_active_course_id()
        if active_cid != "default":
            target_course_id = active_cid
        elif fallback_to_selected:
            target_course_id = get_selected_course_id()
        else:
            target_course_id = active_cid
        if lock_on_lesson:
            enter_lesson_lock(target_course_id)
            _sync_session_course_id(ctx.session_id, target_course_id)

    user_mission = MissionManager.get_user_mission(target_course_id)
    active_course = get_active_course(target_course_id)
    topic_name = active_course["topic"] if active_course else "自由探索（当前无待办课题，请用 /plan 生成）"
    lesson_no = active_course.get("lesson_no", 1) if active_course else 1

    file_context = ""
    if ctx.current_file_path:
        file_context = f"<active_document>The user is currently reviewing the document: {os.path.basename(ctx.current_file_path)}</active_document>"

    return {
        "target_course_id": target_course_id,
        "user_mission": user_mission,
        "topic_name": topic_name,
        "lesson_no": lesson_no,
        "file_context": file_context,
    }


class CommandStrategy(ABC):
    """Strategy interface for a self-contained slash command handler."""

    aliases: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()

    def matches_prefix(self, clean_cmd: str) -> bool:
        """Return True when clean_cmd matches one of this strategy's command prefixes."""
        return any(clean_cmd.startswith(prefix) for prefix in self.prefixes)

    @abstractmethod
    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        """Execute this slash command and return a StreamingResponse."""


class CommandRegistry:
    """Central registry mapping slash command names/prefixes to CommandStrategy instances."""

    def __init__(self) -> None:
        self._exact_strategies: Dict[str, CommandStrategy] = {}
        self._prefix_strategies: List[CommandStrategy] = []
        self._fallback_strategy: Optional[CommandStrategy] = None

    def register(self, strategy: CommandStrategy, *, fallback: bool = False) -> None:
        """Register a CommandStrategy by exact aliases, prefixes, or as fallback."""
        if fallback:
            self._fallback_strategy = strategy
            return
        for alias in strategy.aliases:
            self._exact_strategies[alias.lower()] = strategy
        if strategy.prefixes and strategy not in self._prefix_strategies:
            self._prefix_strategies.append(strategy)

    def resolve(self, clean_cmd: str) -> Optional[CommandStrategy]:
        """Resolve exact alias first, then prefix strategies, then fallback."""
        if clean_cmd in self._exact_strategies:
            return self._exact_strategies[clean_cmd]
        for strategy in self._prefix_strategies:
            if strategy.matches_prefix(clean_cmd):
                return strategy
        return self._fallback_strategy

    def dispatch(self, ctx: SlashCommandContext) -> StreamingResponse:
        """Look up and execute the matching strategy for ctx."""
        strategy = self.resolve(ctx.clean_cmd)
        if strategy is None:
            raise ValueError(f"No command strategy registered for: {ctx.clean_cmd}")
        return strategy.execute(ctx)

    def registered_commands(self) -> List[str]:
        """Return all registered exact command aliases."""
        return list(self._exact_strategies.keys())


class UpdatePersonaCommandStrategy(CommandStrategy):
    aliases = ("/update_persona", "update_persona", "/更新人设", "更新人设")

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.routers.memory import update_persona_stream

        return update_persona_stream()


class SummarizeCommandStrategy(CommandStrategy):
    aliases = ("/summarize",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        def raw_generator():
            yield {"type": "summarize_progress", "state": "loading"}
            result_container: Dict[str, Any] = {}

            def target():
                try:
                    result_container["stats"] = process_memory_decay()
                except Exception as e:
                    result_container["error"] = str(e)

            worker = threading.Thread(target=target)
            worker.start()

            # Yield keep-alive messages to prevent frontend timeout and Errno 22 on Windows
            while worker.is_alive():
                time.sleep(2)
                yield {"type": "summarize_progress", "state": "loading"}

            worker.join()
            if "error" in result_container:
                yield {"type": "summarize_progress", "state": "error", "error": result_container["error"]}
            else:
                yield {"type": "summarize_progress", "state": "done", "stats": result_container.get("stats", {})}

        return _sse_response(raw_generator)


class CompactCommandStrategy(CommandStrategy):
    aliases = ("/compact",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        def raw_generator():
            yield {"type": "system_hint", "icon": "info", "text": "正在提炼会话历史上下文纪要..."}
            from backend.services.compact_service import compact_conversation_messages

            valid_msgs = [m for m in ctx.cleaned_messages if m.get("content", "").strip() != "/compact"]
            _, summary_xml = compact_conversation_messages(valid_msgs, keep_recent_turns=10)

            if not summary_xml:
                yield {"type": "system_hint", "icon": "info", "text": "历史会话长度较短，无需压缩~"}
            else:
                yield {"type": "system_hint", "icon": "check", "text": "✨ 会话上下文已成功浓缩！早期历史已整理为结构化纪要，保留最近鲜活对白。"}

        return _sse_response(raw_generator)


class PrepareLessonCommandStrategy(CommandStrategy):
    aliases = ("/prepare",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        file_path = ctx.current_file_path

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
                    yield f"[知识库联动] 同步出错: {result.get('message')}"
                else:
                    yield "[知识库联动] 同步成功！媚吻锋已熟读这份讲义资料。"
            except Exception as e:
                yield f"[知识库联动] 发生异常: {e}"

        return _sse_response(raw_generator)


class RewardCommandStrategy(CommandStrategy):
    aliases = ("/reward",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        def raw_generator():
            try:
                state = CharacterStateManager.modify_state(affection_delta=10)
                yield {
                    "type": "system_hint",
                    "icon": "check",
                    "text": f"媚吻锋感到十分欢喜，对你的好感度增加了！当前好感度：{state.affection}",
                }
                yield "*眼波流转，娇媚地白了你一眼，但嘴角的笑意却怎么也藏不住：*“夫君这是开窍了？就知道拿这些来哄奴家开心~”"
            except CharacterStateError as e:
                yield {"type": "system_hint", "icon": "draft", "text": f"奖励发送失败: {e}"}

        return _sse_response(raw_generator)


class CooldownCommandStrategy(CommandStrategy):
    aliases = ("/cooldown", "cooldown")

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        def raw_generator():
            try:
                cur_state = CharacterStateManager.get_state()
                state = CharacterStateManager.trigger_cooldown(refractory_period=25)
                mode_name = "余韵温存" if cur_state.refractory_period > 0 else "静心专注"
                yield {
                    "type": "system_hint",
                    "icon": "check",
                    "text": f"已进入【{mode_name}】状态。好感度回退至常态（{state.affection}/100），生理不应期已重置（{state.refractory_period}）。",
                }
                if cur_state.refractory_period > 0:
                    yield "*浑身酥软无力地伏在你怀里，将泛着红晕的脸颊轻轻埋在你颈窝，平复着急促的微喘，指尖无力地轻揪着你的衣襟，又嗔又软地呢喃：*“冤家……刚折腾完，你就这般急着说正事……腿都还是软的呢。也罢，把玉简挪过来些，抱紧我，容我靠着你缓缓神……咱们慢慢看。”"
                else:
                    yield "*敏锐察觉到你眉宇间的肃然与专注，轻轻收敛起平素的嬉闹娇媚，理了理素净的茜红云袖，抬眸时眼神已重归灵动与清朗，嫣然颔首：*“好，既然夫君有一心向学之志，为师自当倾囊相授。收敛心神，刚才这道题目，且看你的真本事了。”"
            except CharacterStateError as e:
                yield {"type": "system_hint", "icon": "draft", "text": f"降温失败: {e}"}

        return _sse_response(raw_generator)


class SetMissionCommandStrategy(CommandStrategy):
    prefixes = ("/set_mission",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        mission_text = ctx.clean_cmd.replace("/set_mission", "").strip()
        try:
            from backend.services.mission_manager import MissionManager

            draft = MissionManager.start_draft(mission_text)
        except Exception as e:
            return _sse_response(lambda: iter([f"[系统报错] 目标设定初始化失败: {e}"]))

        return handle_mission_interrogation(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            draft,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class CancelMissionCommandStrategy(CommandStrategy):
    aliases = ("/cancel_mission",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.services.mission_manager import MissionManager

        MissionManager.cancel_draft()
        system_injection = """<system_directive>
Event: The user just triggered the `/cancel_mission` command, aborting the mission setup.
Action Required:
1. Acknowledge that the mission setup has been cancelled.
2. Keep the mentor persona. Be playful, slightly disappointed, or understanding.
3. Invite the user to continue normal chat or start over when ready.
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class EndLessonCommandStrategy(CommandStrategy):
    aliases = ("/end_lesson", "end_lesson", "/下课", "下课", "/recess", "recess", "/dismiss", "dismiss")

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.services.course_manager import exit_lesson_lock

        exit_lesson_lock()
        prelude_hint = {
            "type": "system_hint",
            "text": "已退出上课锁定，资料归档已切回全局日常记录文件（通用）并切回生活模式。",
            "atmosphere": "daily",
            "in_lesson": False,
        }
        system_injection = """<system_directive mode="recess">
Event: The user triggered the `/end_lesson` (下课) command to conclude class.
Active Knowledge Archive: Unlocked and returned to public basic space (default).

Action Required:
1. Conclude the formal lesson. Warmly acknowledge today's learning effort in your affectionate persona.
2. Return completely to your warm daily companionship tone (tender, relaxed, playful, caring).
3. Do NOT issue any new quizzes, homework, or strict tests. Offer tea, suggest a walk or casual chat, and enjoy off-class leisure.
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            prelude_hint=prelude_hint,
            session_id=ctx.session_id,
            atmosphere_mode="daily",
        )


class LessonContinueCommandStrategy(CommandStrategy):
    aliases = ("/lesson_continue",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.services.course_manager import get_zpd_metrics, record_quiz_result

        cctx = _resolve_course_context(ctx, allow_course_arg=False)
        target_course_id = cctx["target_course_id"]
        topic_name = cctx["topic_name"]

        is_correct = _parse_quiz_result_correct(ctx.last_user_msg)
        if is_correct is not None:
            zpd_metrics = record_quiz_result(is_correct, topic_name, target_course_id)
        else:
            zpd_metrics = get_zpd_metrics(topic_name, target_course_id)
        zpd_coefficient = zpd_metrics["coefficient"]
        total_wrong = zpd_metrics.get("total_consecutive_wrong", zpd_metrics.get("consecutive_wrong", 0))

        slacking_warning = ""
        if is_correct is False and total_wrong >= 3:
            state = CharacterStateManager.modify_state(affection_delta=-2)
            slacking_warning = f"""
<slacking_warning>
[ALERT: USER ANSWERED INCORRECTLY {total_wrong} TIMES IN A ROW]
The user appears to be guessing blindly or fooling around, triggering your core dislike: '有人故意瞎捣乱 / 学习消极敷衍'.
Affection score has dropped by 2 (Current Affection: {state.affection}/100).
Required Persona Tone:
1. Drop your sweet flirtatious indulgence completely for this response.
2. Express genuine disappointment, mild exasperation, and firm mentorship (*收敛了笑意，微蹙秀眉轻叹* “夫君若总是这般心不在焉地胡乱瞎猜，奴家可真要生气了…”).
3. Demand that the user read your explanation attentively before guessing again.
</slacking_warning>
"""

        system_injection = f"""<system_directive>
Event: The user just submitted an answer to your previous quiz.
User's Ultimate Mission: {cctx['user_mission']}
Current Topic: {topic_name}
Current ZPD Difficulty Coefficient: {zpd_coefficient}
{cctx['file_context']}
{slacking_warning}
Action Required & Flow Progression:
1. Evaluate Answer: Inspect the user's choice and correctness via `<submit_quiz_result>`.
2. Pedagogical Feedback:
   - If Correct: Praise and celebrate warmly. Summarize the key takeaway, and ask whether they want to advance to the next topic or challenge a higher-level question. ONLY grant `<property_update affection_delta=\"+1\" />` if this solved a high-difficulty ZPD challenge ({zpd_coefficient} >= 2.0) or significant milestone; otherwise routine correct answers keep affection_delta=\"0\".
   - If Incorrect: Tenderly and patiently diagnose the misconception. Point out why the chosen option is wrong without scolding (unless slacking warning is active). Follow up with a focused variant `<quiz>` to consolidate, preventing endless blind loops.
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            prelude_hint=None,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class LessonCommandStrategy(CommandStrategy):
    prefixes = ("/lesson",)

    def matches_prefix(self, clean_cmd: str) -> bool:
        return clean_cmd.startswith("/lesson") and not clean_cmd.startswith("/lesson_continue")

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.services.course_manager import get_zpd_metrics

        cctx = _resolve_course_context(
            ctx,
            allow_course_arg=True,
            fallback_to_selected=True,
            lock_on_lesson=True,
        )
        target_course_id = cctx["target_course_id"]
        topic_name = cctx["topic_name"]
        lesson_no = cctx["lesson_no"]

        zpd_metrics = get_zpd_metrics(topic_name, target_course_id)
        zpd_coefficient = zpd_metrics["coefficient"]
        prelude_hint = {
            "type": "system_hint",
            "icon": "zpd",
            "text": f"课题：{target_course_id} | 课时 {lesson_no}：{topic_name} | 当前 ZPD 难度系数：{zpd_coefficient}",
            "atmosphere": "study",
            "in_lesson": True,
            "course_id": target_course_id,
        }
        sandbox_path = f"courses/{target_course_id}/Sandbox/" if target_course_id != "default" else "data/materials/Sandbox/"
        system_injection = f"""<system_directive mode="lesson">
Event: The user triggered the `/lesson` command to start a formal lesson in course '{target_course_id}'.
Active Course: {target_course_id} (Sandbox path: {sandbox_path})
User's Mission: {cctx['user_mission']}
Current Lesson: 课时 {lesson_no} - {topic_name}
Current ZPD Difficulty Coefficient: {zpd_coefficient}
{cctx['file_context']}

Action Required: Enter your mentor persona and teach today's topic with living analogies, intuitive models, and short paragraphs.
Lesson & Quiz Guidelines:
1. Grounded Pedagogy: The theory explanation MUST be plain, intuitive, and grounded in common-sense analogies.
2. Isolated Sandbox: Guide the user to inspect and run code in their isolated sandbox: {sandbox_path}.
3. Conclude with a Quiz: Conclude this lesson segment with exactly ONE standard 4-option multiple choice `<quiz>` (encapsulated in `<quiz type="multiple_choice">` adhering to response_format_rules).
4. ZPD Cognitive Gradient (Current Coefficient: {zpd_coefficient}):
   - 0.5 ~ 1.0: Intuitive core definitions and scaffolded discrimination.
   - 1.1 ~ 2.0: Execution flow, boundary traps, and common coding pitfalls.
   - 2.1 ~ 3.0: Deep underlying mechanisms, composite multi-condition deductions, and deceptive distractors.
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            prelude_hint=prelude_hint,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class SubmitCommandStrategy(CommandStrategy):
    aliases = ("/submit",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        cctx = _resolve_course_context(ctx, allow_course_arg=False)
        system_injection = f"""<system_directive mode="socratic_strict_mentor">
Event: The user triggered the `/submit` command, indicating they are ready for assessment.
Current Assessment Topic: {cctx['topic_name']}
User's Ultimate Mission: {cctx['user_mission']}
{cctx['file_context']}

<critical_rules>
1. NEVER GIVE DIRECT ANSWERS.
2. Ask questions that are just slightly beyond the user's current understanding (Zone of Proximal Development).
3. Identify ambiguous areas in the user's logic and pursue them with follow-up questions.
4. PASS CONDITION (EVOLVING SANDBOX): 
   - If the user perfectly masters the current topic/code challenge, do NOT just say "pass".
   - First, praise them and explicitly ask: "干得漂亮！你准备好迎接下一阶挑战了吗？" (Or something similar in your persona's tone).
   - ONLY AFTER the user explicitly replies "yes/ready" in their next message, you MUST use the `<call_tool name="replace_file_content">` tool (to modify existing files) or `<call_tool name="create_file">` tool (to create new files) to surgically evolve their current sandbox code to introduce a new bug or increase the difficulty (Desirable Difficulty / Interleaving).
   - Provide a brief "学情洞察" (Learning Insight) summarizing their newly acquired ZPD edge so the background memory script can log it.
5. INTERACTIVE QUIZ: You may occasionally use the `<quiz type="multiple_choice">` tag to throw a pop quiz at the user. The frontend will render it as a UI component. The JSON inside must have "question", "options" (array), "correct_index" (int), and "explanation".
</critical_rules>
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            prelude_hint=None,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class PlanCommandStrategy(CommandStrategy):
    prefixes = ("/plan",)

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        from backend.services.course_manager import get_formatted_syllabus

        cctx = _resolve_course_context(
            ctx,
            allow_course_arg=True,
            fallback_to_selected=True,
            lock_on_lesson=False,
        )
        target_course_id = cctx["target_course_id"]
        syllabus_text = get_formatted_syllabus(target_course_id)
        system_injection = f"""<system_directive mode="plan">
Event: The user triggered the `/plan` command to plan or revise the syllabus for course '{target_course_id}'.
Active Course: {target_course_id}
User's Ultimate Mission for this course: {cctx['user_mission']}

<current_syllabus_progress>
{syllabus_text}
</current_syllabus_progress>

<critical_rules_for_planning>
1. LIVING SYLLABUS & DYNAMIC REVISION:
   - If the user is dissatisfied or requests modifications, revise and refine the upcoming syllabus accordingly.
   - COMPLETED LESSONS PROTECTION: Any topics marked as [已完成] MUST be strictly preserved and not removed or overwritten. Only re-plan or subdivide [当前] and [未修] lessons.
2. Output Format:
   - Output each newly planned or refined topic using: `<new_course phase="Phase Name" topic="Topic Name" />`.
   - The backend interceptor will append to the course progress table and mirror to courses/{target_course_id}/Lessons/syllabus.md.
</critical_rules_for_planning>
</system_directive>"""
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            system_injection,
            prelude_hint=None,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


class DefaultFallbackCommandStrategy(CommandStrategy):
    """Fallback strategy when an unrecognized slash command is entered."""

    def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
        _resolve_course_context(ctx, allow_course_arg=False)
        return _stream_normal_chat_with_injection(
            ctx.last_user_msg,
            ctx.cleaned_messages,
            ctx.persona_type,
            "",
            prelude_hint=None,
            session_id=ctx.session_id,
            atmosphere_mode=ctx.atmosphere_mode,
        )


def build_default_command_registry() -> CommandRegistry:
    """Create and populate the default Slash CommandRegistry."""
    registry = CommandRegistry()
    for strategy in (
        UpdatePersonaCommandStrategy(),
        SummarizeCommandStrategy(),
        CompactCommandStrategy(),
        PrepareLessonCommandStrategy(),
        RewardCommandStrategy(),
        CooldownCommandStrategy(),
        SetMissionCommandStrategy(),
        CancelMissionCommandStrategy(),
        EndLessonCommandStrategy(),
        LessonContinueCommandStrategy(),
        LessonCommandStrategy(),
        SubmitCommandStrategy(),
        PlanCommandStrategy(),
    ):
        registry.register(strategy)
    registry.register(DefaultFallbackCommandStrategy(), fallback=True)
    return registry


command_registry = build_default_command_registry()


def handle_slash_command(
    command: str,
    payload: Any,
    last_user_msg: str,
    cleaned_messages: List[Dict[str, str]],
) -> StreamingResponse:
    """统一处理各种以斜杠开头的纯前端指令。"""
    ctx = SlashCommandContext.from_request(command, payload, last_user_msg, cleaned_messages)
    return command_registry.dispatch(ctx)


def _stream_normal_chat_with_injection(
    last_user_msg: str,
    cleaned_messages: List[Dict[str, str]],
    persona_type: str,
    system_injection: str,
    prelude_hint: Optional[dict] = None,
    session_id: Optional[str] = None,
    atmosphere_mode: str = "daily",
    on_stream_complete: Optional[Callable[[], None]] = None,
) -> StreamingResponse:
    """
    在原本的大模型对话流基础上，追加特定的 System Prompt 注入，让大模型根据指令自动执行动作。
    采用解耦的 ResponsePipeline。
    """
    from backend.services.context_manager import build_base_system_prompt

    system_prompt, _, _ = build_base_system_prompt(
        last_user_msg=last_user_msg,
        persona_type=persona_type,
        extra_system_injection=system_injection,
        atmosphere_mode=atmosphere_mode or "daily",
    )

    pipeline = ResponsePipeline(registry=action_registry, session_id=session_id)
    pipeline.original_user_msg = last_user_msg

    def event_generator():
        try:
            if prelude_hint:
                yield f"data: {json.dumps(prelude_hint, ensure_ascii=False)}\n\n"
            if system_injection and 'mode="interrogation"' in system_injection:
                warning_json = json.dumps(
                    {"type": "draft_warning", "text": "进入设立学习目标模式，若想放弃输入/cancel_mission解除状态"},
                    ensure_ascii=False,
                )
                yield f"data: {warning_json}\n\n"
            if system_injection and "/cancel_mission" in system_injection:
                hint_json = json.dumps(
                    {"type": "system_hint", "icon": "check", "text": "设立目标模式已退出，恢复正常对话"},
                    ensure_ascii=False,
                )
                yield f"data: {hint_json}\n\n"

            content_stream = stream_chat(cleaned_messages, system_prompt)
            yield from pipeline.process_stream(content_stream)
        except Exception as e:
            import traceback

            traceback.print_exc()
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"
        finally:
            if on_stream_complete:
                try:
                    on_stream_complete()
                except Exception as cb_err:
                    logger.warning(f"on_stream_complete hook error: {cb_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class SlashHandler:
    """斜杠指令分发适配器类，提供统一同步流式代理"""

    @staticmethod
    def handle(command: str, session_id: str = "default"):
        class DummyPayload:
            pass

        response = handle_slash_command(command, DummyPayload(), command, [])
        return response.body_iterator


def handle_mission_interrogation(
    last_user_msg: str,
    cleaned_messages: List[Dict[str, str]],
    persona_type: str,
    draft: dict,
    session_id: Optional[str] = None,
    atmosphere_mode: str = "daily",
) -> StreamingResponse:
    """
    The Interrogation Loop (Hard Block).
    We inject a strict system prompt to force the LLM to extract the missing slots or give a micro-quiz.
    """
    goal = draft.get("goal") or "未提供"
    time_budget = draft.get("daily_time_budget") or "未提供"
    constraints = draft.get("hard_constraints") or "未提供"
    skill = draft.get("current_skill_level") or "未提供"

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
4. If ALL slots are sufficiently filled and verified by you, you MUST output this exact XML tag to propose the mission contract to the user, including an extracted concise ASCII slug for course_id (alphanumeric, dashes, underscores only, e.g. pde_navier_stokes):
   <mission_proposal goal="their refined goal" time="time budget" constraints="constraints" skill="verified skill level" course_id="short_ascii_slug" />
5. If the user replies with `<finalize_mission ... />` (meaning they signed the contract UI), you MUST echo exactly the SAME `<finalize_mission goal="..." time="..." constraints="..." skill="..." course_id="..." />` tag in your response to trigger the backend system hook. In your closing congratulatory response, proactively outline the suggested syllabus for the initial phase using `<new_course phase="第一阶段" topic="..." />`, and inform the user that their course materials and sandbox are prepared: "输入 /lesson 即可开学第一课" to seamlessly transition from planning to lesson 1.
</critical_rules>
</system_directive>"""

    finalize_ran = {"done": False}

    class FinalizeMissionHandler:
        def __init__(self, sess_id: Optional[str] = None):
            self.session_id = sess_id

        def handle(self, attrs: dict, content: str):
            final_goal = attrs.get("goal", goal)
            final_time = attrs.get("time", time_budget)
            final_constraints = attrs.get("constraints", constraints)
            final_skill = attrs.get("skill", skill)
            course_id = attrs.get("course_id")

            if not course_id:
                slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", final_goal.lower()).strip("_")
                slug = re.sub(r"_+", "_", slug)
                course_id = slug[:30] if slug else "default"

            try:
                from backend.services.mission_manager import MissionManager

                MissionManager.finalize_draft(
                    final_goal=final_goal,
                    final_time=final_time,
                    final_constraints=final_constraints,
                    final_skill=final_skill,
                    course_id=course_id,
                    course_name=final_goal[:30],
                )
                finalize_ran["done"] = True
                _sync_session_course_id(self.session_id, course_id)
                logger.info(f"任务设立完成并已写入文件树。强力阻塞已解除。course_id={course_id}")
            except Exception as e:
                logger.error(f"写入 Mission 失败: {e}")

    action_registry.register("finalize_mission", FinalizeMissionHandler(sess_id=session_id))

    def _reset_archive_after_mission_finalize():
        if finalize_ran["done"]:
            from backend.services.course_manager import is_in_lesson, reset_active_course_id

            if not is_in_lesson():
                reset_active_course_id()

    return _stream_normal_chat_with_injection(
        last_user_msg,
        cleaned_messages,
        persona_type,
        system_injection,
        session_id=session_id,
        atmosphere_mode=atmosphere_mode,
        on_stream_complete=_reset_archive_after_mission_finalize,
    )
