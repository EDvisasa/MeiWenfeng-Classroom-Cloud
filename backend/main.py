import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 1. 查找并加载项目根目录的 .env 文件
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# 2. 初始化数据库
from backend.database import init_db
init_db()

# 3. 创建 FastAPI 应用
app = FastAPI(
    title="媚吻锋随身课堂 Backend",
    description="Python FastAPI backend serving character simulation and classroom data",
    version="1.0.0"
)

# 3.5. 静态挂载用户本地图片资源
from fastapi.staticfiles import StaticFiles
IMAGE_DIR = "D:/Games/AI小说文档/01-SillyTarern文件/01-[roll点开局·遇仙记]/02-角色卡/00-[自创]遇仙记/02-媚吻锋/00-图片资源/正常"
if os.path.exists(IMAGE_DIR):
    app.mount("/api/images/static", StaticFiles(directory=IMAGE_DIR), name="character_images")

# 4. 设置跨域 CORS 规则（前端 React 会从 localhost:5173 或其他端口访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地部署允许所有源以简化跨域配置
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. 挂载路由
from backend.routers.chat import router as chat_router
from backend.routers.memory import router as memory_router
from backend.routers.rag import router as rag_router
from backend.routers.course import router as course_router
from backend.routers.models import router as models_router
from backend.routers.files import router as files_router
from backend.routers.db_viewer import router as db_viewer_router

app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(rag_router)
app.include_router(course_router)
app.include_router(models_router)
app.include_router(files_router)
app.include_router(db_viewer_router)

@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "app": "媚吻锋随身课堂 Backend",
        "database": "classroom.db connected"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 12701))
    # 默认绑定 localhost 供本地访问，这样能同时兼容 IPv4 (127.0.0.1) 和 IPv6 (::1)
    print(f"Starting backend server on port {port}...")
    uvicorn.run("backend.main:app", host="localhost", port=port, reload=True)
