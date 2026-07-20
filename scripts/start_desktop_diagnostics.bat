@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo 正在诊断当前前台客服窗口...
echo 请先打开微信、抖音、千牛或拼多多客服窗口，并停留在聊天页。
"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\desktop_diagnostics.py --platform auto --source auto
pause
