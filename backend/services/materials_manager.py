import os
import re
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class MaterialsManager:
    @classmethod
    def _sanitize_course_id(cls, course_id: Optional[str]) -> Optional[str]:
        """Validate course_id: allows alphanumeric, dash, and underscore; rejects paths/traversal."""
        if not course_id or course_id in ("default", "", "root", "None"):
            return None
        if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
            raise ValueError("Forbidden: Invalid course ID: only alphanumeric, dashes, and underscores allowed")
        return course_id

    @classmethod
    def _get_materials_dir(cls, course_id: Optional[str] = None) -> str:
        """Resolve base root for global materials or isolated course project."""
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_materials = os.path.abspath(os.path.join(base_root, "data", "materials"))
        
        safe_course_id = cls._sanitize_course_id(course_id)
        if safe_course_id:
            courses_base = os.path.abspath(os.path.join(base_materials, "courses"))
            target_dir = os.path.abspath(os.path.join(courses_base, safe_course_id))
            if not os.path.normcase(target_dir).startswith(os.path.normcase(courses_base)):
                raise ValueError("Forbidden: Directory traversal attempt")
            return target_dir
            
        return base_materials

    @classmethod
    def _get_safe_path(cls, rel_path: str, course_id: Optional[str] = None, require_md: bool = False) -> str:
        materials_dir = cls._get_materials_dir(course_id)
        safe_path = os.path.abspath(os.path.join(materials_dir, rel_path))
        if not os.path.normcase(safe_path).startswith(os.path.normcase(materials_dir)):
            raise ValueError("Forbidden: Directory traversal attempt")
        if require_md and not safe_path.endswith(".md"):
            raise ValueError("Forbidden: Only .md files can be modified")
        return safe_path

    @classmethod
    def list_courses(cls) -> List[Dict[str, Any]]:
        """List all isolated courses along with the default global course."""
        courses = [
            {
                "id": "default",
                "name": "全局基础课程 (通用)",
                "is_default": True
            }
        ]
        base_materials = cls._get_materials_dir()
        courses_base = os.path.join(base_materials, "courses")
        if os.path.exists(courses_base) and os.path.isdir(courses_base):
            for entry in sorted(os.listdir(courses_base)):
                entry_path = os.path.join(courses_base, entry)
                if os.path.isdir(entry_path):
                    meta_path = os.path.join(entry_path, "course.json")
                    course_name = entry
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                                course_name = meta.get("name", entry)
                        except Exception as e:
                            logger.warning(f"Failed to read course meta for {entry}: {e}")
                    courses.append({
                        "id": entry,
                        "name": course_name,
                        "is_default": False
                    })
        return courses

    @classmethod
    def create_course(cls, course_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new isolated course directory with standard subfolders and metadata."""
        safe_id = cls._sanitize_course_id(course_id)
        if not safe_id:
            raise ValueError("Forbidden: Course ID cannot be empty or default")

        base_materials = cls._get_materials_dir()
        courses_base = os.path.abspath(os.path.join(base_materials, "courses"))
        target_dir = os.path.abspath(os.path.join(courses_base, safe_id))
        if not os.path.normcase(target_dir).startswith(os.path.normcase(courses_base)):
            raise ValueError("Forbidden: Directory traversal attempt")

        os.makedirs(target_dir, exist_ok=True)
        for folder in ["Lessons", "Sandbox", "References", "LDRs", "Settings"]:
            os.makedirs(os.path.join(target_dir, folder), exist_ok=True)

        display_name = name.strip() if name and name.strip() else safe_id
        meta = {
            "id": safe_id,
            "name": display_name
        }
        meta_path = os.path.join(target_dir, "course.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return meta

    @classmethod
    def build_knowledge_tree(cls, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scans data/materials/ (or data/materials/courses/<course_id>/) and returns:
        [
            {
                "category": "Lessons",
                "files": [{"name": "0001-React基础", "path": "Lessons/0001-React基础.md"}]
            },
            ...
        ]
        """
        materials_dir = cls._get_materials_dir(course_id)
        if not os.path.exists(materials_dir):
            return []

        tree = []
        preferred_order = ["Lessons", "LDRs", "References", "Sandbox", "Settings"]
        
        # Subdirs in target dir; exclude "courses" folder if in root
        subdirs = [
            d for d in os.listdir(materials_dir)
            if os.path.isdir(os.path.join(materials_dir, d)) and d != "courses"
        ]
        
        sorted_subdirs = sorted(subdirs, key=lambda x: preferred_order.index(x) if x in preferred_order else 999)

        for category in sorted_subdirs:
            cat_path = os.path.join(materials_dir, category)
            files_list = []
            if os.path.exists(cat_path):
                for file in sorted(os.listdir(cat_path)):
                    if file.endswith(".md"):
                        rel_path = f"{category}/{file}"
                        files_list.append({
                            "name": file[:-3] if file.endswith(".md") else file,
                            "path": rel_path
                        })
            if files_list or category in preferred_order:
                tree.append({
                    "category": category,
                    "files": files_list
                })
                
        return tree

    @classmethod
    def get_material_content(cls, rel_path: str, course_id: Optional[str] = None) -> str:
        """Reads a specific markdown file from data/materials/ or course directory."""
        safe_path = cls._get_safe_path(rel_path, course_id=course_id)
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            with open(safe_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"Document not found: {rel_path}"

    @classmethod
    def save_material_content(cls, rel_path: str, content: str, course_id: Optional[str] = None) -> bool:
        """Saves a markdown file to materials or course directory with path traversal and extension protection."""
        safe_path = cls._get_safe_path(rel_path, course_id=course_id, require_md=True)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
