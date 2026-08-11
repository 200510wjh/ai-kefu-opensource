$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$logDir = Join-Path $repoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$apiUrl = "http://localhost:8000/api/internal-growth/dashboard"
$pageUrl = "http://localhost:5173/internal-growth"
$proxyUrl = "http://localhost:5173/api/internal-growth/dashboard"

function Test-HttpOk {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function ConvertTo-PSLiteral {
  param([string]$Value)
  return "'" + $Value.Replace("'", "''") + "'"
}

function Start-LoggedNpm {
  param(
    [string]$ScriptName,
    [string]$LogName
  )

  $repo = ConvertTo-PSLiteral $repoRoot
  $log = ConvertTo-PSLiteral (Join-Path $logDir $LogName)
  $command = "Set-Location -LiteralPath $repo; npm.cmd run $ScriptName *> $log"

  Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden | Out-Null
}

function Wait-ForUrl {
  param(
    [string]$Url,
    [string]$Name,
    [int]$TimeoutSeconds = 40
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk $Url) {
      Write-Host "[OK] $Name is ready: $Url"
      return $true
    }
    Start-Sleep -Seconds 1
  }

  Write-Host "[WARN] $Name did not become ready in $TimeoutSeconds seconds: $Url"
  return $false
}

Write-Host "============================================================"
Write-Host "Internal Growth OS one-click launcher"
Write-Host "============================================================"
Write-Host ""

if (Test-HttpOk $apiUrl) {
  Write-Host "[OK] Backend already running."
} else {
  Write-Host "[START] Starting backend API on port 8000..."
  Start-LoggedNpm -ScriptName "api" -LogName "internal_growth_api.log"
}

Wait-ForUrl -Url $apiUrl -Name "Backend API" | Out-Null

if (Test-HttpOk $pageUrl) {
  Write-Host "[OK] Frontend already running."
} else {
  Write-Host "[START] Starting frontend on port 5173..."
  Start-LoggedNpm -ScriptName "dev" -LogName "internal_growth_frontend.log"
}

$pageReady = Wait-ForUrl -Url $pageUrl -Name "Frontend page"
$proxyReady = Wait-ForUrl -Url $proxyUrl -Name "Frontend API proxy" -TimeoutSeconds 15

Write-Host ""
if ($pageReady -and $proxyReady) {
  Write-Host "[OPEN] Opening Internal Growth OS..."
  Start-Process $pageUrl
  Write-Host ""
  Write-Host "Done. If the browser does not open, visit:"
  Write-Host $pageUrl
} else {
  Write-Host "[CHECK] Something is still not ready. Logs:"
  Write-Host (Join-Path $logDir "internal_growth_api.log")
  Write-Host (Join-Path $logDir "internal_growth_frontend.log")
}

