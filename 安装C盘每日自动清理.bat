@echo off
setlocal
set "SCRIPT=%~dp0scripts\install-c-drive-cleanup-automation.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
echo.
echo C drive daily cleanup automation is installed or updated.
pause
