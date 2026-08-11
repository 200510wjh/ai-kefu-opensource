@echo off
setlocal
set "SCRIPT=%~dp0scripts\update-codex.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
echo.
echo Codex update check finished.
pause
