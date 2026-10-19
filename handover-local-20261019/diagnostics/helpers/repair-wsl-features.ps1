$ErrorActionPreference = "Stop"

$statusPath = "D:\xprogram\.raven-setup-cache\wsl-repair-status.txt"
$logPath = "D:\xprogram\.raven-setup-cache\wsl-repair.log"

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    "STARTED $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    & dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    if ($LASTEXITCODE -notin @(0, 3010)) { throw "DISM WSL failed with exit $LASTEXITCODE" }
    & dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    if ($LASTEXITCODE -notin @(0, 3010)) { throw "DISM VMP failed with exit $LASTEXITCODE" }
    & bcdedit.exe /set hypervisorlaunchtype auto
    if ($LASTEXITCODE -ne 0) { throw "BCDEdit failed with exit $LASTEXITCODE" }
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
