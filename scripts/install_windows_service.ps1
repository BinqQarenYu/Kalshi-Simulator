<#
.SYNOPSIS
    Installs or uninstalls Kalshi Simulator as an unattended Windows background task / service.
.DESCRIPTION
    Registers a Windows Scheduled Task named "KalshiSimulatorService" that starts automatically
    on system boot, runs continuously with highest privileges, and restarts automatically on crash.
.EXAMPLE
    .\install_windows_service.ps1 -Install
.EXAMPLE
    .\install_windows_service.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Uninstall
)

$TaskName = "KalshiSimulatorService"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    $PythonExe = "C:\Python314\python.exe"
}

if ($Uninstall) {
    Write-Host "[INFO] Removing Windows Scheduled Task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] '$TaskName' has been uninstalled." -ForegroundColor Green
    return
}

if ($Install -or (-not $Uninstall)) {
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Write-Host "   Installing Kalshi Simulator Background Windows Service" -ForegroundColor Yellow
    Write-Host "===============================================================================" -ForegroundColor Cyan

    Write-Host "Working Directory: $ScriptDir" -ForegroundColor Gray
    Write-Host "Python Binary:     $PythonExe" -ForegroundColor Gray

    # Create batch helper for execution with PYTHONPATH
    $runnerBat = Join-Path $ScriptDir "scripts\run_service_daemon.bat"
    $batContent = @"
@echo off
cd /d "$ScriptDir"
set PYTHONPATH=src
"$PythonExe" -m kalshi_sim.server
"@
    Set-Content -Path $runnerBat -Value $batContent -Encoding ASCII

    # Unregister any existing task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    $Action = New-ScheduledTaskAction -Execute "$runnerBat" -WorkingDirectory "$ScriptDir"
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit 0

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Kalshi BTC Quantitative Trading Simulator 24/7 Background Service" -User "NT AUTHORITY\SYSTEM"

    Write-Host "[OK] Successfully registered Windows Task '$TaskName' to start on boot!" -ForegroundColor Green
    Write-Host "[INFO] To start now: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
    Write-Host "[INFO] To uninstall:  .\install_windows_service.ps1 -Uninstall" -ForegroundColor Gray
}
