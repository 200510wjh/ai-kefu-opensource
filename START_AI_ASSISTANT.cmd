@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "data\logs" mkdir "data\logs"
echo Starting AI customer service assistant...
"%PY%" scripts\desktop_listener_launcher.py > "data\logs\start_ai_assistant.log" 2>&1
type "data\logs\start_ai_assistant.log"
pause
endlocal
