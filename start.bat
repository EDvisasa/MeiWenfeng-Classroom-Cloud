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
echo [Info] Synchronizing backend dependencies...
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt > nul

rem 3. Check and Setup Node dependencies
if exist frontend\node_modules goto frontend_ok
echo [Info] Frontend dependencies not found. Installing...
cd frontend
call npm install
cd ..
:frontend_ok

rem 3. Cleanup Zombie Processes
echo ==========================================
echo Cleaning up potential zombie processes...
for /f "tokens=5" %%a in ('%SystemRoot%\System32\netstat.exe -aon ^| find ":12701" ^| find "LISTENING"') do (
    echo Killing zombie process holding port 12701 PID %%a
    %SystemRoot%\System32\taskkill.exe /f /t /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('%SystemRoot%\System32\netstat.exe -aon ^| find ":12703" ^| find "LISTENING"') do (
    echo Killing zombie process holding port 12703 PID %%a
    %SystemRoot%\System32\taskkill.exe /f /t /pid %%a >nul 2>&1
)

rem 4. Start core services using concurrently
echo ==========================================
echo Starting core services concurrently in a single window...
echo Frontend will run at http://localhost:12703/
echo Backend will run at http://127.0.0.1:12701
echo LiteLLM Gateway will run at http://127.0.0.1:12704
echo.
echo * Press Ctrl+C to stop all services safely. *
echo ==========================================

call npx --yes concurrently -n "FastAPI,React,LiteLLM" -c "bgBlue.bold,bgCyan.bold,bgYellow.bold" --kill-others ".venv\Scripts\python.exe -m backend.main" "cd frontend && npm run dev" ".venv\Scripts\litellm.exe --config backend/litellm_config.yaml --port 12704"

pause

