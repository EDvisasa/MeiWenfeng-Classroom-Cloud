import os
import logging
from typing import Dict, Any

from backend.database import get_db_connection
from backend.services.action_registry import SideEffectHandler, action_registry
from backend.services.character_state import CharacterStateManager

logger = logging.getLogger(__name__)

class SystemPassHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        from backend.services.course_manager import advance_course_progress
        advance_course_progress()
        logger.info("课程进度已通过 [SYSTEM_PASS] 自动推进！")

class GlossaryHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        term = attrs.get("term", "").strip()
        definition = content.strip()
        if not term: return
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO glossary (term, definition) VALUES (?, ?)", (term, definition))
            conn.commit()
            logger.info(f"术语已收录: {term}")
        finally:
            conn.close()

class NewCourseHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        phase = attrs.get("phase", "").strip()
        topic = attrs.get("topic", "").strip()
        if not phase or not topic: return
        from backend.services.course_manager import append_to_syllabus
        append_to_syllabus(phase, topic)
        logger.info(f"大纲已成功追加新课题: {phase} - {topic}")

class ExplainerHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        title = attrs.get("title", "").strip()
        content = content.strip()
        if not title: return

        safe_title = os.path.basename(title)
        if not safe_title: return
        if not safe_title.endswith(".md"):
            safe_title += ".md"

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        docs_dir = getattr(self, "base_dir", os.path.join(project_root, "data", "materials", "References"))
        os.makedirs(docs_dir, exist_ok=True)

        # In non-test environment, auto-associate with active course phase & topic
        if not hasattr(self, "base_dir"):
            try:
                from backend.services.course_manager import get_active_course
                active_course = get_active_course()
                if active_course:
                    phase = active_course.get("phase", "")
                    topic = active_course.get("topic", "")
                    
                    prefix = ""
                    if "一" in phase: prefix = "01_第一阶_"
                    elif "二" in phase: prefix = "02_第二阶_"
                    elif "三" in phase: prefix = "03_第三阶_"
                    elif "四" in phase: prefix = "04_第四阶_"
                    elif "五" in phase: prefix = "05_第五阶_"
                    elif "六" in phase: prefix = "06_第六阶_"
                    
                    if prefix and not safe_title.startswith(("01_", "02_", "03_", "04_", "05_", "06_")):
                        safe_title = f"{prefix}{safe_title}"

                    if not content.startswith("> **📚"):
                        header = f"> **📚 课程归属**：{phase} | **课题**：{topic}\n\n"
                        content = header + content
            except Exception as e:
                logger.warning(f"Failed to associate active course in ExplainerHandler: {e}")

        # Additional check: resolve absolute path and ensure it's still inside docs_dir
        filepath = os.path.abspath(os.path.join(docs_dir, safe_title))
        if not filepath.startswith(os.path.abspath(docs_dir)):
            logger.warning(f"Path traversal attempt blocked: {title}")
            return

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"实体讲义玉简已生成: {filepath}")

class PropertyUpdateHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        affection_delta = int(attrs.get("affection_delta", 0))
        social_status_delta = int(attrs.get("social_status_delta", 0))
        social_skills_delta = int(attrs.get("social_skills_delta", 0))
        refractory_delta = int(attrs.get("refractory_delta", 0))

        set_refractory = attrs.get("set_refractory")
        if set_refractory is not None:
            set_refractory = int(set_refractory)

        CharacterStateManager.modify_state(
            affection_delta=affection_delta,
            social_status_delta=social_status_delta,
            social_skills_delta=social_skills_delta,
            refractory_delta=refractory_delta,
            set_refractory=set_refractory
        )
        logger.info(f"动态属性已自动更新: {attrs}")

# Register handlers
action_registry.register("system_pass", SystemPassHandler())
action_registry.register("glossary", GlossaryHandler())
action_registry.register("new_course", NewCourseHandler())
action_registry.register("explainer", ExplainerHandler())
action_registry.register("property_update", PropertyUpdateHandler())