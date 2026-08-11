param([string]$Path)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$files = New-Object System.Collections.Specialized.StringCollection
[void]$files.Add($Path)
for ($i = 0; $i -lt 5; $i++) {
  try {
    [System.Windows.Forms.Clipboard]::SetFileDropList($files)
    Write-Output "clipboard-file-ready"
    exit 0
  } catch {
    Start-Sleep -Milliseconds 300
  }
}
throw "Could not set file clipboard"
