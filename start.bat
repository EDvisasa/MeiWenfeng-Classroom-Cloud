@echo off
chcp 65001 > nul
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

rem 2. Check virtualenv
if exist .venv goto venv_ok
echo [Error] Python virtual environment (.venv) not found!
echo Please make sure the virtual environment is created in the project root.
pause
exit /b
:venv_ok

rem 3. Start all services using concurrently
echo ==========================================
echo Starting all services concurrently in a single window...
echo Frontend will run at http://localhost:12703/
echo Backend will run at http://127.0.0.1:12701
echo Node Bridge will run at http://127.0.0.1:12702
echo MCP Server will be active.
echo.
echo * Press Ctrl+C to stop all services safely. *
echo ==========================================

call npx --yes concurrently -n "FastAPI,MCP,Node,React" -c "bgBlue.bold,bgMagenta.bold,bgGreen.bold,bgCyan.bold" --kill-others ".venv\Scripts\python.exe -m backend.main" ".venv\Scripts\python.exe -m backend.mcp_server" "cd backend\claude_engine && node server.js" "cd frontend && npm run dev"

pause

