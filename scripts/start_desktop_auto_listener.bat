@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%PY%" (
  "%PY%" scripts\desktop_listener_launcher.py
) else (
  python scripts\desktop_listener_launcher.py
)
