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
app.include_router(chat_router)

@app.get("/api/health")
def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "app": "媚吻锋随身课堂 Backend",
        "database": "classroom.db connected"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # 默认绑定 localhost 供本地访问
    print(f"Starting backend server on port {port}...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)
