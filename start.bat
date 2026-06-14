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

rem 3. Start FastAPI Backend
echo [1/4] Starting Python backend service...
start "Backend Service" cmd /c "chcp 65001 > nul && call .venv\Scripts\activate.bat && python -m backend.main"

rem Wait 3 seconds
ping 127.0.0.1 -n 4 > nul

echo [2/4] Starting MCP Server...
start "MCP Service" cmd /c "chcp 65001 > nul && call .venv\Scripts\activate.bat && python -m backend.mcp_server"

echo [3/4] Starting Node.js Claude Engine Bridge...
start "Node Bridge" cmd /c "chcp 65001 > nul && cd backend\claude_engine && node server.js"

rem Wait 3 seconds
ping 127.0.0.1 -n 4 > nul

rem 4. Start React Frontend
echo [4/4] Starting React frontend (Vite)...
start "Frontend Service" cmd /c "chcp 65001 > nul && cd frontend && npm run dev"

echo.
echo ==========================================
echo Startup complete! 
echo Frontend is running at http://localhost:5173/
echo Backend is running at http://127.0.0.1:8000
echo Node Bridge is running at http://127.0.0.1:3001
echo MCP Server is active.
echo.
echo *If you encounter issues, please check the separate command windows.*
echo *Close those windows to stop the services.*
echo ==========================================
pause

