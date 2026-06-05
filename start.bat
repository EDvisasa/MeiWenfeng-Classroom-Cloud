@echo off
chcp 65001 > nul
title 媚吻锋随身课堂 - 启动器

echo ==========================================
echo       媚吻锋随身课堂 一键启动服务
echo ==========================================

rem 1. Check env file
if not exist .env (
    echo [提示] 检测到缺少 .env 配置文件，正在根据模版生成...
    copy .env.example .env > nul
    echo [警告] 已为您生成默认的 .env 文件。
    echo [重要] 请使用记事本打开 .env 并填入您的 DEEPSEEK_API_KEY 才能顺利对话！
    echo.
)

rem 2. Check virtualenv
if not exist .venv (
    echo [错误] 找不到 Python 虚拟环境 (.venv)！
    echo 请确认是否已在项目根目录下创建虚拟环境。
    pause
    exit /b
)

rem 3. Start FastAPI Backend
echo [1/2] 正在启动 Python 后端服务...
start "媚吻锋课堂-后端" cmd /c "chcp 65001 > nul && call .venv\Scripts\activate.bat && python -m backend.main"

rem Wait 3 seconds
timeout /t 3 /nobreak > nul

rem 4. Start React Frontend
echo [2/2] 正在启动前端 React 界面 (Vite)...
start "媚吻锋课堂-前端" cmd /c "chcp 65001 > nul && cd frontend && npm run dev"

echo.
echo ==========================================
echo 启动完成！前端将在浏览器自动打开 http://localhost:5173/
echo 后端服务已在后台运行 (接口地址: http://127.0.0.1:8000)
echo.
echo *如果遇到问题，可以查看弹出的两个独立命令行窗口的日志。*
echo *如需关闭课堂，可直接关闭这两个窗口。*
echo ==========================================
pause
