@echo off
setlocal
cd /d "%~dp0..\.."
node work\xianyu_ai_service\generate_xianyu_pack.mjs --input work\xianyu_ai_service\xianyu_pack_input.example.json
pause
