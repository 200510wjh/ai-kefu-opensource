@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

if not exist "data\logs" mkdir "data\logs"
set "LOG=data\logs\ai_launcher_last.log"

cls
echo ============================================================
echo AI Customer Service Script Launcher
echo ============================================================
echo.
echo 1. Start desktop AI customer service assistant
echo 2. Run today's full script check
echo 3. Build operation delivery pack
echo 4. Scan local files for business demands
echo 5. Check real platform chat windows
echo 6. Open today's delivery pack folder
echo 7. Open online admin page
echo 0. Exit
echo.
set /p choice=Choose a number and press Enter: 

if "%choice%"=="1" goto start_assistant
if "%choice%"=="2" goto today_check
if "%choice%"=="3" goto build_pack
if "%choice%"=="4" goto demand_scan
if "%choice%"=="5" goto real_platforms
if "%choice%"=="6" goto open_pack
if "%choice%"=="7" goto open_admin
if "%choice%"=="0" goto end

echo Unknown choice.
pause
goto end

:start_assistant
echo Starting desktop assistant...
"%PY%" scripts\desktop_listener_launcher.py > "%LOG%" 2>&1
type "%LOG%"
pause
goto end

:today_check
echo Running today's script check...
"%PY%" scripts\today_ops_check.py > "%LOG%" 2>&1
type "%LOG%"
pause
goto end

:build_pack
echo Building operation delivery pack...
"%PY%" scripts\build_ops_delivery_pack.py > "%LOG%" 2>&1
type "%LOG%"
pause
goto end

:demand_scan
echo Scanning local files...
"%PY%" scripts\local_demand_radar.py > "%LOG%" 2>&1
type "%LOG%"
pause
goto end

:real_platforms
echo Checking real platform chat windows...
"%PY%" scripts\desktop_real_platform_acceptance.py --soft > "%LOG%" 2>&1
type "%LOG%"
pause
goto end

:open_pack
start "" "%~dp0运营计划\今日交付包"
goto end

:open_admin
start "" "https://wjhai.cn/merchant-admin/"
goto end

:end
endlocal
