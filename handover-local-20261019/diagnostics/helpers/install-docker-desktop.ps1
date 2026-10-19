$ErrorActionPreference = "Stop"

$installer = "D:\xprogram\.raven-setup-cache\Docker-Desktop-Installer-4.91.0.exe"
$statusPath = "D:\xprogram\.raven-setup-cache\docker-install-status.txt"
$logPath = "D:\xprogram\.raven-setup-cache\docker-install.log"

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    "STARTED $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    $process = Start-Process -FilePath $installer -ArgumentList @(
        "install",
        "--quiet",
        "--backend=wsl-2"
    ) -Wait -PassThru -WindowStyle Hidden
    "FINISHED exit=$($process.ExitCode) $(Get-Date -Format o)" |
        Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit $process.ExitCode
}
catch {
    "FAILED $($_.Exception.Message) $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
