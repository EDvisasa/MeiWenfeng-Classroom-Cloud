import os
import logging

logger = logging.getLogger(__name__)

class MaterialsManager:
    @staticmethod
    def build_knowledge_tree() -> list:
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
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        materials_dir = os.path.join(base_root, "data", "materials")
        
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

    @staticmethod
    def get_material_content(rel_path: str) -> str:
        """Reads a specific markdown file from data/materials/"""
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        materials_dir = os.path.join(base_root, "data", "materials")
        
        # Secure the path (prevent directory traversal)
        safe_path = os.path.abspath(os.path.join(materials_dir, rel_path))
        if not safe_path.startswith(os.path.abspath(materials_dir)):
            raise ValueError("Forbidden: Directory traversal attempt")
            
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            with open(safe_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"Document not found: {rel_path}"
