@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "data\logs" mkdir "data\logs"
echo Building delivery pack...
"%PY%" scripts\build_ops_delivery_pack.py > "data\logs\build_delivery_pack.log" 2>&1
type "data\logs\build_delivery_pack.log"
pause
endlocal
