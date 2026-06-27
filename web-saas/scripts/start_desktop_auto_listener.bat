@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo 正在启动桌面客服自动监听...
echo 打开微信、抖音、千牛或拼多多客服窗口，停留在聊天页。
echo 默认会自动读取当前窗口并粘贴候选回复，但不会按 Enter 发送。
echo 如果要改商家话术，编辑 docs\examples\merchant_knowledge.example.txt。
"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\desktop_auto_reply_listener.py --config scripts\desktop_listener.config.example.json
pause
