@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python
"%PYTHON_EXE%" scripts\desktop_platform_prepare.py --launch
echo.
echo 已生成报告：data\desktop-listener\platform-prepare-report.md
echo 如果平台已打开，请继续双击“验收真实平台.bat”。
pause
