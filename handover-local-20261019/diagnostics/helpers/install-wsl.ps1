$ErrorActionPreference = "Stop"

$statusPath = "D:\xprogram\.raven-setup-cache\wsl-install-status.txt"
$logPath = "D:\xprogram\.raven-setup-cache\wsl-install.log"

try {
    Start-Transcript -Path $logPath -Force | Out-Null
    "STARTED $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    & "$env:SystemRoot\System32\wsl.exe" --install --distribution Ubuntu-22.04 --no-launch
    $exitCode = $LASTEXITCODE
    "FINISHED exit=$exitCode $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit $exitCode
}
catch {
    "FAILED $($_.Exception.Message) $(Get-Date -Format o)" | Set-Content -LiteralPath $statusPath -Encoding UTF8
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch {}
}
