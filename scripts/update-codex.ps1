param(
    [switch]$SkipDesktop
)

$ErrorActionPreference = 'Continue'

$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $logDir "update-codex-$timestamp.log"

function Write-Log {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line
    Write-Host $line
}

function Run-Logged {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    Write-Log "Running: $FilePath $($Arguments -join ' ')"
    $output = & $FilePath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        Write-Log "  $line"
    }
    Write-Log "Exit code: $exitCode"
    return $exitCode
}

Write-Log 'Codex update started.'

$appx = Get-AppxPackage -Name OpenAI.Codex -ErrorAction SilentlyContinue
if ($appx) {
    Write-Log "Desktop app installed: $($appx.Version) ($($appx.PackageFullName))"
} else {
    Write-Log 'Desktop app not found.'
}

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
if ($codexCommand) {
    $versionOutput = & codex --version 2>&1
    Write-Log "CLI before update: $versionOutput"
} else {
    Write-Log 'CLI before update: not found.'
}

Run-Logged -FilePath 'winget' -Arguments @(
    'install',
    '--id', 'OpenAI.Codex',
    '--accept-source-agreements',
    '--accept-package-agreements',
    '--silent'
) | Out-Null

Run-Logged -FilePath 'winget' -Arguments @(
    'upgrade',
    '--id', 'OpenAI.Codex',
    '--accept-source-agreements',
    '--accept-package-agreements',
    '--silent'
) | Out-Null

if (-not $SkipDesktop) {
    Write-Log 'Refreshing Microsoft Store source.'
    Run-Logged -FilePath 'winget' -Arguments @('source', 'update', 'msstore') | Out-Null

    Write-Log 'Trying desktop app update through Microsoft Store package id 9PLM9XGG6VKS.'
    Run-Logged -FilePath 'winget' -Arguments @(
        'install',
        '--id', '9PLM9XGG6VKS',
        '--source', 'msstore',
        '--accept-source-agreements',
        '--accept-package-agreements'
    ) | Out-Null
}

$appxAfter = Get-AppxPackage -Name OpenAI.Codex -ErrorAction SilentlyContinue
if ($appxAfter) {
    Write-Log "Desktop app after update: $($appxAfter.Version) ($($appxAfter.PackageFullName))"
}

$codexAfter = Get-Command codex -ErrorAction SilentlyContinue
if ($codexAfter) {
    $versionOutputAfter = & codex --version 2>&1
    Write-Log "CLI after update: $versionOutputAfter"
}

Write-Log "Codex update finished. Log: $logPath"
