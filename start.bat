@echo off
chcp 65001 > nul
set PYTHONUTF8=1
title Mei Wenfeng Classroom - Launcher

echo ==========================================
echo       Mei Wenfeng Classroom Launcher
echo ==========================================

rem 1. Check env file
if exist .env goto env_ok
echo [Info] .env file not found, creating from template...
copy .env.example .env > nul
echo [Warning] A default .env file has been created.
echo [Important] Please open .env and enter your API Key to enable chat!
echo.
:env_ok

rem 2. Check and Setup virtualenv
if not exist .venv\Scripts\python.exe (
    echo [Info] Python virtual environment venv not found.
    echo [Info] Automatically creating virtual environment...
    python -m venv .venv
)
if not exist .venv\Scripts\uvicorn.exe (
    echo [Info] Installing backend dependencies...
    .venv\Scripts\python.exe -m pip install -r backend/requirements.txt
)

rem 3. Check and Setup Node dependencies
if exist frontend\node_modules goto frontend_ok
echo [Info] Frontend dependencies not found. Installing...
cd frontend
call npm install
cd ..
:frontend_ok

if exist backend\claude_engine\node_modules goto engine_ok
echo [Info] Claude Engine dependencies not found. Installing...
cd backend\claude_engine
call npm install
cd ..\..
:engine_ok

rem 3. Cleanup Zombie Processes
echo ==========================================
echo Cleaning up potential zombie processes...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":12701" ^| find "LISTENING"') do (
    echo Killing zombie process holding port 12701 PID %%a
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| find ":12702" ^| find "LISTENING"') do (
    echo Killing zombie process holding port 12702 PID %%a
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| find ":12703" ^| find "LISTENING"') do (
    echo Killing zombie process holding port 12703 PID %%a
    taskkill /f /pid %%a >nul 2>&1
)

rem 4. Start all services using concurrently
echo ==========================================
echo Starting all services concurrently in a single window...
echo Frontend will run at http://localhost:12703/
echo Backend will run at http://127.0.0.1:12701
echo Node Bridge will run at http://127.0.0.1:12702
echo MCP Server will be active.
echo.
echo * Press Ctrl+C to stop all services safely. *
echo ==========================================

call npx --yes concurrently -n "FastAPI,MCP,Node,React,LiteLLM" -c "bgBlue.bold,bgMagenta.bold,bgGreen.bold,bgCyan.bold,bgYellow.bold" --kill-others ".venv\Scripts\python.exe -m backend.main" ".venv\Scripts\python.exe -m backend.mcp_server" "cd backend\claude_engine && node server.js" "cd frontend && npm run dev" ".venv\Scripts\litellm.exe --config backend/litellm_config.yaml --port 12704"

pause

