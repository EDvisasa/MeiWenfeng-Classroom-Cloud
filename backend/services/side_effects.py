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

        # Sanitize the title to prevent path traversal
        safe_title = os.path.basename(title)
        if not safe_title: return

        docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "讲义玉简")
        os.makedirs(docs_dir, exist_ok=True)

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