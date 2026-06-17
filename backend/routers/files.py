import os
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["files"])

def build_file_tree(dir_path: str):
    ignore_dirs = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', 'build', '.idea', '.vscode'}
    tree = []
    try:
        for entry in os.scandir(dir_path):
            if entry.name in ignore_dirs:
                continue
            if entry.is_dir():
                children = build_file_tree(entry.path)
                tree.append({
                    "name": entry.name,
                    "path": entry.path.replace("\\", "/"),
                    "is_dir": True,
                    "children": children
                })
            else:
                tree.append({
                    "name": entry.name,
                    "path": entry.path.replace("\\", "/"),
                    "is_dir": False
                })
    except Exception as e:
        logger.error(f"Error reading directory {dir_path}: {e}")
    # 文件夹排前面，文件排后面，各按名字升序排序
    tree.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return tree

@router.get("/files/list")
def list_files(root_dir: str = None):
    if not root_dir:
        # 默认到项目根目录
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_dir = os.path.abspath(root_dir)
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        raise HTTPException(status_code=400, detail="Invalid directory path")
    return {
        "root_name": os.path.basename(root_dir) or root_dir,
        "root_path": root_dir.replace("\\", "/"),
        "tree": build_file_tree(root_dir)
    }

@router.get("/files/content")
def get_file_content(file_path: str):
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=400, detail="Invalid file path")
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/images")
def list_character_images():
    """获取本地目录下所有角色图片文件名"""
    IMAGE_DIR = "D:/Games/AI小说文档/01-SillyTarern文件/01-[roll点开局·遇仙记]/02-角色卡/00-[自创]遇仙记/02-媚吻锋/00-图片资源/正常"
    if not os.path.exists(IMAGE_DIR):
        return []
    try:
        files = os.listdir(IMAGE_DIR)
        valid_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        img_files = [f for f in files if os.path.splitext(f)[1].lower() in valid_extensions]
        # 排序以保证列表顺序一致
        img_files.sort()
        return img_files
    except Exception as e:
        logger.error(f"Error listing images: {e}")
        return []
