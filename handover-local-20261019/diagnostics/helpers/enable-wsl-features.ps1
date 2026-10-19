$ErrorActionPreference = "Stop"

$statusPath = "D:\xprogram\.raven-setup-cache\wsl-features-status.txt"
$logPath = "D:\xprogram\.raven-setup-cache\wsl-features.log"

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    "STARTED $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -All -NoRestart | Out-Null
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart | Out-Null
    $wsl = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
    $vmp = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
    "FINISHED wsl=$($wsl.State) vmp=$($vmp.State) restart=$($wsl.RestartNeeded -or $vmp.RestartNeeded) $(Get-Date -Format o)" |
        Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit 0
}
catch {
    "FAILED $($_.Exception.Message) $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
