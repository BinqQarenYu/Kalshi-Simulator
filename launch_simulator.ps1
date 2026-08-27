<#
.SYNOPSIS
    Interactive PowerShell Launcher for the Kalshi BTC Quantitative Trading Simulator.
.DESCRIPTION
    Verifies Python environment, frontend build artifacts, ONNX models, and launches
    the FastAPI server with real-time WebSocket dashboard on http://localhost:8000.
#>

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$LiveMode
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "   KALSHI BTC QUANTITATIVE TRADING SIMULATOR" -ForegroundColor Yellow
Write-Host "   Multi-Timeframe Microstructure ONNX Engine | WebCLOB Dashboard" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Set PYTHONPATH
$env:PYTHONPATH = "src"

# 3. Verify Models
$modelPath = Join-Path $ScriptDir "models\nano_microscope_overhauled.onnx"
if (-not (Test-Path $modelPath)) {
    Write-Host "[WARNING] ONNX model missing at $modelPath" -ForegroundColor Yellow
    Write-Host "[INFO] Attempting sync from Google Drive..." -ForegroundColor Gray
    python -m kalshi_sim.gdrive_sync --pull-models
} else {
    Write-Host "[OK] ONNX model present." -ForegroundColor Green
}

# 4. Verify Frontend Distribution
$distIndex = Join-Path $ScriptDir "frontend\dist\index.html"
if (-not (Test-Path $distIndex)) {
    Write-Host "[INFO] Frontend distribution missing. Building React bundle..." -ForegroundColor Yellow
    Push-Location "frontend"
    npm install
    npm run build
    Pop-Location
    Write-Host "[OK] Frontend build completed." -ForegroundColor Green
} else {
    Write-Host "[OK] Frontend build artifacts verified." -ForegroundColor Green
}

# 5. Launch Browser
$url = "http://localhost:$Port"
if (-not $NoBrowser) {
    Write-Host "[INFO] Opening dashboard in default browser at $url ..." -ForegroundColor Cyan
    Start-Process $url
}

Write-Host ""
Write-Host "[INFO] Launching server on $url (Press Ctrl+C to terminate)..." -ForegroundColor Magenta
Write-Host "-------------------------------------------------------------------------------" -ForegroundColor Gray

python -m kalshi_sim.server
