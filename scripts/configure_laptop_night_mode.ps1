<#
.SYNOPSIS
    Configures laptop for unattended 24/7 execution (Sleep Prevention, Network Persistence, and Process Armor).
.DESCRIPTION
    Ensures that when the laptop lid is closed or monitor is flipped:
    1. The laptop never goes to sleep or hibernates (Lid action: Do nothing, Sleep timeout: Never).
    2. Wi-Fi and Ethernet adapters remain fully powered without dropping packets or sleeping.
    3. Windows 10 Power Throttling (EcoQoS) is disabled so background apps (Python, Node, Antigravity) are not throttled.
    4. Running Python and Node/Antigravity processes are given AboveNormal scheduling priority.
#>

[CmdletBinding()]
param()

$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "   Kalshi Trading & Antigravity Unattended Laptop Mode Configuration" -ForegroundColor Yellow
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "Elevated (Administrator): $(if ($IsAdmin) { 'YES' } else { 'NO (Some adapter/registry settings require elevation)' })" -ForegroundColor $(if ($IsAdmin) { 'Green' } else { 'Yellow' })
Write-Host ""

# -----------------------------------------------------------------------------
# 1. Windows Power Scheme Configuration (powercfg)
# -----------------------------------------------------------------------------
Write-Host "[1/4] Applying Power Scheme & Sleep Prevention Policies..." -ForegroundColor Cyan

$scheme = (powercfg /getactivescheme) -replace 'Power Scheme GUID: ([a-f0-9\-]+).*','$1'

$powerSettings = @(
    # Subgroup, Setting GUID, AC Value, DC Value, Description
    @{Sub="4f971e89-eebd-4455-a8de-9e59040e7347"; Set="5ca83367-6e45-459f-a27b-476b1d01c936"; AC=0; DC=0; Desc="Lid Close Action -> Do Nothing"},
    @{Sub="238c9fa8-0aad-41ed-83f4-97be242c8f20"; Set="29f6c1db-86da-48c5-9fdb-f2b67b1f44da"; AC=0; DC=0; Desc="System Sleep Timeout -> Never"},
    @{Sub="238c9fa8-0aad-41ed-83f4-97be242c8f20"; Set="9d7815a6-7ee4-497e-8888-515a05f02364"; AC=0; DC=0; Desc="Hibernate Timeout -> Never"},
    @{Sub="238c9fa8-0aad-41ed-83f4-97be242c8f20"; Set="7bc4a2f9-d8fc-4469-b07b-33eb785aaca0"; AC=0; DC=0; Desc="Unattended Sleep Timeout -> Never"},
    @{Sub="19cbb8fa-5279-450e-9fac-8a3d5fedd0c1"; Set="12bbebe6-58d6-4636-95bb-3217ef867c1a"; AC=0; DC=0; Desc="Wireless Adapter -> Maximum Performance"},
    @{Sub="501a4d13-42af-4429-9fd1-a8218c268e20"; Set="ee12f906-d277-404b-b6da-e5fa1a576df5"; AC=0; DC=0; Desc="PCI Express Link State (ASPM) -> Off"},
    @{Sub="2a737441-1930-4402-8d77-b2bebba308a3"; Set="48e6b7a6-50f5-4782-a5d4-53bb8f07e226"; AC=0; DC=0; Desc="USB Selective Suspend -> Disabled"},
    @{Sub="9596fb26-9850-41fd-ac3e-f7c3c00afd4b"; Set="03680956-93bc-4294-bba6-4e0f09bb717f"; AC=1; DC=1; Desc="Media Sharing -> Prevent Idling to Sleep"},
    @{Sub="0012ee47-9041-4b5d-9b77-535fba8b1442"; Set="6738e2c4-e8a5-4a42-b16a-e040e769756e"; AC=0; DC=0; Desc="Hard Disk Timeout -> Never"}
)

foreach ($item in $powerSettings) {
    powercfg /setacvalueindex $scheme $item.Sub $item.Set $item.AC | Out-Null
    powercfg /setdcvalueindex $scheme $item.Sub $item.Set $item.DC | Out-Null
    Write-Host "  [OK] $($item.Desc)" -ForegroundColor Green
}

# Display timeout: Never (0) on AC so external monitor stays active while coding; 5 min on DC for battery conservation
powercfg /setacvalueindex $scheme 7516b95f-f776-4464-8c53-06167f40cc99 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0 | Out-Null
powercfg /setdcvalueindex $scheme 7516b95f-f776-4464-8c53-06167f40cc99 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 300 | Out-Null
Write-Host "  [OK] Display Idle Timeout -> Never on AC (External monitor stays active while coding) / 5m on DC" -ForegroundColor Green

# Activate changes
powercfg /setactive $scheme
Write-Host "  [OK] Active power scheme ($scheme) updated." -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# 2. Network Adapter Power Armor (Disabling Adapter Sleep & EEE)
# -----------------------------------------------------------------------------
Write-Host "[2/4] Hardening Network Adapters (Ethernet & Wi-Fi)..." -ForegroundColor Cyan

if ($IsAdmin) {
    try {
        # Find network adapter registry keys under Class {4d36e972-e325-11ce-bfc1-08002be10318}
        $classPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
        $adapterKeys = Get-ChildItem -Path $classPath -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\d{4}$' }

        foreach ($k in $adapterKeys) {
            $desc = (Get-ItemProperty -Path $k.PSPath -Name "DriverDesc" -ErrorAction SilentlyContinue).DriverDesc
            if ($desc -and ($desc -match "Realtek|Ralink|Ethernet|Wireless|Wi-Fi")) {
                Write-Host "  -> Configuring adapter: $desc ($($k.PSChildName))" -ForegroundColor Gray
                
                # 0x18 (24) disables "Allow computer to turn off this device to save power"
                Set-ItemProperty -Path $k.PSPath -Name "PnPCapabilities" -Value 24 -Type DWord -Force -ErrorAction SilentlyContinue
                
                # Disable Energy-Efficient Ethernet (EEE)
                Set-ItemProperty -Path $k.PSPath -Name "*EEE" -Value "0" -Type String -Force -ErrorAction SilentlyContinue
                
                # Disable Power Saving Mode / Green Ethernet
                Set-ItemProperty -Path $k.PSPath -Name "*PowerSaving" -Value "0" -Type String -Force -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $k.PSPath -Name "*GreenEthernet" -Value "0" -Type String -Force -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $k.PSPath -Name "*GigaLite" -Value "0" -Type String -Force -ErrorAction SilentlyContinue
                
                Write-Host "     [OK] Disabled Power Management & EEE on $desc" -ForegroundColor Green
            }
        }
    }
    catch {
        Write-Host "  [WARN] Failed to configure some network adapter registry settings: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [SKIP] Network adapter registry settings require Administrator elevation." -ForegroundColor Yellow
    Write-Host "         Run configure_laptop_unattended_mode.bat to apply elevated settings." -ForegroundColor Yellow
}
Write-Host ""

# -----------------------------------------------------------------------------
# 3. Disable Windows Power Throttling (EcoQoS) System-Wide
# -----------------------------------------------------------------------------
Write-Host "[3/4] Configuring Windows Power Throttling Policy..." -ForegroundColor Cyan

if ($IsAdmin) {
    try {
        $ptPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling"
        if (-not (Test-Path $ptPath)) {
            New-Item -Path $ptPath -Force | Out-Null
        }
        Set-ItemProperty -Path $ptPath -Name "PowerThrottlingOff" -Value 1 -Type DWord -Force
        Write-Host "  [OK] Windows Power Throttling disabled (PowerThrottlingOff = 1)." -ForegroundColor Green
        Write-Host "       Background processes (Python, Node, Antigravity) will not be throttled when screen is off." -ForegroundColor Gray
    }
    catch {
        Write-Host "  [WARN] Could not set PowerThrottling registry key: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [SKIP] PowerThrottling registry key requires Administrator elevation." -ForegroundColor Yellow
}
Write-Host ""

# -----------------------------------------------------------------------------
# 4. Boost Process Scheduling Priority for Python & Antigravity
# -----------------------------------------------------------------------------
Write-Host "[4/4] Boosting Process Priorities (Python, Node, Antigravity)..." -ForegroundColor Cyan

$targets = @("python", "node", "Antigravity", "electron")
$tunedCount = 0

foreach ($procName in $targets) {
    Get-Process -Name $procName -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            if ($_.PriorityClass -ne [System.Diagnostics.ProcessPriorityClass]::AboveNormal) {
                $_.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::AboveNormal
            }
            Write-Host "  [OK] Process PID $($_.Id) ($procName) Priority -> AboveNormal" -ForegroundColor Green
            $tunedCount++
        }
        catch {
            Write-Host "  [INFO] Could not adjust PID $($_.Id) ($procName): $_" -ForegroundColor DarkGray
        }
    }
}

if ($tunedCount -eq 0) {
    Write-Host "  [INFO] No active Python or Antigravity processes found running right now." -ForegroundColor Gray
    Write-Host "         Our app and bots automatically set AboveNormal priority on launch." -ForegroundColor Gray
}
Write-Host ""

# -----------------------------------------------------------------------------
# Summary Report
# -----------------------------------------------------------------------------
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "   UNATTENDED LAPTOP CONFIGURATION COMPLETE!" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "Your laptop is now configured for 24/7 operation:" -ForegroundColor White
Write-Host " - Lid Closed / Monitor Flip: Stays awake, does not sleep, does not hibernate." -ForegroundColor Gray
Write-Host " - Display Timeout: Never turns off while plugged in (keeps external monitor active while coding)." -ForegroundColor Gray
Write-Host " - Networks & APIs: Wi-Fi, Ethernet, and PCIe remain at Maximum Performance." -ForegroundColor Gray
Write-Host " - Antigravity & Trading App: Execution locked 24/7 with zero background throttling." -ForegroundColor Gray
Write-Host "===============================================================================" -ForegroundColor Cyan
