param(
  [string]$HostName = "47.100.53.133",
  [int]$Port = 3002,
  [string]$User = "root",
  [string]$RemoteDir = "/opt/merchant-growth-canvas",
  [string]$ServiceName = "merchant-growth-canvas.service"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$env:VITE_BASE_PATH = "/merchant-admin/"
python scripts/build_desktop_agent_downloads.py
npm run build

New-Item -ItemType Directory -Force tmp | Out-Null
$Package = "tmp/deploy-current.tar.gz"
if (Test-Path $Package) {
  Remove-Item $Package -Force
}

tar -czf $Package backend src dist public desktop_agent douyin-miniapp scripts package.json package-lock.json requirements.txt vite.config.ts tsconfig.json index.html desktop

$Remote = "$User@$HostName"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

ssh -p $Port $Remote "mkdir -p /opt/backups $RemoteDir"
ssh -p $Port $Remote "if [ -d '$RemoteDir' ]; then tar -czf /opt/backups/merchant-growth-canvas-pre-$Stamp.tar.gz -C '$RemoteDir' .; fi"
scp -P $Port $Package "${Remote}:/tmp/merchant-growth-canvas-$Stamp.tar.gz"
ssh -p $Port $Remote "tar -xzf /tmp/merchant-growth-canvas-$Stamp.tar.gz -C '$RemoteDir' && systemctl restart '$ServiceName' && systemctl --no-pager --lines=30 status '$ServiceName'"

Write-Host "Deployed to https://wjhai.cn/merchant-admin/"
