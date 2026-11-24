import os
import json
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

        from backend.services.course_manager import get_active_course_id
        course_id = attrs.get("course_id") or get_active_course_id()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(glossary)")
            cols = [c[1] for c in cursor.fetchall()]
            if "course_id" in cols:
                cursor.execute(
                    "INSERT INTO glossary (term, definition, course_id) VALUES (?, ?, ?)",
                    (term, definition, course_id)
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO glossary (term, definition) VALUES (?, ?)",
                    (term, definition)
                )
            conn.commit()
            logger.info(f"术语已收录 [course={course_id}]: {term}")
        except Exception as e:
            try:
                cursor.execute("UPDATE glossary SET definition = ?, course_id = ? WHERE term = ?", (definition, course_id, term))
                conn.commit()
            except Exception:
                logger.warning(f"Glossary insert/update fallback: {e}")
        finally:
            conn.close()

        # Mirror to Settings/glossary.json in the course folder
        try:
            from backend.services.materials_manager import MaterialsManager
            materials_base = MaterialsManager._get_materials_dir()
            if course_id and course_id != "default":
                settings_dir = os.path.join(materials_base, "courses", course_id, "Settings")
            else:
                settings_dir = os.path.join(materials_base, "Settings")
            os.makedirs(settings_dir, exist_ok=True)
            glossary_json_path = os.path.join(settings_dir, "glossary.json")
            glossary_data = {}
            if os.path.exists(glossary_json_path):
                try:
                    with open(glossary_json_path, "r", encoding="utf-8") as f:
                        glossary_data = json.load(f)
                except Exception:
                    glossary_data = {}
            glossary_data[term] = definition
            with open(glossary_json_path, "w", encoding="utf-8") as f:
                json.dump(glossary_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to mirror glossary to JSON: {e}")

class NewCourseHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        phase = attrs.get("phase", "").strip()
        topic = attrs.get("topic", "").strip()
        if not phase or not topic: return
        from backend.services.course_manager import (
            append_to_syllabus,
            get_active_course_id,
            get_formatted_syllabus,
            get_selected_course_id,
        )
        active_cid = get_active_course_id()
        course_id = attrs.get("course_id") or (active_cid if active_cid != "default" else get_selected_course_id())
        append_to_syllabus(phase, topic, course_id=course_id)
        logger.info(f"大纲已成功追加新课题 [course={course_id}]: {phase} - {topic}")

        # Mirror to Lessons/syllabus.md in isolated course directory
        try:
            from backend.services.materials_manager import MaterialsManager
            materials_base = MaterialsManager._get_materials_dir()
            if course_id and course_id != "default":
                lessons_dir = os.path.join(materials_base, "courses", course_id, "Lessons")
            else:
                lessons_dir = os.path.join(materials_base, "Lessons")
            os.makedirs(lessons_dir, exist_ok=True)
            syllabus_md_path = os.path.join(lessons_dir, "syllabus.md")
            syllabus_content = f"# Course Syllabus: {course_id}\n\n{get_formatted_syllabus(course_id)}\n"
            with open(syllabus_md_path, "w", encoding="utf-8") as f:
                f.write(syllabus_content)
        except Exception as e:
            logger.error(f"Failed to mirror syllabus to markdown: {e}")

class ExplainerHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        title = attrs.get("title", "").strip()
        content = content.strip()
        if not title: return

        safe_title = os.path.basename(title)
        if not safe_title: return
        if not safe_title.endswith(".md"):
            safe_title += ".md"

        from backend.services.course_manager import get_active_course_id
        course_id = attrs.get("course_id") or get_active_course_id()

        if hasattr(self, "base_dir"):
            docs_dir = self.base_dir
        else:
            from backend.services.materials_manager import MaterialsManager
            materials_base = MaterialsManager._get_materials_dir()
            if course_id and course_id != "default":
                docs_dir = os.path.join(materials_base, "courses", course_id, "References")
            else:
                docs_dir = os.path.join(materials_base, "References")

        os.makedirs(docs_dir, exist_ok=True)

        # In non-test environment, auto-associate with active course phase & topic
        if not hasattr(self, "base_dir"):
            try:
                from backend.services.course_manager import get_active_course
                active_course = get_active_course(course_id)
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

                    if not content.startswith("> **课程归属**"):
                        header = f"> **课程归属**：{phase} | **课题**：{topic}\n\n"
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
        logger.info(f"长文参考讲义 Markdown 文件已落地生成: {filepath}")

class PropertyUpdateHandler(SideEffectHandler):
    def handle(self, attrs: Dict[str, Any], content: str) -> None:
        affection_delta = int(attrs.get("affection_delta", 0))
        social_status_delta = int(attrs.get("social_status_delta", 0))
        social_skills_delta = int(attrs.get("social_skills_delta", 0))
        refractory_delta = int(attrs.get("refractory_delta", 0))

        is_climax = str(attrs.get("climax", "")).lower() in ("true", "1") or str(attrs.get("is_climax", "")).lower() in ("true", "1")

        set_refractory = attrs.get("set_refractory")
        if set_refractory is not None:
            set_refractory = int(set_refractory)
            # 大模型高潮触发规范为输出 set_refractory="10"
            # 此时路由至 trigger_climax 进行拟人生理累加 (10 -> 18 -> 24)，防止连战被降级覆盖
            if set_refractory == 10:
                CharacterStateManager.trigger_climax(intensity=10)
                set_refractory = None
        elif is_climax:
            CharacterStateManager.trigger_climax(intensity=10)

        set_affection = attrs.get("set_affection")
        if set_affection is not None:
            set_affection = int(set_affection)

        is_cooldown = str(attrs.get("is_cooldown", "")).lower() in ("true", "1")

        CharacterStateManager.modify_state(
            affection_delta=affection_delta,
            social_status_delta=social_status_delta,
            social_skills_delta=social_skills_delta,
            refractory_delta=refractory_delta,
            set_refractory=set_refractory,
            set_affection=set_affection,
            is_cooldown=is_cooldown,
            enforce_daily_cap=True
        )
        logger.info(f"动态属性已自动更新: {attrs}")

class FinalizeMissionHandler:
    def handle(self, attrs: dict, content: str):
        final_goal = attrs.get('goal', '默认研学目标')
        final_time = attrs.get('time', '每天1小时')
        final_constraints = attrs.get('constraints', '无')
        final_skill = attrs.get('skill', '零基础')
        course_id = attrs.get('course_id')
        if not course_id:
            import re
            slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', final_goal.lower()).strip('_')
            slug = re.sub(r'_+', '_', slug)
            course_id = slug[:30] if slug else "default"

        from backend.services.mission_manager import MissionManager
        MissionManager.finalize_draft(
            final_goal=final_goal,
            final_time=final_time,
            final_constraints=final_constraints,
            final_skill=final_skill,
            course_id=course_id,
            course_name=final_goal[:30]
        )

# Register handlers
action_registry.register("system_pass", SystemPassHandler())
action_registry.register("glossary", GlossaryHandler())
action_registry.register("new_course", NewCourseHandler())
action_registry.register("explainer", ExplainerHandler())
action_registry.register("property_update", PropertyUpdateHandler())
action_registry.register("finalize_mission", FinalizeMissionHandler())