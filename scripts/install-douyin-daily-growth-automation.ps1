$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Get-Command python -ErrorAction Stop).Source
$script = Join-Path $repoRoot "scripts\douyin_daily_growth_runner.py"
$logDir = Join-Path $repoRoot "scripts\logs"
$logFile = Join-Path $logDir "douyin_daily_growth.log"
$taskName = "DouyinDailyGrowthContentPack"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$argument = "-NoProfile -ExecutionPolicy Bypass -Command `"Set-Location '$repoRoot'; & '$python' '$script' *>> '$logFile'`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At 8:30AM
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Generate daily Douyin acquisition content pack and review queue. Does not auto-publish." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $taskName"
Write-Host "Daily time: 08:30"
Write-Host "Script: $script"
Write-Host "Log: $logFile"
