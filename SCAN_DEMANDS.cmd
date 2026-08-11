@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "data\logs" mkdir "data\logs"
echo Scanning local demand files...
"%PY%" scripts\local_demand_radar.py > "data\logs\scan_demands.log" 2>&1
type "data\logs\scan_demands.log"
pause
endlocal
