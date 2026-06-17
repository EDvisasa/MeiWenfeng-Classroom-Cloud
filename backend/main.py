import os
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import ipaddress
import threading
from contextlib import asynccontextmanager

import sys
# 1. 查找并加载项目根目录的 .env 文件
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup (currently handled globally, can be moved here later)
    # 2. 初始化数据库
    from backend.database import init_db
    init_db()

    # 2.5 预加载 ChromaDB (避免初次检索时卡顿和防止“加载”)
    try:
        from backend.services.chroma_client import chroma_rag_client
        print("Preloading ChromaDB...")
        chroma_rag_client._ensure_client()
        print("ChromaDB preloaded successfully.")
    except Exception as e:
        print(f"Failed to preload ChromaDB: {e}")
        
    yield
    # Shutdown: Windows 热重载僵尸进程终极杀手。
    # 拦截到关闭信号时，延迟 1 秒后直接执行操作系统级别的进程抹杀，不给底层后台线程阻塞退出的机会。
    if os.name == 'nt':
        def kill_self():
            os._exit(0)
        # 给正常清理留出 1 秒的窗口期，然后强制拔电源
        threading.Timer(1.0, kill_self).start()

# 3. 创建 FastAPI 应用
app = FastAPI(
    title="媚吻锋随身课堂 Backend",
    description="Python FastAPI backend serving character simulation and classroom data",
    version="1.0.0",
    lifespan=lifespan
)

# 3.5. 静态挂载用户本地图片资源
from fastapi.staticfiles import StaticFiles
# 通过环境变量读取图片目录，若未配置则使用默认的相对路径，避免硬编码暴露隐私路径
IMAGE_DIR = os.getenv("IMAGE_DIR", os.path.join(ROOT_DIR, "data", "images"))
if os.path.exists(IMAGE_DIR):
    app.mount("/api/images/static", StaticFiles(directory=IMAGE_DIR), name="character_images")

# 4. 设置跨域 CORS 规则（前端 React 会从 localhost:5173 或其他端口访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:12703", "http://127.0.0.1:12703", "http://localhost:5173", "http://127.0.0.1:5173"],  # 限制来源，修复 CORS 漏洞
    allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[0-1])\.\d+\.\d+)(?::\d+)?$", # 允许局域网内的跨域请求（手机端访问所需）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4.5. 局域网 IP 白名单中间件
ALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
]

@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else ""
    try:
        if client_ip == "testclient" or client_ip == "":
            # Allow testclient or cases where client is missing (e.g. certain ASGI setups)
            # You might want to be stricter here depending on security requirements
            is_allowed = True
        else:
            ip_obj = ipaddress.ip_address(client_ip)
            # 检查是否属于允许的网段
            is_allowed = any(ip_obj in net for net in ALLOWED_NETWORKS)
    except ValueError:
        is_allowed = False

    if not is_allowed:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Forbidden: IP address not allowed"},
        )
    return await call_next(request)

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
    # 绑定 0.0.0.0 供局域网访问，并依靠上方的白名单中间件保障安全
    print(f"Starting backend server on port {port}...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
