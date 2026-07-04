import os
import logging

logger = logging.getLogger(__name__)

class MaterialsManager:
    @classmethod
    def _get_materials_dir(cls) -> str:
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.abspath(os.path.join(base_root, "data", "materials"))

    @classmethod
    def _get_safe_path(cls, rel_path: str, require_md: bool = False) -> str:
        materials_dir = cls._get_materials_dir()
        safe_path = os.path.abspath(os.path.join(materials_dir, rel_path))
        if not safe_path.startswith(materials_dir):
            raise ValueError("Forbidden: Directory traversal attempt")
        if require_md and not safe_path.endswith(".md"):
            raise ValueError("Forbidden: Only .md files can be modified")
        return safe_path

    @classmethod
    def build_knowledge_tree(cls) -> list:
        """
        Scans data/materials/ and returns a 2-level tree structure:
        [
            {
                "category": "Lessons",
                "files": [{"name": "0001-React基础", "path": "Lessons/0001-React基础.md"}]
            },
            ...
        ]
        """
        materials_dir = cls._get_materials_dir()
        if not os.path.exists(materials_dir):
            return []

        tree = []
        # Categories we specifically care about in a preferred order
        preferred_order = ["Lessons", "LDRs", "References", "Settings"]
        
        # Get all subdirectories
        subdirs = [d for d in os.listdir(materials_dir) if os.path.isdir(os.path.join(materials_dir, d))]
        
        # Sort subdirs based on preferred order, then alphabetically
        sorted_subdirs = sorted(subdirs, key=lambda x: preferred_order.index(x) if x in preferred_order else 999)

        for category in sorted_subdirs:
            cat_path = os.path.join(materials_dir, category)
            files_list = []
            for file in sorted(os.listdir(cat_path)):
                if file.endswith(".md"):
                    rel_path = f"{category}/{file}"
                    files_list.append({
                        "name": file.replace(".md", ""),
                        "path": rel_path
                    })
            # Always include the preferred categories even if empty, to show the structure
            if files_list or category in preferred_order:
                tree.append({
                    "category": category,
                    "files": files_list
                })
                
        return tree

    @classmethod
    def get_material_content(cls, rel_path: str) -> str:
        """Reads a specific markdown file from data/materials/"""
        safe_path = cls._get_safe_path(rel_path)
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            with open(safe_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"Document not found: {rel_path}"

    @classmethod
    def save_material_content(cls, rel_path: str, content: str) -> bool:
        """Saves a markdown file to data/materials/ with path traversal and extension protection."""
        safe_path = cls._get_safe_path(rel_path, require_md=True)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
