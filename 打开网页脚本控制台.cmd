@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" scripts\open_web_console.py
pause
endlocal
