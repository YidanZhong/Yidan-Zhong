param([string]$CommandText, [string]$File)
$ErrorActionPreference = 'Stop'
if ($File) { $CommandText = Get-Content -LiteralPath $File -Raw }
$ravenEncoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($CommandText))
& ssh.exe -i "$env:USERPROFILE\.ssh\raven_4060_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$env:USERPROFILE\.ssh\raven_4060_known_hosts" -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 sophi@10.4.161.239 "powershell.exe -NoProfile -NonInteractive -EncodedCommand $ravenEncoded"
exit $LASTEXITCODE
