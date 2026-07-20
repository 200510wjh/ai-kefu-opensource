$ErrorActionPreference = "Stop"

Write-Host "Installing Tesseract OCR for desktop listener..."
winget install --id UB-Mannheim.TesseractOCR --source winget --accept-source-agreements --accept-package-agreements --silent

$tesseractDir = "C:\Program Files\Tesseract-OCR"
$tesseractExe = Join-Path $tesseractDir "tesseract.exe"
$tessdataDir = Join-Path $tesseractDir "tessdata"
$chiSim = Join-Path $tessdataDir "chi_sim.traineddata"

if (!(Test-Path $tesseractExe)) {
  throw "Tesseract executable was not found at $tesseractExe"
}

if (!(Test-Path $chiSim)) {
  Write-Host "Downloading simplified Chinese language pack..."
  New-Item -ItemType Directory -Force -Path $tessdataDir | Out-Null
  curl.exe -L --retry 3 --connect-timeout 20 --max-time 180 -o $chiSim "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/chi_sim.traineddata"
}

[Environment]::SetEnvironmentVariable("TESSERACT_CMD", $tesseractExe, "User")
[Environment]::SetEnvironmentVariable("DESKTOP_OCR_LANG", "chi_sim+eng", "User")

Write-Host "Tesseract OCR is ready:"
& $tesseractExe --list-langs
