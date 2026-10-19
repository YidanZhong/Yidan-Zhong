$ErrorActionPreference = 'Continue'
$cacheDir = 'D:\xprogram\.raven-setup-cache'
$logPath = Join-Path $cacheDir 'audit-wsl.log'
$statusPath = Join-Path $cacheDir 'audit-wsl-status.json'

Start-Transcript -Path $logPath -Force | Out-Null

Write-Output '=== Windows identity ==='
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, HyperVisorPresent | Format-List

Write-Output '=== Optional feature: WSL ==='
dism.exe /online /get-featureinfo /featurename:Microsoft-Windows-Subsystem-Linux
$wslDismExit = $LASTEXITCODE

Write-Output '=== Optional feature: VirtualMachinePlatform ==='
dism.exe /online /get-featureinfo /featurename:VirtualMachinePlatform
$vmpDismExit = $LASTEXITCODE

Write-Output '=== PowerShell feature states ==='
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
$vmpFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
$wslFeature | Select-Object FeatureName, State, RestartRequired | Format-List
$vmpFeature | Select-Object FeatureName, State, RestartRequired | Format-List

Write-Output '=== Boot configuration ==='
bcdedit.exe /enum '{current}'
$bcdExit = $LASTEXITCODE

Write-Output '=== Processor virtualization ==='
$cpu = Get-CimInstance Win32_Processor | Select-Object Name, VirtualizationFirmwareEnabled, SecondLevelAddressTranslationExtensions, VMMonitorModeExtensions
$cpu | Format-List

Write-Output '=== Computer system ==='
$computer = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, HypervisorPresent, TotalPhysicalMemory
$computer | Format-List

Write-Output '=== Device Guard ==='
$deviceGuard = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard
$deviceGuard | Select-Object VirtualizationBasedSecurityStatus, SecurityServicesConfigured, SecurityServicesRunning, RequiredSecurityProperties, AvailableSecurityProperties | Format-List

Write-Output '=== Pending reboot markers ==='
$pendingCbs = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$pendingWu = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
Write-Output "CBS=$pendingCbs WindowsUpdate=$pendingWu"

$status = [ordered]@{
    completed = $true
    timestamp = (Get-Date).ToString('o')
    wsl_feature_state = [string]$wslFeature.State
    wsl_restart_required = [string]$wslFeature.RestartRequired
    vmp_feature_state = [string]$vmpFeature.State
    vmp_restart_required = [string]$vmpFeature.RestartRequired
    dism_wsl_exit = $wslDismExit
    dism_vmp_exit = $vmpDismExit
    bcdedit_exit = $bcdExit
    hypervisor_present = [bool]$computer.HypervisorPresent
    cpu_virtualization_firmware_enabled = [bool]$cpu.VirtualizationFirmwareEnabled
    cpu_slat = [bool]$cpu.SecondLevelAddressTranslationExtensions
    cpu_vm_monitor = [bool]$cpu.VMMonitorModeExtensions
    vbs_status = $deviceGuard.VirtualizationBasedSecurityStatus
    cbs_reboot_pending = $pendingCbs
    windows_update_reboot_pending = $pendingWu
}
$status | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statusPath -Encoding UTF8

Stop-Transcript | Out-Null
