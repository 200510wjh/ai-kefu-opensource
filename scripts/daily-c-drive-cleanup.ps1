$ErrorActionPreference = 'SilentlyContinue'

$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $logDir "daily-c-drive-cleanup-$timestamp.log"

function Write-Log {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line
}

function Get-FreeGb {
    $drive = Get-PSDrive -Name C
    [math]::Round($drive.Free / 1GB, 2)
}

function Clear-FolderContents {
    param([string]$Path)

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if (-not $resolved) {
        Write-Log "Skip missing path: $Path"
        return
    }

    $fullPath = $resolved.Path
    $protectedRoots = @(
        'C:\Users\Administrator\Documents\运营',
        'C:\Users\Administrator\Documents\运营\scripts'
    )

    foreach ($protectedRoot in $protectedRoots) {
        if ($fullPath.StartsWith($protectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Log "Skip protected workspace path: $fullPath"
            return
        }
    }

    Write-Log "Cleaning: $fullPath"
    Get-ChildItem -LiteralPath $fullPath -Force -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Log "Cleanup started. Free space: $(Get-FreeGb) GB"

$pathsToClean = @(
    $env:TEMP,
    'C:\Windows\Temp',
    'C:\Windows\SoftwareDistribution\Download',
    'C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\Cache',
    'C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\Code Cache',
    'C:\Users\Administrator\AppData\Local\Google\Chrome\User Data\Default\GPUCache',
    'C:\Users\Administrator\AppData\Local\Microsoft\Edge\User Data\Default\Cache',
    'C:\Users\Administrator\AppData\Local\Microsoft\Edge\User Data\Default\Code Cache',
    'C:\Users\Administrator\.cache',
    'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages',
    'C:\Users\Administrator\AppData\Local\Microsoft\Windows\INetCache',
    'C:\Users\Administrator\AppData\Local\Microsoft\Windows\WebCache',
    'C:\Users\Administrator\AppData\Local\CrashDumps',
    'C:\Users\Administrator\AppData\Local\electron\Cache',
    'C:\Users\Administrator\AppData\Local\Steam\htmlcache',
    'C:\Users\Administrator\AppData\Local\NetEase\CloudMusic\Cache',
    'C:\Users\Administrator\AppData\Roaming\Tencent\xwechat\log',
    'C:\Users\Administrator\AppData\Roaming\Tencent\xwechat\update',
    'C:\Users\Administrator\AppData\Roaming\Tencent\xwechat\update\patch',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\logs',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\Cache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\gecko_cache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\mediasdk_log',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\biz-logs',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\loki',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\sdk-call-logs',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\EventSDKLogs',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\Code Cache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\GPUCache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\DawnCache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\DawnWebGPUCache',
    'C:\Users\Administrator\AppData\Roaming\webcast_mate\DawnGraphiteCache',
    'C:\Users\Administrator\AppData\Roaming\ScreenCache\WebView2\EBWebView\Default\Cache',
    'C:\Users\Administrator\AppData\Roaming\Code\Crashpad',
    'C:\Users\Administrator\AppData\Roaming\360Safe\MultiTip\Cache',
    'C:\Users\Administrator\AppData\Roaming\360Safe\SoftMgr\Cache',
    'C:\Users\Administrator\AppData\Roaming\Quark\Cache',
    'C:\Users\Administrator\AppData\Roaming\ACLOS\Cache',
    'C:\Users\Administrator\AppData\Roaming\ACLOS\logs',
    'C:\Users\Administrator\AppData\Roaming\@byted\vela\Cache'
)

foreach ($path in $pathsToClean) {
    Clear-FolderContents -Path $path
}

Clear-RecycleBin -Force -ErrorAction SilentlyContinue
Write-Log 'Recycle Bin cleaned.'

Write-Log "Cleanup finished. Free space: $(Get-FreeGb) GB"
